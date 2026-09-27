"""收藏 / 代码片段服务（`docs/API.md` §2.17）。"""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.constants import MAX_SNIPPET_BYTES
from app.core.errors import AppError, ErrorCode
from app.core.pagination import PageParams, paginate
from app.models.enums import BookmarkKind
from app.models.learning import Bookmark
from app.models.user import User
from app.schemas.bookmark import BookmarkCreateRequest, BookmarkOut, BookmarkUpdateRequest, CollectionOut
from app.utils.validators import validate_code_size

logger = logging.getLogger("pythonlab.bookmark")


def list_bookmarks(
    db: Session,
    user: User,
    *,
    kind: str | None,
    collection: str | None,
    params: PageParams,
) -> tuple[list[Bookmark], int]:
    """分页列出我的收藏（可按类型 / 集合筛选）。"""
    stmt = select(Bookmark).where(Bookmark.user_id == user.id)
    if kind:
        stmt = stmt.where(Bookmark.kind == kind)
    if collection:
        stmt = stmt.where(Bookmark.collection == collection)
    stmt = stmt.order_by(Bookmark.created_at.desc())
    return paginate(db, stmt, params)


def create_bookmark(db: Session, user: User, payload: BookmarkCreateRequest) -> Bookmark:
    """新建收藏 / 代码片段。"""
    kind = payload.kind if payload.kind in BookmarkKind.values() else BookmarkKind.PROBLEM.value
    if kind == BookmarkKind.SNIPPET.value and not (payload.code_snippet or "").strip():
        raise AppError(code=ErrorCode.BAD_REQUEST, message="片段收藏必须提供 code_snippet")
    if payload.code_snippet:
        validate_code_size(payload.code_snippet, limit=MAX_SNIPPET_BYTES)
    record = Bookmark(
        user_id=user.id,
        kind=kind,
        ref_id=payload.ref_id,
        title=payload.title or "",
        description=payload.description,
        code_snippet=payload.code_snippet,
        language=payload.language or "python",
        collection=payload.collection or "default",
        tags_json=list(payload.tags or []),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_bookmark(db: Session, user: User, bookmark_id: str) -> Bookmark:
    """按 id 获取收藏（校验归属）。"""
    record = db.get(Bookmark, bookmark_id)
    if record is None:
        raise AppError(code=ErrorCode.BOOKMARK_NOT_FOUND, message="收藏不存在", status_code=404)
    if record.user_id != user.id:
        raise AppError(code=ErrorCode.FORBIDDEN, message="无权访问他人的收藏", status_code=403)
    return record


def update_bookmark(db: Session, user: User, bookmark_id: str, payload: BookmarkUpdateRequest) -> Bookmark:
    """更新收藏（标题 / 笔记 / 集合 / 标签）。"""
    record = get_bookmark(db, user, bookmark_id)
    data = payload.model_dump(exclude_unset=True)
    if "title" in data and data["title"] is not None:
        record.title = data["title"]
    if "note" in data and data["note"] is not None:
        record.description = data["note"]
    if "collection" in data and data["collection"] is not None:
        record.collection = data["collection"]
    if "tags" in data and data["tags"] is not None:
        record.tags_json = list(data["tags"])
    db.commit()
    db.refresh(record)
    return record


def delete_bookmark(db: Session, user: User, bookmark_id: str) -> None:
    """删除收藏。"""
    record = get_bookmark(db, user, bookmark_id)
    db.delete(record)
    db.commit()


def list_collections(db: Session, user: User) -> list[CollectionOut]:
    """统计我的收藏集合（名称 + 数量）。"""
    rows = db.execute(
        select(Bookmark.collection, func.count(Bookmark.id))
        .where(Bookmark.user_id == user.id)
        .group_by(Bookmark.collection)
        .order_by(func.count(Bookmark.id).desc())
    ).all()
    return [CollectionOut(name=str(name or "default"), count=int(count)) for name, count in rows]


def to_out(record: Bookmark) -> BookmarkOut:
    """ORM → 收藏 Schema。"""
    return BookmarkOut(
        id=record.id,
        kind=record.kind,
        ref_id=record.ref_id,
        title=record.title,
        description=record.description,
        code_snippet=record.code_snippet,
        language=record.language,
        collection=record.collection,
        tags=record.tags,
        created_at=record.created_at,
    )


__all__ = [
    "create_bookmark",
    "delete_bookmark",
    "get_bookmark",
    "list_bookmarks",
    "list_collections",
    "to_out",
    "update_bookmark",
]
