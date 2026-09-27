"""通知与公告端点（`docs/API.md` §2.15，6 条路由）。"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession, Pagination
from app.core.pagination import build_page
from app.core.response import PageModel, ResponseModel, success_response
from app.schemas.common import CountOut
from app.schemas.notification import (
    AnnouncementOut,
    NotificationOut,
    NotificationReadAllOut,
    NotificationReadAllRequest,
)
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=ResponseModel[PageModel[NotificationOut]], summary="通知列表")
def list_notifications(
    db: DbSession,
    current_user: CurrentUser,
    pagination: Pagination,
    is_read: bool | None = Query(default=None, description="按是否已读筛选"),
    type: str | None = Query(default=None, pattern="^(system|achievement|daily|challenge|ai|admin)$"),
) -> dict:
    """分页返回我的通知（可按已读状态 / 类型筛选）。"""
    items, total = notification_service.list_notifications(
        db, current_user, pagination, is_read=is_read, ntype=type
    )
    page = build_page([NotificationOut.model_validate(item) for item in items], total, pagination)
    return success_response(page)


@router.get("/unread-count", response_model=ResponseModel[CountOut], summary="未读数")
def unread_count(db: DbSession, current_user: CurrentUser) -> dict:
    """未读通知数。"""
    return success_response(CountOut(count=notification_service.unread_count(db, current_user)))


@router.post("/read-all", response_model=ResponseModel[NotificationReadAllOut], summary="全部已读")
def read_all(
    payload: NotificationReadAllRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """批量标记已读（可按类型），返回受影响条数。"""
    updated = notification_service.mark_all_read(db, current_user, payload.type)
    return success_response(NotificationReadAllOut(updated=updated))


@router.get("/announcements", response_model=ResponseModel[list[AnnouncementOut]], summary="公告列表")
def list_announcements(
    db: DbSession,
    limit: int = Query(default=5, ge=1, le=50),
) -> dict:
    """公开公告列表（置顶优先，仅生效中）。"""
    items = notification_service.list_announcements(db, limit=limit)
    return success_response([AnnouncementOut.model_validate(item) for item in items])


@router.get("/announcements/{announcement_id}", response_model=ResponseModel[AnnouncementOut], summary="公告详情")
def get_announcement(announcement_id: str, db: DbSession) -> dict:
    """公告详情。"""
    return success_response(AnnouncementOut.model_validate(notification_service.get_announcement(db, announcement_id)))


@router.post("/{notification_id}/read", response_model=ResponseModel[NotificationOut], summary="标记已读")
def mark_read(notification_id: str, db: DbSession, current_user: CurrentUser) -> dict:
    """标记单条通知为已读（仅本人）。"""
    item = notification_service.mark_read(db, current_user, notification_id)
    return success_response(NotificationOut.model_validate(item))


@router.delete("/{notification_id}", response_model=ResponseModel[None], summary="删除通知")
def delete_notification(notification_id: str, db: DbSession, current_user: CurrentUser) -> dict:
    """删除通知（仅本人）。"""
    notification_service.delete(db, current_user, notification_id)
    return success_response(None, message="已删除")
