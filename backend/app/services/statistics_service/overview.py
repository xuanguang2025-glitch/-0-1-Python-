"""统计报表服务 · 概览与名次。"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.course import CourseEnrollment
from app.models.learning import LearningSession
from app.models.project import UserProject
from app.models.user import User
from app.schemas.statistics import RankingOut, StatisticsOverviewOut

from .common import mastery_topics, rank_stats, solved_count, submit_stats, total_seconds


def overview(db: Session, user: User) -> StatisticsOverviewOut:
    """`GET /statistics/overview`。"""
    seconds = total_seconds(db, user.id)
    submissions, accepted = submit_stats(db, user.id)
    _, _, percentile = rank_stats(db, user)

    run_count = int(
        db.scalar(
            select(func.coalesce(func.sum(LearningSession.actions_count), 0)).where(
                LearningSession.user_id == user.id
            )
        )
        or 0
    )
    projects = int(
        db.scalar(select(func.count()).select_from(UserProject).where(UserProject.user_id == user.id)) or 0
    )
    courses = int(
        db.scalar(select(func.count()).select_from(CourseEnrollment).where(CourseEnrollment.user_id == user.id))
        or 0
    )
    strongest = mastery_topics(db, user.id, ascending=False)
    weakest = mastery_topics(db, user.id, ascending=True)

    return StatisticsOverviewOut(
        total_minutes=seconds // 60,
        solved=solved_count(db, user.id),
        submissions=submissions,
        accepted=accepted,
        acceptance_rate=round(accepted / submissions, 4) if submissions else 0.0,
        streak_days=int(user.streak_days or 0),
        xp=int(user.xp or 0),
        level=int(user.level or 1),
        rank_percentile=percentile,
        run_count=run_count,
        projects=projects,
        courses=courses,
        strongest_topic=strongest[0] if strongest else None,
        weakest_topic=weakest[0] if weakest else None,
    )


def ranking(db: Session, user: User) -> RankingOut:
    """`GET /statistics/ranking`：只返回名次，不暴露他人信息。"""
    rank, total, percentile = rank_stats(db, user)
    return RankingOut(my_rank=rank, total_users=total, percentile=percentile, xp=int(user.xp or 0))
