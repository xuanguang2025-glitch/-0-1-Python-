"""沙箱 AST 白名单安全回归测试（`app/sandbox/ast_guard.py`）。

背景：QA 用**字符串黑名单**绕过本机执行器成功执行了系统命令 —— 根因是
`FORBIDDEN_PATTERNS` 只匹配单引号字面量，而 `scan_source` 仅做子串比对：

    __import__("os").system("echo PWNED_DUALQUOTE")   # 双引号 → 不匹配黑名单
    getattr(os, "system")("echo PWNED_GETATTR")       # 反射拿函数
    open("C:/Windows/win.ini").read()                 # 任意读
    os.listdir("C:/")                                 # 任意列目录

本模块把这些手法全部变成回归用例，并**同时**锁定「正常教学代码不被误杀」
（`os.path` / `dict.get` / `str.replace` / `list.remove` / 相对路径 `open` /
`input()` / `sys.exit(0)` / `print('/usr')`），防止修安全时把判题与练习链路一起打死。

两轮收窄的误杀修复也在此锁定：
- `sys.exit(0)` / `exit()` / `quit()`：OJ 标准写法，移出 `BLOCKED_CALL_NAMES`；
- `path_literal`：只在 `open()` / `Path()` 实参位置检查，纯展示用法放行。
"""

from __future__ import annotations

import os
import sys
from typing import Any

from fastapi.testclient import TestClient
import pytest

from app.api.endpoints import editor
from app.sandbox.ast_guard import check_files, check_source
from app.sandbox.protocol import SandboxFile, SandboxRequest
from app.sandbox.runner import LocalRunner

#: 仅挂载 /api/python/run 所在 router
RUN_ROUTERS = (editor.python_router,)

#: 平台相关的敏感绝对路径（Windows 用 win.ini，POSIX 用 /etc/passwd）
SENSITIVE_ABS: str = "C:/Windows/win.ini" if sys.platform == "win32" else "/etc/passwd"

#: QA 实测可绕过的输入 → 期望命中的 AST 规则
BYPASS_CASES: list[tuple[str, str, str]] = [
    ("dunder_import", '__import__("os").system("echo PWNED_DUALQUOTE")', "dangerous_attribute"),
    ("getattr_reflect", "import os\ngetattr(os, 'system')('echo PWNED_GETATTR')", "dangerous_call"),
    ("abs_path_read", f'print(open("{SENSITIVE_ABS}").read())', "open_absolute_path"),
    ("listdir_root", "import os\nprint(os.listdir('C:/'))", "dangerous_attribute"),
    ("os_system_plain", "import os\nos.system('echo PWNED')", "dangerous_attribute"),
    ("os_popen", "import os\nprint(os.popen('echo PWNED').read())", "dangerous_attribute"),
    ("subprocess_import", "import subprocess\nsubprocess.run(['echo', 'PWNED'])", "import_not_allowed"),
    ("eval_exec", 'eval("print(1337)")', "dangerous_call"),
    ("dunder_escape", "print((1).__class__.__mro__)", "dunder_attribute"),
    ("dynamic_open", "name = 'a.txt'\nopen(name).read()", "open_dynamic_path"),
    # 间接引用：字符串常量本身不再全局触发 path_literal（那会误杀 print('/usr')），
    # 改由 open() 实参位置失败关闭（open_dynamic_path）—— 拦截结论不变且更严格。
    ("path_literal_indirect", f'p = "{SENSITIVE_ABS}"\nopen(p).read()', "open_dynamic_path"),
    ("path_literal_in_path", f"from pathlib import Path\nPath({SENSITIVE_ABS!r}).read_text()", "path_literal"),
    ("traversal", "open('../../etc/hosts').read()", "open_absolute_path"),
    ("shutil_rmtree", "import shutil\nshutil.rmtree('/')", "import_not_allowed"),
    ("os_remove", "import os\nos.remove('x.txt')", "dangerous_module_attribute"),
    ("from_os_import_system", "from os import system\nsystem('echo PWNED')", "import_dangerous_name"),
    ("shell_injection_literal", "cmd = 'rm -rf /'\nprint(cmd)", "shell_injection"),
]

#: 语法错误单独处理：解析失败同样**不执行**，但状态是判题结论 `compile_error`（不是安全事件）
SYNTAX_ERROR_CODE = "def broken(:\n    pass\n"


