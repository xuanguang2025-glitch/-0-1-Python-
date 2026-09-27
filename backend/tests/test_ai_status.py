"""AI 状态接口一致性测试：`/api/ai/status` 与 `/api/health/deps` 在 model/provider 上必须一致。"""

from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.endpoints import ai as ai_endpoint
from app.api.endpoints import health as health_endpoint
from app.core.config import get_settings
from app.core.deps import get_current_user
from app.services.ai.registry import build_provider, get_provider, provider_status, reset_provider


def _client() -> TestClient:
    """构造仅含 ai + health 的最小应用，并绕过鉴权（不影响 provider 语义）。"""
    app = FastAPI()
    app.include_router(ai_endpoint.router, prefix="/api")
    app.include_router(health_endpoint.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u1")
    return TestClient(app)


def test_status_matches_health_deps_model_and_provider() -> None:
    """同一进程内两个接口的 model / provider 值必须相等（降级态）。"""
    client = _client()
    ai_status = client.get("/api/ai/status").json()["data"]
    deps_ai = client.get("/api/health/deps").json()["data"]["ai"]

    assert ai_status["degraded"] is True
    assert ai_status["provider"] == "rule_based"
    assert ai_status["model"] == "rule-based"
    # 核心断言：两接口说法一致
    assert ai_status["model"] == deps_ai["model"]
    assert ai_status["provider"] == deps_ai["provider"]
    # 目标模型另开字段，不挤占 model 语义
    assert ai_status["configured_model"] == get_settings().ai_model


def test_provider_status_semantics_offline() -> None:
    """离线态：provider=rule_based / model=rule-based，目标信息在 configured_* 里。"""
    reset_provider()
    settings = get_settings()
    info = provider_status(get_provider())
    expected_model = settings.ai_model if settings.ai_enabled else "rule-based"
    expected_provider = settings.ai_provider if settings.ai_enabled else "rule_based"
    assert info["provider"] == expected_provider
    assert info["model"] == expected_model
    assert info["degraded"] is True
    assert info["configured_model"] == settings.ai_model


def test_provider_status_semantics_online() -> None:
    """在线态：model 为实际目标模型，degraded=False。"""
    settings = SimpleNamespace(
        ai_enabled=True,
        ai_provider="deepseek",
        ai_model="deepseek-chat",
        ai_base_url="https://api.deepseek.com/v1",
        ai_api_key="sk-live-abcdef",
        ai_temperature=0.3,
        ai_max_tokens=2048,
        ai_timeout_ms=30000,
        ai_offline=False,
    )
    info = provider_status(build_provider(settings))
    assert info["provider"] == "deepseek"
    assert info["model"] == "deepseek-chat"
    assert info["degraded"] is False
    assert info["configured_model"] == "deepseek-chat"
