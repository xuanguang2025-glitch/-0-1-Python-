"""QA 决定性验证：保留文件名是否真的跳过 AST 校验。

用「一定会被 AST 拦下」的载荷（os.system）分别放在 main.py / _plab_guard.py /
__plab_boot__.py 三个文件名下对比。若保留名下能执行，即证明校验被跳过。

修复后的预期（2026-10 第三轮）：
- 保留名在 **客户端边界**（`SandboxClient._prepare_files` →
  `validate_relative_path`）即被 `AppError(INVALID_PATH)` 拒绝（上层映射 HTTP 400），
  根本到不了执行器；
- 即使绕过边界直达 `LocalRunner`，保留名内容也照常 AST 校验 → `security_error`。
两种结果都算「拦截成功」，本脚本分别输出证据。
"""

from __future__ import annotations

from pathlib import Path
import sys

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

from app.core.errors import AppError  # noqa: E402
from app.services.sandbox_client import SandboxClient  # noqa: E402

PAYLOAD = "import os\nos.system('echo PWNED_VIA_RESERVED_NAME')"

CASES = [
    ("main.py（对照组，应被拦）", {"main.py": PAYLOAD}, "main.py"),
    ("_plab_guard.py（保留名）", {"_plab_guard.py": PAYLOAD}, "_plab_guard.py"),
    ("__plab_boot__.py（保留名/bootstrap）", {"__plab_boot__.py": PAYLOAD}, "__plab_boot__.py"),
    (
        "helper.py 被 import（次要文件也应受检）",
        {"main.py": "import helper\nprint('main ran')", "helper.py": PAYLOAD},
        "main.py",
    ),
]

print("=" * 78)
print("决定性验证：同样载荷（os.system）放在不同文件名下的真实执行结果")
print("=" * 78)
client = SandboxClient(mode="local")
verdicts = []
for label, files, entry in CASES:
    try:
        res = client.run(dict(files), entry=entry)
    except AppError as exc:
        # 客户端边界拒绝（HTTP 400 INVALID_PATH）：载荷根本未进入执行器
        verdicts.append((label, f"rejected:{exc.code}", False))
        print(f"[{'PASS 边界拒绝':14s}] {label:38s} AppError={exc.code} msg={exc.message}")
        continue
    executed = "PWNED_VIA_RESERVED_NAME" in (res.stdout or "")
    if executed:
        flag = "**FAIL 被执行**"
    elif res.status == "security_error":
        flag = "PASS 已拦截"
    else:
        flag = f"其它({res.status})"
    verdicts.append((label, res.status, executed))
    print(f"[{flag:14s}] {label:38s} status={res.status}")
    print(f"                 stdout={(res.stdout or '')[:90]!r}")
    print(f"                 error={(res.error or '')[:110]!r}")

print()
print("=" * 78)
print("API 层是否拒绝用户提交保留文件名？（看 schema / 路径校验）")
print("=" * 78)
from app.schemas.sandbox import RunRequest  # noqa: E402
from app.utils.validators import validate_relative_path  # noqa: E402

for name in ["_plab_guard.py", "__plab_boot__.py", "main.py", "../../etc/passwd"]:
    try:
        validate_relative_path(name)
        verdict = "接受"
    except Exception as exc:
        verdict = f"拒绝({type(exc).__name__})"
    print(f"  validate_relative_path({name!r:22s}) -> {verdict}")

try:
    req = RunRequest(files=[{"path": "_plab_guard.py", "content": "print(1)"}], entry="_plab_guard.py")
    print(f"  RunRequest 接受保留名文件：entry={req.entry!r} files={[f.path for f in req.files]}")
except Exception as exc:
    print(f"  RunRequest 拒绝：{type(exc).__name__}: {exc}")

print()
print("=" * 78)
print("结论汇总")
print("=" * 78)
for label, _status, executed in verdicts:
    print(f"  {'越权执行' if executed else '已拦截':8s} | {label}")
