"""Anthropic Claude Provider（原生 Messages API）。

Anthropic 原生协议为 `POST {base_url}/messages`（**非** OpenAI 格式），字段映射：
- `system` 消息提取为顶层 `system` 字符串；
- `max_tokens` 为必填；
- 响应正文在 `content[0].text`，用量为 `usage.input_tokens/output_tokens`
  （见 `docs/AI.md` §3.6 表 B）。

密钥经 `x-api-key` 头发送，绝不落日志。
"""

from __future__ import annotations

from typing import Any

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

_ANTHROPIC_VERSION: str = "2023-06-01"


class ClaudeProvider(AIProvider):
    """Anthropic Messages API 适配器。"""

    supports_streaming = False

    def __init__(self, cfg: ProviderConfig, *, client: httpx.AsyncClient | None = None) -> None:
        """初始化。

        Args:
            cfg: Provider 配置（base_url 建议为 `https://api.anthropic.com/v1`）。
            client: 可选预置异步客户端（测试注入）。
        """
        super().__init__(cfg, client=client)
        self.name = "anthropic"

    @property
    def available(self) -> bool:
        """是否具备可用密钥。"""
        return self.cfg.has_key

    def _base(self) -> str:
        """规范化 base_url。"""
        return (self.cfg.base_url or "https://api.anthropic.com/v1").rstrip("/")

    def _headers(self) -> dict[str, str]:
        """构造请求头（含密钥，禁止打印）。"""
        return {
            "x-api-key": self.cfg.api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }

    async def chat(self, messages: list[ChatMessage], **opts: Any) -> AIResponse:
        """非流式对话补全。"""
        system_text, chat_messages = self._split_messages(messages)
        payload: dict[str, Any] = {
            "model": self.cfg.model,
            "messages": chat_messages,
            "max_tokens": self._resolve_max_tokens(opts),
            "temperature": self._resolve_temperature(opts),
        }
        if system_text:
            payload["system"] = system_text

        started = self.now_ms()
        data = await self._request_json(payload)
        return self._parse_response(data, latency_ms=self.now_ms() - started)

    async def health(self) -> bool:
        """连通性探测：发送一个极小请求验证鉴权。"""
        if not self.available:
            return False
        payload = {
            "model": self.cfg.model,
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "ping"}],
        }
        try:
            await self._request_json(payload)
            return True
        except AIProviderUnavailable:
            return False

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------
    @staticmethod
    def _split_messages(messages: list[ChatMessage]) -> tuple[str, list[dict[str, str]]]:
        """把 system 消息抽取为顶层字符串，其余保持 user/assistant。"""
        system_parts: list[str] = []
        chat: list[dict[str, str]] = []
        for message in messages:
            if message.role == "system":
                system_parts.append(message.content)
            else:
                chat.append({"role": message.role, "content": message.content})
        return "\n\n".join(system_parts), chat

    def _new_client(self) -> httpx.AsyncClient:
        """创建带超时的异步客户端。"""
        return httpx.AsyncClient(timeout=self.cfg.timeout_seconds, transport=self.cfg.extra.get("transport"))

    async def _request_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        """发送请求并解析 JSON（含超时与重试上限）。"""
        client = self._client or self._new_client()
        own_client = self._client is None
        attempts = max(1, int(self.cfg.max_retries) + 1)
        last_error: Exception | None = None
        try:
            for _ in range(attempts):
                try:
                    response = await client.post(f"{self._base()}/messages", json=payload, headers=self._headers())
                    if response.status_code >= 400:
                        raise AIProviderUnavailable(f"Claude 服务返回 HTTP {response.status_code}")
                    return response.json()
                except httpx.TimeoutException as exc:
                    last_error = AIProviderTimeout("Claude 服务响应超时")
                    last_error.__cause__ = exc
                except httpx.HTTPError as exc:
                    last_error = AIProviderUnavailable(f"Claude 服务网络错误：{type(exc).__name__}")
                    last_error.__cause__ = exc
        finally:
            if own_client:
                await client.aclose()
        raise last_error or AIProviderUnavailable("Claude 服务调用失败")

    def _parse_response(self, data: dict[str, Any], *, latency_ms: int) -> AIResponse:
        """解析 Anthropic 响应。"""
        blocks = data.get("content") or []
        text = "".join(block.get("text", "") for block in blocks if block.get("type") == "text")
        if not text and not blocks:
            raise AIProviderBadResponse("Claude 响应缺少 content 字段")
        usage = data.get("usage") or {}
        return AIResponse(
            content=text,
            model=str(data.get("model") or self.cfg.model),
            provider=self.name,
            usage=TokenUsage(
                prompt_tokens=int(usage.get("input_tokens") or 0),
                completion_tokens=int(usage.get("output_tokens") or 0),
            ),
            finish_reason=str(data.get("stop_reason") or "stop"),
            degraded=False,
            latency_ms=int(latency_ms),
        )


__all__ = ["ClaudeProvider"]
