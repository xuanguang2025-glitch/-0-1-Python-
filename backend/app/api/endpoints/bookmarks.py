"""收藏 / 代码片段端点（`docs/API.md` §2.17，5 条路由）。"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession, Pagination
from app.core.pagination import build_page
from app.core.response import PageModel, ResponseModel, success_response
from app.schemas.bookmark import (
    BookmarkCreateRequest,
    BookmarkOut,
    BookmarkUpdateRequest,
    CollectionListOut,
)
from app.services import bookmark_service

router = APIRouter(prefix="/bookmarks", tags=["bookmarks"])


@router.get("", response_model=ResponseModel[PageModel[BookmarkOut]], summary="我的收藏")
def list_bookmarks(
    current_user: CurrentUser,
    db: DbSession,
    pagination: Pagination,
    kind: str | None = Query(default=None, description="problem/lesson/project/snippet/challenge"),
    collection: str | None = Query(default=None),
) -> dict:
    """分页返回我的收藏（可按类型 / 集合筛选）。"""
    items, total = bookmark_service.list_bookmarks(
        db, current_user, kind=kind, collection=collection, params=pagination
    )
    briefs = [bookmark_service.to_out(item) for item in items]
    return success_response(build_page(briefs, total, pagination))


@router.get("/collections", response_model=ResponseModel[CollectionListOut], summary="收藏集合")
def list_collections(current_user: CurrentUser, db: DbSession) -> dict:
    """返回我的收藏集合统计。"""
    collections = bookmark_service.list_collections(db, current_user)
    return success_response(CollectionListOut(collections=collections))


@router.post("", response_model=ResponseModel[BookmarkOut], summary="新建收藏")
def create_bookmark(payload: BookmarkCreateRequest, current_user: CurrentUser, db: DbSession) -> dict:
    """新建收藏 / 代码片段。"""
    record = bookmark_service.create_bookmark(db, current_user, payload)
    return success_response(bookmark_service.to_out(record), message="已收藏")


@router.patch("/{bookmark_id}", response_model=ResponseModel[BookmarkOut], summary="更新收藏")
def update_bookmark(
    bookmark_id: str, payload: BookmarkUpdateRequest, current_user: CurrentUser, db: DbSession
) -> dict:
    """更新收藏（标题 / 笔记 / 集合 / 标签）。"""
    record = bookmark_service.update_bookmark(db, current_user, bookmark_id, payload)
    return success_response(bookmark_service.to_out(record))


@router.delete("/{bookmark_id}", response_model=ResponseModel[None], summary="删除收藏")
def delete_bookmark(bookmark_id: str, current_user: CurrentUser, db: DbSession) -> dict:
    """删除收藏。"""
    bookmark_service.delete_bookmark(db, current_user, bookmark_id)
    return success_response(None, message="已删除")


__all__ = ["router"]
