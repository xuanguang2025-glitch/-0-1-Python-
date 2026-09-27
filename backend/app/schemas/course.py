"""课程 / 章节 / 课时 / 知识点 Schema（`docs/API.md` §2.3-2.4）。

本模块在既有契约基础上，按前端 `/lesson/[id]` 页面的明确需求扩展了课时详情：
`LessonDetail` 额外携带所属课程/章节定位信息（`course_id/course_title/course_slug/
chapter_title/chapter_index/lesson_index/total_lessons`）、精简导航（`prev_lesson/
next_lesson`）以及一次性可拿到的完整章节目录 `course_outline`。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.common import IdStr, ORMModel, StrictModel


class TopicOut(ORMModel):
    """知识点响应体。"""

    id: IdStr
    slug: str
    name: str
    parent_id: str | None = None
    description: str | None = None
    order_index: int = 0
    is_primary: bool = False
    mastery_score: float | None = None
    mastery_level: str | None = None


class LessonBrief(ORMModel):
    """课时列表项（不含正文）。"""

    id: IdStr
    chapter_id: IdStr
    slug: str
    title: str
    summary: str | None = None
    lesson_type: str = "concept"
    difficulty: str = "easy"
    estimated_minutes: int = 15
    order_index: int = 0
    xp_reward: int = 10
    has_playground: bool = True
    is_published: bool = True
    progress_percent: int = 0
    status: str = "not_started"


class LessonNav(ORMModel):
    """课时导航项（仅 id/title/slug，供上一节 / 下一节跳转）。"""

    id: IdStr
    title: str
    slug: str


class LessonDetail(ORMModel):
    """课时详情（含正文、前后导航、所属课程章节定位与完整目录）。"""

    id: IdStr
    chapter_id: IdStr
    slug: str
    title: str
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
    topics: list[TopicOut] = Field(default_factory=list)
    prev: LessonBrief | None = None
    next: LessonBrief | None = None
    progress: "LearningProgressOut | None" = None

    # ---- 前端左侧完整章节目录所需的定位信息 ----
    course_id: str | None = None
    course_title: str | None = None
    course_slug: str | None = None
    chapter_title: str | None = None
    chapter_index: int = 0
    lesson_index: int = 0
    total_lessons: int = 0
    prev_lesson: LessonNav | None = None
    next_lesson: LessonNav | None = None
    course_outline: list["ChapterOut"] = Field(default_factory=list)


class ChapterOut(ORMModel):
    """章节响应体（含课时列表）。"""

    id: IdStr
    course_id: IdStr
    slug: str
    title: str
    summary_md: str | None = None
    order_index: int = 0
    lesson_count: int = 0
    is_published: bool = True
    lessons: list[LessonBrief] = Field(default_factory=list)


class CourseBrief(ORMModel):
    """阶段列表项。"""

    id: IdStr
    slug: str
    stage_no: int
    title: str
    subtitle: str | None = None
    level: str = "beginner"
    icon: str | None = None
    cover_url: str | None = None
    estimated_hours: int = 0
    lesson_count: int = 0
    order_index: int = 0
    is_published: bool = True
    progress_percent: int = 0


class StageOut(ORMModel):
    """18 阶段概览（`GET /courses/stages`）。"""

    stage_no: int
    slug: str
    title: str
    subtitle: str | None = None
    level: str = "beginner"
    icon: str | None = None
    lesson_count: int = 0
    estimated_hours: int = 0
    progress_percent: int = 0
    is_current: bool = False


class CourseDetail(ORMModel):
    """阶段详情（含章节树与我的进度）。"""

    course: CourseBrief
    chapters: list[ChapterOut] = Field(default_factory=list)
    progress: "CourseProgressOut | None" = None


class CourseProgressOut(ORMModel):
    """某个阶段的进度摘要。"""

    course_id: IdStr
    percent: int = 0
    completed_lessons: int = 0
    total_lessons: int = 0
    last_lesson_id: str | None = None


class CourseEnrollmentOut(ORMModel):
    """报名结果。"""

    id: IdStr
    user_id: IdStr
    course_id: IdStr
    progress_percent: int = 0
    completed_lessons: int = 0
    last_lesson_id: str | None = None
    status: str = "not_started"
    enrolled_at: datetime | None = None
    completed_at: datetime | None = None


class LearningProgressOut(ORMModel):
    """课时进度响应体。"""

    id: IdStr
    lesson_id: IdStr
    status: str = "not_started"
    progress_percent: int = 0
    time_spent_seconds: int = 0
    attempt_count: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime | None = None


class LessonProgressRequest(StrictModel):
    """上报课时进度请求体。"""

    progress_percent: int = Field(..., ge=0, le=100)
    time_spent_seconds: int | None = Field(default=None, ge=0, le=86_400)
    code_snapshot: str | None = Field(default=None, max_length=200_000)


class LessonCompleteRequest(StrictModel):
    """完成课时请求体。"""

    time_spent_seconds: int | None = Field(default=None, ge=0, le=86_400)


class LessonCompleteOut(ORMModel):
    """完成课时响应体。"""

    progress: LearningProgressOut
    xp_earned: int = 0
    level_up: bool = False
    unlocked_achievements: list[str] = Field(default_factory=list)


class QuizAnswer(StrictModel):
    """单道随堂练习作答。"""

    qid: str = Field(..., min_length=1, max_length=64)
    value: str | int | bool | list[str] | None = None


class QuizSubmitRequest(StrictModel):
    """随堂练习提交请求体。"""

    answers: list[QuizAnswer] = Field(default_factory=list, max_length=50)


class QuizResultDetail(ORMModel):
    """随堂练习逐题结果。"""

    qid: str
    correct: bool = False
    expected: Any | None = None
    explain: str | None = None


class QuizResultOut(ORMModel):
    """随堂练习判分结果。"""

    correct_count: int = 0
    total: int = 0
    passed: bool = False
    details: list[QuizResultDetail] = Field(default_factory=list)


# 解决前向引用（LessonDetail.progress / course_outline，CourseDetail.progress）
LessonDetail.model_rebuild()
CourseDetail.model_rebuild()
