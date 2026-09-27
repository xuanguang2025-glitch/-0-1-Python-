"""统计报表服务 · 公共聚合辅助（一律走 SQL，不在 Python 里全表遍历）。"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.course import Topic
from app.models.enums import SubmissionStatus
from app.models.learning import KnowledgeMastery, LearningProgress, LearningSession
from app.models.submission import Submission
from app.models.user import User
from app.schemas.statistics import WeakTopicItem
from app.utils.time import today_utc

ACCEPTED: str = SubmissionStatus.ACCEPTED.value
TREND_METRICS: tuple[str, ...] = ("submissions", "accepted", "minutes")


def rank_stats(db: Session, user: User) -> tuple[int | None, int, float]:
    """返回 `(我的名次, 总人数, 百分位)`；仅基于 XP，不返回他人信息。"""
    base = [User.deleted_at.is_(None), User.status != "deleted"]
    total = int(db.scalar(select(func.count()).select_from(User).where(*base)) or 0)
    if total == 0:
        return None, 0, 0.0
    higher = int(
        db.scalar(select(func.count()).select_from(User).where(*base, User.xp > int(user.xp or 0))) or 0
    )
    rank = higher + 1
    percentile = round((1 - (rank - 1) / total) * 100, 1) if total else 0.0
    return rank, total, percentile


def total_seconds(db: Session, user_id: str) -> int:
    """累计学习秒数：优先学习会话，缺失时回退课时进度累计。"""
    total = int(
        db.scalar(
            select(func.coalesce(func.sum(LearningSession.duration_seconds), 0)).where(
                LearningSession.user_id == user_id
            )
        )
        or 0
    )
    if not total:
        total = int(
            db.scalar(
                select(func.coalesce(func.sum(LearningProgress.time_spent_seconds), 0)).where(
                    LearningProgress.user_id == user_id
                )
            )
            or 0
        )
    return total


def submit_stats(db: Session, user_id: str) -> tuple[int, int]:
    """返回 `(提交总数, 通过数)`。"""
    total = int(
        db.scalar(select(func.count()).select_from(Submission).where(Submission.user_id == user_id)) or 0
    )
    accepted = int(
        db.scalar(
            select(func.count())
            .select_from(Submission)
            .where(Submission.user_id == user_id, Submission.status == ACCEPTED)
        )
        or 0
    )
    return total, accepted


def solved_count(db: Session, user_id: str) -> int:
    """通过的不同题目数。"""
    return int(
        db.scalar(
            select(func.count(func.distinct(Submission.problem_id))).where(
                Submission.user_id == user_id,
                Submission.status == ACCEPTED,
                Submission.problem_id.is_not(None),
            )
        )
        or 0
    )


def mastery_topics(
    db: Session, user_id: str, *, ascending: bool, limit: int = 1
) -> list[WeakTopicItem]:
    """按掌握度排序取知识点（`ascending=True` 取最薄弱）。"""
    order = KnowledgeMastery.mastery_score.asc() if ascending else KnowledgeMastery.mastery_score.desc()
    rows = db.execute(
        select(KnowledgeMastery.topic_id, Topic.name, KnowledgeMastery.mastery_score)
        .join(Topic, Topic.id == KnowledgeMastery.topic_id)
        .where(KnowledgeMastery.user_id == user_id, KnowledgeMastery.practiced_count > 0)
        .order_by(order)
        .limit(limit)
    ).all()
    return [WeakTopicItem(topic_id=str(r[0]), name=str(r[1] or ""), score=float(r[2] or 0.0)) for r in rows]


def daily_map(rows: list[tuple[object, object]]) -> dict[str, int]:
    """把 `(date, value)` 查询结果转换为 `{date_str: int}`。"""
    result: dict[str, int] = {}
    for key, value in rows:
        if key is None:
            continue
        day = key.isoformat() if hasattr(key, "isoformat") else str(key)
        result[day] = result.get(day, 0) + int(value or 0)
    return result


def window(period: str) -> tuple[date, date, int]:
    """返回 `(起始日, 结束日, 天数)`。"""
    span = 30 if period == "month" else 7
    end = today_utc()
    return end - timedelta(days=span - 1), end, span
