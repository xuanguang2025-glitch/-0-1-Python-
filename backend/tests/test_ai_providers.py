"""Provider 层测试：用 httpx.MockTransport 打桩，验证三类请求体与响应解析（全离线）。"""

from __future__ import annotations

import asyncio
import json

import httpx

from app.services.ai.base import ChatMessage, ProviderConfig
from app.services.ai.claude import ClaudeProvider
from app.services.ai.gemini import GeminiProvider
from app.services.ai.openai_compatible import OpenAICompatibleProvider


def _cfg(provider: str = "deepseek", **over) -> ProviderConfig:
    base = dict(
        provider=provider,
        model="deepseek-chat",
        base_url="https://api.deepseek.com/v1",
        api_key="sk-test-123456",
        temperature=0.2,
        max_tokens=256,
        timeout_ms=5000,
        max_retries=0,
    )
    base.update(over)
    return ProviderConfig(**base)


# ---------------------------------------------------------------------------
# OpenAI 兼容
# ---------------------------------------------------------------------------


def test_openai_compatible_request_and_parse() -> None:
    """请求体/鉴权头正确，响应解析为统一结构。"""
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "model": "deepseek-chat",
                "choices": [{"message": {"role": "assistant", "content": "你好"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        )

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = OpenAICompatibleProvider(_cfg(), client=client)
            return await provider.chat([ChatMessage(role="user", content="hi")], json_mode=True)

    response = asyncio.run(run())

    assert str(captured["url"]).endswith("/v1/chat/completions")
    assert captured["auth"] == "Bearer sk-test-123456"
    body = captured["body"]
    assert body["model"] == "deepseek-chat"
    assert body["stream"] is False
    assert body["response_format"] == {"type": "json_object"}
    assert body["messages"] == [{"role": "user", "content": "hi"}]

    assert response.content == "你好"
    assert response.provider == "deepseek"
    assert response.usage.prompt_tokens == 10
    assert response.usage.completion_tokens == 5
    assert response.usage.total_tokens == 15
    assert response.degraded is False
    assert response.finish_reason == "stop"


def test_openai_compatible_stream() -> None:
    """SSE 流式逐块解析。"""
    sse = (
        'data: {"choices":[{"delta":{"content":"Hello"}}]}\n\n'
        'data: {"choices":[{"delta":{"content":" world"}}]}\n\n'
        "data: [DONE]\n\n"
    ).encode("utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=sse, headers={"content-type": "text/event-stream"})

    async def run():
        chunks: list[str] = []
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = OpenAICompatibleProvider(_cfg(), client=client)
            async for chunk in provider.chat_stream([ChatMessage(role="user", content="hi")]):
                chunks.append(chunk)
        return "".join(chunks)

    assert asyncio.run(run()) == "Hello world"


def test_openai_compatible_http_error_raises() -> None:
    """HTTP 4xx/5xx 抛 AIProviderUnavailable（由上层回落）。"""
    from app.services.ai.base import AIProviderUnavailable

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = OpenAICompatibleProvider(_cfg(), client=client)
            await provider.chat([ChatMessage(role="user", content="hi")])

    try:
        asyncio.run(run())
    except AIProviderUnavailable as exc:
        assert "500" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("应抛出 AIProviderUnavailable")


# ---------------------------------------------------------------------------
# Claude（原生 Messages API）
# ---------------------------------------------------------------------------


def test_claude_request_and_parse() -> None:
    """system 抽取为顶层字段、max_tokens 必填、响应解析正确。"""
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["key"] = request.headers.get("x-api-key")
        captured["version"] = request.headers.get("anthropic-version")
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "model": "claude-3-5-sonnet-latest",
                "content": [{"type": "text", "text": "答案在此"}],
                "usage": {"input_tokens": 12, "output_tokens": 7},
                "stop_reason": "end_turn",
            },
        )

    cfg = _cfg("anthropic", base_url="https://api.anthropic.com/v1", model="claude-3-5-sonnet-latest")

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = ClaudeProvider(cfg, client=client)
            return await provider.chat(
                [ChatMessage(role="system", content="你是导师"), ChatMessage(role="user", content="hi")]
            )

    response = asyncio.run(run())

    assert str(captured["url"]).endswith("/v1/messages")
    assert captured["key"] == "sk-test-123456"
    assert captured["version"] == "2023-06-01"
    body = captured["body"]
    assert body["system"] == "你是导师"
    assert body["max_tokens"] == 256
    assert body["messages"] == [{"role": "user", "content": "hi"}]

    assert response.content == "答案在此"
    assert response.provider == "anthropic"
    assert response.usage.prompt_tokens == 12
    assert response.usage.completion_tokens == 7


# ---------------------------------------------------------------------------
# Gemini（generateContent）
# ---------------------------------------------------------------------------


def test_gemini_request_and_parse() -> None:
    """角色映射 + systemInstruction + 响应解析。"""
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["key"] = request.headers.get("x-goog-api-key")
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": "Gemini 回答"}]}, "finishReason": "STOP"}
                ],
                "usageMetadata": {"promptTokenCount": 9, "candidatesTokenCount": 4},
            },
        )

    cfg = _cfg(
        "gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        model="gemini-1.5-flash",
    )

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = GeminiProvider(cfg, client=client)
            return await provider.chat(
                [ChatMessage(role="system", content="系统"), ChatMessage(role="user", content="hi")]
            )

    response = asyncio.run(run())

    assert str(captured["url"]).endswith("/models/gemini-1.5-flash:generateContent")
    assert captured["key"] == "sk-test-123456"
    body = captured["body"]
    assert body["contents"] == [{"role": "user", "parts": [{"text": "hi"}]}]
    assert body["systemInstruction"] == {"parts": [{"text": "系统"}]}

    assert response.content == "Gemini 回答"
    assert response.provider == "gemini"
    assert response.usage.prompt_tokens == 9
    assert response.usage.completion_tokens == 4
