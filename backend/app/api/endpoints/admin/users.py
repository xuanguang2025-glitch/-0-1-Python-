"""管理端端点 · 用户管理。"""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.core.deps import AdminUser, DbSession, Pagination
from app.core.pagination import build_page
from app.core.response import PageModel, ResponseModel, success_response
from app.schemas.admin import (
    AdminPasswordResetRequest,
    AdminUserBrief,
    AdminUserCreateRequest,
    AdminUserUpdateRequest,
)
from app.services import admin_service

from ._common import meta

router = APIRouter()


@router.get("/users", response_model=ResponseModel[PageModel[AdminUserBrief]], summary="用户列表")
def list_users(
    request: Request,
    db: DbSession,
    admin: AdminUser,
    pagination: Pagination,
    q: str | None = Query(default=None),
    role: str | None = Query(default=None),
    status: str | None = Query(default=None),
) -> dict:
    """用户列表（搜索 / 筛选 / 分页）。"""
    items, total = admin_service.list_users(db, pagination, q=q, role=role, status=status)
    return success_response(build_page([AdminUserBrief.model_validate(u) for u in items], total, pagination))


@router.post("/users", response_model=ResponseModel[AdminUserBrief], summary="新建用户")
def create_user(payload: AdminUserCreateRequest, request: Request, db: DbSession, admin: AdminUser) -> dict:
    """新建用户（写审计日志）。"""
    user = admin_service.create_user(db, admin, payload.model_dump(), meta(request))
    return success_response(AdminUserBrief.model_validate(user), message="用户已创建")


@router.patch("/users/{user_id}", response_model=ResponseModel[AdminUserBrief], summary="更新用户")
def update_user(
    user_id: str,
    payload: AdminUserUpdateRequest,
    request: Request,
    db: DbSession,
    admin: AdminUser,
) -> dict:
    """更新角色 / 状态 / 资料（写审计日志）。"""
    user = admin_service.update_user(db, admin, user_id, payload.model_dump(exclude_unset=True), meta(request))
    return success_response(AdminUserBrief.model_validate(user), message="用户已更新")


@router.delete("/users/{user_id}", response_model=ResponseModel[None], summary="删除用户")
def delete_user(user_id: str, request: Request, db: DbSession, admin: AdminUser) -> dict:
    """软删除用户（写审计日志）。"""
    admin_service.delete_user(db, admin, user_id, meta(request))
    return success_response(None, message="用户已删除")


@router.post("/users/{user_id}/reset-password", response_model=ResponseModel[None], summary="重置密码")
def reset_password(
    user_id: str,
    payload: AdminPasswordResetRequest,
    request: Request,
    db: DbSession,
    admin: AdminUser,
) -> dict:
    """重置用户密码（写审计日志，不回显明文）。"""
    admin_service.reset_password(db, admin, user_id, payload.new_password, meta(request))
    return success_response(None, message="密码已重置")
