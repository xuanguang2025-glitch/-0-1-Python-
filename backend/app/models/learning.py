"""学习过程模型：进度 / 掌握度 / 错题本 / 收藏 / 代码历史 / 学习会话（DATABASE.md §6）。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import MASTERY_CORRECT_GAIN, MASTERY_REVIEW_INTERVAL_DAYS, MASTERY_WRONG_DECAY, mastery_level_of
from app.db.base import Base, TimestampMixin, UUIDPkMixin, utc_now
from app.models.enums import (
    BookmarkKind,
    CodeContextType,
    CodeSource,
    LearningMode,
    MistakeErrorType,
    MasteryLevel,
    ProgressStatus,
    SessionType,
)
from app.utils.time import add_days

if TYPE_CHECKING:
    from app.models.course import Lesson, Topic
    from app.models.user import User


class LearningProgress(Base, UUIDPkMixin):
    """用户对单个课时的学习进度。"""

    __tablename__ = "learning_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "lesson_id", name="uq_lp_user_lesson"),
        Index("ix_lp_user_id", "user_id"),
        Index("ix_lp_lesson_id", "lesson_id"),
        Index("ix_lp_status", "status"),
        Index("ix_lp_completed_at", "completed_at"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    lesson_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default=ProgressStatus.NOT_STARTED.value, nullable=False)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    time_spent_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    code_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True, doc="最近一次编辑器内容")
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    user: Mapped["User"] = relationship()
    lesson: Mapped["Lesson"] = relationship(back_populates="progresses")

    @property
    def is_completed(self) -> bool:
        """是否已完成。"""
        return self.status == ProgressStatus.COMPLETED.value

    def touch(self, percent: int, seconds: int = 0) -> None:
        """更新进度百分比与累计时长，并维护状态与时间戳。"""
        self.progress_percent = max(0, min(100, int(percent)))
        self.time_spent_seconds = int(self.time_spent_seconds or 0) + max(0, int(seconds))
        if self.started_at is None:
            self.started_at = utc_now()
        if self.progress_percent >= 100:
            self.status = ProgressStatus.COMPLETED.value
            if self.completed_at is None:
                self.completed_at = utc_now()
        elif self.progress_percent > 0:
            self.status = ProgressStatus.IN_PROGRESS.value


class KnowledgeMastery(Base, UUIDPkMixin):
    """知识点掌握度（SM-2 简化算法）。"""

    __tablename__ = "knowledge_mastery"
    __table_args__ = (
        UniqueConstraint("user_id", "topic_id", name="uq_km_user_topic"),
        Index("ix_km_user_id", "user_id"),
        Index("ix_km_topic_id", "topic_id"),
        Index("ix_km_level", "mastery_level"),
        Index("ix_km_score", "mastery_score"),
        Index("ix_km_next_review", "next_review_at"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    topic_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("topics.id", ondelete="CASCADE"), nullable=False
    )
    mastery_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, doc="0-100")
    mastery_level: Mapped[str] = mapped_column(String(20), default=MasteryLevel.NONE.value, nullable=False)
    practiced_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    correct_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mistake_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_practiced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    user: Mapped["User"] = relationship()
    topic: Mapped["Topic"] = relationship()

    def apply_result(self, correct: bool) -> float:
        """应用一次答题结果，更新分数 / 级别 / 复习时间，返回最新分数。

        算法（DATABASE.md §6.2）：正确 `score += (100-score)*0.2`；
        错误 `score -= score*0.25`；级别由分数阈值推导，复习间隔按级别递增。
        """
        score = float(self.mastery_score or 0.0)
        if correct:
            score += (100.0 - score) * MASTERY_CORRECT_GAIN
            self.correct_count = int(self.correct_count or 0) + 1
        else:
            score -= score * MASTERY_WRONG_DECAY
            self.mistake_count = int(self.mistake_count or 0) + 1
            score = max(0.0, score)

        self.mastery_score = round(min(100.0, max(0.0, score)), 2)
        self.mastery_level = mastery_level_of(self.mastery_score)
        self.practiced_count = int(self.practiced_count or 0) + 1
        now = utc_now()
        self.last_practiced_at = now
        self.next_review_at = add_days(now, MASTERY_REVIEW_INTERVAL_DAYS.get(self.mastery_level, 1))
        return self.mastery_score

    @property
    def needs_review(self) -> bool:
        """是否到达复习时间。"""
        if self.next_review_at is None:
            return False
        return self.next_review_at <= utc_now()


class Mistake(Base, UUIDPkMixin, TimestampMixin):
    """错题本条目。"""

    __tablename__ = "mistakes"
    __table_args__ = (
        Index("ix_mk_user_id", "user_id"),
        Index("ix_mk_problem_id", "problem_id"),
        Index("ix_mk_resolved", "resolved"),
        Index("ix_mk_next_review", "next_review_at"),
        Index("ix_mk_error_type", "error_type"),
        Index("ix_mk_created_at", "created_at"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    problem_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("problems.id", ondelete="SET NULL"), nullable=True
    )
    submission_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("submissions.id", ondelete="SET NULL"), nullable=True
    )
    lesson_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    topic_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("topics.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    question_snapshot_md: Mapped[str | None] = mapped_column(Text, nullable=True, doc="题干快照（题目可改）")
    user_answer: Mapped[str | None] = mapped_column(Text, nullable=True, doc="用户答案/代码")
    correct_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_type: Mapped[str] = mapped_column(
        String(30), default=MistakeErrorType.LOGIC.value, nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    note_md: Mapped[str | None] = mapped_column(Text, nullable=True, doc="用户笔记")
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship()

    def resolve(self, resolved: bool = True) -> None:
        """标记已掌握 / 取消掌握。"""
        self.resolved = bool(resolved)
        self.resolved_at = utc_now() if resolved else None

    def schedule_review(self, days: int = 1) -> None:
        """安排下一次复习并累加复习次数。"""
        self.review_count = int(self.review_count or 0) + 1
        self.next_review_at = add_days(utc_now(), days)


class Bookmark(Base, UUIDPkMixin):
    """收藏 / 代码片段库。"""

    __tablename__ = "bookmarks"
    __table_args__ = (
        Index("ix_bm_user_id", "user_id"),
        Index("ix_bm_kind", "kind"),
        Index("ix_bm_collection", "collection"),
        Index("ix_bm_ref", "ref_id"),
        Index("ix_bm_created_at", "created_at"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(20), default=BookmarkKind.PROBLEM.value, nullable=False)
    ref_id: Mapped[str | None] = mapped_column(String(36), nullable=True, doc="被收藏对象 id")
    title: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    code_snippet: Mapped[str | None] = mapped_column(Text, nullable=True, doc="kind=snippet 时必填")
    language: Mapped[str] = mapped_column(String(20), default="python", nullable=False)
    collection: Mapped[str] = mapped_column(String(50), default="default", nullable=False, doc="集合名")
    tags_json: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    user: Mapped["User"] = relationship()

    @property
    def tags(self) -> list[str]:
        """标签列表（缺省为空）。"""
        return [str(item) for item in (self.tags_json or [])]


class CodeHistory(Base, UUIDPkMixin):
    """代码历史版本（同一上下文保留最近 30 版，见 DATABASE.md §6.5）。"""

    __tablename__ = "code_history"
    __table_args__ = (
        Index("ix_ch_user_id", "user_id"),
        Index("ix_ch_context", "context_type", "context_id"),
        Index("ix_ch_created_at", "created_at"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    context_type: Mapped[str] = mapped_column(
        String(20), default=CodeContextType.PLAYGROUND.value, nullable=False
    )
    context_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    file_path: Mapped[str] = mapped_column(String(255), default="main.py", nullable=False)
    code: Mapped[str] = mapped_column(Text, default="", nullable=False)
    label: Mapped[str | None] = mapped_column(String(120), nullable=True, doc="「提交前」「自动保存」")
    version_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False, doc="同上下文递增")
    parent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("code_history.id", ondelete="SET NULL"), nullable=True, doc="版本链"
    )
    source: Mapped[str] = mapped_column(String(20), default=CodeSource.MANUAL.value, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    user: Mapped["User"] = relationship()

    @property
    def line_count(self) -> int:
        """代码行数（按换行切分）。"""
        return len((self.code or "").splitlines())


class LearningSession(Base, UUIDPkMixin):
    """学习会话（用于时长统计与热力图）。"""

    __tablename__ = "learning_sessions"
    __table_args__ = (
        Index("ix_ls_user_id", "user_id"),
        Index("ix_ls_started_at", "started_at"),
        Index("ix_ls_mode", "learning_mode"),
        Index("ix_ls_type", "session_type"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    session_type: Mapped[str] = mapped_column(String(20), default=SessionType.LESSON.value, nullable=False)
    learning_mode: Mapped[str] = mapped_column(String(20), default=LearningMode.SYSTEM.value, nullable=False)
    ref_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    xp_earned: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    actions_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, doc="提交 / 运行次数")

    user: Mapped["User"] = relationship()

    def close(self, *, duration_seconds: int | None = None) -> int:
        """结束会话并返回本次时长（秒）。"""
        now = utc_now()
        self.ended_at = now
        if duration_seconds is not None:
            self.duration_seconds = max(0, int(duration_seconds))
        else:
            self.duration_seconds = max(0, int((now - self.started_at).total_seconds()))
        return self.duration_seconds
