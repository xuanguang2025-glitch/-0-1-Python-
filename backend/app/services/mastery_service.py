"""知识点掌握度服务（SM-2 简化版，`docs/DATABASE.md` §6.2）。

- `apply_practice`：按一次答题结果更新掌握度（正确 +、错误 -）；
- `list_mastery`：我的掌握度列表 + 薄弱知识点；
- `weak_topics`：供推荐 / 报告复用的薄弱知识点查询。
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError, ErrorCode
from app.models.course import Topic
from app.models.enums import MasteryLevel
from app.models.learning import KnowledgeMastery
from app.models.user import User
from app.schemas.progress import KnowledgeMasteryOut, MasteryOverviewOut

logger = logging.getLogger("pythonlab.mastery")

#: 视为「薄弱」的掌握级别
WEAK_LEVELS: tuple[str, ...] = (MasteryLevel.NONE.value, MasteryLevel.WEAK.value)
#: 薄弱判定分数阈值
WEAK_SCORE_THRESHOLD: float = 50.0


def get_or_create_mastery(db: Session, user_id: str, topic_id: str) -> KnowledgeMastery:
    """取用户对某知识点的掌握度记录，缺失时创建（不提交事务）。"""
    record = db.scalars(
        select(KnowledgeMastery).where(
            KnowledgeMastery.user_id == user_id, KnowledgeMastery.topic_id == topic_id
        )
    ).one_or_none()
    if record is None:
        record = KnowledgeMastery(user_id=user_id, topic_id=topic_id)
        db.add(record)
        db.flush()
    return record


def apply_practice(db: Session, user: User, topic_id: str, correct: bool) -> KnowledgeMasteryOut:
    """应用一次答题结果并落库，返回最新掌握度。"""
    topic = db.get(Topic, topic_id)
    if topic is None:
        raise AppError(code=ErrorCode.NOT_FOUND, message="知识点不存在", status_code=404, details=f"topic_id={topic_id}")
    record = get_or_create_mastery(db, user.id, topic_id)
    record.apply_result(correct)
    db.commit()
    db.refresh(record)
    return _to_out(record, topic.name)


def get_topic_mastery(db: Session, user: User, topic_id: str) -> KnowledgeMasteryOut:
    """读取单个知识点掌握度（无记录时返回零值，并附带知识点名称）。"""
    topic = db.get(Topic, topic_id)
    if topic is None:
        raise AppError(code=ErrorCode.NOT_FOUND, message="知识点不存在", status_code=404, details=f"topic_id={topic_id}")
    record = db.scalars(
        select(KnowledgeMastery).where(
            KnowledgeMastery.user_id == user.id, KnowledgeMastery.topic_id == topic_id
        )
    ).one_or_none()
    if record is None:
        return KnowledgeMasteryOut(topic_id=topic_id, name=topic.name)
    return _to_out(record, topic.name)


def list_mastery(db: Session, user: User, parent_topic_id: str | None = None) -> MasteryOverviewOut:
    """我的知识点掌握度列表（可按父知识点过滤），并给出薄弱知识点。"""
    stmt = (
        select(KnowledgeMastery, Topic.name)
        .join(Topic, Topic.id == KnowledgeMastery.topic_id)
        .where(KnowledgeMastery.user_id == user.id)
    )
    if parent_topic_id:
        stmt = stmt.where(Topic.parent_id == parent_topic_id)
    rows = db.execute(stmt.order_by(Topic.order_index.asc())).all()
    topics = [_to_out(record, name) for record, name in rows]
    weak = [item for item in topics if item.mastery_level in WEAK_LEVELS or item.mastery_score < WEAK_SCORE_THRESHOLD]
    average = round(sum(item.mastery_score for item in topics) / len(topics), 2) if topics else 0.0
    return MasteryOverviewOut(topics=topics, weak_topics=weak, average_score=average)


def weak_topics(db: Session, user: User, limit: int = 10) -> list[KnowledgeMasteryOut]:
    """薄弱知识点（分数升序），供复习 / 推荐复用。"""
    stmt = (
        select(KnowledgeMastery, Topic.name)
        .join(Topic, Topic.id == KnowledgeMastery.topic_id)
        .where(KnowledgeMastery.user_id == user.id)
        .order_by(KnowledgeMastery.mastery_score.asc())
        .limit(limit)
    )
    rows = db.execute(stmt).all()
    return [
        _to_out(record, name)
        for record, name in rows
        if record.mastery_level in WEAK_LEVELS or record.mastery_score < WEAK_SCORE_THRESHOLD
    ]


def touch_topics(db: Session, user: User, topic_ids: Sequence[str], correct: bool) -> int:
    """批量更新多个知识点的掌握度（课时完成 / 题目通过时调用），返回更新条数。

    不在此处提交事务，由调用方统一 `commit`，保证一次业务操作原子性。
    """
    count = 0
    for topic_id in dict.fromkeys(topic_ids):
        if not topic_id:
            continue
        if db.get(Topic, topic_id) is None:
            continue
        record = get_or_create_mastery(db, user.id, topic_id)
        record.apply_result(correct)
        count += 1
    return count


def _to_out(record: KnowledgeMastery, name: str | None = None) -> KnowledgeMasteryOut:
    """ORM 掌握度 → Schema。"""
    return KnowledgeMasteryOut(
        id=record.id,
        topic_id=record.topic_id,
        name=name,
        mastery_score=float(record.mastery_score or 0.0),
        mastery_level=record.mastery_level or MasteryLevel.NONE.value,
        practiced_count=int(record.practiced_count or 0),
        correct_count=int(record.correct_count or 0),
        mistake_count=int(record.mistake_count or 0),
        last_practiced_at=record.last_practiced_at,
        next_review_at=record.next_review_at,
    )