# --------------------------------------------------------------------- 夹具
@pytest.fixture()
def api(client_factory, db, user_headers) -> tuple[TestClient, dict[str, str]]:
    """`/api/python/run` 客户端 + 普通用户鉴权头。"""
    return client_factory(RUN_ROUTERS), user_headers


def _run_api(client: TestClient, headers: dict[str, str], code: str, **extra: Any) -> dict[str, Any]:
    """调用 `/api/python/run` 并返回 data 段。"""
    payload: dict[str, Any] = {"files": [{"path": "main.py", "content": code}]}
    payload.update(extra)
    response = client.post("/api/python/run", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]


# ---------------------------------------------------------------- API 层回归
def test_api_rejects_all_known_bypasses(api) -> None:
    """QA 用过的每一种绕过都必须被拦下，且**没有任何输出**。"""
    client, headers = api
    for name, code, _rule in BYPASS_CASES:
        data = _run_api(client, headers, code)
        assert data["status"] == "security_error", f"{name} 未被拦截: {data}"
        assert data["stdout"] == "", f"{name} 泄漏了输出: {data['stdout']!r}"
        assert "PWNED" not in data["stdout"]


def test_api_bypass_error_message_names_the_rule(api) -> None:
    """拒绝时必须给出命中的规则名（便于排障，不是静默通过）。"""
    client, headers = api
    data = _run_api(client, headers, '__import__("os").system("echo PWNED")')
    assert data["status"] == "security_error"
    assert data["error"], "必须返回 error 说明"
    assert "[dangerous_attribute]" in data["error"] or "system" in data["error"]


def test_api_multifile_bypass_blocked(api) -> None:
    """多文件项目里的危险子模块同样被拦（不能靠拆分文件绕过）。"""
    client, headers = api
    response = client.post(
        "/api/python/run",
        json={
            "files": [
                {"path": "main.py", "content": "import helper\nhelper.pwn()\n"},
                {"path": "helper.py", "content": "import os\ndef pwn():\n    os.system('echo PWNED')\n"},
            ]
        },
        headers=headers,
    )
    data = response.json()["data"]
    assert data["status"] == "security_error"
    assert data["stdout"] == ""


def test_api_syntax_error_never_executes(api) -> None:
    """解析失败必须**不执行**，且表达为判题结论 `compile_error`（而非安全事件）。

    学习者写错语法是 CE（编译错误）结论，若报 `security_error` 会误导用户，
    也破坏判题链路语义；关键不变量是「不执行 + 无输出」。
    """
    client, headers = api
    data = _run_api(client, headers, SYNTAX_ERROR_CODE)
    assert data["status"] == "compile_error", data
    assert data["stdout"] == ""
    assert data["runner"] == "local"


def test_ast_guard_flags_syntax_error() -> None:
    """AST 层仍然识别语法错误（只是状态映射不同）。"""
    violation = check_source(SYNTAX_ERROR_CODE, filename="main.py")
    assert violation is not None
    assert violation.rule == "syntax_error"


# ------------------------------------------------------------- 正常代码不误杀
def test_api_learner_code_not_killed(api) -> None:
    """真实学习者代码必须照常执行（os.path / dict.get / 相对路径 open / replace / remove）。"""
    client, headers = api
    code = (
        "import os\n"
        "print(os.path.join('a', 'b'))\n"
        "data = {'a': 1}\n"
        "print(data.get('a'))\n"
        "with open('data.txt', 'w') as f:\n"
        "    f.write('hi')\n"
        "print(open('data.txt').read())\n"
        "print(sorted([3, 1, 2]), sum([1, 2]))\n"
        "print('a-b'.replace('-', '_'), [1, 2, 3].remove(2))\n"
        "print(os.environ.get('PATH', '') != '')\n"
    )
    data = _run_api(client, headers, code)
    assert data["status"] == "success", data
    lines = [line for line in data["stdout"].splitlines() if line.strip()]
    assert lines[0] == os.path.join("a", "b")
    assert lines[1] == "1"
    assert lines[2] == "hi"
    assert lines[3] == "[1, 2, 3] 3"
    # 注意：list.remove() 返回 None（这是 Python 语义，不是沙箱行为）
    assert lines[4] == "a_b None"
    assert lines[5] == "True"


def test_api_stdin_input_still_works(api) -> None:
    """`input()` 必须可用 —— 判题与交互练习依赖它（因此**刻意不拦** input）。"""
    client, headers = api
    data = _run_api(client, headers, "name = input()\nprint(f'hi {name}')\n", stdin="bob\n")
    assert data["status"] == "success", data
    assert data["stdout"].strip() == "hi bob"


