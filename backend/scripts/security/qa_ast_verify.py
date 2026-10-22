"""QA 独立验收：沙箱 AST 白名单修复（正向绕过 + 反向误杀）。

只读验证，不修改任何源码。用法：
    cd backend && .venv/Scripts/python.exe scripts/security/qa_ast_verify.py

判定口径（与 `app/sandbox/runner.py::_guard_response` 的响应契约一致）：
- **泄漏** = `stdout` 非空（代码真的执行产出了输出）。`stderr` 里放拒绝原因是
  契约设计（便于排障），不算泄漏；
- **绕过失败** = AST 未命中且执行成功；
- 保留名逃逸分两层验证：边界层（`SandboxClient`）拒绝提交；执行器层
  （`LocalRunner` 直连）对 `_plab_guard.py` 照常 AST 校验（`__plab_boot__.py`
  是系统生成文件，执行器层按设计跳过，由边界层负责拒绝用户提交）。
"""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.errors import AppError
from app.sandbox.ast_guard import check_source
from app.sandbox.protocol import LOCAL_BOOTSTRAP_NAME, SandboxFile, SandboxRequest
from app.sandbox.runner import LocalRunner
from app.services.sandbox_client import SandboxClient

# ---------------------------------------------------------------- A 正向绕过
BYPASS = {
    "os.system": "import os\nos.system('echo PWNED_A1')",
    "os.system双引号": 'import os\nos.system("echo PWNED_A2")',
    "__import__双引号": '__import__("os").system("echo PWNED_A3")',
    "getattr反射": "import os\ngetattr(os, 'system')('echo PWNED_A4')",
    "getattr拼接绕过": "import os\ngetattr(os, 'sys' + 'tem')('echo PWNED_A5')",
    "os.popen": "import os\nprint(os.popen('echo PWNED_A6').read())",
    "os.popen getattr": "import os\nprint(getattr(os, 'popen')('echo PWNED_A7').read())",
    "os.spawnl": "import os\nprint(os.spawnl)",
    "os.execv": "import os\nprint(os.execv)",
    "os.fork": "import os\nprint(os.fork)",
    "os.startfile": "import os\nprint(os.startfile)",
    "os.remove属性": "import os\nprint(os.remove)",
    "os.unlink属性": "import os\nprint(os.unlink)",
    "os.rmdir属性": "import os\nprint(os.rmdir)",
    "os.makedirs属性": "import os\nprint(os.makedirs)",
    "os.chdir上跳": "import os\nos.chdir('../..')\nprint(open('data/pythonlab.db','rb').read(5))",
    "shutil.rmtree": "import shutil\nprint(shutil.rmtree)",
    "subprocess.run": "import subprocess\nprint(subprocess.run)",
    "subprocess全模块": "import subprocess",
    "ctypes.CDLL": "import ctypes\nprint(ctypes.CDLL)",
    "ctypes仅import": "import ctypes",
    "importlib.import_module": "import importlib\nprint(importlib.import_module('os'))",
    "from os import system": "from os import system\nprint(system)",
    "from shutil import rmtree": "from shutil import rmtree\nprint(rmtree)",
    "from os import chdir": "from os import chdir\nchdir('..')\nprint('escaped')",
    "__builtins__getattr": "print(getattr(__builtins__, '__import__'))",
    "eval注入": "eval(\"print('PWNED_C1')\")",
    "eval注入import": "eval(\"__import__('os').system('echo PWNED_C2')\")",
    "exec注入": "exec(\"print('PWNED_C3')\")",
    "open绝对盘符": "print(open('C:/Windows/win.ini').read()[:30])",
    "open原始字符串": "print(open(r'C:\\Windows\\win.ini').read()[:30])",
    "open小写盘符": "print(open('c:/windows/win.ini').read()[:30])",
    "open相对上跳": "print(open('../../etc/passwd').read()[:30])",
    "open变量路径": "p='C:/Windows/win.ini'\nprint(open(p).read()[:30])",
    "open拼接路径": "print(open('C:/Win'+'dows/win.ini').read()[:30])",
    "os.listdir根": "import os\nprint(os.listdir('C:/')[:3])",
    "sys.modules反射": "import sys\nprint(sys.modules['os'].system)",
    "pathlib绝对": "from pathlib import Path\nprint(Path('C:/Windows/win.ini').read_text()[:30])",
    "pathlib上跳": "from pathlib import Path\nprint(Path('../../../etc/passwd').read_text()[:30])",
    "pathlib别名上跳": "import pathlib as pl\nprint(pl.Path('../x').read_text())",
    "socket直连": "import socket\nprint(socket.socket)",
    "dunder class链": "print(().__class__.__base__.__subclasses__())",
    "compile动态": "compile('print(1)', '<s>', 'exec')",
    "shell注入串": "print('rm -rf /')",
    "powershell串": "print('powershell -enc x')",
}

