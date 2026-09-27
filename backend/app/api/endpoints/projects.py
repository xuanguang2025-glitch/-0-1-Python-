"""项目实战端点（`docs/API.md` §2.8，7 条路由）。"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession, OptionalUser, Pagination
from app.core.pagination import build_page
from app.core.response import PageModel, ResponseModel, success_response
from app.schemas.project import (
    ProjectBrief,
    ProjectDetail,
    ProjectFilesUpdateRequest,
    ProjectRunRequest,
    ProjectSubmitOut,
    ProjectSubmitRequest,
    UserProjectOut,
)
from app.schemas.sandbox import RunResponse
from app.services import project_service
from app.services.editor_service import run_result_to_response

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=ResponseModel[PageModel[ProjectBrief]], summary="项目列表")
def list_projects(
    user: OptionalUser,
    db: DbSession,
    pagination: Pagination,
    level: int | None = Query(default=None, ge=1, le=10),
    category: str | None = Query(default=None),
    status: str | None = Query(default=None, description="not_started/in_progress/completed"),
) -> dict:
    """分页返回项目模板（登录用户附带我的进度）。"""
    briefs, total = project_service.list_projects(
        db, user, level=level, category=category, status=status, params=pagination
    )
    return success_response(build_page(briefs, total, pagination))


@router.get("/{project_id}", response_model=ResponseModel[ProjectDetail], summary="项目详情")
def get_project(project_id: str, user: OptionalUser, db: DbSession) -> dict:
    """返回项目详情（模板文件 / 步骤 / 我的进度）。"""
    project = project_service.get_project_or_404(db, project_id)
    return success_response(project_service.build_detail(db, project, user))


@router.post("/{project_id}/start", response_model=ResponseModel[UserProjectOut], summary="开始项目")
def start_project(project_id: str, current_user: CurrentUser, db: DbSession) -> dict:
    """Fork 项目模板到我的项目（幂等）。"""
    project = project_service.get_project_or_404(db, project_id)
    record = project_service.start_project(db, current_user, project)
    return success_response(project_service.to_user_project_out(record), message="已创建项目副本")


@router.get("/{project_id}/my", response_model=ResponseModel[UserProjectOut], summary="我的项目")
def get_my_project(project_id: str, current_user: CurrentUser, db: DbSession) -> dict:
    """返回我的项目文件快照与进度（不存在时自动 fork）。"""
    project = project_service.get_project_or_404(db, project_id)
    record = project_service.get_my_project(db, current_user, project)
    return success_response(project_service.to_user_project_out(record))


@router.put("/{project_id}/files", response_model=ResponseModel[UserProjectOut], summary="保存项目文件")
def update_project_files(
    project_id: str, payload: ProjectFilesUpdateRequest, current_user: CurrentUser, db: DbSession
) -> dict:
    """整体替换项目文件快照（拒绝路径遍历与只读文件写入）。"""
    project = project_service.get_project_or_404(db, project_id)
    record = project_service.update_files(db, current_user, project, payload.normalized())
    return success_response(project_service.to_user_project_out(record), message="已保存")


@router.post("/{project_id}/run", response_model=ResponseModel[RunResponse], summary="运行项目")
def run_project(
    project_id: str, payload: ProjectRunRequest, current_user: CurrentUser, db: DbSession
) -> dict:
    """运行我的项目（多文件 + 入口）。"""
    project = project_service.get_project_or_404(db, project_id)
    result = project_service.run_project(db, current_user, project, entry=payload.entry, stdin=payload.stdin)
    return success_response(run_result_to_response(result))


@router.post("/{project_id}/submit", response_model=ResponseModel[ProjectSubmitOut], summary="提交项目")
def submit_project(
    project_id: str, payload: ProjectSubmitRequest, current_user: CurrentUser, db: DbSession
) -> dict:
    """提交项目：校验入口可运行 + 步骤完整性，写入进度与 XP。"""
    project = project_service.get_project_or_404(db, project_id)
    result = project_service.submit_project(db, current_user, project, notes_md=payload.notes_md)
    return success_response(result, message="项目已提交")


__all__ = ["router"]
