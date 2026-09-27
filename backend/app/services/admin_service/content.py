"""管理端服务 · 标签 / 公告。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ErrorCode
from app.core.pagination import PageParams
from app.models.notification import Announcement
from app.models.problem import Tag
from app.models.user import User
from app.utils.time import now_utc

from .common import apply_fields, audit, get_or_404, snapshot


def list_tags(db: Session) -> list[Tag]:
    """标签列表。"""
    return list(db.scalars(select(Tag).order_by(Tag.order_index.asc())).all())


def create_tag(db: Session, actor: User, payload: dict[str, Any], meta: dict[str, Any]) -> Tag:
    """新建标签。"""
    tag = Tag(**payload)
    db.add(tag)
    db.flush()
    audit(db, actor, "admin.tag.create", "tag", tag.id, after={"slug": tag.slug}, meta=meta)
    db.commit()
    db.refresh(tag)
    return tag


def update_tag(db: Session, actor: User, tag_id: str, payload: dict[str, Any], meta: dict[str, Any]) -> Tag:
    """更新标签。"""
    tag = get_or_404(db, Tag, tag_id, ErrorCode.NOT_FOUND, "标签不存在")
    apply_fields(tag, payload)
    audit(db, actor, "admin.tag.update", "tag", tag.id, meta=meta)
    db.commit()
    db.refresh(tag)
    return tag


def delete_tag(db: Session, actor: User, tag_id: str, meta: dict[str, Any]) -> None:
    """删除标签。"""
    tag = get_or_404(db, Tag, tag_id, ErrorCode.NOT_FOUND, "标签不存在")
    db.delete(tag)
    audit(db, actor, "admin.tag.delete", "tag", tag_id, meta=meta)
    db.commit()


def list_announcements(db: Session, params: PageParams) -> tuple[list[Announcement], int]:
    """公告列表（含下线）。"""
    total = int(db.scalar(select(func.count()).select_from(Announcement)) or 0)
    rows = list(
        db.scalars(
            select(Announcement)
            .order_by(Announcement.published_at.desc())
            .offset(params.offset)
            .limit(params.limit)
        ).all()
    )
    return rows, total


def create_announcement(
    db: Session, actor: User, payload: dict[str, Any], meta: dict[str, Any]
) -> Announcement:
    """新建公告。"""
    item = Announcement(**payload, created_by=actor.id, published_at=now_utc())
    db.add(item)
    db.flush()
    audit(db, actor, "admin.announcement.create", "announcement", item.id, after={"title": item.title}, meta=meta)
    db.commit()
    db.refresh(item)
    return item


def update_announcement(
    db: Session, actor: User, announcement_id: str, payload: dict[str, Any], meta: dict[str, Any]
) -> Announcement:
    """更新公告 / 发布 / 下线。"""
    item = get_or_404(db, Announcement, announcement_id, ErrorCode.NOT_FOUND, "公告不存在")
    before = snapshot(item, ["is_active", "is_pinned"])
    apply_fields(item, payload)
    audit(
        db, actor, "admin.announcement.update", "announcement", item.id,
        before=before, after=snapshot(item, ["is_active", "is_pinned"]), meta=meta,
    )
    db.commit()
    db.refresh(item)
    return item


def delete_announcement(db: Session, actor: User, announcement_id: str, meta: dict[str, Any]) -> None:
    """删除公告。"""
    item = get_or_404(db, Announcement, announcement_id, ErrorCode.NOT_FOUND, "公告不存在")
    db.delete(item)
    audit(db, actor, "admin.announcement.delete", "announcement", announcement_id, meta=meta)
    db.commit()
