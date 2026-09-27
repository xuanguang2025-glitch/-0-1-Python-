"""认证端点（`docs/API.md` §2.1，7 条路由）。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.api.deps import build_request_meta, rate_limit
from app.core.deps import CurrentUser, DbSession, require_admin
from app.core.response import ResponseModel, success_response
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenPair,
    UserMe,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"], dependencies=[Depends(rate_limit("auth"))])


@router.post("/register", response_model=ResponseModel[TokenPair], summary="注册")
def register(payload: RegisterRequest, request: Request, db: DbSession) -> dict:
    """注册新用户并直接返回令牌对（注册即登录）。"""
    meta = build_request_meta(request)
    return success_response(auth_service.register(db, payload, meta), message="注册成功")


@router.post("/login", response_model=ResponseModel[TokenPair], summary="登录")
def login(payload: LoginRequest, request: Request, db: DbSession) -> dict:
    """账号（邮箱或用户名）+ 密码登录。"""
    meta = build_request_meta(request)
    return success_response(auth_service.login(db, payload, meta), message="登录成功")


@router.post("/refresh", response_model=ResponseModel[TokenPair], summary="刷新令牌")
def refresh(payload: RefreshRequest, request: Request, db: DbSession) -> dict:
    """刷新令牌（轮换：旧 refresh 立即吊销）。"""
    meta = build_request_meta(request)
    return success_response(auth_service.refresh(db, payload.refresh_token, meta))


@router.post("/logout", response_model=ResponseModel[None], summary="登出")
def logout(
    payload: LogoutRequest,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """登出：吊销 refresh 记录并将当前 access 的 jti 加入黑名单。"""
    meta = build_request_meta(request, with_token_context=True)
    auth_service.logout(db, current_user, meta, payload.refresh_token)
    return success_response(None, message="已退出登录")


@router.get("/me", response_model=ResponseModel[UserMe], summary="当前用户信息")
def me(current_user: CurrentUser) -> dict:
    """返回当前登录用户（含资料摘要，绝不含密码哈希）。"""
    return success_response(auth_service.build_user_me(current_user))


@router.post("/change-password", response_model=ResponseModel[None], summary="修改密码")
def change_password(
    payload: ChangePasswordRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """修改自己的密码，并吊销全部 Refresh Token。"""
    auth_service.change_password(db, current_user, payload)
    return success_response(None, message="密码已更新，请重新登录")


@router.post(
    "/reset-password",
    response_model=ResponseModel[None],
    summary="管理员重置指定用户密码",
)
def reset_password(
    payload: ResetPasswordRequest,
    db: DbSession,
    admin: Annotated[User, Depends(require_admin)],
) -> dict:
    """管理员重置他人密码（同时吊销其全部 Refresh Token）。"""
    auth_service.reset_password(db, payload.user_id, payload.new_password)
    return success_response(None, message="密码已重置")
