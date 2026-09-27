"""认证相关 Schema（`docs/API.md` §2.1 与 §3.1）。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import EmailStr, Field, field_validator

from app.core.security import validate_username
from app.schemas.common import IdStr, ORMModel, StrictModel

if TYPE_CHECKING:
    from app.models.user import User


class RegisterRequest(StrictModel):
    """注册请求体。"""

    email: EmailStr = Field(..., description="邮箱（唯一，小写存储）")
    username: str = Field(..., min_length=3, max_length=20, description="3-20 位字母数字下划线")
    password: str = Field(..., min_length=8, max_length=72, description="至少 8 位，须含字母与数字")

    @field_validator("username")
    @classmethod
    def _check_username(cls, value: str) -> str:
        validate_username(value)
        return value

    @field_validator("email")
    @classmethod
    def _lower_email(cls, value: str) -> str:
        return str(value).strip().lower()


class LoginRequest(StrictModel):
    """登录请求体：`account` 支持邮箱或用户名。"""

    account: str = Field(..., min_length=3, max_length=255, description="邮箱或用户名")
    password: str = Field(..., min_length=1, max_length=72)

    @field_validator("account")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()


class RefreshRequest(StrictModel):
    """刷新令牌请求体。"""

    refresh_token: str = Field(..., min_length=10, description="refresh_token（登录时下发）")


class LogoutRequest(ORMModel):
    """登出请求体（`refresh_token` 可选，用于同时吊销对应记录）。"""

    refresh_token: str | None = Field(default=None, description="可选：同时吊销该 refresh_token")


class ChangePasswordRequest(StrictModel):
    """修改密码请求体。"""

    old_password: str = Field(..., min_length=1, max_length=72)
    new_password: str = Field(..., min_length=8, max_length=72)


class ResetPasswordRequest(StrictModel):
    """管理员重置他人密码请求体。"""

    user_id: IdStr
    new_password: str = Field(..., min_length=8, max_length=72)


class UserBrief(ORMModel):
    """嵌入在 TokenPair / 各类引用中的用户摘要。"""

    id: IdStr
    email: str
    username: str
    display_name: str = ""
    role: str = "user"
    level: int = 1
    xp: int = 0

    @classmethod
    def from_user(cls, user: "User") -> "UserBrief":
        """由 ORM 用户对象构造摘要（display_name 缺省回退用户名）。"""
        return cls(
            id=user.id,
            email=user.email,
            username=user.username,
            display_name=user.display_name,
            role=user.role,
            level=int(user.level or 1),
            xp=int(user.xp or 0),
        )


class ProfileBrief(ORMModel):
    """`/auth/me` 中内嵌的资料摘要。"""

    display_name: str = ""
    avatar_url: str | None = None
    bio: str | None = None
    theme_preference: str = "system"
    ai_mode: str = "standard"
    learning_mode: str = "system"


class UserMe(ORMModel):
    """`GET /api/auth/me` 的响应体。"""

    id: IdStr
    email: str
    username: str
    role: str
    status: str = "active"
    is_verified: bool = True
    xp: int = 0
    level: int = 1
    streak_days: int = 0
    max_streak_days: int = 0
    login_count: int = 0
    created_at: datetime | None = None
    last_login_at: datetime | None = None
    profile: ProfileBrief | None = None


class TokenPair(ORMModel):
    """登录 / 注册 / 刷新成功后的令牌对（`docs/API.md` §3.1）。"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(default=900, description="access_token 有效期（秒）")
    user: UserBrief
