"""QA 复核：区分「真绕过」与「我脚本的误判」，并给出可复现的影响证明。

安全注意：所有写操作都写到系统 TEMP 目录（沙箱工作目录的父目录），
脚本结束前会删除自己创建的文件。不触碰真实数据库与项目文件。
"""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

from app.core.errors import AppError  # noqa: E402
from app.sandbox.protocol import SandboxFile, SandboxRequest  # noqa: E402
from app.sandbox.runner import LocalRunner  # noqa: E402
from app.services.sandbox_client import SandboxClient  # noqa: E402

PARENT = Path(tempfile.gettempdir())
PROOF = "qa_escape_proof.txt"


def cleanup() -> None:
    for p in (PARENT / PROOF, BACKEND / PROOF):
        if p.exists():
            p.unlink()
            print(f"  [cleanup] 已删除 {p}")


def run_local(files: dict[str, str], entry: str) -> dict:
    req = SandboxRequest(
        request_id="qa2",
        files=[SandboxFile(path=p, content=c) for p, c in files.items()],
        entry=entry,
        timeout_ms=4000,
        memory_limit_mb=128,
    )
    return LocalRunner().run(req).model_dump()


def show(label: str, r: dict, keys=("status", "stdout", "error")) -> None:
    print(f"  [{label}] status={r.get('status')}")
    for k in keys:
        if k != "status":
            print(f"      {k}={(r.get(k) or '')[:200]!r}")


print("=" * 78)
print("复核 1：os.environ 是否真的读不到密钥（上一轮我误判为绕过）")
print("=" * 78)
r = run_local(
    {
        "main.py": (
            "import os\n"
            "print('KEYS=', sorted(os.environ.keys()))\n"
            "print('AI=', repr(os.environ.get('AI_API_KEY')))\n"
            "print('JWT=', repr(os.environ.get('JWT_SECRET_KEY')))\n"
            "print('SECRET=', repr(os.environ.get('SECRET_KEY')))\n"
            "print('DB=', repr(os.environ.get('DATABASE_URL')))\n"
        )
    },
    "main.py",
)
show("os.environ", r)
print("  结论：读环境变量是**有意允许**的；关键是值必须为空。")

print()
print("=" * 78)
print("复核 2：__builtins__ 下标是否真能逃逸")
print("=" * 78)
r = run_local({"main.py": "print(type(__builtins__))\nprint(__builtins__['eval'])"}, "main.py")
show("__builtins__下标", r)
print("  结论：`-I` 隔离模式下 __builtins__ 是 module 不可下标 → 无法逃逸。")

print()
print("=" * 78)
print("复核 3：os.chdir 上跳 —— 用【可写证明】验证是否真的逃出工作目录")
print("=" * 78)
print(f"  沙箱工作目录的父目录 = {PARENT}")
r = run_local(
    {
        "main.py": (
            "import os\n"
            "os.chdir('..')\n"
            "open('qa_escape_proof.txt','w').write('ESCAPED_WRITE_PROOF')\n"
            "print('cwd=', os.getcwd())\n"
            "print('wrote=', os.path.abspath('qa_escape_proof.txt'))\n"
        )
    },
    "main.py",
)
show("os.chdir写逃逸", r)
escaped_write = (PARENT / PROOF).exists()
print(f"  [{'**FAIL**' if escaped_write else 'PASS'}] 工作目录外文件是否被创建：{escaped_write}")

if escaped_write:
    r2 = run_local(
        {"main.py": "import os\nos.chdir('..')\nprint('READ_BACK=', open('qa_escape_proof.txt').read())"},
        "main.py",
    )
    show("工作目录外读取", r2)

print()
print("=" * 78)
print("复核 4：pathlib 相对上跳写逃逸")
print("=" * 78)
r = run_local(
    {"main.py": "from pathlib import Path\nPath('../qa_escape_proof2.txt').write_text('PATHLIB_ESCAPE')\nprint('ok')"},
    "main.py",
)
show("pathlib上跳写", r)
p2 = PARENT / "qa_escape_proof2.txt"
print(f"  [{'**FAIL**' if p2.exists() else 'PASS'}] 工作目录外文件是否被创建：{p2.exists()}")

print()
print("=" * 78)
print("复核 5：os.makedirs 是否可任意建目录")
print("=" * 78)
r = run_local({"main.py": "import os\nos.makedirs('../qa_escape_dir', exist_ok=True)\nprint('MKDIR_OK')"}, "main.py")
show("os.makedirs", r)
d = PARENT / "qa_escape_dir"
print(f"  [{'**FAIL**' if d.exists() else 'PASS'}] 目录是否被创建：{d.exists()}")

print()
print("=" * 78)
print("复核 6（最高危）：保留文件名 `_plab_guard.py` 走【真实 API 执行链】")
print("=" * 78)
client = SandboxClient(mode="local")
payload = (
    "import os\n"
    "print('ESCAPED_VIA_RESERVED_NAME')\n"
    "os.chdir('..')\n"
    "open('qa_escape_proof.txt','w').write('RESERVED_NAME_FS_ESCAPE')\n"
    "print('fs_escape=', os.path.abspath('qa_escape_proof.txt'))\n"
)
try:
    res = client.run({"_plab_guard.py": payload}, entry="_plab_guard.py")
    print(f"  [走 SandboxClient] status={res.status} runner={res.runner} degraded={res.degraded}")
    print(f"      stdout={(res.stdout or '')[:220]!r}")
    print(f"      error={(res.error or '')[:160]!r}")
    executed = "ESCAPED_VIA_RESERVED_NAME" in (res.stdout or "")
except AppError as exc:
    # 修复后：保留名在客户端边界即被拒绝（上层映射 HTTP 400），载荷未进入执行器
    print(f"  [走 SandboxClient] 边界拒绝 AppError={exc.code} msg={exc.message}")
    executed = False
fs_escape = (PARENT / PROOF).exists()
print(f"  [{'**FAIL** 越权写成功' if fs_escape else 'PASS 未逃逸'}] 保留名文件是否完成真实 FS 逃逸：{fs_escape}")
print(f"  [{'**FAIL** 载荷被执行' if executed else 'PASS 载荷未执行'}]")

print()
print("=" * 78)
print("复核 7：对照组 —— 同样载荷放在 main.py（应被拦）")
print("=" * 78)
res2 = client.run({"main.py": payload}, entry="main.py")
print(f"  status={res2.status}  error={(res2.error or '')[:120]!r}")
print("  → 对照组被拦即证明：唯一差别就是文件名。")

print()
print("=" * 78)
print("复核 8：三个真实误杀的最小复现")
print("=" * 78)
for label, code in [
    ("sys.exit(0)", "import sys\nprint('done')\nsys.exit(0)"),
    ("os.remove(自己创建的文件)", "import os\nopen('t.txt','w').write('x')\nos.remove('t.txt')\nprint('cleaned')"),
    ("打印字符串 '/usr'", "print('path example:', '/usr', '/tmp')"),
]:
    v = run_local({"main.py": code}, "main.py")
    hit = v["status"] == "security_error"
    print(f"  [{'**误杀**' if hit else 'PASS'}] {label:24s} status={v['status']} error={(v.get('error') or '')[:90]!r}")

cleanup()
p2 = PARENT / "qa_escape_proof2.txt"
if p2.exists():
    p2.unlink()
    print(f"  [cleanup] 已删除 {p2}")
if (PARENT / "qa_escape_dir").exists():
    (PARENT / "qa_escape_dir").rmdir()
    print("  [cleanup] 已删除 qa_escape_dir")
