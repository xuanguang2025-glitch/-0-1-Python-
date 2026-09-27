"""统计报表服务 · 周期报告（周报 / 月报）。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import ProgressStatus
from app.models.learning import LearningProgress, LearningSession
from app.models.problem import Problem
from app.models.submission import Submission
from app.models.user import User
from app.schemas.statistics import (
    RecommendationItem,
    ReportMetrics,
    ReportOut,
    WeakTopicItem,
)
from app.utils.time import format_minutes

from .common import ACCEPTED, mastery_topics, window


def report(db: Session, user: User, period: str = "week") -> ReportOut:
    """`GET /statistics/report`：周报 / 月报。"""
    period = "month" if period == "month" else "week"
    start_date, end_date, _ = window(period)
    since = datetime(start_date.year, start_date.month, start_date.day, tzinfo=timezone.utc)

    minutes = int(
        db.scalar(
            select(func.coalesce(func.sum(LearningSession.duration_seconds), 0)).where(
                LearningSession.user_id == user.id, LearningSession.started_at >= since
            )
        )
        or 0
    ) // 60
    lessons = int(
        db.scalar(
            select(func.count())
            .select_from(LearningProgress)
            .where(
                LearningProgress.user_id == user.id,
                LearningProgress.status == ProgressStatus.COMPLETED.value,
                LearningProgress.completed_at >= since,
            )
        )
        or 0
    )
    submissions = int(
        db.scalar(
            select(func.count())
            .select_from(Submission)
            .where(Submission.user_id == user.id, Submission.created_at >= since)
        )
        or 0
    )
    accepted = int(
        db.scalar(
            select(func.count())
            .select_from(Submission)
            .where(Submission.user_id == user.id, Submission.status == ACCEPTED, Submission.created_at >= since)
        )
        or 0
    )

    metrics = ReportMetrics(
        minutes=minutes,
        lessons=lessons,
        submissions=submissions,
        accepted=accepted,
        acceptance_rate=round(accepted / submissions, 4) if submissions else 0.0,
    )
    highlights: list[str] = []
    if lessons:
        highlights.append(f"完成 {lessons} 个课时")
    if accepted:
        highlights.append(f"通过 {accepted} 道题目")
    if minutes:
        highlights.append(f"累计学习 {format_minutes(minutes)}")
    if int(user.streak_days or 0) > 1:
        highlights.append(f"连续学习 {int(user.streak_days)} 天")

    weak_topics = mastery_topics(db, user.id, ascending=True, limit=5)
    recommendations = build_recommendations(db, user, weak_topics)
    summary = (
        f"本{'月' if period == 'month' else '周'}你学习 {format_minutes(minutes)}，"
        f"完成 {lessons} 个课时，提交 {submissions} 次（通过 {accepted} 次）。"
    )
    return ReportOut(
        period=period,
        start_date=start_date,
        end_date=end_date,
        summary_md=summary,
        highlights=highlights,
        metrics=metrics,
        weak_topics=weak_topics,
        recommendations=recommendations,
        degraded=False,
    )


def build_recommendations(
    db: Session, user: User, weak_topics: list[WeakTopicItem]
) -> list[RecommendationItem]:
    """基于薄弱知识点推荐未通过题目（最多 3 条）。"""
    solved_ids = set(
        db.scalars(
            select(Submission.problem_id).where(
                Submission.user_id == user.id,
                Submission.status == ACCEPTED,
                Submission.problem_id.is_not(None),
            )
        ).all()
    )
    stmt = select(Problem).where(Problem.is_published.is_(True))
    if solved_ids:
        stmt = stmt.where(Problem.id.not_in(solved_ids))
    problems = list(db.scalars(stmt.order_by(Problem.difficulty.asc(), Problem.id.asc()).limit(3)).all())
    reason = weak_topics[0].name if weak_topics else "巩固基础知识"
    return [
        RecommendationItem(type="problem", id=item.id, title=item.title, reason=f"强化「{reason}」")
        for item in problems
    ]
