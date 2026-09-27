"""健康检查端点（`docs/API.md` §2.22）。"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.response import ResponseModel, success_response
from app.models.enums import enum_dict
from app.schemas.health import DepsHealthOut, HealthOut
from app.services import health_service

router = APIRouter(tags=["health"])


@router.get("/health", response_model=ResponseModel[HealthOut], summary="基础健康检查")
def health() -> dict:
    """返回服务存活状态、版本与环境名。"""
    return success_response(health_service.get_health())


@router.get("/health/deps", response_model=ResponseModel[DepsHealthOut], summary="依赖健康检查")
def health_deps() -> dict:
    """返回 db / cache / queue / runner / ai 的**实际生效**实现与降级状态。"""
    return success_response(health_service.get_deps_health())


@router.get("/health/enums", summary="枚举字典（前后端一致性校验用）")
def health_enums() -> dict:
    """返回全库枚举字典，供前端比对 `types/enums.ts`。"""
    return success_response(enum_dict())
