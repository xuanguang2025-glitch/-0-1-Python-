"""考试模型：`exams` / `exam_attempts`（DATABASE.md §9.3-9.4）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPkMixin, utc_now
from app.models.enums import ExamAttemptStatus, ExamLevel


class Exam(Base, UUIDPkMixin, TimestampMixin):
    """试卷定义（题目与分值存 `question_ids_json`）。"""

    __tablename__ = "exams"
    __table_args__ = (
        Index("ix_exams_code", "code", unique=True),
        Index("ix_exams_level", "level"),
        Index("ix_exams_published", "is_published"),
    )

    code: Mapped[str] = mapped_column(String(60), nullable=False, doc="如 py-basic-01")
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    level: Mapped[str] = mapped_column(String(20), default=ExamLevel.BASIC.value, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    total_score: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    pass_score: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    question_ids_json: Mapped[Any] = mapped_column(JSON, default=list, nullable=False, doc="题目 id + 分值")
    shuffle: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    attempts: Mapped[list["ExamAttempt"]] = relationship(
        back_populates="exam",
        cascade="all, delete-orphan",
    )

    @property
    def question_specs(self) -> list[dict[str, Any]]:
        """题目与分值定义列表。"""
        return [dict(item) for item in (self.question_ids_json or []) if isinstance(item, dict)]

    @property
    def problem_ids(self) -> list[str]:
        """全部题目 id。"""
        ids: list[str] = []
        for item in self.question_ids_json or []:
            if isinstance(item, dict) and item.get("id"):
                ids.append(str(item["id"]))
            elif isinstance(item, str):
                ids.append(item)
        return ids


class ExamAttempt(Base, UUIDPkMixin):
    """一次考试作答记录（服务端计时，`deadline_at` 为准）。"""

    __tablename__ = "exam_attempts"
    __table_args__ = (
        Index("ix_ea_user_id", "user_id"),
        Index("ix_ea_exam_id", "exam_id"),
        Index("ix_ea_status", "status"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    exam_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("exams.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), default=ExamAttemptStatus.IN_PROGRESS.value, nullable=False
    )
    answers_json: Mapped[Any] = mapped_column(JSON, default=dict, nullable=False, doc="{problem_id: {answer/code}}")
    report_json: Mapped[Any | None] = mapped_column(JSON, nullable=True, doc="逐题结果 + 知识点分析")
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, doc="服务端计时")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship()  # type: ignore[name-defined]
    exam: Mapped["Exam"] = relationship(back_populates="attempts")

    @property
    def is_expired(self) -> bool:
        """是否已超过截止时间。"""
        return self.deadline_at is not None and self.deadline_at <= utc_now()

    @property
    def remaining_seconds(self) -> int:
        """剩余作答秒数（非负）。"""
        if self.deadline_at is None:
            return 0
        return max(0, int((self.deadline_at - utc_now()).total_seconds()))

    def grade(self, score: int, passed: bool, report: dict[str, Any]) -> None:
        """交卷：写入成绩、报告与状态。"""
        self.score = int(score)
        self.passed = bool(passed)
        self.report_json = report
        self.status = ExamAttemptStatus.GRADED.value
        self.submitted_at = utc_now()

    def abandon(self) -> None:
        """放弃作答（超时未交卷等）。"""
        self.status = ExamAttemptStatus.ABANDONED.value
        self.submitted_at = utc_now()
