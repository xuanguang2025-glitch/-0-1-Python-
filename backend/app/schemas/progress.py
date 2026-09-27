"""学习进度与掌握度 Schema（`docs/API.md` §2.11）。

除既有契约外，补充：
- `LearningDashboardOut`：学习看板概览（今日 / 本周时长、连续天数、等级 XP、完成度等）；
- 学习会话相关请求 / 响应体（开始 / 心跳 / 结束）。
"""

from __future__ import annotations

from datetime import date as DateType
from datetime import datetime

from pydantic import Field, field_validator

from app.models.enums import LearningMode, SessionType
from app.schemas.common import IdStr, ORMModel, StrictModel


class CourseProgressItem(ORMModel):
    """进度总览中的单个阶段。"""

    course_id: IdStr
    slug: str | None = None
    stage_no: int = 0
    title: str = ""
    percent: int = 0
    completed_lessons: int = 0
    total_lessons: int = 0
    last_lesson_id: str | None = None


class ProgressOverviewOut(ORMModel):
    """`GET /progress` 响应体。"""

    courses: list[CourseProgressItem] = Field(default_factory=list)
    completed_lessons: int = 0
    total_lessons: int = 0
    overall_percent: int = 0
    current_stage: int | None = None


class CourseProgressOut(ORMModel):
    """`GET /progress/courses/{id}` 响应体。"""

    course_id: IdStr
    percent: int = 0
    completed_lessons: list[str] = Field(default_factory=list)
    last_lesson_id: str | None = None


class KnowledgeMasteryOut(ORMModel):
    """单个知识点掌握度。"""

    id: IdStr | None = None
    topic_id: IdStr
    name: str | None = None
    mastery_score: float = 0.0
    mastery_level: str = "none"
    practiced_count: int = 0
    correct_count: int = 0
    mistake_count: int = 0
    last_practiced_at: datetime | None = None
    next_review_at: datetime | None = None


class MasteryOverviewOut(ORMModel):
    """`GET /progress/mastery` 响应体。"""

    topics: list[KnowledgeMasteryOut] = Field(default_factory=list)
    weak_topics: list[KnowledgeMasteryOut] = Field(default_factory=list)
    average_score: float = 0.0


class MasteryPracticeRequest(StrictModel):
    """`POST /progress/mastery/{topic_id}` 请求体。"""

    correct: bool


class HeatmapPoint(ORMModel):
    """热力图单日数据。"""

    date: DateType
    count: int = 0
    minutes: int = 0


class HeatmapOut(ORMModel):
    """热力图响应体。"""

    points: list[HeatmapPoint] = Field(default_factory=list)
    total_count: int = 0
    active_days: int = 0
    max_count: int = 0


class ModeUpdateRequest(StrictModel):
    """学习模式切换请求体。"""

    learning_mode: str = Field(..., description="free/system/exam/drill/project/challenge/ai")

    @field_validator("learning_mode")
    @classmethod
    def _check_mode(cls, value: str) -> str:
        """校验学习模式取值合法（枚举白名单）。"""
        if not LearningMode.has(value):
            raise ValueError(f"learning_mode 必须是 {LearningMode.values()} 之一")
        return value


class ModeOut(ORMModel):
    """学习模式响应体。"""

    learning_mode: str = "system"


class LearningDashboardOut(ORMModel):
    """学习看板概览（`GET /progress/dashboard`）。"""

    today_minutes: int = 0
    week_minutes: int = 0
    streak_days: int = 0
    max_streak_days: int = 0
    level: int = 1
    xp: int = 0
    next_level_xp: int = 0
    completed_lessons: int = 0
    total_lessons: int = 0
    completed_courses: int = 0
    total_courses: int = 0
    overall_percent: int = 0
    solved_problems: int = 0
    submissions: int = 0
    projects_completed: int = 0
    projects_total: int = 0
    current_stage: int | None = None


class LearningSessionOut(ORMModel):
    """学习会话响应体。"""

    id: IdStr
    session_type: str = "lesson"
    learning_mode: str = "system"
    ref_id: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_seconds: int = 0
    xp_earned: int = 0
    actions_count: int = 0


class LearningSessionStartRequest(StrictModel):
    """开始学习会话请求体。"""

    session_type: str = Field(default=SessionType.LESSON.value, description="lesson/problem/project/exam/playground/challenge/ai")
    learning_mode: str = Field(default=LearningMode.SYSTEM.value, description="free/system/exam/drill/project/challenge/ai")
    ref_id: str | None = Field(default=None, max_length=64)

    @field_validator("session_type")
    @classmethod
    def _check_type(cls, value: str) -> str:
        """校验会话类型合法。"""
        if not SessionType.has(value):
            raise ValueError(f"session_type 必须是 {SessionType.values()} 之一")
        return value

    @field_validator("learning_mode")
    @classmethod
    def _check_mode(cls, value: str) -> str:
        """校验学习模式合法。"""
        if not LearningMode.has(value):
            raise ValueError(f"learning_mode 必须是 {LearningMode.values()} 之一")
        return value


class LearningSessionHeartbeatRequest(StrictModel):
    """会话心跳请求体（累加时长 / 行为数 / 经验）。"""

    seconds: int = Field(default=0, ge=0, le=3600)
    actions: int = Field(default=0, ge=0, le=10_000)
    xp_earned: int = Field(default=0, ge=0, le=100_000)


class LearningSessionEndRequest(StrictModel):
    """结束会话请求体。"""

    duration_seconds: int | None = Field(default=None, ge=0, le=86_400)
    actions_count: int | None = Field(default=None, ge=0, le=1_000_000)
