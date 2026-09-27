"""兼容层：`docs/ARCHITECTURE.md` §2.3 约定的 `services/ai_provider.py` 入口。

真正的实现位于 `app.services.ai` 包内，本模块仅做再导出，便于基座组按架构文档
的路径引入（`from app.services.ai_provider import build_provider`）。
"""

from app.services.ai.registry import (
    ProviderFactory,
    ResilientProvider,
    build_primary_provider,
    build_provider,
    build_provider_config,
    get_provider,
    provider_status,
    reset_provider,
    resolve_api_key,
)

# 常用类型再导出，便于 `from app.services.ai_provider import AIProvider`
from app.services.ai.base import (  # noqa: F401  (re-export)
    AIProvider,
    AIProviderError,
    AIResponse,
    ChatMessage,
    ProviderConfig,
    TokenUsage,
)

__all__ = [
    "AIProvider",
    "AIProviderError",
    "AIResponse",
    "ChatMessage",
    "ProviderConfig",
    "ProviderFactory",
    "ResilientProvider",
    "TokenUsage",
    "build_primary_provider",
    "build_provider",
    "build_provider_config",
    "get_provider",
    "provider_status",
    "reset_provider",
    "resolve_api_key",
]