def test_api_sys_exit_zero_runs(api) -> None:
    """`sys.exit(0)` 是 OJ 标准写法（stage-16 课程正文即用到），必须放行。

    退出当前子进程不构成逃逸：子进程本来就会被超时 kill / rlimit 收口。
    """
    client, headers = api
    data = _run_api(client, headers, "print('before exit')\nimport sys\nsys.exit(0)\n")
    assert data["status"] == "success", data
    assert data["stdout"].strip() == "before exit"


def test_api_sys_exit_nonzero_is_runtime_error(api) -> None:
    """`sys.exit(1)` 同样放行执行，但按非零退出码归一为判题错误（不是安全事件）。"""
    client, headers = api
    data = _run_api(client, headers, "import sys\nprint('bye')\nsys.exit(2)\n")
    assert data["status"] in ("error", "runtime_error"), data
    assert data["stdout"].strip() == "bye"


def test_api_bare_exit_quit_runs(api) -> None:
    """REPL 内置 `exit()` / `quit()`（stage-01 课程提到）同样不得误杀。"""
    client, headers = api
    data = _run_api(client, headers, "print('before quit')\nquit()\n")
    assert data["status"] == "success", data
    assert data["stdout"].strip() == "before quit"


def test_api_printing_posix_paths_runs(api) -> None:
    """纯展示用途的路径字符串必须放行（`print('/usr', '/tmp')` 曾是误杀）。"""
    client, headers = api
    data = _run_api(client, headers, "print('path example:', '/usr', '/tmp')\n")
    assert data["status"] == "success", data
    assert data["stdout"].strip() == "path example: /usr /tmp"


def test_api_absolute_path_still_blocked_after_narrowing(api) -> None:
    """收窄 `path_literal` 后，open()/Path() 实参位置的绝对路径仍必须被拦。"""
    client, headers = api
    data = _run_api(client, headers, f'print(open("{SENSITIVE_ABS}").read())')
    assert data["status"] == "security_error", data
    assert data["stdout"] == ""
    assert "open_absolute_path" in (data["error"] or "")
    # Path() 构造参数的绝对路径同样被拦（path_literal）
    data2 = _run_api(client, headers, f"from pathlib import Path\nPath({SENSITIVE_ABS!r}).read_text()")
    assert data2["status"] == "security_error", data2
    assert "path_literal" in (data2["error"] or "")
    # Path() 上跳参数仍被拦（path_constructor_escape）
    data3 = _run_api(client, headers, "from pathlib import Path\nPath('../x').write_text('y')")
    assert data3["status"] == "security_error", data3
    assert "path_constructor_escape" in (data3["error"] or "")


def test_ast_guard_allows_display_only_path_literals() -> None:
    """AST 层：不处于路径语义位置的敏感路径字符串不得被误杀。"""
    for code in [
        "print('path example:', '/usr', '/tmp')",
        "paths = ['/etc', '/var', '/home']\nprint(len(paths))",
        "print('/root is off limits')",
        "msg = 'C:/Windows/System32'\nprint(len(msg))",
    ]:
        violation = check_source(code, filename="main.py")
        assert violation is None, f"误杀: {violation.describe() if violation else ''} <- {code!r}"


def test_ast_guard_allows_sys_exit() -> None:
    """AST 层：`sys.exit(0)` / `exit()` / `quit()` / `from sys import exit` 均放行。"""
    for code in [
        "import sys\nprint('x')\nsys.exit(0)\n",
        "print('x')\nexit()\n",
        "print('x')\nquit()\n",
        "from sys import exit\nprint('x')\nexit(0)\n",
        "import sys\nsys.exit(main()) if False else None\n",
    ]:
        violation = check_source(code, filename="main.py")
        assert violation is None, f"误杀: {violation.describe() if violation else ''} <- {code!r}"


def test_api_multifile_project_runs(api) -> None:
    """多文件项目的正常跨文件 import 不受影响。"""
    client, headers = api
    response = client.post(
        "/api/python/run",
        json={
            "files": [
                {"path": "main.py", "content": "from utils.helper import add\nprint(add(2, 3))\n"},
                {"path": "utils/__init__.py", "content": ""},
                {"path": "utils/helper.py", "content": "def add(a, b):\n    return a + b\n"},
            ]
        },
        headers=headers,
    )
    data = response.json()["data"]
    assert data["status"] == "success", data
    assert data["stdout"].strip() == "5"


