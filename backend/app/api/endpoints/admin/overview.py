"""管理端端点 · 总览。"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import AdminUser, DbSession
from app.core.response import ResponseModel, success_response
from app.schemas.statistics import DashboardOut
from app.services import admin_service

router = APIRouter()


@router.get("/dashboard", response_model=ResponseModel[DashboardOut], summary="后台总览")
def dashboard(db: DbSession, admin: AdminUser) -> dict:
    """用户 / 活跃 / 提交 / AI 调用 / 依赖健康状态。"""
    return success_response(admin_service.dashboard(db))
