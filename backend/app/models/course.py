"""课程内容模型：`courses` / `chapters` / `lessons` / `topics` / `lesson_topics` / `course_enrollments`。

对应 DATABASE.md §2，级联规则：Course → Chapter → Lesson 逐级 `ON DELETE CASCADE`。
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

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
from app.models.enums import CourseLevel, Difficulty, LessonType, ProgressStatus

if TYPE_CHECKING:
    from app.models.user import User


class Course(Base, UUIDPkMixin, TimestampMixin):
    """课程（= 学习阶段，共 18 个）。"""

    __tablename__ = "courses"
    __table_args__ = (
        Index("ix_courses_slug", "slug", unique=True),
        Index("ix_courses_stage_no", "stage_no", unique=True),
        Index("ix_courses_level", "level"),
        Index("ix_courses_published", "is_published"),
        Index("ix_courses_order", "order_index"),
    )

    slug: Mapped[str] = mapped_column(String(120), nullable=False, doc="如 stage-01-python-basics")
    stage_no: Mapped[int] = mapped_column(Integer, nullable=False, doc="阶段序号 1..18")
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(300), nullable=True)
    description_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    level: Mapped[str] = mapped_column(String(20), default=CourseLevel.BEGINNER.value, nullable=False)
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True, doc="lucide 图标名")
    cover_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    estimated_hours: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lesson_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, doc="冗余字段，seed 时计算")
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    chapters: Mapped[list["Chapter"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="Chapter.order_index",
    )
    enrollments: Mapped[list["CourseEnrollment"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
    )

    @property
    def chapter_count(self) -> int:
        """章节数量（内存中已加载时为实际值）。"""
        return len(self.chapters or [])

    def refresh_lesson_count(self) -> int:
        """重算并写回冗余字段 `lesson_count`。"""
        total = sum(len(chapter.lessons or []) for chapter in (self.chapters or []))
        self.lesson_count = total
        return total

    def ordered_chapters(self) -> list["Chapter"]:
        """按 `order_index` 返回已发布章节。"""
        return sorted(
            [chapter for chapter in (self.chapters or []) if chapter.is_published],
            key=lambda item: item.order_index,
        )


class Chapter(Base, UUIDPkMixin, TimestampMixin):
    """课程章节。"""

    __tablename__ = "chapters"
    __table_args__ = (
        UniqueConstraint("course_id", "slug", name="uq_chapters_course_slug"),
        Index("ix_chapters_course_id", "course_id"),
        Index("ix_chapters_order", "order_index"),
    )

    course_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lesson_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    course: Mapped["Course"] = relationship(back_populates="chapters")
    lessons: Mapped[list["Lesson"]] = relationship(
        back_populates="chapter",
        cascade="all, delete-orphan",
        order_by="Lesson.order_index",
    )

    def refresh_lesson_count(self) -> int:
        """重算并写回冗余字段 `lesson_count`。"""
        self.lesson_count = len(self.lessons or [])
        return self.lesson_count


class Lesson(Base, UUIDPkMixin, TimestampMixin):
    """课时（正文 Markdown + 可选内嵌编辑器与随堂练习）。"""

    __tablename__ = "lessons"
    __table_args__ = (
        UniqueConstraint("chapter_id", "slug", name="uq_lessons_chapter_slug"),
        Index("ix_lessons_chapter_id", "chapter_id"),
        Index("ix_lessons_type", "lesson_type"),
        Index("ix_lessons_difficulty", "difficulty"),
        Index("ix_lessons_published", "is_published"),
        Index("ix_lessons_order", "order_index"),
    )

    chapter_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False
    )
    slug: Mapped[str] = mapped_column(String(120), nullable=False, doc="与 lessons/stage-XX.md 的锚点一致")
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content_md: Mapped[str] = mapped_column(Text, default="", nullable=False, doc="正文 Markdown")
    content_html: Mapped[str | None] = mapped_column(Text, nullable=True, doc="渲染缓存（可选）")
    lesson_type: Mapped[str] = mapped_column(String(20), default=LessonType.CONCEPT.value, nullable=False)
    difficulty: Mapped[str] = mapped_column(String(20), default=Difficulty.EASY.value, nullable=False)
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    xp_reward: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    has_playground: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    starter_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    solution_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    quiz_json: Mapped[Any | None] = mapped_column(JSON, nullable=True, doc="随堂练习 [{q,options,answer,explain}]")
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    chapter: Mapped["Chapter"] = relationship(back_populates="lessons")
    lesson_topics: Mapped[list["LessonTopic"]] = relationship(
        back_populates="lesson",
        cascade="all, delete-orphan",
    )
    progresses: Mapped[list["LearningProgress"]] = relationship(
        back_populates="lesson",
        cascade="all, delete-orphan",
    )

    @property
    def primary_topic_slugs(self) -> list[str]:
        """主知识点 slug 列表（掌握度加权用）。"""
        return [
            link.topic.slug
            for link in (self.lesson_topics or [])
            if link.is_primary and link.topic is not None
        ]


class Topic(Base, UUIDPkMixin):
    """知识点树（自引用，parent_id 为空表示根节点）。"""

    __tablename__ = "topics"
    __table_args__ = (
        Index("ix_topics_slug", "slug", unique=True),
        Index("ix_topics_parent_id", "parent_id"),
        Index("ix_topics_order", "order_index"),
    )

    slug: Mapped[str] = mapped_column(String(120), nullable=False, doc="如 list-comprehension")
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("topics.id", ondelete="SET NULL"), nullable=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    parent: Mapped["Topic | None"] = relationship(
        back_populates="children",
        remote_side="Topic.id",
        foreign_keys="Topic.parent_id",
    )
    children: Mapped[list["Topic"]] = relationship(
        back_populates="parent",
        foreign_keys="Topic.parent_id",
        passive_deletes=True,
    )
    lesson_topics: Mapped[list["LessonTopic"]] = relationship(
        back_populates="topic",
        cascade="all, delete-orphan",
    )


class LessonTopic(Base):
    """课时 ↔ 知识点 关联表（显式关联，支持 `is_primary` 附加列）。"""

    __tablename__ = "lesson_topics"
    __table_args__ = (
        Index("ix_lt_topic_id", "topic_id"),
        Index("ix_lt_lesson_id", "lesson_id"),
    )

    lesson_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("lessons.id", ondelete="CASCADE"), primary_key=True
    )
    topic_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, doc="主知识点，计入掌握度主权重")

    lesson: Mapped["Lesson"] = relationship(back_populates="lesson_topics")
    topic: Mapped["Topic"] = relationship(back_populates="lesson_topics")


class CourseEnrollment(Base, UUIDPkMixin):
    """用户在某个阶段的报名与进度。"""

    __tablename__ = "course_enrollments"
    __table_args__ = (
        UniqueConstraint("user_id", "course_id", name="uq_ce_user_course"),
        Index("ix_ce_user_id", "user_id"),
        Index("ix_ce_course_id", "course_id"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    course_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False, doc="0-100")
    completed_lessons: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_lesson_id: Mapped[str | None] = mapped_column(String(36), nullable=True, doc="继续学习用")
    enrolled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    user: Mapped["User"] = relationship()
    course: Mapped["Course"] = relationship(back_populates="enrollments")

    @property
    def status(self) -> str:
        """按进度推导状态字符串，便于前端直接展示。"""
        if self.progress_percent >= 100:
            return ProgressStatus.COMPLETED.value
        if self.progress_percent > 0:
            return ProgressStatus.IN_PROGRESS.value
        return ProgressStatus.NOT_STARTED.value
