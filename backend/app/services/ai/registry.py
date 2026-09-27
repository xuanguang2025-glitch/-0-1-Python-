"""Provider 注册与降级工厂（`docs/ARCHITECTURE.md` §1.3 ⑤、`docs/AI.md` §5）。

选型与降级逻辑：

1. `AI_OFFLINE=1` 或 `AI_API_KEY` 缺失/占位 → `RuleBasedProvider`（纯离线）；
2. 否则按 `AI_PROVIDER` 选择 `OpenAICompatibleProvider` / `ClaudeProvider` / `GeminiProvider`，
   并用 `ResilientProvider` 包裹：远程调用失败/超时 → **自动回落** `RuleBasedProvider`
   并把 `degraded=True` 透出，保证接口永不 5xx。

密钥来源：优先 `AI_API_KEY`，为空时按服务商读取 `DEEPSEEK_API_KEY` / `OPENAI_API_KEY` 等
（仅从环境变量读取，**绝不入库、不回前端、不打日志**）。
"""

from __future__ import annotations

import os
from typing import Any, AsyncIterator

from app.services.ai.base import (
    AIProvider,
    AIProviderError,
    AIResponse,
    ChatMessage,
    ProviderConfig,
)
from app.services.ai.claude import ClaudeProvider
from app.services.ai.gemini import GeminiProvider
from app.services.ai.openai_compatible import OpenAICompatibleProvider
from app.services.ai.rule_based import RuleBasedProvider

#: 服务商 → 专用环境变量名
VENDOR_KEY_ENV: dict[str, str] = {
    "deepseek": "DEEPSEEK_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "qwen": "QWEN_API_KEY",
    "zhipu": "ZHIPU_API_KEY",
    "moonshot": "MOONSHOT_API_KEY",
}

#: 使用厂商原生协议（非 OpenAI 兼容）的服务商
NATIVE_PROVIDERS: set[str] = {"anthropic", "gemini"}

#: 离线降级时对外统一的 provider / model 名称（必须与 `/api/health/deps` 的 `ai` 项一致）
#: 口径：provider = "rule_based"（与 `docs/AI.md §4`、`AIResponse.provider` 一致），model = "rule-based"
OFFLINE_PROVIDER_ALIAS: str = "rule_based"
OFFLINE_MODEL_ALIAS: str = "rule-based"

#: 强制离线时可识别的占位密钥前缀
_PLACEHOLDER_PREFIXES = ("sk-your-", "your-", "xxx")


def resolve_api_key(settings: Any, provider: str) -> str:
    """解析服务商密钥：`AI_API_KEY` 优先，其次厂商专用环境变量。

    Args:
        settings: 配置对象（含 `ai_api_key`）。
        provider: 服务商标识。

    Returns:
        密钥字符串（未配置时为空串）。
    """
    key = (getattr(settings, "ai_api_key", "") or "").strip()
    if key and not key.startswith(_PLACEHOLDER_PREFIXES):
        return key
    env_name = VENDOR_KEY_ENV.get(provider)
    if env_name:
        return (os.environ.get(env_name) or "").strip()
    return ""


def build_provider_config(settings: Any) -> ProviderConfig:
    """由全局配置构造 `ProviderConfig`。"""
    provider = (getattr(settings, "ai_provider", "deepseek") or "deepseek").lower()
    return ProviderConfig(
        provider=provider,
        model=getattr(settings, "ai_model", "deepseek-chat") or "deepseek-chat",
        base_url=getattr(settings, "ai_base_url", None),
        api_key=resolve_api_key(settings, provider),
        temperature=float(getattr(settings, "ai_temperature", 0.3)),
        max_tokens=int(getattr(settings, "ai_max_tokens", 2048)),
        timeout_ms=int(getattr(settings, "ai_timeout_ms", 30_000)),
        max_retries=1,
    )


def build_primary_provider(cfg: ProviderConfig) -> AIProvider:
    """按 `cfg.provider` 构造远程 Provider 实例。"""
    provider = (cfg.provider or "openai").lower()
    if provider == "anthropic":
        return ClaudeProvider(cfg)
    if provider == "gemini":
        return GeminiProvider(cfg)
    return OpenAICompatibleProvider(cfg)


