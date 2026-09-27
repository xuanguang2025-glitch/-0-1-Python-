"""考试 Schema（`docs/API.md` §2.20）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.common import IdStr, ORMModel, StrictModel


class ExamBrief(ORMModel):
    """试卷列表项（含我的最好成绩）。"""

    id: IdStr
    code: str
    title: str
    level: str = "basic"
    duration_minutes: int = 60
    total_score: int = 100
    pass_score: int = 60
    question_count: int = 0
    my_best_score: int | None = None
    my_passed: bool = False


class ExamQuestionOut(ORMModel):
    """考试题目（**不含答案**）。"""

    problem_id: IdStr
    title: str = ""
    problem_type: str = "coding"
    difficulty: str = "easy"
    score: int = 0
    statement_md: str = ""
    options_json: Any | None = None
    starter_code: str | None = None
    sample_input: str | None = None
    sample_output: str | None = None


class ExamDetail(ORMModel):
    """试卷详情（不含答案）。"""

    exam: ExamBrief
    questions: list[ExamQuestionOut] = Field(default_factory=list)


class ExamAttemptOut(ORMModel):
    """开始考试后的作答会话。"""

    attempt_id: IdStr
    exam_id: IdStr
    deadline_at: datetime
    remaining_seconds: int = 0
    questions: list[ExamQuestionOut] = Field(default_factory=list)


class ExamSubmitRequest(StrictModel):
    """交卷请求体。"""

    attempt_id: IdStr
    answers: dict[str, Any] = Field(default_factory=dict, description="{problem_id: value}")


class ExamPerQuestionResult(ORMModel):
    """逐题判分结果。"""

    problem_id: str
    correct: bool = False
    score: int = 0
    expected: Any | None = None


class ExamReportOut(ORMModel):
    """考试报告。"""

    attempt_id: IdStr | None = None
    exam_id: IdStr | None = None
    score: int = 0
    total_score: int = 100
    passed: bool = False
    per_question: list[ExamPerQuestionResult] = Field(default_factory=list)
    weak_topics: list[dict[str, Any]] = Field(default_factory=list)
    submitted_at: datetime | None = None


class ExamAttemptBrief(ORMModel):
    """作答历史项。"""

    id: IdStr
    exam_id: IdStr
    exam_title: str | None = None
    status: str = "in_progress"
    score: int = 0
    passed: bool = False
    started_at: datetime | None = None
    submitted_at: datetime | None = None


class ExamSaveOut(ORMModel):
    """中途保存作答的响应体。"""

    attempt_id: IdStr
    saved: int = 0
    remaining_seconds: int = 0
    status: str = "in_progress"
