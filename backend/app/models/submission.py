"""提交与判题结果模型：`submissions` / `submission_results`（DATABASE.md §4）。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPkMixin, utc_now
from app.models.enums import RunnerType, SubmissionStatus

# 终态集合：判断是否还需要轮询
TERMINAL_STATUSES: frozenset[str] = frozenset(
    {
        SubmissionStatus.ACCEPTED.value,
        SubmissionStatus.WRONG_ANSWER.value,
        SubmissionStatus.RUNTIME_ERROR.value,
        SubmissionStatus.TIME_LIMIT_EXCEEDED.value,
        SubmissionStatus.MEMORY_LIMIT_EXCEEDED.value,
        SubmissionStatus.COMPILE_ERROR.value,
        SubmissionStatus.SECURITY_ERROR.value,
        SubmissionStatus.INTERNAL_ERROR.value,
    }
)


class Submission(Base, UUIDPkMixin):
    """一次代码提交（同步判题，复杂场景可转异步轮询）。"""

    __tablename__ = "submissions"
    __table_args__ = (
        Index("ix_sub_user_id", "user_id"),
        Index("ix_sub_problem_id", "problem_id"),
        Index("ix_sub_status", "status"),
        Index("ix_sub_created_at", "created_at"),
        Index("ix_sub_problem_status", "problem_id", "status"),
        Index("ix_sub_user_problem", "user_id", "problem_id"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    problem_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("problems.id", ondelete="SET NULL"), nullable=True, doc="客观题也可能为空"
    )
    lesson_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("lessons.id", ondelete="SET NULL"), nullable=True, doc="随堂练习"
    )
    challenge_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("challenges.id", ondelete="SET NULL"), nullable=True
    )
    language: Mapped[str] = mapped_column(String(20), default="python", nullable=False)
    code: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default=SubmissionStatus.PENDING.value, nullable=False)
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    passed_cases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_cases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    time_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False, doc="最大单用例耗时")
    memory_kb: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_type: Mapped[str | None] = mapped_column(String(60), nullable=True, doc="ValueError/IndexError/…")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, doc="截断到 2000 字符")
    runner: Mapped[str] = mapped_column(String(20), default=RunnerType.LOCAL.value, nullable=False)
    judged_by: Mapped[str] = mapped_column(String(20), default=RunnerType.LOCAL.value, nullable=False)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    results: Mapped[list["SubmissionResult"]] = relationship(
        back_populates="submission",
        cascade="all, delete-orphan",
        order_by="SubmissionResult.id",
    )

    @property
    def is_finished(self) -> bool:
        """是否已判题完成（终态）。"""
        return self.status in TERMINAL_STATUSES

    @property
    def is_accepted(self) -> bool:
        """是否通过。"""
        return self.status == SubmissionStatus.ACCEPTED.value

    def finish(self, status: str) -> None:
        """标记判题结束并写入结束时间。"""
        self.status = status
        self.finished_at = utc_now()


class SubmissionResult(Base, UUIDPkMixin):
    """单个测试用例的判题结果（隐藏用例的输出会被脱敏）。"""

    __tablename__ = "submission_results"
    __table_args__ = (Index("ix_sr_submission_id", "submission_id"),)

    submission_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False
    )
    test_case_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("test_cases.id", ondelete="SET NULL"), nullable=True
    )
    passed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    actual_output: Mapped[str | None] = mapped_column(Text, nullable=True, doc="截断 8000 字符")
    expected_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    stdout: Mapped[str | None] = mapped_column(Text, nullable=True)
    stderr: Mapped[str | None] = mapped_column(Text, nullable=True)
    diff: Mapped[str | None] = mapped_column(Text, nullable=True, doc="行级差异")
    time_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    memory_kb: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    message: Mapped[str | None] = mapped_column(String(300), nullable=True)

    submission: Mapped["Submission"] = relationship(back_populates="results")


# 复合索引：用户最近提交（DESC），用于「我的提交」列表分页
Index("ix_sub_user_created", Submission.user_id, Submission.created_at.desc())