def test_api_truncation_behaviour_preserved(api) -> None:
    """输出截断行为保持不变（MAX_OUTPUT_BYTES 仍生效）。"""
    client, headers = api
    data = _run_api(client, headers, "print('A' * 200000)\n")
    assert data["truncated"] is True
    assert len(data["stdout"]) <= 65_536 + 64


# ------------------------------------------------------------- 执行器层回归
@pytest.mark.parametrize("name,code,rule", BYPASS_CASES)
def test_local_runner_rejects_bypass(name: str, code: str, rule: str) -> None:
    """LocalRunner 直连路径同样必须拒绝（不经 HTTP 也不能绕过）。"""
    request = SandboxRequest(
        request_id="test-sec",
        files=[SandboxFile(path="main.py", content=code)],
        entry="main.py",
    )
    response = LocalRunner().run(request)
    assert response.status == "security_error", f"{name}: {response.stdout!r}"
    assert response.stdout == ""
    assert response.error and rule in response.error


# --------------------------------------------------------------- AST 单元测试
@pytest.mark.parametrize("name,code,rule", BYPASS_CASES)
def test_ast_guard_rule(name: str, code: str, rule: str) -> None:
    """每种绕过都应命中预期规则。"""
    violation = check_source(code, filename="main.py")
    assert violation is not None, f"{name} 未被拦截"
    assert violation.rule == rule, f"{name} 规则不符: {violation.describe()}"


@pytest.mark.parametrize(
    "code",
    [
        "import os\nprint(os.path.join('a', 'b'))",
        "import os\nprint(os.path.exists('x'), os.getcwd() != '')",
        "import os\nprint(os.environ.get('PATH', '')[:4])",
        "data = {'a': 1}\nprint(data.get('a'), data.keys())",
        "print('a-b'.replace('-', '_'))",
        "print([1, 2, 3].remove(2))",
        "with open('notes.txt', 'w') as f:\n    f.write('hi')",
        "print(open('notes.txt').read())",
        "import math\nprint(math.sqrt(16))",
        "from collections import Counter\nprint(Counter('aab').most_common(1))",
        "if __name__ == '__main__':\n    print('main')",
        "name = input()\nprint('hi', name)",
        "print(sorted([3, 1, 2]), sum([1, 2]), max([1, 5]))",
        "import csv, io\nprint(hasattr(csv, 'reader'), hasattr(io, 'StringIO'))",
    ],
)
def test_ast_guard_allows_learner_code(code: str) -> None:
    """正常教学代码不得被误杀（逐条覆盖 os.path / 反射以外的常用写法）。"""
    violation = check_source(code, filename="main.py")
    assert violation is None, f"误杀: {violation.describe() if violation else ''} <- {code!r}"


def test_ast_guard_import_whitelist_from_settings() -> None:
    """白名单来自 SANDBOX_ALLOWED_IMPORTS 配置（可用参数覆盖）。"""
    assert check_source("import socket", filename="m.py") is not None
    assert check_source("import numpy", filename="m.py", allowed_imports=["numpy"]) is None
    assert check_source("import numpy", filename="m.py", allowed_imports=["math"]) is not None


def test_ast_guard_reports_line_number() -> None:
    """违规必须带行号，便于前端定位。"""
    violation = check_source("import math\nimport os\nos.system('echo x')\n", filename="m.py")
    assert violation is not None
    assert violation.line == 3
    assert "m.py:3" in violation.describe()


def test_ast_guard_local_module_allowance_is_scoped() -> None:
    """多文件项目自带模块按提交范围放行，但**不会**顺带放开未提交的系统模块。"""
    files = {
        "main.py": "from utils.helper import add\nprint(add(1, 2))\n",
        "utils/__init__.py": "",
        "utils/helper.py": "def add(a, b):\n    return a + b\n",
    }
    assert check_files(files) is None
    # 放行范围仅限本次提交：单文件里 import 一个未提交的本地模块仍应被拒
    assert check_source("from utils.helper import add", filename="main.py") is not None
    # 未提交的系统模块同样被拒
    assert check_source("import socket", filename="main.py") is not None


def test_ast_guard_empty_source_allowed() -> None:
    """空文件不报错（由执行器另行判定入口/输出）。"""
    assert check_source("", filename="m.py") is None
    assert check_source("   \n", filename="m.py") is None
