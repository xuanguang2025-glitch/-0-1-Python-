"""游戏化模型：`achievements` / `user_achievements` / `daily_tasks` / `user_daily_tasks` / `xp_transactions`。

对应 DATABASE.md §7。
"""

from __future__ import annotations

from datetime import date as date_type
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPkMixin, utc_now
from app.models.enums import AchievementCategory


class Achievement(Base, UUIDPkMixin):
    """成就定义（解锁条件用 `condition_json` 描述）。"""

    __tablename__ = "achievements"
    __table_args__ = (
        Index("ix_ach_code", "code", unique=True),
        Index("ix_ach_category", "category"),
        Index("ix_ach_active", "is_active"),
    )

    code: Mapped[str] = mapped_column(String(60), nullable=False, doc="如 first_ac")
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    category: Mapped[str] = mapped_column(
        String(20), default=AchievementCategory.LEARNING.value, nullable=False
    )
    condition_json: Mapped[Any] = mapped_column(
        JSON, default=dict, nullable=False, doc='{"metric":"accepted_count","op":">=","value":1}'
    )
    xp_reward: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    badge_color: Mapped[str] = mapped_column(String(20), default="blue", nullable=False)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    user_achievements: Mapped[list["UserAchievement"]] = relationship(
        back_populates="achievement",
        cascade="all, delete-orphan",
    )

    @property
    def condition(self) -> dict[str, Any]:
        """解锁条件字典（缺省为空字典）。"""
        return dict(self.condition_json or {})

    def matches(self, metrics: dict[str, int]) -> bool:
        """按 `condition_json` 判断指标是否满足解锁条件。

        Args:
            metrics: 形如 `{"accepted_count": 3, "streak_days": 5}` 的指标快照。

        Returns:
            是否满足（条件缺失或指标缺失时返回 False）。
        """
        rule = self.condition
        metric = rule.get("metric")
        if not metric:
            return False
        if metric not in metrics:
            return False
        target = rule.get("value", 0)
        op = rule.get("op", ">=")
        actual = metrics[metric]
        try:
            target_value = int(target)
        except (TypeError, ValueError):
            return False
        if op == ">=":
            return int(actual) >= target_value
        if op == ">":
            return int(actual) > target_value
        if op == "==":
            return int(actual) == target_value
        if op == "<=":
            return int(actual) <= target_value
        if op == "<":
            return int(actual) < target_value
        return False


class UserAchievement(Base, UUIDPkMixin):
    """用户已解锁成就。"""

    __tablename__ = "user_achievements"
    __table_args__ = (
        UniqueConstraint("user_id", "achievement_id", name="uq_ua_user_ach"),
        Index("ix_ua_user_id", "user_id"),
        Index("ix_ua_seen", "seen"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    achievement_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("achievements.id", ondelete="CASCADE"), nullable=False
    )
    unlocked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    seen: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, doc="是否已弹窗提示")

    user: Mapped["User"] = relationship()  # type: ignore[name-defined]
    achievement: Mapped["Achievement"] = relationship(back_populates="user_achievements")

    def mark_seen(self) -> None:
        """标记为已提示（前端弹窗后调用）。"""
        self.seen = True


class DailyTask(Base, UUIDPkMixin):
    """每日任务定义。"""

    __tablename__ = "daily_tasks"
    __table_args__ = (
        Index("ix_dt_code", "code", unique=True),
        Index("ix_dt_active", "is_active"),
    )

    code: Mapped[str] = mapped_column(String(60), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    metric: Mapped[str] = mapped_column(String(40), nullable=False, doc="统计指标名，如 submissions")
    target_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    xp_reward: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    user_tasks: Mapped[list["UserDailyTask"]] = relationship(
        back_populates="daily_task",
        cascade="all, delete-orphan",
    )


class UserDailyTask(Base, UUIDPkMixin):
    """用户某天的任务进度（`(user_id, daily_task_id, date)` 唯一）。"""

    __tablename__ = "user_daily_tasks"
    __table_args__ = (
        UniqueConstraint("user_id", "daily_task_id", "date", name="uq_udt_user_task_date"),
        Index("ix_udt_user_id", "user_id"),
        Index("ix_udt_date", "date"),
        Index("ix_udt_completed", "completed"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    daily_task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("daily_tasks.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date_type] = mapped_column(Date, nullable=False, doc="任务归属日期（UTC）")
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship()  # type: ignore[name-defined]
    daily_task: Mapped["DailyTask"] = relationship(back_populates="user_tasks")

    def bump(self, amount: int = 1, *, target: int | None = None) -> bool:
        """推进任务进度，返回本次是否刚好达成（用于发放 XP 且避免重复发放）。"""
        self.progress = int(self.progress or 0) + max(0, int(amount))
        goal = int(target if target is not None else (self.daily_task.target_count if self.daily_task else 1))
        if not self.completed and self.progress >= goal:
            self.completed = True
            self.completed_at = utc_now()
            return True
        return False


class XPTransaction(Base, UUIDPkMixin):
    """经验值流水（正负均可，`balance_after` 便于对账）。"""

    __tablename__ = "xp_transactions"
    __table_args__ = (
        Index("ix_xp_user_id", "user_id"),
        Index("ix_xp_reason", "reason"),
        Index("ix_xp_created_at", "created_at"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False, doc="正负")
    reason: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    ref_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    ref_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    balance_after: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    user: Mapped["User"] = relationship()  # type: ignore[name-defined]


# 说明：achievements / daily_tasks / xp_transactions 按 DATABASE.md §7 无 updated_at，
# 因此仅使用 UUIDPkMixin（不带 TimestampMixin）。
