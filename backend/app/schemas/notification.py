"""通知与公告 Schema（`docs/API.md` §2.15）。"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.common import IdStr, ORMModel, StrictModel


class NotificationOut(ORMModel):
    """通知响应体。"""

    id: IdStr
    type: str = "system"
    title: str = ""
    content_md: str | None = None
    link_url: str | None = None
    icon: str | None = None
    is_read: bool = False
    read_at: datetime | None = None
    created_at: datetime | None = None


class NotificationReadAllRequest(StrictModel):
    """批量已读请求体（`type` 为空表示全部类型）。"""

    type: str | None = None


class NotificationReadAllOut(ORMModel):
    """批量已读结果。"""

    updated: int = 0


class AnnouncementOut(ORMModel):
    """公告响应体。"""

    id: IdStr
    title: str
    content_md: str = ""
    level: str = "info"
    is_pinned: bool = False
    published_at: datetime | None = None
    expires_at: datetime | None = None


class AdminAnnouncementIn(StrictModel):
    """管理端公告写入体。"""

    title: str = Field(..., min_length=1, max_length=200)
    content_md: str = ""
    level: str = "info"
    is_pinned: bool = False
    is_active: bool = True
    expires_at: datetime | None = None
