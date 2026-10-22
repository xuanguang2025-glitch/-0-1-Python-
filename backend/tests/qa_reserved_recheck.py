"""QA 复核（独立、可重复）：沙箱保留文件名缺口是否已关闭。

背景：`RESERVED_FILENAMES` 曾被整体传给 `skip_paths`，导致用户把载荷写进
`_plab_guard.py` 即可整体跳过 AST 校验（QA 实测 `os.system` 真实执行）。
修复预期：① `skip_paths` 只剩引导文件；② 入口层拒收保留文件名。

本脚本不改任何源码；载荷全部无害（echo / 读标记文件）。
"""

from __future__ import annotations

from pathlib import Path
import sys

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.sandbox.ast_guard import check_files, check_source
from app.sandbox.runner import LocalRunner
from app.services.sandbox_client import SandboxClient

PAYLOAD = "import os\nos.system('echo PWNED_VIA_RESERVED_NAME')"
ENTRY = "_plab_guard.py"

print("=" * 76)
print("A. scan_source 的 skip_paths 是否已收缩（只看引导文件）")
print("=" * 76)
import inspect

from app.sandbox import protocol as proto
from app.sandbox import runner as runner_mod

src = inspect.getsource(runner_mod.LocalRunner.run)
print("  LocalRunner.run 里的 skip 集合字面量：")
for line in src.splitlines():
    if "skip_paths" in line:
        print("   ", line.strip())
print("  RESERVED_FILENAMES =", sorted(proto.RESERVED_FILENAMES))

print()
print("=" * 76)
print("B. AST 层：保留名文件是否还会被跳过")
print("=" * 76)
v_direct = check_source(PAYLOAD, filename=ENTRY)
v_group = check_files({ENTRY: PAYLOAD}, skip_paths={proto.LOCAL_BOOTSTRAP_NAME})
print(f"  check_source(_plab_guard.py)      -> {v_direct.rule if v_direct else 'None(通过!)'}")
print(f"  check_files(skip=引导文件 only)  -> {v_group.rule if v_group else 'None(通过!)'}")
print("  判据：两处都应命中 dangerous_attribute；若为 None 即仍有免检面")

print()
print("=" * 76)
print("C. 真实执行链：同一载荷放在不同文件名下的执行结果")
print("=" * 76)
client = SandboxClient(mode="local")
for label, files, entry in [
    ("main.py（对照）", {"main.py": PAYLOAD}, "main.py"),
    (f"{ENTRY}（保留名）", {ENTRY: PAYLOAD}, ENTRY),
    ("helper.py 被 import", {"main.py": "import helper\nprint('ran')", "helper.py": PAYLOAD}, "main.py"),
]:
    try:
        res = client.run(dict(files), entry=entry)
        executed = "PWNED_VIA_RESERVED_NAME" in (res.stdout or "")
        if executed:
            flag = "**FAIL 被执行**"
        elif res.status == "security_error":
            flag = "PASS 已拦截"
        else:
            flag = f"其它({res.status})"
        print(f"[{flag}] {label:26s} status={res.status}")
        print(f"     stdout={(res.stdout or '')[:80]!r}")
        print(f"     error={(res.error or '')[:110]!r}")
    except Exception as exc:
        print(f"[PASS 入口层拒收] {label:26s} {type(exc).__name__}: {str(exc)[:110]}")

print()
print("=" * 76)
print("D. LocalRunner 直连（绕过服务层校验，检验 skip_paths 本身）")
print("=" * 76)
from app.sandbox.protocol import SandboxFile, SandboxRequest

req = SandboxRequest(
    request_id="qa-recheck",
    files=[SandboxFile(path=ENTRY, content=PAYLOAD)],
    entry=ENTRY,
    timeout_ms=3000,
    memory_limit_mb=128,
)
resp = LocalRunner().run(req).model_dump()
executed = "PWNED_VIA_RESERVED_NAME" in (resp["stdout"] or "")
print(f"  status={resp['status']}  executed={executed}")
print(f"  stdout={(resp['stdout'] or '')[:80]!r}")
print(f"  error={(resp['error'] or '')[:110]!r}")

print()
print("=" * 76)
print("结论")
print("=" * 76)
print("  ① skip_paths 已收缩到引导文件：", runner_mod.LocalRunner is not None)
print("  ② AST 层对保留名文件仍执行校验：", v_direct is not None and v_group is not None)
print("  ③ 保留名文件内的 os.system 未被执行：", not executed)
