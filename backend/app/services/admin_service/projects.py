"""管理端服务 · 项目 / 项目文件。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ErrorCode
from app.core.pagination import PageParams
from app.models.project import Project, ProjectFile
from app.models.user import User

from .common import apply_fields, audit, get_or_404


def list_projects(db: Session, params: PageParams) -> tuple[list[Project], int]:
    """项目列表。"""
    total = int(db.scalar(select(func.count()).select_from(Project)) or 0)
    rows = list(
        db.scalars(
            select(Project).order_by(Project.order_index.asc()).offset(params.offset).limit(params.limit)
        ).all()
    )
    return rows, total


def create_project(db: Session, actor: User, payload: dict[str, Any], meta: dict[str, Any]) -> Project:
    """新建项目。"""
    project = Project(**payload)
    db.add(project)
    db.flush()
    audit(db, actor, "admin.project.create", "project", project.id, after={"slug": project.slug}, meta=meta)
    db.commit()
    db.refresh(project)
    return project


def update_project(
    db: Session, actor: User, project_id: str, payload: dict[str, Any], meta: dict[str, Any]
) -> Project:
    """更新项目。"""
    project = get_or_404(db, Project, project_id, ErrorCode.PROJECT_NOT_FOUND, "项目不存在")
    apply_fields(project, payload)
    audit(db, actor, "admin.project.update", "project", project.id, after={"title": project.title}, meta=meta)
    db.commit()
    db.refresh(project)
    return project


def delete_project(db: Session, actor: User, project_id: str, meta: dict[str, Any]) -> None:
    """删除项目。"""
    project = get_or_404(db, Project, project_id, ErrorCode.PROJECT_NOT_FOUND, "项目不存在")
    db.delete(project)
    audit(db, actor, "admin.project.delete", "project", project_id, meta=meta)
    db.commit()


def create_project_file(
    db: Session, actor: User, payload: dict[str, Any], meta: dict[str, Any]
) -> ProjectFile:
    """新建项目文件。"""
    item = ProjectFile(**payload)
    db.add(item)
    db.flush()
    audit(db, actor, "admin.project_file.create", "project_file", item.id, meta=meta)
    db.commit()
    db.refresh(item)
    return item


def update_project_file(
    db: Session, actor: User, file_id: str, payload: dict[str, Any], meta: dict[str, Any]
) -> ProjectFile:
    """更新项目文件。"""
    item = get_or_404(db, ProjectFile, file_id, ErrorCode.NOT_FOUND, "项目文件不存在")
    apply_fields(item, payload)
    audit(db, actor, "admin.project_file.update", "project_file", item.id, meta=meta)
    db.commit()
    db.refresh(item)
    return item


def delete_project_file(db: Session, actor: User, file_id: str, meta: dict[str, Any]) -> None:
    """删除项目文件。"""
    item = get_or_404(db, ProjectFile, file_id, ErrorCode.NOT_FOUND, "项目文件不存在")
    db.delete(item)
    audit(db, actor, "admin.project_file.delete", "project_file", file_id, meta=meta)
    db.commit()
