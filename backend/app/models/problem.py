"""题目与判题用例模型：`problems` / `test_cases` / `tags` / `problem_tags`（DATABASE.md §3）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPkMixin, utc_now
from app.models.enums import ComparisonMode, Difficulty, ProblemCategory, ProblemType, TagKind


class Problem(Base, UUIDPkMixin, TimestampMixin):
    """题目主表（7 种题型统一建模，客观题答案存 `answer_json`）。"""

    __tablename__ = "problems"
    __table_args__ = (
        Index("ix_problems_slug", "slug", unique=True),
        Index("ix_problems_title", "title"),
        Index("ix_problems_type", "problem_type"),
        Index("ix_problems_difficulty", "difficulty"),
        Index("ix_problems_category", "category"),
        Index("ix_problems_published", "is_published"),
        Index("ix_problems_acceptance", "acceptance_rate"),
        Index("ix_problems_created_at", "created_at"),
    )

    slug: Mapped[str] = mapped_column(String(150), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    statement_md: Mapped[str] = mapped_column(Text, default="", nullable=False, doc="题干（含输入/输出/约束/样例）")
    problem_type: Mapped[str] = mapped_column(String(20), default=ProblemType.CODING.value, nullable=False)
    difficulty: Mapped[str] = mapped_column(String(20), default=Difficulty.EASY.value, nullable=False)
    category: Mapped[str] = mapped_column(String(40), default=ProblemCategory.BASICS.value, nullable=False)
    input_format: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_format: Mapped[str | None] = mapped_column(Text, nullable=True)
    sample_input: Mapped[str | None] = mapped_column(Text, nullable=True)
    sample_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    constraints: Mapped[str | None] = mapped_column(Text, nullable=True)
    options_json: Mapped[Any | None] = mapped_column(JSON, nullable=True, doc="选择题选项 / 填空题空位定义")
    answer_json: Mapped[Any | None] = mapped_column(JSON, nullable=True, doc="客观题标准答案")
    hint_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    solution_md: Mapped[str | None] = mapped_column(Text, nullable=True, doc="题解（默认不展示）")
    starter_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_solution: Mapped[str | None] = mapped_column(Text, nullable=True, doc="判题参考 / AI 讲解用")
    buggy_code: Mapped[str | None] = mapped_column(Text, nullable=True, doc="debug 题型的错误代码")
    time_limit_ms: Mapped[int] = mapped_column(Integer, default=5000, nullable=False, doc="clamp 1000-10000")
    memory_limit_mb: Mapped[int] = mapped_column(Integer, default=256, nullable=False, doc="clamp 32-512")
    score: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    xp_reward: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    submission_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    accepted_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    acceptance_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, doc="冗余，通过率")
    avg_time_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    test_cases: Mapped[list["TestCase"]] = relationship(
        back_populates="problem",
        cascade="all, delete-orphan",
        order_by="TestCase.order_index",
    )
    problem_tags: Mapped[list["ProblemTag"]] = relationship(
        back_populates="problem",
        cascade="all, delete-orphan",
    )

    @property
    def is_objective(self) -> bool:
        """是否为客观题（选择 / 判断 / 填空）。"""
        return self.problem_type in (ProblemType.CHOICE.value, ProblemType.JUDGE.value, ProblemType.BLANK.value)

    @property
    def sample_cases(self) -> list["TestCase"]:
        """样例用例（可对前端展示）。"""
        return [case for case in (self.test_cases or []) if case.is_sample]

    def refresh_acceptance_rate(self) -> float:
        """按提交与通过计数重算通过率（0.0-1.0）。"""
        total = int(self.submission_count or 0)
        self.acceptance_rate = round((int(self.accepted_count or 0) / total), 4) if total else 0.0
        return self.acceptance_rate

    def clamp_limits(self) -> None:
        """把时间/内存限制收敛到安全区间（1000-10000ms / 32-512MB）。"""
        self.time_limit_ms = max(1000, min(10_000, int(self.time_limit_ms or 5000)))
        self.memory_limit_mb = max(32, min(512, int(self.memory_limit_mb or 256)))


class TestCase(Base, UUIDPkMixin):
    """判题测试用例。"""

    __tablename__ = "test_cases"
    __table_args__ = (
        Index("ix_tc_problem_id", "problem_id"),
        Index("ix_tc_is_sample", "is_sample"),
        Index("ix_tc_order", "order_index"),
    )

    problem_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("problems.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    input: Mapped[str] = mapped_column(Text, default="", nullable=False, doc="标准输入")
    expected_output: Mapped[str] = mapped_column(Text, default="", nullable=False)
    comparison: Mapped[str] = mapped_column(String(20), default=ComparisonMode.TRIMMED.value, nullable=False)
    float_tolerance: Mapped[float | None] = mapped_column(Float, default=1e-6, nullable=True)
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, doc="样例（前端可展示）")
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    weight: Mapped[int] = mapped_column(Integer, default=1, nullable=False, doc="计分权重")
    timeout_ms: Mapped[int | None] = mapped_column(Integer, nullable=True, doc="覆盖题目默认超时")
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    problem: Mapped["Problem"] = relationship(back_populates="test_cases")

    @property
    def display_name(self) -> str:
        """用例展示名（缺省用「用例 N」）。"""
        return self.name or f"用例 {self.order_index}"

    def effective_timeout_ms(self, default_ms: int) -> int:
        """生效超时：用例级覆盖优先，否则用题目默认。"""
        return int(self.timeout_ms or default_ms)


class Tag(Base, UUIDPkMixin):
    """标签（题目 / 课程 / 项目 / 课时 / 片段共用）。"""

    __tablename__ = "tags"
    __table_args__ = (
        Index("ix_tags_slug", "slug", unique=True),
        Index("ix_tags_kind", "kind"),
    )

    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    kind: Mapped[str] = mapped_column(String(20), default=TagKind.PROBLEM.value, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    problem_tags: Mapped[list["ProblemTag"]] = relationship(
        back_populates="tag",
        cascade="all, delete-orphan",
    )


class ProblemTag(Base):
    """题目 ↔ 标签 关联表。"""

    __tablename__ = "problem_tags"
    __table_args__ = (Index("ix_pt_tag_id", "tag_id"),)

    problem_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("problems.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    problem: Mapped["Problem"] = relationship(back_populates="problem_tags")
    tag: Mapped["Tag"] = relationship(back_populates="problem_tags")
