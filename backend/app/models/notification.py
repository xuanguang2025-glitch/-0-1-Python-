"""通知与公告模型：`notifications` / `announcements`（DATABASE.md §10.1-10.2）。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPkMixin, utc_now
from app.models.enums import AnnouncementLevel, NotificationType


class Notification(Base, UUIDPkMixin):
    """站内通知（`user_id` 为空表示广播，当前设计不启用）。"""

    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_nt_user_id", "user_id"),
        Index("ix_nt_is_read", "is_read"),
        Index("ix_nt_created_at", "created_at"),
        Index("ix_nt_type", "type"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(20), default=NotificationType.SYSTEM.value, nullable=False)
    title: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    content_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    link_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    user: Mapped["User"] = relationship()  # type: ignore[name-defined]

    def mark_read(self) -> None:
        """标记为已读并记录时间（幂等）。"""
        if not self.is_read:
            self.is_read = True
            self.read_at = utc_now()


class Announcement(Base, UUIDPkMixin, TimestampMixin):
    """全站公告。"""

    __tablename__ = "announcements"
    __table_args__ = (
        Index("ix_ann_pinned", "is_pinned"),
        Index("ix_ann_active", "is_active"),
        Index("ix_ann_published", "published_at"),
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content_md: Mapped[str] = mapped_column(Text, default="", nullable=False)
    level: Mapped[str] = mapped_column(String(20), default=AnnouncementLevel.INFO.value, nullable=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    creator: Mapped["User | None"] = relationship(foreign_keys=[created_by])  # type: ignore[name-defined]

    @property
    def is_visible(self) -> bool:
        """当前是否对用户可见（启用中且未过期）。"""
        if not self.is_active:
            return False
        if self.expires_at is None:
            return True
        return self.expires_at > utc_now()
