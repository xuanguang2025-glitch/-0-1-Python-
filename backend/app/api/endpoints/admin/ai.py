"""管理端端点 · AI 配置 / 模型。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Request

from app.core.deps import AdminUser, DbSession
from app.core.response import ResponseModel, success_response
from app.schemas.admin import (
    AIConfigOut,
    AIConfigUpdateRequest,
    AIModelConfigIn,
    AIModelConfigOut,
    ModelTestOut,
)
from app.services import admin_service

from ._common import meta

router = APIRouter()


@router.get("/ai-config", response_model=ResponseModel[AIConfigOut], summary="全局 AI 配置")
def get_ai_config(db: DbSession, admin: AdminUser) -> dict:
    """读取全局 AI 配置（密钥脱敏）。"""
    return success_response(AIConfigOut(**admin_service.get_ai_config(db)))


@router.put("/ai-config", response_model=ResponseModel[AIConfigOut], summary="更新 AI 配置")
def update_ai_config(payload: AIConfigUpdateRequest, request: Request, db: DbSession, admin: AdminUser) -> dict:
    """更新全局 AI 配置（`api_key` 只写，读取永远脱敏）。"""
    data = admin_service.update_ai_config(db, admin, payload.model_dump(exclude_unset=True), meta(request))
    return success_response(AIConfigOut(**data), message="AI 配置已更新")


@router.get("/models", response_model=ResponseModel[list[AIModelConfigOut]], summary="模型配置列表")
def list_models(db: DbSession, admin: AdminUser) -> dict:
    """模型配置列表（密钥脱敏）。"""
    return success_response([AIModelConfigOut(**item) for item in admin_service.list_models_out(db)])


@router.post("/models", response_model=ResponseModel[AIModelConfigOut], summary="新建模型配置")
def create_model(payload: AIModelConfigIn, request: Request, db: DbSession, admin: AdminUser) -> dict:
    """新建模型配置（`api_key` 只写，读取返回脱敏值）。"""
    data = admin_service.create_model(db, admin, payload.model_dump(exclude_unset=True), meta(request))
    return success_response(AIModelConfigOut(**data), message="模型配置已创建")


@router.patch("/models/{model_id}", response_model=ResponseModel[AIModelConfigOut], summary="更新模型配置")
def update_model(
    model_id: str, request: Request, db: DbSession, admin: AdminUser, payload: dict[str, Any] = Body(...)
) -> dict:
    """更新模型配置。"""
    data = admin_service.update_model(db, admin, model_id, payload, meta(request))
    return success_response(AIModelConfigOut(**data), message="模型配置已更新")


@router.delete("/models/{model_id}", response_model=ResponseModel[None], summary="删除模型配置")
def delete_model(model_id: str, request: Request, db: DbSession, admin: AdminUser) -> dict:
    """删除模型配置（连同密钥）。"""
    admin_service.delete_model(db, admin, model_id, meta(request))
    return success_response(None, message="模型配置已删除")


@router.post("/models/{model_id}/test", response_model=ResponseModel[ModelTestOut], summary="连通性测试")
def test_model(model_id: str, request: Request, db: DbSession, admin: AdminUser) -> dict:
    """模型连通性测试（**不回显 key**）。"""
    return success_response(ModelTestOut(**admin_service.test_model(db, admin, model_id, meta(request))))
