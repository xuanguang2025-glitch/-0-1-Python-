"""错题本服务（`docs/API.md` §2.18）。

除标准 CRUD 外，提供「高频错误知识点统计」，用于学习报告与复习计划。
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError, ErrorCode
from app.core.pagination import PageParams, paginate
from app.models.course import Topic
from app.models.learning import Mistake
from app.models.user import User
from app.schemas.mistake import MistakeCreateRequest, MistakeOut, MistakeUpdateRequest

logger = logging.getLogger("pythonlab.mistake")


def list_mistakes(
    db: Session,
    user: User,
    *,
    error_type: str | None,
    topic_id: str | None,
    resolved: bool | None,
    params: PageParams,
) -> tuple[list[Mistake], int]:
    """分页列出错题（可按错误类型 / 知识点 / 是否已掌握筛选）。"""
    stmt = select(Mistake).where(Mistake.user_id == user.id)
    if error_type:
        stmt = stmt.where(Mistake.error_type == error_type)
    if topic_id:
        stmt = stmt.where(Mistake.topic_id == topic_id)
    if resolved is not None:
        stmt = stmt.where(Mistake.resolved.is_(bool(resolved)))
    stmt = stmt.order_by(Mistake.updated_at.desc(), Mistake.created_at.desc())
    return paginate(db, stmt, params)


def create_mistake(db: Session, user: User, payload: MistakeCreateRequest) -> Mistake:
    """手动新增错题。"""
    record = Mistake(
        user_id=user.id,
        problem_id=payload.problem_id,
        submission_id=payload.submission_id,
        lesson_id=payload.lesson_id,
        topic_id=payload.topic_id,
        title=payload.title or "错题",
        user_answer=payload.user_answer,
        correct_answer=payload.correct_answer,
        error_type=payload.error_type,
        error_message=payload.error_message,
        note_md=payload.note_md,
    )
    record.schedule_review(1)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_mistake(db: Session, user: User, mistake_id: str) -> Mistake:
    """按 id 获取错题（校验归属）。"""
    record = db.get(Mistake, mistake_id)
    if record is None:
        raise AppError(code=ErrorCode.MISTAKE_NOT_FOUND, message="错题不存在", status_code=404)
    if record.user_id != user.id:
        raise AppError(code=ErrorCode.FORBIDDEN, message="无权访问他人的错题", status_code=403)
    return record


def update_mistake(db: Session, user: User, mistake_id: str, payload: MistakeUpdateRequest) -> Mistake:
    """更新错题笔记 / 知识点。"""
    record = get_mistake(db, user, mistake_id)
    data = payload.model_dump(exclude_unset=True)
    if "note_md" in data and data["note_md"] is not None:
        record.note_md = data["note_md"]
    if "topic_id" in data and data["topic_id"] is not None:
        record.topic_id = data["topic_id"]
    db.commit()
    db.refresh(record)
    return record


def resolve_mistake(db: Session, user: User, mistake_id: str, resolved: bool) -> Mistake:
    """标记 / 取消「已掌握」。"""
    record = get_mistake(db, user, mistake_id)
    record.resolve(bool(resolved))
    db.commit()
    db.refresh(record)
    return record


def delete_mistake(db: Session, user: User, mistake_id: str) -> None:
    """删除错题。"""
    record = get_mistake(db, user, mistake_id)
    db.delete(record)
    db.commit()


def review_queue(db: Session, user: User, *, limit: int = 10) -> list[Mistake]:
    """复习队列：按下次复习时间升序取未掌握错题。"""
    stmt = (
        select(Mistake)
        .where(Mistake.user_id == user.id, Mistake.resolved.is_(False))
        .order_by(Mistake.next_review_at.asc().nullsfirst(), Mistake.updated_at.asc())
        .limit(max(1, min(50, limit)))
    )
    return list(db.scalars(stmt).all())


def high_frequency_topics(db: Session, user: User, *, limit: int = 10) -> list[dict[str, Any]]:
    """高频错误知识点统计（按错误次数降序）。"""
    rows = db.execute(
        select(
            Mistake.topic_id,
            Topic.name,
            func.count(Mistake.id).label("mistake_count"),
            func.sum(Mistake.review_count).label("error_count"),
        )
        .outerjoin(Topic, Topic.id == Mistake.topic_id)
        .where(Mistake.user_id == user.id)
        .group_by(Mistake.topic_id, Topic.name)
        .order_by(func.count(Mistake.id).desc())
        .limit(max(1, min(50, limit)))
    ).all()
    return [
        {
            "topic_id": topic_id,
            "name": name or "未归类",
            "mistake_count": int(mistake_count or 0),
            "error_count": int(error_count or 0),
        }
        for topic_id, name, mistake_count, error_count in rows
    ]


def to_out(record: Mistake) -> MistakeOut:
    """ORM → 错题 Schema。"""
    return MistakeOut.model_validate(record)


__all__ = [
    "create_mistake",
    "delete_mistake",
    "get_mistake",
    "high_frequency_topics",
    "list_mistakes",
    "resolve_mistake",
    "review_queue",
    "to_out",
    "update_mistake",
]
