"""AI 相关 Schema（`docs/API.md` §2.10 与 §3.4-3.5）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.common import IdStr, ORMModel, StrictModel


class AIContextIn(StrictModel):
    """AI 请求上下文（课时 / 题目 / 项目 / 临时编辑器）。"""

    type: str | None = Field(default=None, description="lesson/problem/project/playground")
    id: IdStr | None = None
    code: str | None = Field(default=None, max_length=200_000)
    error: str | None = Field(default=None, max_length=10_000)


class ChatRequest(StrictModel):
    """`POST /ai/chat` 请求体。"""

    conversation_id: IdStr | None = None
    message: str = Field(..., min_length=1, max_length=8000)
    mode: str | None = Field(default=None, description="beginner/standard/advanced")
    scene: str | None = Field(default=None, description="tutor/review/error/exam/free")
    level: str | None = Field(default=None, description="hint/approach/partial/full/explain")
    practice_mode: bool = Field(
        default=False,
        description="练习模式：后端强制禁止直接输出完整答案（除非 AI_ALLOW_FULL_ANSWER_IN_DRILL=true）",
    )
    context: AIContextIn | None = None
    stream: bool = False


class ChatOut(ORMModel):
    """`POST /ai/chat` 响应体（`docs/API.md` §3.4）。"""

    conversation_id: IdStr
    message_id: IdStr
    role: str = "assistant"
    kind: str = "explain"
    content_md: str = ""
    degraded: bool = False
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    suggestions: list[str] = Field(default_factory=list)


class ReviewRequest(StrictModel):
    """`POST /ai/review` 请求体。"""

    code: str = Field(..., min_length=1, max_length=200_000)
    language: str = "python"
    context_type: str | None = None
    context_id: IdStr | None = None
    focus: str | None = Field(default=None, max_length=200, description="关注点，如「性能」「可读性」")


class ReviewIssue(ORMModel):
    """代码评审问题项。"""

    severity: str = "warning"
    line: int | None = None
    title: str = ""
    suggestion: str = ""


class ReviewOut(ORMModel):
    """`POST /ai/review` 响应体（`docs/API.md` §3.5）。"""

    score: int = 0
    summary_md: str = ""
    issues: list[ReviewIssue] = Field(default_factory=list)
    improved_code: str | None = None
    degraded: bool = False


class AnalyzeErrorRequest(StrictModel):
    """`POST /ai/analyze-error` 请求体。"""

    code: str = Field(default="", max_length=200_000)
    error_message: str = Field(..., min_length=1, max_length=10_000)
    traceback: str | None = Field(default=None, max_length=20_000)
    problem_id: IdStr | None = None


class ErrorAnalysisOut(ORMModel):
    """报错分析结果。"""

    error_type: str = "runtime"
    cause: str = ""
    location: str | None = None
    fix_steps: list[str] = Field(default_factory=list)
    minimal_example: str | None = None
    related_topics: list[str] = Field(default_factory=list)
    degraded: bool = False


class AIConversationCreateRequest(StrictModel):
    """新建会话请求体。"""

    title: str | None = Field(default=None, max_length=200)
    mode: str | None = None
    scene: str | None = None
    context_type: str | None = None
    context_id: IdStr | None = None


class AIConversationBrief(ORMModel):
    """会话列表项。"""

    id: IdStr
    title: str = "新对话"
    mode: str = "standard"
    scene: str = "free"
    context_type: str | None = None
    context_id: str | None = None
    message_count: int = 0
    total_tokens: int = 0
    is_archived: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AIMessageOut(ORMModel):
    """会话中的消息。"""

    id: IdStr
    role: str = "user"
    content_md: str = ""
    kind: str | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    degraded: bool = False
    meta_json: Any | None = None
    created_at: datetime | None = None


class AIConversationOut(ORMModel):
    """会话详情。"""

    id: IdStr
    title: str = "新对话"
    mode: str = "standard"
    scene: str = "free"
    context_type: str | None = None
    context_id: str | None = None
    message_count: int = 0
    total_tokens: int = 0
    is_archived: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AIConversationDetail(ORMModel):
    """会话 + 消息列表。"""

    conversation: AIConversationOut
    messages: list[AIMessageOut] = Field(default_factory=list)


class ArchiveRequest(StrictModel):
    """归档切换请求体。"""

    is_archived: bool = True


class AIStatusOut(ORMModel):
    """`GET /ai/status` 响应体。

    `provider` / `model` 反映**当前实际生效**的实现（降级态为 rule / rule-based，
    与 `/api/health/deps` 的 `ai` 项一致）；用户配置的**目标**服务商/模型另放
    `configured_provider` / `configured_model`。
    """

    provider: str = "rule"
    model: str = "rule-based"
    degraded: bool = True
    remaining_quota: int = 0
    modes: list[str] = Field(default_factory=list)
    scenes: list[str] = Field(default_factory=list)
    configured_provider: str | None = None
    configured_model: str | None = None
