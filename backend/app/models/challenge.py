"""挑战模型：`challenges` / `user_challenges`（DATABASE.md §9.1-9.2）。"""

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
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPkMixin, utc_now
from app.models.enums import ChallengeStatus, ChallengeType, Difficulty


class Challenge(Base, UUIDPkMixin, TimestampMixin):
    """挑战赛（日赛 / 周赛 / 月赛 / 特别赛）。"""

    __tablename__ = "challenges"
    __table_args__ = (
        Index("ix_challenges_slug", "slug", unique=True),
        Index("ix_challenges_type", "challenge_type"),
        Index("ix_challenges_start", "start_at"),
        Index("ix_challenges_end", "end_at"),
        Index("ix_challenges_published", "is_published"),
    )

    slug: Mapped[str] = mapped_column(String(150), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    challenge_type: Mapped[str] = mapped_column(
        String(20), default=ChallengeType.DAILY.value, nullable=False
    )
    difficulty: Mapped[str] = mapped_column(String(20), default=Difficulty.EASY.value, nullable=False)
    problem_ids_json: Mapped[Any] = mapped_column(JSON, default=list, nullable=False, doc="题目 id 数组")
    rules_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    xp_reward: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    participant_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user_challenges: Mapped[list["UserChallenge"]] = relationship(
        back_populates="challenge",
        cascade="all, delete-orphan",
    )

    @property
    def problem_ids(self) -> list[str]:
        """题目 id 列表。"""
        return [str(item) for item in (self.problem_ids_json or [])]

    @property
    def is_open(self) -> bool:
        """挑战是否仍在进行中（未结束）。"""
        return self.end_at is not None and self.end_at > utc_now()

    @property
    def is_closed(self) -> bool:
        """挑战是否已结束。"""
        return not self.is_open


class UserChallenge(Base, UUIDPkMixin):
    """用户参与挑战的成绩（排行榜排序键：score 降序 + 用时升序）。"""

    __tablename__ = "user_challenges"
    __table_args__ = (
        UniqueConstraint("user_id", "challenge_id", name="uq_uc_user_challenge"),
        Index("ix_uc_user_id", "user_id"),
        Index("ix_uc_challenge_id", "challenge_id"),
        Index("ix_uc_status", "status"),
        Index("ix_uc_score", "score"),
        Index("ix_uc_rank", "rank"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    challenge_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default=ChallengeStatus.JOINED.value, nullable=False)
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False, doc="排行榜排序键")
    passed_cases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_time_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False, doc="用时（升序优先）")
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True, doc="结算后写入")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    user: Mapped["User"] = relationship()  # type: ignore[name-defined]
    challenge: Mapped["Challenge"] = relationship(back_populates="user_challenges")

    def apply_result(self, score: int, passed_cases: int, total_time_ms: int) -> None:
        """记录一次挑战成绩（保留历史最优）。"""
        if score > int(self.score or 0) or (
            score == int(self.score or 0) and total_time_ms < int(self.total_time_ms or 0)
        ):
            self.score = int(score)
            self.total_time_ms = int(total_time_ms)
        self.passed_cases = max(int(self.passed_cases or 0), int(passed_cases))
        self.status = ChallengeStatus.COMPLETED.value
        self.submitted_at = utc_now()
