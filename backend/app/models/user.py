"""身份与用户模型：`users` / `profiles` / `refresh_tokens`（DATABASE.md §1）。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPkMixin, utc_now
from app.models.enums import AIMode, LearningMode, ThemePreference, UserRole, UserStatus
from app.utils.time import to_utc

if TYPE_CHECKING:  # 仅用于类型检查，避免运行期循环导入
    from app.models.ai import AIConversation
    from app.models.gamification import UserAchievement, XPTransaction
    from app.models.learning import Bookmark, CodeHistory, KnowledgeMastery, LearningProgress, LearningSession, Mistake


class User(Base, UUIDPkMixin, TimestampMixin, SoftDeleteMixin):
    """用户主表。`hashed_password` 永不出现在任何 Schema 中。"""

    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_email", "email", unique=True),
        Index("ix_users_username", "username", unique=True),
        Index("ix_users_role", "role"),
        Index("ix_users_status", "status"),
        Index("ix_users_xp", "xp"),
        Index("ix_users_level", "level"),
    )

    email: Mapped[str] = mapped_column(String(255), nullable=False, doc="登录邮箱（小写存储）")
    username: Mapped[str] = mapped_column(String(50), nullable=False, doc="3-20 位字母数字下划线")
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False, doc="密码哈希，禁止外泄")
    role: Mapped[str] = mapped_column(String(20), default=UserRole.USER.value, nullable=False, doc="user/admin/superadmin")
    status: Mapped[str] = mapped_column(String(20), default=UserStatus.ACTIVE.value, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, doc="邮箱验证（本机默认 true）")
    xp: Mapped[int] = mapped_column(Integer, default=0, nullable=False, doc="累计经验值")
    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False, doc="1-7，由 XP 阈值推导")
    streak_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False, doc="当前连续学习天数")
    max_streak_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False, doc="历史最长连续天数")
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locale: Mapped[str] = mapped_column(String(10), default="zh-CN", nullable=False)

    profile: Mapped["Profile | None"] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin",
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="RefreshToken.user_id",
    )

    # ---- 便捷方法 ----
    @property
    def is_admin(self) -> bool:
        """是否为管理员（admin / superadmin）。"""
        return self.role in (UserRole.ADMIN.value, UserRole.SUPERADMIN.value)

    @property
    def display_name(self) -> str:
        """排行榜与界面上唯一对外展示的名称（来自 profile，缺省回退用户名）。"""
        if self.profile and self.profile.display_name:
            return self.profile.display_name
        return self.username

    def touch_active(self) -> None:
        """刷新最近活跃时间（鉴权链路上低频调用）。"""
        self.last_active_at = utc_now()

    def record_login(self) -> None:
        """记录一次成功登录（时间 + 次数）。"""
        now = utc_now()
        self.last_login_at = now
        self.last_active_at = now
        self.login_count = int(self.login_count or 0) + 1


class Profile(Base, UUIDPkMixin, TimestampMixin):
    """用户资料（与 users 一对一）。`display_name` 是排行榜唯一展示名。"""

    __tablename__ = "profiles"
    __table_args__ = (
        Index("ix_profiles_user_id", "user_id", unique=True),
        Index("ix_profiles_display_name", "display_name"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(50), default="", nullable=False, doc="昵称，排行榜唯一展示名")
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True, doc="本地 /uploads/... 或外链")
    bio: Mapped[str | None] = mapped_column(String(500), nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), default="UTC", nullable=False)
    theme_preference: Mapped[str] = mapped_column(
        String(10), default=ThemePreference.SYSTEM.value, nullable=False
    )
    ai_mode: Mapped[str] = mapped_column(String(20), default=AIMode.STANDARD.value, nullable=False)
    learning_mode: Mapped[str] = mapped_column(String(20), default=LearningMode.SYSTEM.value, nullable=False)
    public_profile: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    weekly_goal_minutes: Mapped[int] = mapped_column(Integer, default=300, nullable=False)

    user: Mapped["User"] = relationship(back_populates="profile")

    @property
    def leaderboard_name(self) -> str:
        """排行榜展示名：昵称为空时回退为「学习者」。"""
        return self.display_name or "学习者"


class RefreshToken(Base, UUIDPkMixin):
    """Refresh Token 记录：只保存 sha256 摘要，支持单设备吊销。"""

    __tablename__ = "refresh_tokens"
    __table_args__ = (
        Index("ix_rt_jti", "jti", unique=True),
        Index("ix_rt_token_hash", "token_hash", unique=True),
        Index("ix_rt_user_id", "user_id"),
        Index("ix_rt_expires_at", "expires_at"),
        Index("ix_rt_created_at", "created_at"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    jti: Mapped[str] = mapped_column(String(36), nullable=False, doc="JWT ID，用于吊销")
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, doc="sha256(token)")
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    user: Mapped["User"] = relationship(back_populates="refresh_tokens", foreign_keys=[user_id])

    @property
    def is_valid(self) -> bool:
        """是否仍然有效（未吊销且未过期）。"""
        if self.revoked:
            return False
        return to_utc(self.expires_at) > utc_now()

    def revoke(self) -> None:
        """吊销该令牌。"""
        self.revoked = True
        self.revoked_at = utc_now()
