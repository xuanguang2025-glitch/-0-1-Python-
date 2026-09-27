"""管理端端点 · 项目 / 项目文件。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Request

from app.core.deps import AdminUser, DbSession, Pagination
from app.core.pagination import build_page
from app.core.response import PageModel, ResponseModel, success_response
from app.schemas.admin import AdminProjectFileIn, AdminProjectIn
from app.schemas.project import ProjectBrief
from app.services import admin_service

from ._common import meta

router = APIRouter()


@router.get("/projects", response_model=ResponseModel[PageModel[ProjectBrief]], summary="项目列表")
def list_projects(db: DbSession, admin: AdminUser, pagination: Pagination) -> dict:
    """项目列表。"""
    items, total = admin_service.list_projects(db, pagination)
    return success_response(build_page([ProjectBrief.model_validate(p) for p in items], total, pagination))


@router.post("/projects", response_model=ResponseModel[ProjectBrief], summary="新建项目")
def create_project(payload: AdminProjectIn, request: Request, db: DbSession, admin: AdminUser) -> dict:
    """新建项目。"""
    project = admin_service.create_project(db, admin, payload.model_dump(), meta(request))
    return success_response(ProjectBrief.model_validate(project), message="项目已创建")


@router.patch("/projects/{project_id}", response_model=ResponseModel[ProjectBrief], summary="更新项目")
def update_project(
    project_id: str, request: Request, db: DbSession, admin: AdminUser, payload: dict[str, Any] = Body(...)
) -> dict:
    """更新项目。"""
    project = admin_service.update_project(db, admin, project_id, payload, meta(request))
    return success_response(ProjectBrief.model_validate(project), message="项目已更新")


@router.delete("/projects/{project_id}", response_model=ResponseModel[None], summary="删除项目")
def delete_project(project_id: str, request: Request, db: DbSession, admin: AdminUser) -> dict:
    """删除项目。"""
    admin_service.delete_project(db, admin, project_id, meta(request))
    return success_response(None, message="项目已删除")


@router.post("/project-files", response_model=ResponseModel[dict], summary="新建项目文件")
def create_project_file(payload: AdminProjectFileIn, request: Request, db: DbSession, admin: AdminUser) -> dict:
    """新建项目文件。"""
    item = admin_service.create_project_file(db, admin, payload.model_dump(), meta(request))
    return success_response({"id": item.id}, message="项目文件已创建")


@router.patch("/project-files/{file_id}", response_model=ResponseModel[dict], summary="更新项目文件")
def update_project_file(
    file_id: str, request: Request, db: DbSession, admin: AdminUser, payload: dict[str, Any] = Body(...)
) -> dict:
    """更新项目文件。"""
    item = admin_service.update_project_file(db, admin, file_id, payload, meta(request))
    return success_response({"id": item.id}, message="项目文件已更新")


@router.delete("/project-files/{file_id}", response_model=ResponseModel[None], summary="删除项目文件")
def delete_project_file(file_id: str, request: Request, db: DbSession, admin: AdminUser) -> dict:
    """删除项目文件。"""
    admin_service.delete_project_file(db, admin, file_id, meta(request))
    return success_response(None, message="项目文件已删除")
