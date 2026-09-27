"""通知与公告服务（`docs/API.md` §2.15）。

提供 `create()` 作为**跨域统一入口**：每日提醒 / 新课程 / 项目更新 / 挑战开始 /
成就解锁 / 学习完成等场景均由其他服务调用本模块落库。
"""

from __future__ import annotations

import logging

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.errors import AppError, ErrorCode
from app.core.pagination import PageParams
from app.models.enums import NotificationType
from app.models.notification import Announcement, Notification
from app.models.user import User
from app.utils.time import now_utc, to_utc

logger = logging.getLogger("pythonlab.notification")


def _is_visible(announcement: Announcement) -> bool:
    """安全判断公告是否可见（归一化时区，避免 naive/aware 比较异常）。"""
    if not announcement.is_active:
        return False
    if announcement.expires_at is None:
        return True
    return to_utc(announcement.expires_at) > now_utc()


def create(
    db: Session,
    user: User | str,
    ntype: str,
    title: str,
    content: str = "",
    link: str | None = None,
    icon: str | None = None,
) -> Notification:
    """创建一条站内通知（**不提交**，由调用方统一 commit）。

    Args:
        db: 数据库会话。
        user: 目标用户对象或其 id。
        ntype: 通知类型（见 `NotificationType`）。
        title: 标题。
        content: 内容（Markdown）。
        link: 跳转地址。
        icon: 图标名。

    Returns:
        新建的 `Notification`（已 flush，带 id）。
    """
    user_id = user.id if isinstance(user, User) else str(user)
    if ntype not in NotificationType.values():
        ntype = NotificationType.SYSTEM.value
    item = Notification(
        user_id=user_id,
        type=ntype,
        title=title[:200],
        content_md=content or None,
        link_url=link,
        icon=icon,
    )
    db.add(item)
    db.flush()
    return item


def create_many(db: Session, user_ids: list[str], ntype: str, title: str, content: str = "", link: str | None = None) -> int:
    """给多个用户批量创建通知（管理端广播用），返回创建条数。"""
    count = 0
    for user_id in user_ids:
        create(db, user_id, ntype, title, content, link)
        count += 1
    return count


def list_notifications(
    db: Session,
    user: User,
    params: PageParams,
    *,
    is_read: bool | None = None,
    ntype: str | None = None,
) -> tuple[list[Notification], int]:
    """分页查询当前用户的通知（可按已读状态 / 类型筛选）。"""
    conditions = [Notification.user_id == user.id]
    if is_read is not None:
        conditions.append(Notification.is_read.is_(is_read))
    if ntype:
        conditions.append(Notification.type == ntype)

    total = int(db.scalar(select(func.count()).select_from(Notification).where(*conditions)) or 0)
    stmt = (
        select(Notification)
        .where(*conditions)
        .order_by(Notification.created_at.desc())
        .offset(params.offset)
        .limit(params.limit)
    )
    return list(db.scalars(stmt).all()), total


def unread_count(db: Session, user: User) -> int:
    """未读通知数。"""
    return int(
        db.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user.id, Notification.is_read.is_(False))
        )
        or 0
    )


def get_owned(db: Session, user: User, notification_id: str) -> Notification:
    """获取属于当前用户的通知（不存在抛 404）。"""
    item = db.get(Notification, notification_id)
    if item is None or item.user_id != user.id:
        raise AppError(code=ErrorCode.NOTIFICATION_NOT_FOUND, message="通知不存在", status_code=404)
    return item


def mark_read(db: Session, user: User, notification_id: str) -> Notification:
    """标记单条通知为已读。"""
    item = get_owned(db, user, notification_id)
    item.mark_read()
    db.commit()
    db.refresh(item)
    return item


def mark_all_read(db: Session, user: User, ntype: str | None = None) -> int:
    """批量标记已读，返回受影响条数。"""
    stmt = (
        update(Notification)
        .where(Notification.user_id == user.id, Notification.is_read.is_(False))
        .values(is_read=True, read_at=now_utc())
    )
    if ntype:
        stmt = stmt.where(Notification.type == ntype)
    result = db.execute(stmt)
    db.commit()
    return int(result.rowcount or 0)


def delete(db: Session, user: User, notification_id: str) -> None:
    """删除属于当前用户的通知。"""
    item = get_owned(db, user, notification_id)
    db.delete(item)
    db.commit()


def list_announcements(db: Session, limit: int = 5) -> list[Announcement]:
    """公开公告列表（仅生效中，置顶优先，按发布时间倒序）。"""
    stmt = (
        select(Announcement)
        .where(Announcement.is_active.is_(True))
        .order_by(Announcement.is_pinned.desc(), Announcement.published_at.desc())
        .limit(max(1, min(50, limit)))
    )
    items = list(db.scalars(stmt).all())
    return [item for item in items if _is_visible(item)]


def get_announcement(db: Session, announcement_id: str) -> Announcement:
    """公告详情（不存在抛 404）。"""
    item = db.get(Announcement, announcement_id)
    if item is None:
        raise AppError(code=ErrorCode.NOT_FOUND, message="公告不存在", status_code=404)
    return item
