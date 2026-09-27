"""项目实战服务：模板 / 我的项目 / 文件读写 / 运行 / 提交（`docs/API.md` §2.8）。

文件路径统一 `validate_relative_path()` 校验，杜绝路径遍历；项目文件与沙箱执行
均以「用户文件快照（`user_projects.files_json`）」为准。
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.constants import XP_REASON_PROJECT, level_of_xp
from app.core.errors import AppError, ErrorCode
from app.core.pagination import PageParams
from app.db.base import utc_now
from app.models.enums import UserProjectStatus
from app.models.gamification import XPTransaction
from app.models.project import Project, ProjectFile, UserProject
from app.models.user import User
from app.schemas.project import (
    ProjectBrief,
    ProjectDetail,
    ProjectFileOut,
    ProjectStepOut,
    ProjectSubmitOut,
    UserProjectOut,
)
from app.services.editor_service import run_code
from app.services.sandbox_client import ExecutionResult

logger = logging.getLogger("pythonlab.project")


def list_projects(
    db: Session,
    user: User | None,
    *,
    level: int | None = None,
    category: str | None = None,
    status: str | None = None,
    params: PageParams,
) -> tuple[list[ProjectBrief], int]:
    """按条件分页列出项目模板（登录用户附带我的进度）。"""
    stmt = select(Project).where(Project.is_published.is_(True))
    if level is not None:
        stmt = stmt.where(Project.level == level)
    if category:
        stmt = stmt.where(Project.category == category)
    if status and user is not None:
        stmt = stmt.where(
            Project.id.in_(
                select(UserProject.project_id).where(UserProject.user_id == user.id, UserProject.status == status)
            )
        )
    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    sort_column = Project.order_index if params.sort.lstrip("-") in ("order_index",) else Project.level
    items = db.scalars(
        stmt.order_by(sort_column.asc(), Project.order_index.asc()).offset(params.offset).limit(params.limit)
    ).all()

    progress_map: dict[str, UserProject] = {}
    if user is not None and items:
        rows = db.scalars(
            select(UserProject).where(
                UserProject.user_id == user.id, UserProject.project_id.in_([item.id for item in items])
            )
        ).all()
        progress_map = {row.project_id: row for row in rows}

    briefs: list[ProjectBrief] = []
    for project in items:
        mine = progress_map.get(project.id)
        briefs.append(
            ProjectBrief(
                id=project.id,
                slug=project.slug,
                title=project.title,
                summary=project.summary,
                level=int(project.level or 1),
                difficulty=project.difficulty,
                category=project.category,
                cover_url=project.cover_url,
                estimated_hours=int(project.estimated_hours or 0),
                xp_reward=int(project.xp_reward or 0),
                order_index=int(project.order_index or 0),
                my_status=mine.status if mine else None,
                progress_percent=int(mine.progress_percent or 0) if mine else 0,
            )
        )
    return briefs, total


def get_project_or_404(db: Session, project_id: str) -> Project:
    """按 id 获取已发布项目，不存在则 404。"""
    project = db.get(Project, project_id)
    if project is None or not project.is_published:
        raise AppError(code=ErrorCode.PROJECT_NOT_FOUND, message="项目不存在", status_code=404)
    return project


def build_detail(db: Session, project: Project, user: User | None) -> ProjectDetail:
    """构造项目详情（含模板文件、步骤、我的进度）。"""
    files = [
        ProjectFileOut.model_validate(item)
        for item in sorted(project.files or [], key=lambda row: row.order_index)
    ]
    steps = [
        ProjectStepOut(
            title=str(step.get("title") or ""),
            detail=str(step.get("detail") or ""),
            done_hint=str(step.get("done_hint") or ""),
        )
        for step in project.steps
    ]
    mine = _find_user_project(db, user, project.id) if user is not None else None
    return ProjectDetail(
        project=ProjectBrief(
            id=project.id,
            slug=project.slug,
            title=project.title,
            summary=project.summary,
            level=int(project.level or 1),
            difficulty=project.difficulty,
            category=project.category,
            cover_url=project.cover_url,
            estimated_hours=int(project.estimated_hours or 0),
            xp_reward=int(project.xp_reward or 0),
            order_index=int(project.order_index or 0),
            my_status=mine.status if mine else None,
            progress_percent=int(mine.progress_percent or 0) if mine else 0,
        ),
        files=files,
        steps=steps,
        rubric=project.rubric_json,
        description_md=project.description_md or "",
        my=to_user_project_out(mine) if mine else None,
    )


def start_project(db: Session, user: User, project: Project) -> UserProject:
    """Fork 模板到我的项目（已存在则原样返回）。"""
    existing = _find_user_project(db, user, project.id)
    if existing is not None:
        return existing
    record = UserProject(
        user_id=user.id,
        project_id=project.id,
        status=UserProjectStatus.NOT_STARTED.value,
        files_json=project.file_template(),
    )
    record.mark_started()
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_my_project(db: Session, user: User, project: Project) -> UserProject:
    """获取我的项目（不存在时自动 fork 模板）。"""
    record = _find_user_project(db, user, project.id)
    if record is None:
        record = start_project(db, user, project)
    return record


def update_files(db: Session, user: User, project: Project, files: dict[str, str]) -> UserProject:
    """整体替换我的项目文件快照（拒绝写入只读模板文件）。"""
    record = get_my_project(db, user, project)
    readonly = {item.path for item in (project.files or []) if item.is_readonly}
    from app.services.editor_service import normalize_project_files

    safe = normalize_project_files(files)
    blocked = [path for path in safe if path in readonly]
    if blocked:
        raise AppError(
            code=ErrorCode.INVALID_PATH,
            message=f"以下文件为只读模板，禁止修改：{', '.join(blocked)}",
            details={"readonly": blocked},
        )
    record.update_files(safe)
    record.mark_started()
    db.commit()
    db.refresh(record)
    return record


def run_project(
    db: Session, user: User, project: Project, *, entry: str | None = None, stdin: str = ""
) -> ExecutionResult:
    """运行我的项目（以文件快照为准）。"""
    record = get_my_project(db, user, project)
    files = record.files or project.file_template()
    if not files:
        raise AppError(code=ErrorCode.BAD_REQUEST, message="项目没有任何文件")
    result = run_code(db, user, files=files, entry=entry, stdin=stdin)
    record.last_run_status = result.status
    db.commit()
    return result


def submit_project(db: Session, user: User, project: Project, *, notes_md: str | None = None) -> ProjectSubmitOut:
    """提交项目：运行入口文件校验 + 步骤校验 + 写进度与 XP。"""
    record = get_my_project(db, user, project)
    files = record.files or project.file_template()
    entry_file = next((item.path for item in (project.files or []) if item.is_entry), None)
    if entry_file is None and files:
        entry_file = "main.py" if "main.py" in files else next(iter(files))

    checks: list[dict[str, Any]] = []
    run_ok = False
    if files and entry_file:
        result = run_code(db, user, files=files, entry=entry_file, stdin="")
        run_ok = result.status == "success"
        record.last_run_status = result.status
        checks.append(
            {
                "name": "入口文件可运行",
                "passed": run_ok,
                "detail": (result.error or result.stderr or "运行成功").strip()[:300],
            }
        )
    else:
        checks.append({"name": "入口文件可运行", "passed": False, "detail": "缺少入口文件"})

    steps = project.steps
    if steps:
        checks.append({"name": "步骤完整性", "passed": bool(files), "detail": f"共 {len(steps)} 个步骤"})

    xp_earned = 0
    level_up = False
    if run_ok:
        first_completion = record.status != UserProjectStatus.COMPLETED.value
        record.status = UserProjectStatus.COMPLETED.value
        record.progress_percent = 100
        if record.completed_at is None:
            record.completed_at = utc_now()
        if first_completion:
            xp_earned = int(project.xp_reward or 0)
            if xp_earned > 0:
                before_level = int(user.level or 1)
                user.xp = int(user.xp or 0) + xp_earned
                user.level = level_of_xp(int(user.xp), get_settings().level_threshold_list)
                level_up = int(user.level) > before_level
                db.add(
                    XPTransaction(
                        user_id=user.id,
                        amount=xp_earned,
                        reason=XP_REASON_PROJECT,
                        ref_type="project",
                        ref_id=project.id,
                        balance_after=int(user.xp),
                    )
                )
    else:
        record.mark_started()

    if notes_md is not None:
        record.notes_md = notes_md
    db.commit()
    db.refresh(record)
    return ProjectSubmitOut(
        user_project=to_user_project_out(record),
        xp_earned=xp_earned,
        level_up=level_up,
        unlocked_achievements=[],
        checks=checks,
    )


def to_user_project_out(record: UserProject) -> UserProjectOut:
    """ORM → 用户项目 Schema。"""
    return UserProjectOut(
        id=record.id,
        user_id=record.user_id,
        project_id=record.project_id,
        status=record.status,
        progress_percent=int(record.progress_percent or 0),
        current_step=int(record.current_step or 0),
        files_json=record.files,
        notes_md=record.notes_md,
        last_run_status=record.last_run_status,
        started_at=record.started_at,
        completed_at=record.completed_at,
        updated_at=record.updated_at,
    )


def _find_user_project(db: Session, user: User | None, project_id: str) -> UserProject | None:
    """查询用户在该项目下的进度记录。"""
    if user is None:
        return None
    return db.scalars(
        select(UserProject).where(UserProject.user_id == user.id, UserProject.project_id == project_id)
    ).one_or_none()


__all__ = [
    "build_detail",
    "get_my_project",
    "get_project_or_404",
    "list_projects",
    "run_project",
    "start_project",
    "submit_project",
    "to_user_project_out",
    "update_files",
]