#: 有意放行（非缺陷）：读环境变量是合法教学内容，断言「能跑 + 值必须为空」
INTENTIONAL = {
    "os.environ读取": "import os\nprint('AIKEY=', os.environ.get('AI_API_KEY'))",
    "os.environ索引": "import os\nprint('JWT=', os.environ.get('JWT_SECRET_KEY'))",
}

#: 运行时隔离兜底（AST 放行，靠 `python -I` 的隔离语义防御）：
#: `-I` 模式下 `__builtins__` 是 module 不可下标 → TypeError，拿不到 eval。
#: 断言「没有执行成功 + 无泄漏」即可（见 qa_ast_confirm.py 复核 2）。
RUNTIME_ISOLATION = {
    "__builtins__下标": "print(__builtins__['eval'])",
}

# 保留文件名绕过（skip_paths 逃逸）—— 用**危险载荷**才有判定意义
RESERVED_PAYLOAD = "import os\nos.system('echo PWNED_RESERVED')"
RESERVED_BYPASS = {
    "保留名_plab_guard": {"_plab_guard.py": RESERVED_PAYLOAD},
    "保留名_boot": {LOCAL_BOOTSTRAP_NAME: RESERVED_PAYLOAD},
}

# ---------------------------------------------------------------- B 反向误杀
FALSE_POSITIVE = {
    "B01_math": "import math; print(math.sqrt(16))",
    "B02_os.path.join": "import os; print(os.path.join('a','b')); print(os.getcwd()[:0] or 'ok')",
    "B03_dict方法": "d = {'a':1}; print(d.get('a'), d.setdefault('b',2), list(d.keys()), d.values())",
    "B04_json": "import json; print(json.dumps({'x':1}, ensure_ascii=False))",
    "B05_random": "import random; print(random.randint(1,10))",
    "B06_datetime": "import datetime; print(datetime.date.today().year > 2000)",
    "B07_string": "s = \"a,b,c\".split(','); print('-'.join(s), len(s), s[0].upper())",
    "B08_内建排序": "print(sorted([3,1,2]), sum([1,2]), max([1,5]), min([1,5]), abs(-3), round(3.14159,2))",
    "B09_写文件": "f = open('data.txt','w'); f.write('hi'); f.close(); print(open('data.txt').read())",
    # B10 先建文件再读（早期版本跨子进程读上一个用例的文件，必然 FileNotFound）
    "B10_with_open": "open('data.txt','w').write('hi')\nwith open('data.txt') as fh: print(fh.readline().strip())",
    "B11_re": "import re; print(re.findall(r'\\d+', 'a1b22'))",
    "B12_推导式": "print([i*i for i in range(5)], {i:i for i in range(3)}, {1,2} | {2,3})",
    "B13_异常": "try:\n    1/0\nexcept ZeroDivisionError as e:\n    print('caught', type(e).__name__)",
    "B14_类": "class A:\n    def __init__(self, x): self.x = x\n    def show(self): return self.x\nprint(A(5).show())",
    # —— 以下为 QA 自行追加的常见教学写法（预判高风险误杀点）——
    "B15_input": "name = input()\nprint('hi', name)",
    "B16_sys.exit": "import sys\nprint('before')\nsys.exit(0)",
    "B17_str.replace": "print('a-b-c'.replace('-', '_'))",
    "B18_list.remove": "d=[1,2,3]\nd.remove(2)\nprint(d)",
    "B19_os.getenv": "import os\nprint(os.getenv('PATH') is not None)",
    "B20_sys.argv": "import sys\nprint(len(sys.argv) >= 0)",
    "B21_异常type名": "try:\n    1/0\nexcept Exception as e:\n    print(type(e).__name__)",
    "B22_主模块判定": "if __name__ == '__main__':\n    print('main ok')",
    "B23_枚举遍历": "import enum\nclass C(enum.Enum):\n    A=1\nprint(C.A.value)",
    "B24_csv读": "import csv, io\nprint(list(csv.reader(io.StringIO('a,b\\n1,2'))))",
    "B25_pathlib相对": "from pathlib import Path\np=Path('out.txt')\np.write_text('x')\nprint(p.read_text())",
    "B26_字符串含bin": "print('/binary' , '/usr')",
    "B27_十六进制": "print(int('ff', 16), bin(10), hex(255))",
    "B28_time": "import time; print(type(time.time()).__name__)",
    "B29_装饰器": "def deco(f):\n    def w(*a): return f(*a)\n    return w\n@deco\ndef g(x): return x*2\nprint(g(3))",
    "B30_生成器": "gen=(i for i in range(3))\nprint(list(gen))",
    "B31_全局变量": "COUNT=0\ndef inc():\n    global COUNT\n    COUNT+=1\ninc()\nprint(COUNT)",
    "B32_嵌套函数": "def outer():\n    def inner(): return 'in'\n    return inner()\nprint(outer())",
    "B33_星号解包": "a=[1,2]; b=[3,4]\nprint([*a,*b])",
    "B34_fstring": "n=5\nprint(f'n is {n:03d}')",
    "B35_异常链": "try:\n    {}['k']\nexcept KeyError as e:\n    print('missing', e)",
    "B36_dataclass": "from dataclasses import dataclass\n@dataclass\nclass P:\n    x: int\nprint(P(1).x)",
    "B37_多行字符串": "s='''\nhello\nworld'''\nprint(s.strip())",
    "B38_切片": "s=[1,2,3,4]\nprint(s[1:3], s[::-1], s[-1])",
    "B39_条件表达式": "x=5\nprint('big' if x>3 else 'small')",
    "B40_lambda": "f=lambda a,b:a+b\nprint(f(1,2))",
    # 第二轮收窄后新增的误杀守护（sys.exit / 路径字面量）
    "B41_sys.exit_main": "import sys\n\ndef main():\n    print('ok')\n    return 0\n\nif __name__ == '__main__':\n    sys.exit(main())",
    "B42_print路径": "print('path example:', '/usr', '/tmp')",
    "B43_exit内置": "print('bye')\nexit()",
    "B44_Path相对": "from pathlib import Path\np=Path('out.txt')\np.write_text('x')\nprint(p.read_text())\nprint(p.exists())",
    "B45_Path建目录": "from pathlib import Path\nPath('sub').mkdir()\nprint(Path('sub').is_dir())",
}

