"""AI Provider 抽象层（`docs/AI.md` §1、`docs/ARCHITECTURE.md` §6）。

本模块定义整个 AI 子系统的稳定契约：

- `ProviderConfig`：Provider 运行期配置（密钥仅存内存，**绝不落库 / 打日志 / 回前端**）；
- `ChatMessage`：角色 + 内容；
- `TokenUsage` / `AIResponse`：统一响应结构，含 `degraded` 降级标记；
- `AIProvider`：抽象基类，`chat()`（异步）/ `chat_stream()`（异步生成器）+
  `name` / `supports_streaming` / `available` 属性 + `count_tokens()` / `health()`。

设计原则：任何远程实现失败都必须抛出 `AIProviderError` 子类，由 `registry` 统一回落
到 `RuleBasedProvider`，保证接口永不 5xx。
"""

from __future__ import annotations

import abc
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

# ---------------------------------------------------------------------------
# 错误体系
# ---------------------------------------------------------------------------


class AIProviderError(Exception):
    """AI Provider 调用异常的基类（携带机器可读错误码）。"""

    code: str = "AI_PROVIDER_UNAVAILABLE"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code

    def __str__(self) -> str:  # pragma: no cover - 简单透传
        return self.message


class AIProviderUnavailable(AIProviderError):
    """网络不可达 / 5xx / 认证失败等无法完成调用的情形。"""

    code = "AI_PROVIDER_UNAVAILABLE"


class AIProviderTimeout(AIProviderError):
    """远程调用超时。"""

    code = "AI_PROVIDER_UNAVAILABLE"


class AIProviderBadResponse(AIProviderError):
    """远程返回无法解析（结构不符 / JSON 解析失败）。"""

    code = "AI_BAD_RESPONSE"


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class TokenUsage:
    """Token 用量。"""

    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        """入参 + 出参 token 总数。"""
        return int(self.prompt_tokens) + int(self.completion_tokens)

    def as_dict(self) -> dict[str, int]:
        """序列化为字典（供 meta_json 使用）。"""
        return {
            "prompt_tokens": int(self.prompt_tokens),
            "completion_tokens": int(self.completion_tokens),
            "total_tokens": self.total_tokens,
        }


@dataclass(slots=True)
class ChatMessage:
    """一条对话消息（与 OpenAI 角色约定一致）。"""

    role: str
    content: str

    def as_openai(self) -> dict[str, str]:
        """转换为 OpenAI 兼容消息体。"""
        return {"role": self.role, "content": self.content}


@dataclass(slots=True)
class ProviderConfig:
    """Provider 运行期配置。

    Attributes:
        provider: 服务商标识（openai/deepseek/qwen/zhipu/anthropic/gemini/custom）。
        model: 模型名。
        base_url: OpenAI 兼容或厂商专用端点。
        api_key: 运行时密钥（**只在内存中**，禁止写入数据库或日志）。
        temperature: 采样温度。
        max_tokens: 单次生成上限。
        timeout_ms: 超时毫秒数。
        max_retries: 失败重试上限（不含首次）。
        extra: 附加参数（如注入的 httpx transport，仅测试用）。
    """

    provider: str = "deepseek"
    model: str = "deepseek-chat"
    base_url: str | None = None
    api_key: str = ""
    temperature: float = 0.3
    max_tokens: int = 2048
    timeout_ms: int = 30_000
    max_retries: int = 1
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def has_key(self) -> bool:
        """是否配置了可用密钥（占位值视为未配置）。"""
        key = (self.api_key or "").strip()
        return bool(key) and not key.startswith("sk-your-")

    @property
    def timeout_seconds(self) -> float:
        """超时秒数（httpx 使用）。"""
        return max(1.0, float(self.timeout_ms) / 1000.0)

    def redacted(self) -> dict[str, Any]:
        """返回可安全打日志的配置摘要（**不含密钥**）。"""
        return {
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "has_key": self.has_key,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout_ms": self.timeout_ms,
        }


