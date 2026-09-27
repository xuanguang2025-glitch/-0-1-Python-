"""用户与资料 Schema（`docs/API.md` §2.2）。"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator

from app.models.enums import AIMode, LearningMode, ThemePreference
from app.schemas.common import IdStr, ORMModel, StrictModel


class ProfileOut(ORMModel):
    """用户资料响应体。"""

    id: IdStr
    user_id: IdStr
    display_name: str = ""
    avatar_url: str | None = None
    bio: str | None = None
    timezone: str = "UTC"
    theme_preference: str = "system"
    ai_mode: str = "standard"
    learning_mode: str = "system"
    public_profile: bool = True
    weekly_goal_minutes: int = 300
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProfileUpdateRequest(StrictModel):
    """`PATCH /users/me/profile` 请求体（全部字段可选）。"""

    display_name: str | None = Field(default=None, min_length=1, max_length=50)
    avatar_url: str | None = Field(default=None, max_length=512)
    bio: str | None = Field(default=None, max_length=500)
    timezone: str | None = Field(default=None, max_length=50)


class PreferencesUpdateRequest(StrictModel):
    """`PATCH /users/me/preferences` 请求体。"""

    ai_mode: str | None = None
    learning_mode: str | None = None
    theme_preference: str | None = None
    weekly_goal_minutes: int | None = Field(default=None, ge=0, le=10080)

    @field_validator("ai_mode")
    @classmethod
    def _check_ai_mode(cls, value: str | None) -> str | None:
        if value is not None and not AIMode.has(value):
            raise ValueError(f"ai_mode 必须是 {AIMode.values()} 之一")
        return value

    @field_validator("learning_mode")
    @classmethod
    def _check_learning_mode(cls, value: str | None) -> str | None:
        if value is not None and not LearningMode.has(value):
            raise ValueError(f"learning_mode 必须是 {LearningMode.values()} 之一")
        return value

    @field_validator("theme_preference")
    @classmethod
    def _check_theme(cls, value: str | None) -> str | None:
        if value is not None and not ThemePreference.has(value):
            raise ValueError(f"theme_preference 必须是 {ThemePreference.values()} 之一")
        return value


class AvatarOut(ORMModel):
    """头像上传结果。"""

    avatar_url: str


class UserOverviewOut(ORMModel):
    """学习概览（首页仪表盘）。"""

    xp: int = 0
    level: int = 1
    next_level_xp: int = 0
    streak_days: int = 0
    completed_lessons: int = 0
    solved_problems: int = 0
    today_minutes: int = 0
    daily_tasks_done: int = 0


class DeleteAccountRequest(StrictModel):
    """注销账号请求体（需再次输入密码确认）。"""

    password: str = Field(..., min_length=1, max_length=72)


class PublicUserOut(ORMModel):
    """`GET /users/{id}/public`：**仅昵称与等级**，不暴露任何联系方式。"""

    id: IdStr
    display_name: str = ""
    avatar_url: str | None = None
    level: int = 1
    xp: int = 0
