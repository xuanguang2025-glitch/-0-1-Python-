"""项目中心模型：`projects` / `project_files` / `user_projects`（DATABASE.md §5）。"""

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
from app.models.enums import Difficulty, ProblemCategory, UserProjectStatus

if TYPE_CHECKING:
    from app.models.user import User


class Project(Base, UUIDPkMixin, TimestampMixin):
    """实战项目（含步骤指引与评分维度）。"""

    __tablename__ = "projects"
    __table_args__ = (
        Index("ix_projects_slug", "slug", unique=True),
        Index("ix_projects_level", "level"),
        Index("ix_projects_category", "category"),
        Index("ix_projects_published", "is_published"),
        Index("ix_projects_order", "order_index"),
    )

    slug: Mapped[str] = mapped_column(String(150), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description_md: Mapped[str] = mapped_column(Text, default="", nullable=False, doc="需求文档")
    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False, doc="1..10")
    difficulty: Mapped[str] = mapped_column(String(20), default=Difficulty.EASY.value, nullable=False)
    category: Mapped[str] = mapped_column(String(40), default=ProblemCategory.BASICS.value, nullable=False)
    cover_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    estimated_hours: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    xp_reward: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    steps_json: Mapped[Any | None] = mapped_column(JSON, nullable=True, doc="[{title, detail, done_hint}]")
    rubric_json: Mapped[Any | None] = mapped_column(JSON, nullable=True, doc="评分维度")
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    files: Mapped[list["ProjectFile"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ProjectFile.order_index",
    )
    user_projects: Mapped[list["UserProject"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )

    @property
    def steps(self) -> list[dict[str, Any]]:
        """步骤列表（无配置时返回空列表）。"""
        return list(self.steps_json or [])

    @property
    def entry_file(self) -> "ProjectFile | None":
        """入口文件（无显式入口时回退到第一个文件）。"""
        for item in self.files or []:
            if item.is_entry:
                return item
        return (self.files or [None])[0]

    def file_template(self) -> dict[str, str]:
        """返回 `{相对路径: 初始内容}` 的模板字典。"""
        return {item.path: item.content for item in (self.files or [])}


class ProjectFile(Base, UUIDPkMixin):
    """项目模板文件。"""

    __tablename__ = "project_files"
    __table_args__ = (
        UniqueConstraint("project_id", "path", name="uq_pf_project_path"),
        Index("ix_pf_project_id", "project_id"),
    )

    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    path: Mapped[str] = mapped_column(String(512), nullable=False, doc="如 main.py")
    content: Mapped[str] = mapped_column(Text, default="", nullable=False, doc="初始模板内容")
    language: Mapped[str] = mapped_column(String(20), default="python", nullable=False)
    is_entry: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_readonly: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, doc="只读文件（如 README）")
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    project: Mapped["Project"] = relationship(back_populates="files")


class UserProject(Base, UUIDPkMixin):
    """用户在项目中的进度与文件快照。"""

    __tablename__ = "user_projects"
    __table_args__ = (
        UniqueConstraint("user_id", "project_id", name="uq_up_user_project"),
        Index("ix_up_user_id", "user_id"),
        Index("ix_up_status", "status"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default=UserProjectStatus.NOT_STARTED.value, nullable=False)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_step: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    files_json: Mapped[Any | None] = mapped_column(JSON, nullable=True, doc="用户当前文件快照 {path: content}")
    notes_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_run_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    user: Mapped["User"] = relationship()
    project: Mapped["Project"] = relationship(back_populates="user_projects")

    @property
    def files(self) -> dict[str, str]:
        """用户文件快照（缺省为空字典）。"""
        return dict(self.files_json or {})

    def update_files(self, files: dict[str, str]) -> None:
        """整体替换文件快照（编辑器保存时调用）。"""
        self.files_json = dict(files)

    def mark_started(self) -> None:
        """标记项目已开始。"""
        if self.status == UserProjectStatus.NOT_STARTED.value:
            self.status = UserProjectStatus.IN_PROGRESS.value
        if self.started_at is None:
            self.started_at = utc_now()
