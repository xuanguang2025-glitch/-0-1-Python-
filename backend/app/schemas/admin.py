"""管理端 Schema（`docs/API.md` §2.21）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import EmailStr, Field

from app.schemas.common import IdStr, ORMModel, StrictModel


class AdminUserBrief(ORMModel):
    """管理端用户列表项。"""

    id: IdStr
    email: str
    username: str
    display_name: str = ""
    role: str = "user"
    status: str = "active"
    level: int = 1
    xp: int = 0
    login_count: int = 0
    created_at: datetime | None = None
    last_login_at: datetime | None = None


class AdminUserCreateRequest(StrictModel):
    """管理端新建用户请求体。"""

    email: EmailStr
    username: str = Field(..., min_length=3, max_length=20)
    password: str = Field(..., min_length=8, max_length=72)
    role: str = "user"
    display_name: str = Field(default="", max_length=50)


class AdminUserUpdateRequest(StrictModel):
    """管理端更新用户请求体。"""

    role: str | None = None
    status: str | None = None
    display_name: str | None = Field(default=None, max_length=50)
    is_verified: bool | None = None


class AdminPasswordResetRequest(StrictModel):
    """管理端重置密码请求体。"""

    new_password: str = Field(..., min_length=8, max_length=72)


class AdminCourseIn(StrictModel):
    """管理端课程写入体。"""

    slug: str = Field(..., min_length=1, max_length=120)
    stage_no: int = Field(..., ge=1, le=99)
    title: str = Field(..., min_length=1, max_length=200)
    subtitle: str | None = None
    description_md: str | None = None
    level: str = "beginner"
    icon: str | None = None
    cover_url: str | None = None
    estimated_hours: int = 0
    is_published: bool = True


class AdminChapterIn(StrictModel):
    """管理端章节写入体。"""

    course_id: IdStr
    slug: str = Field(..., min_length=1, max_length=120)
    title: str = Field(..., min_length=1, max_length=200)
    summary_md: str | None = None
    order_index: int = 0
    is_published: bool = True


class AdminLessonIn(StrictModel):
    """管理端课时写入体。"""

    chapter_id: IdStr
    slug: str = Field(..., min_length=1, max_length=120)
    title: str = Field(..., min_length=1, max_length=200)
    summary: str | None = None
    content_md: str = ""
    lesson_type: str = "concept"
    difficulty: str = "easy"
    estimated_minutes: int = 15
    order_index: int = 0
    xp_reward: int = 10
    has_playground: bool = True
    starter_code: str | None = None
    solution_code: str | None = None
    quiz_json: Any | None = None
    is_published: bool = True
    topic_slugs: list[str] = Field(default_factory=list)


class AdminProjectIn(StrictModel):
    """管理端项目写入体。"""

    slug: str = Field(..., min_length=1, max_length=150)
    title: str = Field(..., min_length=1, max_length=200)
    summary: str | None = None
    description_md: str = ""
    level: int = Field(default=1, ge=1, le=10)
    difficulty: str = "easy"
    category: str = "basics"
    cover_url: str | None = None
    estimated_hours: int = 4
    xp_reward: int = 100
    steps_json: Any | None = None
    rubric_json: Any | None = None
    is_published: bool = True
    order_index: int = 0


class AdminProjectFileIn(StrictModel):
    """管理端项目文件写入体。"""

    project_id: IdStr
    path: str = Field(..., min_length=1, max_length=512)
    content: str = ""
    language: str = "python"
    is_entry: bool = False
    is_readonly: bool = False
    description: str | None = Field(default=None, max_length=300)
    order_index: int = 0


class AIConfigOut(ORMModel):
    """全局 AI 配置（**不回显任何密钥明文**）。"""

    provider: str = "deepseek"
    model: str = "deepseek-chat"
    base_url: str | None = None
    temperature: float = 0.3
    max_tokens: int = 2048
    offline: bool = False
    rate_limit_per_hour: int = 60
    degraded: bool = True
    api_key_configured: bool = False
    api_key_masked: str | None = Field(default=None, description="脱敏后的密钥，如 sk-****3456")
    prompt_overrides: dict[str, Any] = Field(default_factory=dict)


class AIConfigUpdateRequest(StrictModel):
    """AI 配置更新请求体（`api_key` 为只写字段，永不回传）。"""

    provider: str | None = None
    model: str | None = None
    base_url: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=64, le=32_768)
    offline: bool | None = None
    rate_limit_per_hour: int | None = Field(default=None, ge=1, le=10_000)
    prompt_overrides: dict[str, Any] | None = None
    api_key: str | None = Field(default=None, max_length=512, description="只写：真实密钥，读取时永远脱敏")


class AIModelConfigOut(ORMModel):
    """模型配置响应体（`api_key_env` 只暴露环境变量名；密钥永远脱敏）。"""

    id: IdStr
    provider: str = "deepseek"
    name: str = ""
    model: str = ""
    base_url: str | None = None
    api_key_env: str | None = None
    temperature: float = 0.3
    max_tokens: int = 2048
    is_default: bool = False
    is_active: bool = True
    capability_json: Any | None = None
    api_key_masked: str | None = Field(default=None, description="脱敏后的密钥，如 sk-****3456")


class AIModelConfigIn(StrictModel):
    """模型配置写入体（`api_key` 为只写字段，最后 4 位以外全部脱敏）。"""

    provider: str = "deepseek"
    name: str = Field(..., min_length=1, max_length=80)
    model: str = Field(..., min_length=1, max_length=80)
    base_url: str | None = Field(default=None, max_length=255)
    api_key_env: str | None = Field(default=None, max_length=80)
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=64, le=32_768)
    is_default: bool = False
    is_active: bool = True
    capability_json: Any | None = None
    api_key: str | None = Field(default=None, max_length=512, description="只写：真实密钥，读取时永远脱敏")


class ModelTestOut(ORMModel):
    """模型连通性测试结果（**不回显 key**）。"""

    ok: bool = False
    latency_ms: int = 0
    error: str | None = None


class AuditLogOut(ORMModel):
    """审计日志项。"""

    id: IdStr
    actor_id: str | None = None
    action: str = ""
    target_type: str | None = None
    target_id: str | None = None
    detail_json: Any | None = None
    ip: str | None = None
    created_at: datetime | None = None


class AIUsageLogOut(ORMModel):
    """AI 用量日志项。"""

    id: IdStr
    user_id: str | None = None
    provider: str = ""
    model: str = ""
    scene: str | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    success: bool = True
    degraded: bool = False
    error_code: str | None = None
    created_at: datetime | None = None


class ErrorLogGroup(ORMModel):
    """错误日志聚合项。"""

    code: str
    count: int = 0
    last_at: datetime | None = None
    sample_message: str | None = None


class MaintenanceRejudgeRequest(StrictModel):
    """批量重判请求体。"""

    problem_id: IdStr | None = None
    limit: int = Field(default=20, ge=1, le=500)


class SystemSettingOut(ORMModel):
    """系统设置项（敏感值脱敏）。"""

    id: IdStr
    key: str
    value_json: Any = None
    description: str | None = None
    updated_at: datetime | None = None
    is_sensitive: bool = Field(default=False, description="是否为敏感项（值已脱敏）")


class SystemSettingUpdateRequest(StrictModel):
    """系统设置写入体。"""

    value_json: Any = None
    description: str | None = Field(default=None, max_length=300)


class SessionTypeStat(ORMModel):
    """学习会话按类型聚合项。"""

    session_type: str
    sessions: int = 0
    minutes: int = 0


class SessionOverviewOut(ORMModel):
    """学习会话概览（管理端）。"""

    total_sessions: int = 0
    total_minutes: int = 0
    active_users: int = 0
    by_type: list[SessionTypeStat] = Field(default_factory=list)
