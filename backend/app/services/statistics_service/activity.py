"""统计报表服务 · 趋势与活跃热力图。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.learning import LearningSession
from app.models.submission import Submission
from app.models.user import User
from app.schemas.progress import HeatmapOut, HeatmapPoint
from app.schemas.statistics import TrendOut, TrendPoint
from app.utils.time import last_n_days

from .common import ACCEPTED, TREND_METRICS, daily_map


def trend(db: Session, user: User, days: int = 30, metric: str = "submissions") -> TrendOut:
    """`GET /statistics/trend`：按日聚合指定指标。"""
    days = max(1, min(365, int(days or 30)))
    metric = metric if metric in TREND_METRICS else "submissions"
    win = last_n_days(days)
    since = datetime(win[0].year, win[0].month, win[0].day, tzinfo=timezone.utc)

    if metric == "minutes":
        rows = db.execute(
            select(func.date(LearningSession.started_at), func.sum(LearningSession.duration_seconds))
            .where(LearningSession.user_id == user.id, LearningSession.started_at >= since)
            .group_by(func.date(LearningSession.started_at))
        ).all()
        daily = {key: int(value or 0) // 60 for key, value in daily_map(rows).items()}
    else:
        stmt = select(func.date(Submission.created_at), func.count()).where(
            Submission.user_id == user.id, Submission.created_at >= since
        )
        if metric == "accepted":
            stmt = stmt.where(Submission.status == ACCEPTED)
        rows = db.execute(stmt.group_by(func.date(Submission.created_at))).all()
        daily = daily_map(rows)

    points = [TrendPoint(date=day, value=float(daily.get(day.isoformat(), 0))) for day in win]
    return TrendOut(metric=metric, points=points, total=float(sum(point.value for point in points)))


def heatmap(db: Session, user: User, days: int = 180) -> HeatmapOut:
    """`GET /statistics/heatmap`：按日聚合活跃次数与学习分钟（供热力图）。"""
    days = max(1, min(365, int(days or 180)))
    win = last_n_days(days)
    since = datetime(win[0].year, win[0].month, win[0].day, tzinfo=timezone.utc)

    sub_rows = db.execute(
        select(func.date(Submission.created_at), func.count())
        .where(Submission.user_id == user.id, Submission.created_at >= since)
        .group_by(func.date(Submission.created_at))
    ).all()
    sub_map = daily_map(sub_rows)

    session_rows = db.execute(
        select(func.date(LearningSession.started_at), func.count(), func.sum(LearningSession.duration_seconds))
        .where(LearningSession.user_id == user.id, LearningSession.started_at >= since)
        .group_by(func.date(LearningSession.started_at))
    ).all()
    sess_count: dict[str, int] = {}
    sess_minutes: dict[str, int] = {}
    for key, count, seconds in session_rows:
        if key is None:
            continue
        day = key.isoformat() if hasattr(key, "isoformat") else str(key)
        sess_count[day] = int(count or 0)
        sess_minutes[day] = int(seconds or 0) // 60

    points: list[HeatmapPoint] = []
    for day in win:
        key = day.isoformat()
        points.append(
            HeatmapPoint(
                date=day,
                count=sub_map.get(key, 0) + sess_count.get(key, 0),
                minutes=sess_minutes.get(key, 0),
            )
        )
    active = [p for p in points if p.count > 0]
    return HeatmapOut(
        points=points,
        total_count=sum(p.count for p in points),
        active_days=len(active),
        max_count=max((p.count for p in points), default=0),
    )
