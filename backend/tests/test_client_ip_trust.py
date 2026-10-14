"""限流取 IP 的信任边界回归测试（P2：伪造 X-Forwarded-For 绕过限流）。

`X-Forwarded-For` 完全由客户端可控。旧实现无条件取其**最左侧**值，于是攻击者
轮换该头即可让每次请求都落到新 IP，限流形同虚设。QA 实测：

    固定伪造 XFF 登录 15 次 → 5 次 429
    轮换伪造 XFF 登录 15 次 → 0 次 429   ← 限流被完全绕过

修复后语义（`app/api/deps.py::client_ip`）：

- `TRUSTED_PROXIES` 为空（默认）→ 不信任任何代理，一律用 `request.client.host`；
- 对端命中可信代理 → 才读 XFF，且取**最右侧**一跳（最左侧是客户端可写的）；
  多级反代时跳过右侧仍属可信的地址，取第一个非可信地址。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.api.deps import client_ip
from app.api.endpoints import auth as auth_ep
from app.core import config as app_config

AUTH_ROUTERS = (auth_ep.router,)
LOGIN_BODY = {"account": "tester@pythonlab.dev", "password": "definitely-wrong-password"}


@pytest.fixture()
def ip_app() -> TestClient:
    """暴露 `client_ip()` 的最小应用（不碰数据库）。"""
    app = FastAPI()

    @app.get("/ip")
    def _ip(request: Request) -> dict[str, str | None]:
        return {"ip": client_ip(request)}

    return TestClient(app)


@pytest.fixture()
def trusted_proxy(monkeypatch: pytest.MonkeyPatch):
    """注入 `TRUSTED_PROXIES` 并在结束后恢复配置单例。"""

    def _apply(value: str) -> None:
        monkeypatch.setenv("TRUSTED_PROXIES", value)
        app_config.get_settings.cache_clear()

    yield _apply
    app_config.get_settings.cache_clear()


def test_forged_xff_ignored_by_default(ip_app: TestClient, trusted_proxy) -> None:
    """默认（无可信代理）时 XFF 完全不可信 —— 伪造值不得影响限流键。"""
    trusted_proxy("")
    seen = {
        ip_app.get("/ip", headers={"X-Forwarded-For": ip}).json()["ip"]
        for ip in ("1.1.1.1", "2.2.2.2", "3.3.3.3")
    }
    assert len(seen) == 1, f"伪造 XFF 影响了客户端 IP：{seen}"


def test_xff_ignored_when_peer_is_not_trusted(ip_app: TestClient, trusted_proxy) -> None:
    """即使配置了可信代理，**非**可信对端发来的 XFF 也不能采信。"""
    trusted_proxy("10.0.0.1")  # TestClient 的对端是 testclient，不在名单内
    data = ip_app.get("/ip", headers={"X-Forwarded-For": "9.9.9.9"}).json()
    assert data["ip"] != "9.9.9.9"


def test_xff_rightmost_hop_used_when_peer_trusted(ip_app: TestClient, trusted_proxy) -> None:
    """可信代理场景下取**最右侧**一跳（客户端伪造的左侧值被忽略）。"""
    trusted_proxy("testclient")
    data = ip_app.get("/ip", headers={"X-Forwarded-For": "6.6.6.6, 9.9.9.9"}).json()
    assert data["ip"] == "9.9.9.9"


def test_xff_skips_trusted_hops_in_multi_proxy_chain(ip_app: TestClient, trusted_proxy) -> None:
    """多级反代：跳过右侧仍属可信代理的地址，取第一个非可信地址。"""
    trusted_proxy("testclient,10.0.0.5")
    data = ip_app.get("/ip", headers={"X-Forwarded-For": "6.6.6.6, 10.0.0.5"}).json()
    assert data["ip"] == "6.6.6.6"


def test_xff_cidr_support(ip_app: TestClient, trusted_proxy) -> None:
    """可信代理支持 CIDR 网段写法。"""
    trusted_proxy("10.0.0.0/8")
    assert ip_app.get("/ip", headers={"X-Forwarded-For": "1.2.3.4"}).json()["ip"] == "testclient"


def test_login_rate_limit_not_bypassed_by_rotating_xff(client_factory, db) -> None:
    """QA 复现：轮换 XFF 登录 15 次，限流必须照样触发（修复前是 0 次 429）。"""
    client = client_factory(AUTH_ROUTERS)
    codes = [
        client.post(
            "/api/auth/login", json=LOGIN_BODY, headers={"X-Forwarded-For": f"198.51.100.{i}"}
        ).status_code
        for i in range(1, 16)
    ]
    assert codes.count(429) >= 1, f"限流仍可被轮换 XFF 绕过: {codes}"


def test_login_rate_limit_still_applies_with_fixed_xff(client_factory, db) -> None:
    """固定伪造 XFF 仍然被限流（原行为不变）。"""
    client = client_factory(AUTH_ROUTERS)
    headers = {"X-Forwarded-For": "203.0.113.7"}
    codes = [
        client.post("/api/auth/login", json=LOGIN_BODY, headers=headers).status_code
        for _ in range(15)
    ]
    assert codes.count(429) >= 1, codes


def test_env_example_mentions_trusted_proxies() -> None:
    """.env.example 必须暴露 TRUSTED_PROXIES，否则部署时无从配置。"""
    doc = Path(__file__).resolve().parents[2] / ".env.example"
    text = doc.read_text(encoding="utf-8")
    assert "TRUSTED_PROXIES" in text