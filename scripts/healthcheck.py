#!/usr/bin/env python
"""健康与降级状态自检（仅标准库，任何 Python 3.9+ 可运行）。

用法：
    python scripts/healthcheck.py
    python scripts/healthcheck.py --backend http://127.0.0.1:8000 --sandbox http://127.0.0.1:8081
    python scripts/healthcheck.py --json

输出后端 `/api/health/deps` 里各外部依赖（db / cache / queue / runner / ai）的
降级状态，并单独探测沙箱服务的 `security_level`。
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple

GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
RESET = "\033[0m"


def _opener() -> urllib.request.OpenerDirector:
    """构造**绕过系统代理**的 opener（本机地址不应走 http_proxy）。"""
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def fetch_json(url: str, timeout: float) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """GET 一个 JSON 端点，返回 (payload, error)。"""
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with _opener().open(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", "replace")
            return json.loads(body), None
    except urllib.error.HTTPError as exc:
        return None, f"HTTP {exc.code}"
    except urllib.error.URLError as exc:
        return None, f"连接失败（{exc.reason}）"
    except (ValueError, OSError) as exc:
        return None, f"解析失败（{exc}）"


def unwrap(payload: Any) -> Any:
    """兼容统一响应包装 {success, data}。"""
    if isinstance(payload, dict) and "data" in payload and "success" in payload:
        return payload.get("data")
    return payload


def mark(ok: bool, degraded: bool = False) -> str:
    """着色状态标记。"""
    if not ok:
        return f"{RED}FAIL{RESET}"
    if degraded:
        return f"{YELLOW}DEGRADED{RESET}"
    return f"{GREEN}OK{RESET}"


def check_backend(base_url: str, timeout: float) -> Tuple[bool, Dict[str, Any]]:
    """检查后端进程与依赖状态。"""
    url = f"{base_url.rstrip('/')}/api/health/deps"
    payload, error = fetch_json(url, timeout)
    if error:
        print(f"backend   {base_url:<28} {mark(False)}  {error}")
        return False, {"ok": False, "error": error}

    data = unwrap(payload) or {}
    print(f"backend   {base_url:<28} {mark(True)}")
    rows = [
        ("db", data.get("db", {})),
        ("cache", data.get("cache", {})),
        ("queue", data.get("queue", {})),
        ("runner", data.get("runner", {})),
        ("ai", data.get("ai", {})),
    ]
    for name, item in rows:
        item = item if isinstance(item, dict) else {"value": item}
        detail = ", ".join(f"{key}={value}" for key, value in item.items())
        degraded = bool(item.get("degraded")) or name == "runner" and item.get("mode") == "local"
        ok = item.get("ok", True) is not False
        print(f"  - {name:<7} {mark(ok, degraded):<20} {detail}")
    return True, data


def check_sandbox(base_url: str, timeout: float) -> bool:
    """检查独立沙箱服务及其安全等级。"""
    url = f"{base_url.rstrip('/')}/health"
    payload, error = fetch_json(url, timeout)
    if error:
        print(f"sandbox   {base_url:<28} {mark(False)}  {error}（后端将降级为 LocalRunner）")
        return False
    data = payload if isinstance(payload, dict) else {}
    level = str(data.get("security_level", "unknown"))
    print(
        f"sandbox   {base_url:<28} {mark(True, level != 'hardened')}  "
        f"security_level={level} platform={data.get('platform')} python={data.get('python')}"
    )
    capabilities = data.get("capabilities", {})
    if isinstance(capabilities, dict):
        print(
            "  - capabilities rlimit={rlimit} psutil={psutil} "
            "network_isolation={network_isolation} note={note}".format(
                rlimit=capabilities.get("rlimit"),
                psutil=capabilities.get("psutil"),
                network_isolation=capabilities.get("network_isolation"),
                note=capabilities.get("note", ""),
            )
        )
    return True


def main(argv: Optional[list] = None) -> int:
    """命令行入口。"""
    parser = argparse.ArgumentParser(description="PYTHON LAB 健康与降级状态自检")
    parser.add_argument("--backend", default="http://127.0.0.1:8000", help="后端地址")
    parser.add_argument("--sandbox", default="http://127.0.0.1:8081", help="沙箱地址")
    parser.add_argument("--timeout", type=float, default=3.0, help="单次请求超时（秒）")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")
    parser.add_argument("--no-sandbox", action="store_true", help="跳过沙箱探测")
    args = parser.parse_args(argv)

    print(f"{CYAN}=== PYTHON LAB healthcheck ==={RESET}")
    backend_ok, backend_data = check_backend(args.backend, args.timeout)
    sandbox_ok = False
    if not args.no_sandbox:
        sandbox_ok = check_sandbox(args.sandbox, args.timeout)

    if args.json:
        print(json.dumps({"backend_ok": backend_ok, "sandbox_ok": sandbox_ok,
                          "backend": backend_data}, ensure_ascii=False, indent=2))

    if not backend_ok:
        print(f"\n{RED}后端不可用。请先运行 scripts/dev.sh（或 dev.ps1）。{RESET}")
        return 1
    print(f"\n{GREEN}后端就绪{RESET}；沙箱{'可用' if sandbox_ok else '不可用（将走本地降级）'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
