"""QA 独立验收：C 组（密钥策略 / XFF 限流 / 只读打开真实库）。只读验证。"""

from __future__ import annotations

from pathlib import Path
import sqlite3
import sys
import tempfile

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

REAL_DB = BACKEND / "data" / "pythonlab.db"


def c1_secret_policy() -> None:
    print("=" * 78)
    print("C1. enforce_secret_policy —— 生产环境弱密钥必须拒绝启动")
    print("=" * 78)
    from app.core.config import Settings, enforce_secret_policy, is_weak_secret

    cases = [
        ("production + 默认 change-me", {"app_env": "production"}),
        ("production + 空密钥", {"app_env": "production", "jwt_secret_key": "", "secret_key": ""}),
        (
            "production + 短密钥(<32)",
            {"app_env": "production", "jwt_secret_key": "short-key-abc", "secret_key": "short-key-abc"},
        ),
        (
            "production + 占位符 your-jwt-secret",
            {
                "app_env": "production",
                "jwt_secret_key": "your-jwt-secret-here-xxxxx",
                "secret_key": "your-jwt-secret-here-xxxxx",
            },
        ),
        ("production + 正常强密钥", {"app_env": "production", "jwt_secret_key": "K" * 48, "secret_key": "S" * 48}),
        ("development + 默认 change-me", {"app_env": "development"}),
        ("testing + 默认 change-me", {"app_env": "testing"}),
    ]
    for label, kw in cases:
        s = Settings(_env_file=None, **kw)  # type: ignore[call-arg]
        try:
            replaced = enforce_secret_policy(s)
            strong = not is_weak_secret(s.jwt_secret_key)
            print(f"[启动成功] {label:34s} 自动替换={replaced or '无'} 替换后强度足够={strong}")
            if s.app_env == "production":
                print("            ^^^^^^^^^^^^^^^^^^^ 生产环境竟然没有拒绝启动！")
        except RuntimeError as exc:
            msg = str(exc)
            print(f"[拒绝启动] {label:34s} RuntimeError: {msg[:96]}...")
            if label.startswith("production"):
                assert "JWT_SECRET_KEY" in msg, "报错需给出明确指引"
        print()


def c2_xff_rate_limit() -> None:
    print("=" * 78)
    print("C2. XFF 限流绕过（回归红线：修复前轮换 XFF 15 次 0 次 429）")
    print("=" * 78)
    from fastapi import FastAPI

    from app.api.endpoints import auth as auth_endpoint
    from app.core.cache import MemoryCache, cache_container
    from app.core.config import get_settings
    from app.core.errors import register_exception_handlers
    from app.core.security import hash_password  # noqa: F401  (确保密钥模块可导入)

    def probe(label: str, trusted: str, xff_list: list[str]) -> None:
        settings = get_settings()
        old_trusted = settings.trusted_proxies
        settings.trusted_proxies = trusted
        cache_container.override(MemoryCache())
        app = FastAPI()
        register_exception_handlers(app)
        app.include_router(auth_endpoint.router, prefix="/api")
        from fastapi.testclient import TestClient

        codes: list[int] = []
        with TestClient(app) as client:
            for i in range(15):
                headers = {"X-Forwarded-For": xff_list[i % len(xff_list)]} if xff_list else {}
                r = client.post(
                    "/api/auth/login", json={"account": f"nobody{i}@x.dev", "password": "x"}, headers=headers
                )
                codes.append(r.status_code)
        settings.trusted_proxies = old_trusted
        limited = codes.count(429)
        verdict = "PASS(已限流)" if limited > 0 else "**FAIL(可绕过)**"
        print(f"[{verdict}] {label}")
        print(f"          trusted={trusted!r} 429次数={limited}/15 序列={codes}")
        print()

    # 回归红线：默认不信任代理 + 轮换伪造 XFF
    probe("默认(TRUSTED_PROXIES 空) + 轮换伪造 XFF", "", [f"198.51.100.{i}" for i in range(1, 16)])
    # 对照：固定伪造 XFF
    probe("默认 + 固定伪造 XFF", "", ["203.0.113.7"] * 15)
    # 配置可信代理后：XFF 最右侧一跳生效
    probe("TRUSTED_PROXIES=testclient + 轮换 XFF(应仍限流)", "testclient", [f"198.51.100.{i}" for i in range(1, 16)])


def c2b_trusted_proxy_semantics() -> None:
    print("=" * 78)
    print("C2b. 可信代理下 XFF 取最右侧一跳（客户端可控的最左侧被忽略）")
    print("=" * 78)
    from starlette.datastructures import Headers
    from starlette.requests import Request

    from app.api.deps import client_ip
    from app.core.config import get_settings

    def make(peer: str, xff: str) -> Request:
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": Headers({"x-forwarded-for": xff}).raw,
            "client": (peer, 1234),
        }
        return Request(scope)

    settings = get_settings()
    old = settings.trusted_proxies
    for trusted, peer, xff in [
        ("", "10.0.0.9", "1.1.1.1, 2.2.2.2"),
        ("testclient", "testclient", "1.1.1.1, 2.2.2.2"),
        ("127.0.0.1", "127.0.0.1", "1.1.1.1, 2.2.2.2, 127.0.0.1"),
    ]:
        settings.trusted_proxies = trusted
        got = client_ip(make(peer, xff))
        print(f"  trusted={trusted!r:14s} peer={peer:12s} XFF={xff!r:26s} -> client_ip={got!r}")
    settings.trusted_proxies = old
    print()


def c3_readonly_real_db() -> None:
    print("=" * 78)
    print("C3. 真实库只读打开（mode=ro）—— 写入必须失败")
    print("=" * 78)
    uri = f"file:{REAL_DB.as_posix()}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        print(f"  只读打开成功：{uri}")
        try:
            con.execute("CREATE TABLE _qa_probe(x int)")
            print("  **FAIL**：只读连接竟然可以建表！")
        except sqlite3.OperationalError as exc:
            print(f"  [PASS] 写入被拒：sqlite3.OperationalError: {exc}")
        try:
            con.execute("DELETE FROM users")
            print("  **FAIL**：只读连接竟然可以 DELETE！")
        except sqlite3.OperationalError as exc:
            print(f"  [PASS] DELETE 被拒：sqlite3.OperationalError: {exc}")
    finally:
        con.close()

    # conftest.copy_real_db 仍能工作
    sys.path.insert(0, str(BACKEND / "tests"))
    from conftest import copy_real_db

    with tempfile.TemporaryDirectory() as td:
        target = Path(td) / "seed.db"
        try:
            copy_real_db(target)
            n = sqlite3.connect(str(target)).execute("select count(*) from courses").fetchone()[0]
            print(f"  [PASS] copy_real_db 备份成功，courses={n}（内容域测试仍可用真实种子数据）")
        except Exception as exc:
            print(f"  **FAIL** copy_real_db 失败：{type(exc).__name__}: {exc}")
    print()


def main() -> None:
    c1_secret_policy()
    c2b_trusted_proxy_semantics()
    c2_xff_rate_limit()
    c3_readonly_real_db()


if __name__ == "__main__":
    main()
