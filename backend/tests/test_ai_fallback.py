"""降级链路测试：无 Key → rule_based；远程 500 / 超时 → 回落且 degraded=True（全离线）。"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import httpx
import pytest

from app.services.ai.base import ChatMessage, ProviderConfig
from app.services.ai.openai_compatible import OpenAICompatibleProvider
from app.services.ai.registry import (
    ResilientProvider,
    build_provider,
    build_provider_config,
    get_provider,
    provider_status,
    reset_provider,
    resolve_api_key,
)
from app.services.ai.rule_based import RuleBasedProvider


def _settings(**over) -> SimpleNamespace:
    base = dict(
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
    base.update(over)
    return SimpleNamespace(**base)


# ---------------------------------------------------------------------------
# 选型
# ---------------------------------------------------------------------------


def test_offline_when_disabled() -> None:
    """ai_enabled=False → 纯 RuleBasedProvider。"""
    provider = build_provider(_settings(ai_enabled=False))
    assert isinstance(provider, RuleBasedProvider)
    assert provider.available is True
    status = provider_status(provider)
    assert status["degraded"] is True
    assert status["provider"] == "rule_based"
    assert status["model"] == "rule-based"
    assert status["configured_model"] == "deepseek-chat"


def test_remote_when_enabled() -> None:
    """ai_enabled=True → ResilientProvider（主 Provider 为 OpenAI 兼容）。"""
    provider = build_provider(_settings())
    assert isinstance(provider, ResilientProvider)
    assert provider.name == "deepseek"
    assert provider.available is True
    assert provider_status(provider)["degraded"] is False


def test_real_settings_is_offline() -> None:
    """测试环境 AI_OFFLINE=true → 全局单例为规则引擎。"""
    reset_provider()
    provider = get_provider()
    assert isinstance(provider, RuleBasedProvider)


def test_resolve_api_key_vendor_fallback() -> None:
    """AI_API_KEY 为空时读取厂商专用环境变量。"""
    settings = _settings(ai_api_key="", ai_provider="openai")
    import os

    os.environ["OPENAI_API_KEY"] = "sk-vendor-xyz"
    try:
        assert resolve_api_key(settings, "openai") == "sk-vendor-xyz"
    finally:
        os.environ.pop("OPENAI_API_KEY", None)


def test_provider_config_redacted() -> None:
    """配置摘要不得包含明文密钥。"""
    cfg = build_provider_config(_settings())
    redacted = cfg.redacted()
    assert "sk-live-abcdef" not in str(redacted)
    assert redacted["has_key"] is True


# ---------------------------------------------------------------------------
# 回落
# ---------------------------------------------------------------------------


def _primary_with(handler: httpx.MockTransport) -> OpenAICompatibleProvider:
    cfg = ProviderConfig(
        provider="deepseek",
        model="deepseek-chat",
        base_url="https://api.deepseek.com/v1",
        api_key="sk-live-abcdef",
        max_retries=0,
    )
    return OpenAICompatibleProvider(cfg, client=httpx.AsyncClient(transport=handler))


def test_fallback_on_http_500() -> None:
    """远程 500 → 回落规则引擎且 degraded=True。"""
    transport = httpx.MockTransport(lambda request: httpx.Response(500, json={"error": "boom"}))
    resilient = ResilientProvider(_primary_with(transport), RuleBasedProvider())

    response = asyncio.run(
        resilient.chat([ChatMessage(role="user", content="这段代码为什么报错")], task="qa")
    )
    assert response.degraded is True
    assert response.provider == "rule_based"
    assert response.content.strip() != ""
    assert resilient.last_degraded is True


def test_fallback_on_timeout() -> None:
    """远程超时 → 回落规则引擎且 degraded=True。"""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out")

    transport = httpx.MockTransport(handler)
    resilient = ResilientProvider(_primary_with(transport), RuleBasedProvider())

    response = asyncio.run(
        resilient.chat([ChatMessage(role="user", content="给我一个提示")], task="tutor", level="hint")
    )
    assert response.degraded is True
    assert response.provider == "rule_based"


def test_no_fallback_on_success() -> None:
    """远程成功时不降级。"""
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "model": "deepseek-chat",
                "choices": [{"message": {"content": "远程答案"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            },
        )
    )
    resilient = ResilientProvider(_primary_with(transport), RuleBasedProvider())
    response = asyncio.run(resilient.chat([ChatMessage(role="user", content="hi")], task="qa"))
    assert response.degraded is False
    assert response.content == "远程答案"
    assert resilient.last_degraded is False


@pytest.mark.parametrize("status_code", [401, 429, 500, 503])
def test_fallback_on_all_http_error_status(status_code: int) -> None:
    """401 / 429 / 5xx 全部触发回落且 degraded=True（接口不 5xx）。"""
    transport = httpx.MockTransport(lambda request: httpx.Response(status_code, json={"error": "x"}))
    resilient = ResilientProvider(_primary_with(transport), RuleBasedProvider())
    response = asyncio.run(resilient.chat([ChatMessage(role="user", content="hi")], task="qa"))
    assert response.degraded is True
    assert response.provider == "rule_based"


def test_fallback_on_malformed_json() -> None:
    """200 但响应不是合法 JSON → 回落。"""
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, content=b"not-a-json", headers={"content-type": "application/json"}
        )
    )
    resilient = ResilientProvider(_primary_with(transport), RuleBasedProvider())
    response = asyncio.run(resilient.chat([ChatMessage(role="user", content="hi")], task="qa"))
    assert response.degraded is True
    assert response.provider == "rule_based"


def test_fallback_on_missing_choices() -> None:
    """200 且 JSON 合法但缺少 choices → AIProviderBadResponse → 回落。"""
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"model": "deepseek-chat"}))
    resilient = ResilientProvider(_primary_with(transport), RuleBasedProvider())
    response = asyncio.run(resilient.chat([ChatMessage(role="user", content="hi")], task="qa"))
    assert response.degraded is True
    assert response.provider == "rule_based"