class ResilientProvider(AIProvider):
    """带回落的 Provider 包装器：主 Provider 失败时自动回落离线规则引擎。"""

    def __init__(self, primary: AIProvider, fallback: AIProvider) -> None:
        """初始化。

        Args:
            primary: 远程 Provider。
            fallback: 降级 Provider（通常为 `RuleBasedProvider`）。
        """
        super().__init__(primary.cfg)
        self._primary = primary
        self._fallback = fallback
        self.name = primary.name
        self.supports_streaming = primary.supports_streaming
        self.last_degraded: bool = False

    @property
    def primary_name(self) -> str:
        """主 Provider 名称。"""
        return self._primary.name

    @property
    def available(self) -> bool:
        """主 Provider 是否可用（有 key）。"""
        return self._primary.available

    async def chat(self, messages: list[ChatMessage], **opts: Any) -> AIResponse:
        """调用主 Provider，失败则回落规则引擎（`degraded=True`）。"""
        try:
            response = await self._primary.chat(messages, **opts)
            self.last_degraded = False
            return response
        except (AIProviderError, Exception):  # noqa: BLE001 - 任何远程异常都回落，保证不 5xx
            self.last_degraded = True
            return await self._fallback.chat(messages, **opts)

    async def chat_stream(self, messages: list[ChatMessage], **opts: Any) -> AsyncIterator[str]:
        """流式：优先主 Provider，首块前失败则回落规则引擎。"""
        try:
            async for chunk in self._primary.chat_stream(messages, **opts):
                yield chunk
            self.last_degraded = False
        except Exception:  # noqa: BLE001 - 流式途中失败也回落，保证有输出
            self.last_degraded = True
            async for chunk in self._fallback.chat_stream(messages, **opts):
                yield chunk

    async def health(self) -> bool:
        """主 Provider 健康检查。"""
        return await self._primary.health()


class ProviderFactory:
    """Provider 工厂（兼容 `docs/AI.md` §1 的命名）。"""

    @staticmethod
    def create(settings: Any | None = None) -> AIProvider:
        """按配置创建 Provider（等价于 `build_provider`）。"""
        return build_provider(settings)


def build_provider(settings: Any | None = None) -> AIProvider:
    """构造当前生效的 AI Provider（含离线判定与降级包装）。

    Args:
        settings: 可选配置对象；为空时读取全局配置。

    Returns:
        `RuleBasedProvider`（离线）或 `ResilientProvider`（远程 + 回落）。
    """
    if settings is None:
        from app.core.config import get_settings

        settings = get_settings()

    if not bool(getattr(settings, "ai_enabled", False)):
        return RuleBasedProvider(build_provider_config(settings))

    cfg = build_provider_config(settings)
    primary = build_primary_provider(cfg)
    return ResilientProvider(primary, RuleBasedProvider(cfg))


#: 全局 Provider 单例（惰性构建，测试可 `reset_provider()` 清理）
_PROVIDER_SINGLETON: AIProvider | None = None


def get_provider() -> AIProvider:
    """获取进程内单例 Provider。"""
    global _PROVIDER_SINGLETON
    if _PROVIDER_SINGLETON is None:
        _PROVIDER_SINGLETON = build_provider()
    return _PROVIDER_SINGLETON


def reset_provider() -> None:
    """清空单例（测试或配置热更新时调用）。"""
    global _PROVIDER_SINGLETON
    _PROVIDER_SINGLETON = None


def status_provider_name(provider: AIProvider) -> str:
    """状态接口的 provider 取值。

    离线降级统一为 `rule_based`（与 `/api/health/deps` 的 `ai.provider` 及
    `docs/AI.md §4` 一致），否则返回实际服务商名（openai/deepseek/...）。
    """
    return OFFLINE_PROVIDER_ALIAS if isinstance(provider, RuleBasedProvider) else provider.name


def status_model_name(provider: AIProvider) -> str:
    """状态接口的 model 取值：反映**当前实际生效**的模型。

    离线降级统一为 `rule-based`（与 `/api/health/deps` 的 `ai.model` 完全一致），
    否则返回实际使用的模型名。
    """
    return OFFLINE_MODEL_ALIAS if isinstance(provider, RuleBasedProvider) else provider.model


def provider_status(provider: AIProvider) -> dict[str, Any]:
    """构造 `/ai/status` 所需的 Provider 摘要（不含任何密钥）。

    关键语义：`provider` / `model` 一律反映**当前实际生效**的实现；
    用户配置的「目标」provider/model 另放 `configured_provider` / `configured_model`，
    避免 `degraded=true` 时出现「离线助手（deepseek-chat）」这类自相矛盾的展示。
    """
    offline = isinstance(provider, RuleBasedProvider)
    return {
        "provider": status_provider_name(provider),
        "model": status_model_name(provider),
        "degraded": bool(offline or not provider.available),
        "configured": bool(provider.available),
        "supports_streaming": bool(provider.supports_streaming),
        "configured_provider": provider.cfg.provider,
        "configured_model": provider.cfg.model,
    }


__all__ = [
    "NATIVE_PROVIDERS",
    "OFFLINE_MODEL_ALIAS",
    "OFFLINE_PROVIDER_ALIAS",
    "ProviderFactory",
    "ResilientProvider",
    "VENDOR_KEY_ENV",
    "build_primary_provider",
    "build_provider",
    "build_provider_config",
    "get_provider",
    "provider_status",
    "reset_provider",
    "resolve_api_key",
    "status_model_name",
    "status_provider_name",
]
