"""系统模型：`audit_logs` / `system_settings`（DATABASE.md §10.3-10.4）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Index,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPkMixin, utc_now


class AuditLog(Base, UUIDPkMixin):
    """审计日志：记录管理员等敏感操作的前后快照。"""

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_al_actor_id", "actor_id"),
        Index("ix_al_action", "action"),
        Index("ix_al_target_id", "target_id"),
        Index("ix_al_created_at", "created_at"),
    )

    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True, doc="操作者用户 id（删除后保留）")
    action: Mapped[str] = mapped_column(String(60), default="", nullable=False, doc="如 admin.user.ban")
    target_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    detail_json: Mapped[Any | None] = mapped_column(JSON, nullable=True, doc="before/after 快照")
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    @property
    def detail(self) -> dict[str, Any]:
        """审计详情字典。"""
        return dict(self.detail_json or {})


class SystemSetting(Base, UUIDPkMixin):
    """系统键值配置（值为 JSON，便于扩展）。"""

    __tablename__ = "system_settings"
    __table_args__ = (
        Index("ix_ss_key", "key", unique=True),
    )

    key: Mapped[str] = mapped_column(String(80), nullable=False, doc="如 site.announcement")
    value_json: Mapped[Any] = mapped_column(JSON, default=dict, nullable=False)
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


# 说明：system_settings 无 created_at 字段（按 DATABASE.md §10.4），故未使用 TimestampMixin。
