"""Google Gemini Provider（`generateContent` 原生协议）。

端点：`POST {base_url}/models/{model}:generateContent`，
鉴权：`x-goog-api-key` 头（或 `?key=` 查询参数）。

角色映射：`user → user`、`assistant → model`；`system` 消息映射到顶层
`systemInstruction`。响应正文在 `candidates[0].content.parts[*].text`，
用量为 `usageMetadata.promptTokenCount/candidatesTokenCount`。
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

_DEFAULT_BASE: str = "https://generativelanguage.googleapis.com/v1beta"


class GeminiProvider(AIProvider):
    """Google Gemini 适配器。"""

    supports_streaming = False

    def __init__(self, cfg: ProviderConfig, *, client: httpx.AsyncClient | None = None) -> None:
        """初始化。

        Args:
            cfg: Provider 配置（base_url 建议为 `https://generativelanguage.googleapis.com/v1beta`）。
            client: 可选预置异步客户端（测试注入）。
        """
        super().__init__(cfg, client=client)
        self.name = "gemini"

    @property
    def available(self) -> bool:
        """是否具备可用密钥。"""
        return self.cfg.has_key

    def _base(self) -> str:
        """规范化 base_url。"""
        return (self.cfg.base_url or _DEFAULT_BASE).rstrip("/")

    def _headers(self) -> dict[str, str]:
        """构造请求头（含密钥，禁止打印）。"""
        return {"x-goog-api-key": self.cfg.api_key, "Content-Type": "application/json"}

    async def chat(self, messages: list[ChatMessage], **opts: Any) -> AIResponse:
        """非流式内容生成。"""
        payload = self._build_payload(messages, opts)
        started = self.now_ms()
        data = await self._request_json(payload)
        return self._parse_response(data, latency_ms=self.now_ms() - started)

    async def health(self) -> bool:
        """连通性探测。"""
        if not self.available:
            return False
        payload = {"contents": [{"role": "user", "parts": [{"text": "ping"}]}]}
        try:
            await self._request_json(payload)
            return True
        except AIProviderUnavailable:
            return False

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------
    def _build_payload(self, messages: list[ChatMessage], opts: dict[str, Any]) -> dict[str, Any]:
        """把统一消息映射为 Gemini 请求体。"""
        system_parts: list[str] = []
        contents: list[dict[str, Any]] = []
        for message in messages:
            if message.role == "system":
                system_parts.append(message.content)
                continue
            role = "model" if message.role == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": message.content}]})

        generation_config: dict[str, Any] = {
            "temperature": self._resolve_temperature(opts),
            "maxOutputTokens": self._resolve_max_tokens(opts),
        }
        if opts.get("json_mode"):
            generation_config["responseMimeType"] = "application/json"

        payload: dict[str, Any] = {"contents": contents, "generationConfig": generation_config}
        if system_parts:
            payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}
        return payload

    def _request_url(self) -> str:
        """generateContent 端点。"""
        return f"{self._base()}/models/{self.cfg.model}:generateContent"

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
                    response = await client.post(self._request_url(), json=payload, headers=self._headers())
                    if response.status_code >= 400:
                        raise AIProviderUnavailable(f"Gemini 服务返回 HTTP {response.status_code}")
                    return response.json()
                except httpx.TimeoutException as exc:
                    last_error = AIProviderTimeout("Gemini 服务响应超时")
                    last_error.__cause__ = exc
                except httpx.HTTPError as exc:
                    last_error = AIProviderUnavailable(f"Gemini 服务网络错误：{type(exc).__name__}")
                    last_error.__cause__ = exc
        finally:
            if own_client:
                await client.aclose()
        raise last_error or AIProviderUnavailable("Gemini 服务调用失败")

    def _parse_response(self, data: dict[str, Any], *, latency_ms: int) -> AIResponse:
        """解析 Gemini 响应。"""
        candidates = data.get("candidates") or []
        if not candidates:
            raise AIProviderBadResponse("Gemini 响应缺少 candidates 字段")
        parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "".join(part.get("text", "") for part in parts)
        usage = data.get("usageMetadata") or {}
        return AIResponse(
            content=text,
            model=self.cfg.model,
            provider=self.name,
            usage=TokenUsage(
                prompt_tokens=int(usage.get("promptTokenCount") or 0),
                completion_tokens=int(usage.get("candidatesTokenCount") or 0),
            ),
            finish_reason=str(candidates[0].get("finishReason") or "stop"),
            degraded=False,
            latency_ms=int(latency_ms),
        )


__all__ = ["GeminiProvider"]
