"""AI 模型：`ai_conversations` / `ai_messages` / `ai_model_configs` / `ai_usage_logs`（DATABASE.md §8）。

安全约定：`ai_model_configs.api_key_env` 只保存**环境变量名**，绝不落库真实密钥。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPkMixin, utc_now
from app.models.enums import AIMessageRole, AIMode, AIScene, AIProviderName


class AIConversation(Base, UUIDPkMixin, TimestampMixin):
    """AI 会话。"""

    __tablename__ = "ai_conversations"
    __table_args__ = (
        Index("ix_aic_user_id", "user_id"),
        Index("ix_aic_updated_at", "updated_at"),
        Index("ix_aic_scene", "scene"),
        Index("ix_aic_context", "context_type", "context_id"),
        Index("ix_aic_archived", "is_archived"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), default="新对话", nullable=False)
    mode: Mapped[str] = mapped_column(String(20), default=AIMode.STANDARD.value, nullable=False)
    scene: Mapped[str] = mapped_column(String(20), default=AIScene.FREE.value, nullable=False)
    context_type: Mapped[str | None] = mapped_column(String(20), nullable=True, doc="lesson/problem/project/playground")
    context_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(30), nullable=True)
    model: Mapped[str | None] = mapped_column(String(60), nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped["User"] = relationship()  # type: ignore[name-defined]
    messages: Mapped[list["AIMessage"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="AIMessage.created_at",
    )

    def rename_from_first_message(self, content: str) -> None:
        """首次提问后用提问内容生成标题（截断 30 字）。"""
        if self.title and self.title != "新对话":
            return
        text = (content or "").strip().replace("\n", " ")
        self.title = (text[:30] + "…") if len(text) > 30 else (text or "新对话")

    def count_message(self, tokens: int = 0) -> None:
        """累加消息数与 token 数。"""
        self.message_count = int(self.message_count or 0) + 1
        self.total_tokens = int(self.total_tokens or 0) + max(0, int(tokens))


class AIMessage(Base, UUIDPkMixin):
    """AI 会话中的单条消息。`degraded=True` 表示由本地规则助手兜底生成。"""

    __tablename__ = "ai_messages"
    __table_args__ = (
        Index("ix_aim_conversation_id", "conversation_id"),
        Index("ix_aim_kind", "kind"),
        Index("ix_aim_created_at", "created_at"),
    )

    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), default=AIMessageRole.USER.value, nullable=False)
    content_md: Mapped[str] = mapped_column(Text, default="", nullable=False)
    kind: Mapped[str | None] = mapped_column(String(30), nullable=True)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    degraded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, doc="是否本地规则兜底")
    meta_json: Mapped[Any | None] = mapped_column(JSON, nullable=True, doc="模型原始片段、代码引用等")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    conversation: Mapped["AIConversation"] = relationship(back_populates="messages")

    @property
    def is_user(self) -> bool:
        """是否为用户消息。"""
        return self.role == AIMessageRole.USER.value


class AIModelConfig(Base, UUIDPkMixin, TimestampMixin):
    """AI 模型配置（多服务商可选，默认 DeepSeek）。"""

    __tablename__ = "ai_model_configs"
    __table_args__ = (
        Index("ix_amc_provider", "provider"),
        Index("ix_amc_is_default", "is_default"),
        Index("ix_amc_is_active", "is_active"),
    )

    provider: Mapped[str] = mapped_column(
        String(30), default=AIProviderName.DEEPSEEK.value, nullable=False
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False, doc="显示名")
    model: Mapped[str] = mapped_column(String(80), nullable=False, doc="如 deepseek-chat")
    base_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    api_key_env: Mapped[str | None] = mapped_column(
        String(80), nullable=True, doc="**只存环境变量名**，如 DEEPSEEK_API_KEY"
    )
    temperature: Mapped[float] = mapped_column(Float, default=0.3, nullable=False)
    max_tokens: Mapped[int] = mapped_column(Integer, default=2048, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    capability_json: Mapped[Any | None] = mapped_column(JSON, nullable=True, doc='{"stream":true,"json_mode":true}')

    @property
    def capability(self) -> dict[str, Any]:
        """能力声明字典。"""
        return dict(self.capability_json or {})


class AIUsageLog(Base, UUIDPkMixin):
    """AI 调用用量日志（用于配额统计与降级观察）。"""

    __tablename__ = "ai_usage_logs"
    __table_args__ = (
        Index("ix_aul_user_id", "user_id"),
        Index("ix_aul_created_at", "created_at"),
        Index("ix_aul_success", "success"),
        Index("ix_aul_provider", "provider"),
        Index("ix_aul_conversation_id", "conversation_id"),
    )

    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    conversation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    provider: Mapped[str] = mapped_column(String(30), default="", nullable=False)
    model: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    scene: Mapped[str | None] = mapped_column(String(20), nullable=True)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    degraded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    @property
    def total_tokens(self) -> int:
        """入参 + 出参 token 总数。"""
        return int(self.tokens_in or 0) + int(self.tokens_out or 0)
