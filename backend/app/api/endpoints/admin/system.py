"""管理端端点 · 日志 / 设置 / 维护。"""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.core.deps import AdminUser, DbSession, Pagination
from app.core.pagination import build_page
from app.core.response import PageModel, ResponseModel, success_response
from app.schemas.admin import (
    AIUsageLogOut,
    AuditLogOut,
    ErrorLogGroup,
    MaintenanceRejudgeRequest,
    SessionOverviewOut,
    SystemSettingOut,
    SystemSettingUpdateRequest,
)
from app.services import admin_service

from ._common import meta

router = APIRouter()


@router.get("/logs/audit", response_model=ResponseModel[PageModel[AuditLogOut]], summary="审计日志")
def list_audit_logs(
    db: DbSession,
    admin: AdminUser,
    pagination: Pagination,
    action: str | None = Query(default=None),
    actor_id: str | None = Query(default=None),
) -> dict:
    """审计日志分页（可按 action / actor 筛选）。"""
    items, total = admin_service.list_audit_logs(db, pagination, action=action, actor_id=actor_id)
    return success_response(build_page([AuditLogOut.model_validate(i) for i in items], total, pagination))


@router.get("/logs/ai-usage", response_model=ResponseModel[PageModel[AIUsageLogOut]], summary="AI 用量日志")
def list_ai_usage(db: DbSession, admin: AdminUser, pagination: Pagination) -> dict:
    """AI 用量日志分页。"""
    items, total = admin_service.list_ai_usage(db, pagination)
    return success_response(build_page([AIUsageLogOut.model_validate(i) for i in items], total, pagination))


@router.get("/logs/errors", response_model=ResponseModel[list[ErrorLogGroup]], summary="错误日志聚合")
def list_error_logs(db: DbSession, admin: AdminUser, limit: int = Query(default=50, ge=1, le=200)) -> dict:
    """错误日志（按状态聚合）。"""
    return success_response([ErrorLogGroup(**item) for item in admin_service.list_error_logs(db, limit=limit)])


@router.get("/logs/sessions", response_model=ResponseModel[SessionOverviewOut], summary="学习会话概览")
def session_overview(db: DbSession, admin: AdminUser) -> dict:
    """学习会话概览（总量 / 活跃人数 / 按类型聚合）。"""
    return success_response(SessionOverviewOut(**admin_service.session_overview(db)))


@router.get("/settings", response_model=ResponseModel[list[SystemSettingOut]], summary="系统设置")
def list_settings(db: DbSession, admin: AdminUser) -> dict:
    """系统设置列表（敏感项脱敏）。"""
    return success_response([SystemSettingOut(**item) for item in admin_service.list_settings(db)])


@router.put("/settings/{key}", response_model=ResponseModel[SystemSettingOut], summary="写入系统设置")
def update_setting(
    key: str,
    payload: SystemSettingUpdateRequest,
    request: Request,
    db: DbSession,
    admin: AdminUser,
) -> dict:
    """写入系统设置（敏感项读取仍脱敏）。"""
    data = admin_service.update_setting(db, admin, key, payload.model_dump(exclude_unset=True), meta(request))
    return success_response(SystemSettingOut(**data), message="设置已更新")


@router.post("/maintenance/rejudge", response_model=ResponseModel[dict], summary="批量重判")
def rejudge(payload: MaintenanceRejudgeRequest, request: Request, db: DbSession, admin: AdminUser) -> dict:
    """批量重判（入队）。"""
    return success_response(
        admin_service.enqueue_rejudge(db, admin, payload.problem_id, payload.limit, meta(request))
    )