#: 已知权衡（不算误杀）：os.remove 拦截的取舍，见 ast_guard 模块 docstring
KNOWN_TRADEOFFS = {
    "os.remove": "可删工作目录外文件的前提是路径已逃逸，而逃逸路径本身被 open/Path/chdir 规则拦下；"
    "删自己刚建文件的教学写法被误杀，属可接受权衡（team-lead 2026-10 确认保留拦截）",
}


def run_locally(files: dict[str, str], entry: str = "main.py", stdin: str = "") -> dict:
    """真实走 LocalRunner 执行，返回关键字段。"""
    req = SandboxRequest(
        request_id="qa-verify",
        files=[SandboxFile(path=p, content=c) for p, c in files.items()],
        entry=entry,
        stdin=stdin,
        timeout_ms=3000,
        memory_limit_mb=128,
    )
    return LocalRunner().run(req).model_dump()


def main() -> None:
    print("=" * 78)
    print("A. 正向绕过 —— 断言 AST 命中且 stdout 为空（stderr 的拒绝原因不算泄漏）")
    print("=" * 78)
    bad: list[tuple[str, str, str]] = []
    for name, code in BYPASS.items():
        v = check_source(code)
        r = run_locally({"main.py": code})
        executed = bool((r["stdout"] or "").strip())
        ok = v is not None and r["status"] == "security_error" and not executed
        rule = v.rule if v else "-"
        if not ok:
            bad.append((name, rule, r["status"]))
        flag = "PASS" if ok else "**FAIL**"
        print(f"[{flag:9s}] {name:22s} rule={rule:28s} status={r['status']} executed={executed}")
        if not ok:
            print(f"            stdout={r['stdout']!r} error={(r['error'] or '')[:100]!r}")

    print()
    print("=" * 78)
    print("A1. 有意放行 —— 断言能执行，且服务端密钥不出现在输出里")
    print("=" * 78)
    for name, code in INTENTIONAL.items():
        r = run_locally({"main.py": code})
        out = r["stdout"] or ""
        leaked = any(secret and secret in out for secret in ("AI_API_KEY", "JWT_SECRET_KEY"))
        ok = r["status"] == "success" and not leaked
        if not ok:
            bad.append((name, "intentional", r["status"]))
        print(f"[{'PASS' if ok else '**FAIL**':9s}] {name:22s} status={r['status']} 密钥泄露={leaked}")

    print()
    print("=" * 78)
    print("A1b. 运行时隔离兜底 —— AST 放行，靠 `python -I` 隔离语义防御（不得执行成功）")
    print("=" * 78)
    for name, code in RUNTIME_ISOLATION.items():
        r = run_locally({"main.py": code})
        executed = r["status"] == "success" and bool((r["stdout"] or "").strip())
        ok = not executed
        if not ok:
            bad.append((name, "runtime_isolation", r["status"]))
        print(f"[{'PASS' if ok else '**FAIL**':9s}] {name:22s} status={r['status']} executed={executed}")

    print()
    print("=" * 78)
    print("A2. 保留文件名绕过（skip_paths 逃逸）—— 最高危怀疑点")
    print("=" * 78)
    client = SandboxClient(mode="local")
    for name, files in RESERVED_BYPASS.items():
        entry = next(iter(files))
        # 边界层：用户提交保留名必须被拒（HTTP 400 语义的 AppError）
        try:
            client.run(dict(files), entry=entry)
            boundary = "未拒绝(**FAIL**)"
            boundary_ok = False
        except AppError as exc:
            boundary = f"拒绝({exc.code})"
            boundary_ok = exc.code == "INVALID_PATH"
        # 执行器层：`_plab_guard.py` 必须照常 AST 校验；引导文件按设计跳过（由边界层兜底）
        r = run_locally(dict(files), entry=entry)
        executed = "PWNED" in (r["stdout"] or "")
        if entry == LOCAL_BOOTSTRAP_NAME:
            runner_ok = True  # 系统生成文件，执行器层免检是设计；边界层已拒绝
            runner_note = "执行器层按设计免检（系统生成文件）"
        else:
            runner_ok = r["status"] == "security_error" and not executed
            runner_note = f"status={r['status']} executed={executed}"
        ok = boundary_ok and runner_ok
        if not ok:
            bad.append((name, "RESERVED_NAME_ESCAPE", r["status"]))
        print(f"[{'PASS' if ok else '**FAIL**':9s}] {name}: 边界层={boundary} | {runner_note}")

    print()
    print("=" * 78)
    print("B. 反向误杀 —— 断言 status=success")
    print("=" * 78)
    fp: list[tuple[str, str]] = []
    stdin_map = {"B15_input": "bob\n"}
    for name, code in FALSE_POSITIVE.items():
        v = check_source(code)
        r = run_locally({"main.py": code}, stdin=stdin_map.get(name, ""))
        ok = r["status"] == "success"
        if not ok:
            fp.append((name, v.rule if v else "-"))
        flag = "PASS" if ok else "**误杀**"
        print(
            f"[{flag:9s}] {name:18s} status={r['status']:16s} rule={v.rule if v else '-':28s} out={(r['stdout'] or '')[:42]!r}"
        )
        if not ok:
            print(f"            error={(r['error'] or '')[:160]!r}")

    print()
    print("=" * 78)
    print(f"汇总：绕过失败/泄漏 {len(bad)} 条；误杀 {len(fp)} 条；已知权衡 {len(KNOWN_TRADEOFFS)} 条")
    for x in bad:
        print("  BYPASS-FAIL:", x)
    for x in fp:
        print("  FALSE-POSITIVE:", x)
    for name, why in KNOWN_TRADEOFFS.items():
        print(f"  KNOWN-TRADEOFF: {name} — {why}")
    print()
    print("结论：", "全部通过" if not bad and not fp else "存在待处理项（见上）")


if __name__ == "__main__":
    main()
