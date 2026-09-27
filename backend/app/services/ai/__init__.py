"""AI 子系统（Provider 抽象 + 各厂商适配 + 离线规则引擎 + 业务编排）。

对外统一出口，业务代码从这里导入即可：

```python
from app.services.ai import build_provider, get_provider, TutorService, CodeReviewService
```

模块划分：
- `base`        抽象基类、配置与响应结构；
- `openai_compatible` / `claude` / `gemini`  远程适配器；
- `rule_based`  离线规则引擎（无 Key / 远程失败降级）；
- `registry`    Provider 选型与自动回落；
- `prompts`     提示词模板集中管理；
- `tutor`       导师编排（五级递进 + 三模式 + 练习约束）；
- `review`      九维度代码评审 + 报错分析；
- `repository`  会话/消息/用量持久化（隔离 ORM）。
"""

from app.services.ai.base import (
    AIProvider,
    AIProviderBadResponse,
    AIProviderError,
    AIProviderTimeout,
    AIProviderUnavailable,
    AIResponse,
    ChatMessage,
    ProviderConfig,
    TokenUsage,
)
from app.services.ai.claude import ClaudeProvider
from app.services.ai.gemini import GeminiProvider
from app.services.ai.openai_compatible import OpenAICompatibleProvider
from app.services.ai.registry import (
    ProviderFactory,
    ResilientProvider,
    build_provider,
    build_provider_config,
    get_provider,
    provider_status,
    reset_provider,
)
from app.services.ai.review import CodeReviewService, analyze_error_report, extract_json_object
from app.services.ai.rule_based import RuleBasedProvider
from app.services.ai.tutor import (
    TutorService,
    enforce_practice_constraint,
    normalize_level,
    normalize_mode,
)

__all__ = [
    "AIProvider",
    "AIProviderBadResponse",
    "AIProviderError",
    "AIProviderTimeout",
    "AIProviderUnavailable",
    "AIResponse",
    "ChatMessage",
    "ClaudeProvider",
    "CodeReviewService",
    "GeminiProvider",
    "OpenAICompatibleProvider",
    "ProviderConfig",
    "ProviderFactory",
    "ResilientProvider",
    "RuleBasedProvider",
    "TokenUsage",
    "TutorService",
    "analyze_error_report",
    "build_provider",
    "build_provider_config",
    "enforce_practice_constraint",
    "extract_json_object",
    "get_provider",
    "normalize_level",
    "normalize_mode",
    "provider_status",
    "reset_provider",
]
