"""QA：验证 test_testbase.py 的 6 条守护用例是否【真的在守护】（kill-the-test）。

对 conftest.py 做 5 种定向破坏，每次只跑守护用例（BREAK3 额外跑全量），
记录是否变红；全部破坏结束后按字节还原并复跑，确认回到全绿。
"""

from __future__ import annotations

import pathlib
import re
import subprocess

CONFTEST = pathlib.Path("tests/conftest.py")
PY = ".venv/Scripts/python.exe"


def run(args: list[str]) -> tuple[int, str, list[str]]:
    proc = subprocess.run(
        [PY, "-m", "pytest", *args, "-q", "--no-header", "-p", "no:cacheprovider"],
        capture_output=True,
        text=True,
    )
    tail = re.findall(r"(\d+ (?:passed|failed)[^\n]*)", proc.stdout)
    failed = re.findall(r"(FAILED [^\n]*)", proc.stdout)
    return proc.returncode, (tail[-1] if tail else "?"), failed


def main() -> None:
    original = CONFTEST.read_bytes()
    text = original.decode("utf-8")

    breaks: list[tuple[str, list[str], str, str]] = [
        (
            "BREAK1 少建一张表（create_all 跳过 users）",
            ["tests/test_testbase.py"],
            r"( *)Base\.metadata\.create_all\(engine\)",
            r"\1Base.metadata.create_all(engine, tables=[t for n, t in Base.metadata.tables.items() if n != 'users'])",
        ),
        (
            "BREAK2 内存库 -> 磁盘库",
            ["tests/test_testbase.py"],
            r'"sqlite://",',
            "f\"sqlite:///{Path('data') / 'qa_break2.db'}\",",
        ),
        (
            "BREAK3 移除每用例 MemoryCache 注入（限流隔离）",
            [],
            r" *cache_container\.override\(MemoryCache\(\)\)\r?\n",
            "",
        ),
        (
            "BREAK4 移除 App 会话级缓存（提速机制）",
            ["tests/test_testbase.py"],
            r" *cached = _APP_CACHE\.get\(key\)\r?\n *if cached is not None:\r?\n *return cached\r?\n",
            "",
        ),
        (
            "BREAK5 完全不建表",
            ["tests/test_testbase.py"],
            r" *Base\.metadata\.create_all\(engine\)\r?\n",
            "",
        ),
        (
            "BREAK6 seeded_users 只建普通用户（不建 admin）",
            ["tests/test_testbase.py"],
            r"    admin = User\(\r?\n(?:.*\r?\n)*?    \)\r?\n",
            "",
        ),
        (
            "BREAK7 user_headers 换成 admin token（鉴权链路被篡改）",
            ["tests/test_testbase.py"],
            r'return \{"Authorization": f"Bearer \{auth_tokens\.user\}"\}',
            'return {"Authorization": f"Bearer {auth_tokens.admin}"}',
        ),
    ]

    try:
        code, summary, _ = run(["tests/test_testbase.py"])
        print(f"[BASELINE] exit={code} | {summary}")

        for label, targets, pattern, repl in breaks:
            patched, n = re.subn(pattern, repl, text, count=1)
            if n == 0 or patched == text:
                print(f"[{label}] !! 补丁未命中，跳过（正则失效）")
                continue
            CONFTEST.write_text(patched, encoding="utf-8", newline="")
            code, summary, failed = run(targets)
            verdict = "🔴 变红(守护有效)" if code != 0 else "🟢 **仍然全绿(假守护)**"
            print(f"[{label}] exit={code} | {summary}  => {verdict}")
            for line in failed[:8]:
                print(f"      {line}")
            CONFTEST.write_bytes(original)
    finally:
        CONFTEST.write_bytes(original)

    same = CONFTEST.read_bytes() == original
    print(f"[RESTORE] 字节级一致: {same}")
    code, summary, _ = run(["tests/test_testbase.py"])
    print(f"[RESTORED] exit={code} | {summary}")


if __name__ == "__main__":
    main()