@dataclass(slots=True)
class AIResponse:
    """Provider 统一响应结构。"""

    content: str
    model: str = ""
    provider: str = ""
    usage: TokenUsage = field(default_factory=TokenUsage)
    finish_reason: str = "stop"
    degraded: bool = False
    latency_ms: int = 0
    raw: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        """序列化为字典（供测试与日志使用，不含原始响应体）。"""
        return {
            "content": self.content,
            "model": self.model,
            "provider": self.provider,
            "usage": self.usage.as_dict(),
            "finish_reason": self.finish_reason,
            "degraded": self.degraded,
            "latency_ms": self.latency_ms,
        }


# ---------------------------------------------------------------------------
# 抽象 Provider
# ---------------------------------------------------------------------------

_CJK_RANGE = ("\u4e00", "\u9fff")


def estimate_tokens(text: str) -> int:
    """粗略估算 token 数：CJK 按字计，ASCII 按 ~4 字符 1 token 计。"""
    raw = text or ""
    cjk = sum(1 for ch in raw if _CJK_RANGE[0] <= ch <= _CJK_RANGE[1])
    ascii_len = len(raw) - cjk
    return max(1, cjk + ascii_len // 4) if raw else 0


class AIProvider(abc.ABC):
    """AI Provider 抽象基类。

    子类必须实现 `chat()`；`chat_stream()` 默认回退为一次性 `chat()` 的分块输出。
    """

    #: Provider 名称（用于 /ai/status 展示与降级判断）
    name: str = "base"
    #: 是否原生支持流式输出
    supports_streaming: bool = False

    def __init__(self, cfg: ProviderConfig, *, client: Any | None = None) -> None:
        """初始化 Provider。

        Args:
            cfg: Provider 配置。
            client: 可选的预置 httpx.AsyncClient（测试注入 MockTransport 时使用）。
        """
        self.cfg = cfg
        self._client = client

    # ------------------------- 对外属性 -------------------------
    @property
    def model(self) -> str:
        """当前模型名。"""
        return self.cfg.model

    @property
    def available(self) -> bool:
        """当前 Provider 是否可用（默认：配置里有 key）。"""
        return self.cfg.has_key

    # ------------------------- 核心方法 -------------------------
    @abc.abstractmethod
    async def chat(self, messages: list[ChatMessage], **opts: Any) -> AIResponse:
        """执行一次（非流式）对话补全。

        Args:
            messages: 对话消息列表。
            **opts: 可选覆盖项（temperature / max_tokens / json_mode / task 等）。

        Returns:
            `AIResponse`。
        """
        raise NotImplementedError

    async def chat_stream(self, messages: list[ChatMessage], **opts: Any) -> AsyncIterator[str]:
        """流式输出文本增量。

        默认实现：调用 `chat()` 后按行/按块吐出，保证接口可用。
        """
        response = await self.chat(messages, **opts)
        for chunk in _chunk_text(response.content):
            yield chunk

    # ------------------------- 辅助方法 -------------------------
    def count_tokens(self, text: str) -> int:
        """估算文本 token 数。"""
        return estimate_tokens(text)

    async def health(self) -> bool:
        """健康检查（默认：`available` 为 True 即视为健康）。"""
        return self.available

    # ------------------------- 内部工具 -------------------------
    def _resolve_temperature(self, opts: dict[str, Any]) -> float:
        """解析 temperature（请求优先，其次配置默认）。"""
        value = opts.get("temperature")
        return float(value) if value is not None else float(self.cfg.temperature)

    def _resolve_max_tokens(self, opts: dict[str, Any]) -> int:
        """解析 max_tokens（请求优先，其次配置默认）。"""
        value = opts.get("max_tokens")
        return int(value) if value is not None else int(self.cfg.max_tokens)

    @staticmethod
    def now_ms() -> int:
        """当前时间毫秒（用于计算延迟）。"""
        return int(time.time() * 1000)


def _chunk_text(text: str, size: int = 24) -> list[str]:
    """把长文本切成固定长度片段（默认流式回退用）。"""
    raw = text or ""
    return [raw[i : i + size] for i in range(0, len(raw), size)] or [""]


__all__ = [
    "AIProvider",
    "AIProviderBadResponse",
    "AIProviderError",
    "AIProviderTimeout",
    "AIProviderUnavailable",
    "AIResponse",
    "ChatMessage",
    "ProviderConfig",
    "TokenUsage",
    "estimate_tokens",
]
