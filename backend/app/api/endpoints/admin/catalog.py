"""管理端端点 · 标签 / 公告。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Request

from app.core.deps import AdminUser, DbSession, Pagination
from app.core.pagination import build_page
from app.core.response import PageModel, ResponseModel, success_response
from app.schemas.notification import AdminAnnouncementIn, AnnouncementOut
from app.schemas.problem import AdminTagIn, TagOut
from app.services import admin_service

from ._common import meta

router = APIRouter()


@router.get("/tags", response_model=ResponseModel[list[TagOut]], summary="标签列表")
def list_tags(db: DbSession, admin: AdminUser) -> dict:
    """标签列表。"""
    return success_response([TagOut.model_validate(t) for t in admin_service.list_tags(db)])


@router.post("/tags", response_model=ResponseModel[TagOut], summary="新建标签")
def create_tag(payload: AdminTagIn, request: Request, db: DbSession, admin: AdminUser) -> dict:
    """新建标签。"""
    tag = admin_service.create_tag(db, admin, payload.model_dump(), meta(request))
    return success_response(TagOut.model_validate(tag), message="标签已创建")


@router.patch("/tags/{tag_id}", response_model=ResponseModel[TagOut], summary="更新标签")
def update_tag(
    tag_id: str, request: Request, db: DbSession, admin: AdminUser, payload: dict[str, Any] = Body(...)
) -> dict:
    """更新标签。"""
    tag = admin_service.update_tag(db, admin, tag_id, payload, meta(request))
    return success_response(TagOut.model_validate(tag), message="标签已更新")


@router.delete("/tags/{tag_id}", response_model=ResponseModel[None], summary="删除标签")
def delete_tag(tag_id: str, request: Request, db: DbSession, admin: AdminUser) -> dict:
    """删除标签。"""
    admin_service.delete_tag(db, admin, tag_id, meta(request))
    return success_response(None, message="标签已删除")


@router.get("/announcements", response_model=ResponseModel[PageModel[AnnouncementOut]], summary="公告列表")
def list_announcements(db: DbSession, admin: AdminUser, pagination: Pagination) -> dict:
    """公告列表。"""
    items, total = admin_service.list_announcements(db, pagination)
    return success_response(build_page([AnnouncementOut.model_validate(a) for a in items], total, pagination))


@router.post("/announcements", response_model=ResponseModel[AnnouncementOut], summary="新建公告")
def create_announcement(payload: AdminAnnouncementIn, request: Request, db: DbSession, admin: AdminUser) -> dict:
    """新建公告。"""
    item = admin_service.create_announcement(db, admin, payload.model_dump(), meta(request))
    return success_response(AnnouncementOut.model_validate(item), message="公告已创建")


@router.patch(
    "/announcements/{announcement_id}",
    response_model=ResponseModel[AnnouncementOut],
    summary="更新/发布/下线公告",
)
def update_announcement(
    announcement_id: str, request: Request, db: DbSession, admin: AdminUser, payload: dict[str, Any] = Body(...)
) -> dict:
    """更新公告（含发布 / 下线）。"""
    item = admin_service.update_announcement(db, admin, announcement_id, payload, meta(request))
    return success_response(AnnouncementOut.model_validate(item), message="公告已更新")


@router.delete("/announcements/{announcement_id}", response_model=ResponseModel[None], summary="删除公告")
def delete_announcement(announcement_id: str, request: Request, db: DbSession, admin: AdminUser) -> dict:
    """删除公告。"""
    admin_service.delete_announcement(db, admin, announcement_id, meta(request))
    return success_response(None, message="公告已删除")
