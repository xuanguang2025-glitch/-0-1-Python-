#!/usr/bin/env python
"""端到端联调冒烟测试：健康检查 + 注册 → 登录 → me → refresh → 登出。

用法：
    # 1) 先启动服务
    #    uvicorn app.main:app --host 127.0.0.1 --port 8000
    # 2) 再运行本脚本
    python scripts/smoke_test.py [--base-url http://127.0.0.1:8000]

退出码：0 表示全部通过，1 表示存在失败项。
"""

from __future__ import annotations

import argparse
import sys
import uuid

import httpx


class Checker:
    """记录断言结果的小工具。"""

    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0

    def check(self, name: str, condition: bool, detail: str = "") -> None:
        """记录一项断言。"""
        mark = "PASS" if condition else "FAIL"
        suffix = f" | {detail}" if detail else ""
        print(f"[{mark}] {name}{suffix}")
        if condition:
            self.passed += 1
        else:
            self.failed += 1


def run(base_url: str) -> int:
    """执行全链路冒烟测试。"""
    checker = Checker()
    client = httpx.Client(base_url=base_url, timeout=15.0)
    suffix = uuid.uuid4().hex[:8]
    email = f"smoke_{suffix}@pythonlab.dev"
    username = f"smoke_{suffix}"
    password = "Smoke@12345"

    # 1) 依赖健康检查
    try:
        resp = client.get("/api/health/deps")
        data = resp.json()
        db_payload = (data.get("data") or data).get("db", {}) if isinstance(data, dict) else {}
        flavor = db_payload.get("flavor") if isinstance(db_payload, dict) else None
        checker.check("health/deps 可用", resp.status_code == 200, f"status={resp.status_code}")
        checker.check("db=sqlite", flavor == "sqlite", f"flavor={flavor}")
    except httpx.HTTPError as exc:
        checker.check("health/deps 可用", False, str(exc))
        return _finish(checker)

    # 2) 注册
    resp = client.post(
        "/api/auth/register",
        json={"email": email, "username": username, "password": password},
    )
    checker.check("注册成功", resp.status_code in (200, 201), f"status={resp.status_code}")
    tokens = _extract_data(resp)
    access = tokens.get("access_token", "")
    refresh = tokens.get("refresh_token", "")
    checker.check("返回 access_token", bool(access))
    checker.check("返回 refresh_token", bool(refresh))

    # 3) 登录
    resp = client.post("/api/auth/login", json={"account": email, "password": password})
    checker.check("登录成功", resp.status_code == 200, f"status={resp.status_code}")
    login_data = _extract_data(resp)
    access = login_data.get("access_token", access)
    refresh = login_data.get("refresh_token", refresh)
    checker.check("登录返回令牌", bool(access and refresh))

    headers = {"Authorization": f"Bearer {access}"}

    # 4) 当前用户
    resp = client.get("/api/auth/me", headers=headers)
    me = _extract_data(resp)
    checker.check("获取当前用户", resp.status_code == 200, f"status={resp.status_code}")
    checker.check("用户邮箱匹配", me.get("email") == email, f"email={me.get('email')}")
    checker.check("响应不含密码哈希", "hashed_password" not in resp.text)

    # 4b) 用户组路由联调（有效令牌）
    resp = client.get("/api/users/me/profile", headers=headers)
    checker.check("users 组可访问", resp.status_code == 200, f"status={resp.status_code}")

    # 5) 刷新令牌
    resp = client.post("/api/auth/refresh", json={"refresh_token": refresh})
    checker.check("刷新令牌成功", resp.status_code == 200, f"status={resp.status_code}")
    refreshed = _extract_data(resp)
    new_access = refreshed.get("access_token", access)
    new_refresh = refreshed.get("refresh_token", refresh)
    checker.check("刷新返回新令牌", bool(new_access and new_refresh))

    # 6) 登出（用最新 access + refresh）
    resp = client.post(
        "/api/auth/logout",
        json={"refresh_token": new_refresh},
        headers={"Authorization": f"Bearer {new_access}"},
    )
    checker.check("登出成功", resp.status_code == 200, f"status={resp.status_code}")

    # 7) 登出后原 access 应失效（jti 黑名单）
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {new_access}"})
    checker.check("登出后令牌失效", resp.status_code == 401, f"status={resp.status_code}")

    client.close()
    return _finish(checker)


def _extract_data(resp: httpx.Response) -> dict:
    """从统一响应壳中取出 data 字段（失败时回退整包）。"""
    try:
        payload = resp.json()
    except ValueError:
        return {}
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, dict):
            return data
        return payload
    return {}


def _finish(checker: Checker) -> int:
    """输出汇总并返回退出码。"""
    print(f"\n结果：通过 {checker.passed} 项，失败 {checker.failed} 项")
    return 0 if checker.failed == 0 else 1


def main(argv: list[str] | None = None) -> int:
    """脚本入口。"""
    parser = argparse.ArgumentParser(description="PYTHON LAB 端到端冒烟测试")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="服务基址")
    args = parser.parse_args(argv)
    return run(args.base_url)


if __name__ == "__main__":
    raise SystemExit(main())
