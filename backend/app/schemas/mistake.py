"""错题本 Schema（`docs/API.md` §2.18）。"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.common import IdStr, ORMModel, StrictModel


class MistakeCreateRequest(StrictModel):
    """新增错题请求体。"""

    problem_id: IdStr | None = None
    submission_id: IdStr | None = None
    lesson_id: IdStr | None = None
    topic_id: IdStr | None = None
    title: str = Field(default="", max_length=200)
    user_answer: str | None = Field(default=None, max_length=200_000)
    correct_answer: str | None = Field(default=None, max_length=200_000)
    error_type: str = Field(default="logic", description="concept/syntax/logic/runtime/timeout/style/output")
    error_message: str | None = Field(default=None, max_length=10_000)
    note_md: str | None = Field(default=None, max_length=10_000)


class MistakeUpdateRequest(StrictModel):
    """更新错题请求体。"""

    note_md: str | None = Field(default=None, max_length=10_000)
    topic_id: IdStr | None = None


class MistakeResolveRequest(StrictModel):
    """标记掌握请求体。"""

    resolved: bool = True


class MistakeOut(ORMModel):
    """错题响应体。"""

    id: IdStr
    problem_id: str | None = None
    submission_id: str | None = None
    lesson_id: str | None = None
    topic_id: str | None = None
    title: str = ""
    question_snapshot_md: str | None = None
    user_answer: str | None = None
    correct_answer: str | None = None
    error_type: str = "logic"
    error_message: str | None = None
    note_md: str | None = None
    resolved: bool = False
    resolved_at: datetime | None = None
    review_count: int = 0
    next_review_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
