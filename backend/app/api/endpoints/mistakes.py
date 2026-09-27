"""错题本端点（`docs/API.md` §2.18，7 条 + 高频错误知识点统计）。

注：`GET /mistakes/topics` 为「高频错误知识点统计」新增的第 8 条路由（任务 §7 要求），
其余 7 条严格对齐 `docs/API.md`。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession, Pagination
from app.core.pagination import build_page
from app.core.response import PageModel, ResponseModel, success_response
from app.schemas.mistake import (
    MistakeCreateRequest,
    MistakeOut,
    MistakeResolveRequest,
    MistakeUpdateRequest,
)
from app.services import mistake_service

router = APIRouter(prefix="/mistakes", tags=["mistakes"])


@router.get("", response_model=ResponseModel[PageModel[MistakeOut]], summary="错题列表")
def list_mistakes(
    current_user: CurrentUser,
    db: DbSession,
    pagination: Pagination,
    error_type: str | None = Query(default=None),
    topic_id: str | None = Query(default=None),
    resolved: bool | None = Query(default=None),
) -> dict:
    """分页返回错题（含知识点 / 错误次数 / 最后错误时间）。"""
    items, total = mistake_service.list_mistakes(
        db, current_user, error_type=error_type, topic_id=topic_id, resolved=resolved, params=pagination
    )
    briefs = [mistake_service.to_out(item) for item in items]
    return success_response(build_page(briefs, total, pagination))


@router.get("/review-queue", response_model=ResponseModel[list[MistakeOut]], summary="复习队列")
def review_queue(
    current_user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=10, ge=1, le=50),
) -> dict:
    """按下次复习时间返回待复习错题。"""
    items = mistake_service.review_queue(db, current_user, limit=limit)
    return success_response([mistake_service.to_out(item) for item in items])


@router.get("/topics", response_model=ResponseModel[list[dict[str, Any]]], summary="高频错误知识点统计")
def high_frequency_topics(
    current_user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=10, ge=1, le=50),
) -> dict:
    """按错误次数统计高频错误知识点。"""
    return success_response(mistake_service.high_frequency_topics(db, current_user, limit=limit))


@router.post("", response_model=ResponseModel[MistakeOut], summary="新增错题")
def create_mistake(payload: MistakeCreateRequest, current_user: CurrentUser, db: DbSession) -> dict:
    """手动新增一条错题。"""
    record = mistake_service.create_mistake(db, current_user, payload)
    return success_response(mistake_service.to_out(record), message="已加入错题本")


@router.get("/{mistake_id}", response_model=ResponseModel[MistakeOut], summary="错题详情")
def get_mistake(mistake_id: str, current_user: CurrentUser, db: DbSession) -> dict:
    """返回错题详情。"""
    record = mistake_service.get_mistake(db, current_user, mistake_id)
    return success_response(mistake_service.to_out(record))


@router.patch("/{mistake_id}", response_model=ResponseModel[MistakeOut], summary="更新错题")
def update_mistake(
    mistake_id: str, payload: MistakeUpdateRequest, current_user: CurrentUser, db: DbSession
) -> dict:
    """更新错题笔记 / 知识点。"""
    record = mistake_service.update_mistake(db, current_user, mistake_id, payload)
    return success_response(mistake_service.to_out(record))


@router.post("/{mistake_id}/resolve", response_model=ResponseModel[MistakeOut], summary="标记已掌握")
def resolve_mistake(
    mistake_id: str, payload: MistakeResolveRequest, current_user: CurrentUser, db: DbSession
) -> dict:
    """标记 / 取消「已掌握」。"""
    record = mistake_service.resolve_mistake(db, current_user, mistake_id, payload.resolved)
    return success_response(mistake_service.to_out(record))


@router.delete("/{mistake_id}", response_model=ResponseModel[None], summary="删除错题")
def delete_mistake(mistake_id: str, current_user: CurrentUser, db: DbSession) -> dict:
    """删除错题。"""
    mistake_service.delete_mistake(db, current_user, mistake_id)
    return success_response(None, message="已删除")


__all__ = ["router"]
