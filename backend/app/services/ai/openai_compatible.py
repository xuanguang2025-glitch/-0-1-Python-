"""OpenAI 兼容 Provider（覆盖 OpenAI / DeepSeek / 通义 / 智谱 / Moonshot / 自建中转）。

统一走 `POST {base_url}/chat/completions`，凭 `Authorization: Bearer <key>` 鉴权，
因此任意 OpenAI 兼容端点只需 `base_url + model + key` 三项即可接入
（见 `docs/AI.md` §3）。

安全：密钥仅在内存中构造请求头，绝不写入日志、异常信息或响应体。
所有远程调用都有超时与重试上限，最终失败抛 `AIProviderError` 由 registry 回落。
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx

from app.services.ai.base import (
    AIProvider,
    AIProviderBadResponse,
    AIProviderTimeout,
    AIProviderUnavailable,
    AIResponse,
    ChatMessage,
    ProviderConfig,
    TokenUsage,
)


class OpenAICompatibleProvider(AIProvider):
    """基于 httpx 的 OpenAI 兼容 Provider（异步）。"""

    supports_streaming = True

    def __init__(self, cfg: ProviderConfig, *, client: httpx.AsyncClient | None = None) -> None:
        """初始化。

        Args:
            cfg: Provider 配置（必须含 base_url 与 api_key）。
            client: 可选的预置异步客户端（测试注入 `MockTransport` 用）。
        """
        super().__init__(cfg, client=client)
        self.name = cfg.provider or "openai"

    # ------------------------------------------------------------------
    # 属性
    # ------------------------------------------------------------------
    @property
    def available(self) -> bool:
        """是否具备可用密钥。"""
        return self.cfg.has_key

    def _base(self) -> str:
        """规范化 base_url（去尾斜杠）。"""
        return (self.cfg.base_url or "").rstrip("/")

    def _headers(self) -> dict[str, str]:
        """构造请求头（含密钥，禁止打印）。"""
        return {
            "Authorization": f"Bearer {self.cfg.api_key}",
            "Content-Type": "application/json",
        }

    def _chat_url(self) -> str:
        """chat/completions 端点。"""
        return f"{self._base()}/chat/completions"

    # ------------------------------------------------------------------
    # 核心方法
    # ------------------------------------------------------------------
    async def chat(self, messages: list[ChatMessage], **opts: Any) -> AIResponse:
        """非流式对话补全。"""
        payload = self._build_payload(messages, opts, stream=False)
        started = self.now_ms()
        data = await self._request_json(payload)
        return self._parse_response(data, latency_ms=self.now_ms() - started)

    async def chat_stream(self, messages: list[ChatMessage], **opts: Any) -> AsyncIterator[str]:
        """流式对话补全（SSE，逐段产出文本）。"""
        payload = self._build_payload(messages, opts, stream=True)
        own_client = self._client is None
        client = self._client or self._new_client()
        try:
            async with client.stream("POST", self._chat_url(), json=payload, headers=self._headers()) as response:
                if response.status_code >= 400:
                    await response.aread()
                    raise AIProviderUnavailable(f"模型服务返回 HTTP {response.status_code}")
                async for line in response.aiter_lines():
                    chunk = self._parse_sse_line(line)
                    if chunk:
                        yield chunk
        except httpx.TimeoutException as exc:
            raise AIProviderTimeout("模型服务响应超时") from exc
        except httpx.HTTPError as exc:
            raise AIProviderUnavailable(f"模型服务网络错误：{type(exc).__name__}") from exc
        finally:
            if own_client:
                await client.aclose()

    async def health(self) -> bool:
        """连通性探测（GET /models）。"""
        if not self.available:
            return False
        client = self._client or self._new_client()
        own_client = self._client is None
        try:
            response = await client.get(f"{self._base()}/models", headers=self._headers())
            return response.status_code < 400
        except httpx.HTTPError:
            return False
        finally:
            if own_client:
                await client.aclose()

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------
    def _new_client(self) -> httpx.AsyncClient:
        """创建带超时的异步客户端。"""
        transport = self.cfg.extra.get("transport")
        return httpx.AsyncClient(timeout=self.cfg.timeout_seconds, transport=transport)

    def _build_payload(self, messages: list[ChatMessage], opts: dict[str, Any], *, stream: bool) -> dict[str, Any]:
        """组装请求体。"""
        payload: dict[str, Any] = {
            "model": self.cfg.model,
            "messages": [message.as_openai() for message in messages],
            "temperature": self._resolve_temperature(opts),
            "max_tokens": self._resolve_max_tokens(opts),
            "stream": stream,
        }
        if opts.get("json_mode"):
            payload["response_format"] = {"type": "json_object"}
        stop = opts.get("stop")
        if stop:
            payload["stop"] = list(stop)
        return payload

    async def _request_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        """发送请求并解析 JSON（含超时与重试上限）。"""
        client = self._client or self._new_client()
        own_client = self._client is None
        attempts = max(1, int(self.cfg.max_retries) + 1)
        last_error: Exception | None = None
        try:
            for _ in range(attempts):
                try:
                    response = await client.post(self._chat_url(), json=payload, headers=self._headers())
                    if response.status_code >= 400:
                        raise AIProviderUnavailable(f"模型服务返回 HTTP {response.status_code}")
                    return response.json()
                except httpx.TimeoutException as exc:
                    last_error = AIProviderTimeout("模型服务响应超时")
                    last_error.__cause__ = exc
                except httpx.HTTPError as exc:
                    last_error = AIProviderUnavailable(f"模型服务网络错误：{type(exc).__name__}")
                    last_error.__cause__ = exc
        finally:
            if own_client:
                await client.aclose()
        raise last_error or AIProviderUnavailable("模型服务调用失败")

    def _parse_response(self, data: dict[str, Any], *, latency_ms: int) -> AIResponse:
        """解析 OpenAI 兼容响应。"""
        choices = data.get("choices") or []
        if not choices:
            raise AIProviderBadResponse("模型响应缺少 choices 字段")
        message = choices[0].get("message") or {}
        content = message.get("content") or ""
        usage = data.get("usage") or {}
        return AIResponse(
            content=content,
            model=str(data.get("model") or self.cfg.model),
            provider=self.name,
            usage=TokenUsage(
                prompt_tokens=int(usage.get("prompt_tokens") or 0),
                completion_tokens=int(usage.get("completion_tokens") or 0),
            ),
            finish_reason=str(choices[0].get("finish_reason") or "stop"),
            degraded=False,
            latency_ms=int(latency_ms),
        )

    @staticmethod
    def _parse_sse_line(line: str) -> str:
        """解析单行 SSE，返回文本增量（无内容返回空串）。"""
        if not line or not line.startswith("data:"):
            return ""
        payload = line[len("data:") :].strip()
        if not payload or payload == "[DONE]":
            return ""
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError:
            return ""
        choices = obj.get("choices") or []
        if not choices:
            return ""
        delta = choices[0].get("delta") or {}
        return delta.get("content") or ""


__all__ = ["OpenAICompatibleProvider"]
