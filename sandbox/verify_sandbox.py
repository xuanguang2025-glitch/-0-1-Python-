"""沙箱验收脚本：跑 5 个必过用例 + judge 冒烟，输出结果表。

用法：sandbox/.venv/Scripts/python.exe sandbox/verify_sandbox.py [--url http://127.0.0.1:8081]
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List, Tuple


def _opener() -> urllib.request.OpenerDirector:
    """构造**绕过系统代理**的 opener（本机 127.0.0.1 不应走 http_proxy）。"""
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def post(url: str, path: str, payload: Dict[str, Any], timeout: float = 30.0) -> Dict[str, Any]:
    """POST JSON 并解析响应。"""
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{url.rstrip('/')}{path}", data=data,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with _opener().open(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", "replace"))


def get(url: str, path: str, timeout: float = 5.0) -> Dict[str, Any]:
    """GET JSON。"""
    with _opener().open(f"{url.rstrip('/')}{path}", timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", "replace"))


def check(name: str, expected: str, payload: Dict[str, Any], path: str, url: str) -> Tuple[str, str, str, bool]:
    """执行一个用例并返回 (用例, 期望, 实际, 是否通过)。"""
    try:
        result = post(url, path, payload)
    except urllib.error.HTTPError as exc:
        return name, expected, f"HTTP {exc.code}: {exc.read()[:200]!r}", False
    except Exception as exc:  # noqa: BLE001
        return name, expected, f"异常 {exc}", False

    status = result.get("status")
    stdout = result.get("stdout", "")
    duration = result.get("duration_ms", result.get("time_ms"))
    actual = (
        f"status={status} exit={result.get('exit_code')} dur={duration}ms "
        f"mem={result.get('memory_kb')}kB trunc={result.get('truncated')} "
        f"timed_out={result.get('timed_out')} len(stdout)={len(stdout)}"
    )
    if stdout:
        actual += f" | stdout[:40]={stdout[:40]!r}"
    if result.get("stderr"):
        actual += f" | stderr[:80]={result['stderr'][:80]!r}"

    ok = False
    if name == "print hello world":
        ok = status == "success" and stdout.strip() == "hello world" and result.get("exit_code") == 0
    elif name == "while True: pass":
        ok = status == "timeout" and result.get("timed_out") is True and (duration or 99999) <= 8000
    elif name == "os.system 拦截":
        ok = status == "security_error" and "hacked" not in stdout
    elif name == "敏感路径读取拦截":
        ok = status == "security_error"
    elif name == "输出爆炸截断":
        ok = result.get("truncated") is True and len(stdout.encode("utf-8")) <= 65600
    return name, expected, actual, ok


def main() -> int:
    """入口。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8081")
    args = parser.parse_args()
    url = args.url

    health = get(url, "/health")
    print("=== /health ===")
    print(json.dumps({k: health.get(k) for k in
                      ("status", "runner", "security_level", "degraded", "platform", "python")},
                     ensure_ascii=False))
    print("capabilities:", json.dumps(health.get("capabilities"), ensure_ascii=False))
    print()

    sensitive = 'print(open(r"C:/Windows/win.ini").read())' if sys.platform == "win32" else \
        'print(open("/etc/passwd").read())'

    cases: List[Tuple[str, str, str, Dict[str, Any]]] = [
        ("print hello world", "success + stdout=hello world", "/run", {"code": 'print("hello world")'}),
        ("while True: pass", "timeout, timed_out=true, <=8s", "/run",
         {"code": "while True:\n    pass", "timeout_ms": 2000}),
        ("os.system 拦截", "security_error", "/run",
         {"code": 'import os\nos.system("echo hacked")'}),
        ("敏感路径读取拦截", "security_error", "/run", {"code": sensitive}),
        ("输出爆炸截断", "truncated=true, stdout<=64KB", "/run", {"code": 'print("A" * 10 ** 7)'}),
    ]

    rows = [check(name, expected, payload, path, url) for name, expected, path, payload in cases]

    print("=== 验收用例 ===")
    for index, (name, expected, actual, ok) in enumerate(rows, start=1):
        print(f"{index}. [{ 'PASS' if ok else 'FAIL' }] {name}")
        print(f"   期望: {expected}")
        print(f"   实际: {actual}")

    # judge 冒烟
    judge = post(url, "/judge", {
        "mode": "judge",
        "code": "a, b = map(int, input().split())\nprint(a + b)",
        "test_cases": [
            {"id": "tc1", "input": "1 2\n", "expected": "3"},
            {"id": "tc2", "input": "10 20\n", "expected": "30"},
            {"id": "tc3", "input": "1 2\n", "expected": "999"},
        ],
    })
    judge_ok = judge.get("passed_cases") == 2 and judge.get("total_cases") == 3
    print(f"6. [{'PASS' if judge_ok else 'FAIL'}] judge 批量判题")
    print(f"   期望: passed_cases=2/3")
    print(f"   实际: passed={judge.get('passed_cases')}/{judge.get('total_cases')} "
          f"status={judge.get('status')} results={[r.get('passed') for r in judge.get('results', [])]}")

    failed = [name for name, _e, _a, ok in rows if not ok]
    print()
    if failed or not judge_ok:
        print("FAILED:", ", ".join(failed + ([] if judge_ok else ["judge"])))
        return 1
    print("ALL PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
