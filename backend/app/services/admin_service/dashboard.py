"""管理端服务 · 仪表盘与系统状态。"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.ai import AIUsageLog
from app.models.submission import Submission
from app.models.user import User
from app.schemas.statistics import DashboardOut
from app.utils.time import today_utc

from .common import ACCEPTED, logger


def day_bounds() -> tuple[datetime, datetime]:
    """返回今日起止（UTC，含首不含尾）。"""
    start = datetime(today_utc().year, today_utc().month, today_utc().day, tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


def dashboard(db: Session) -> DashboardOut:
    """`GET /admin/dashboard`：后台总览。"""
    day_start, _ = day_bounds()
    users_total = int(
        db.scalar(select(func.count()).select_from(User).where(User.deleted_at.is_(None))) or 0
    )
    active_today = int(
        db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.deleted_at.is_(None), User.last_active_at >= day_start)
        )
        or 0
    )
    submissions_today = int(
        db.scalar(
            select(func.count()).select_from(Submission).where(Submission.created_at >= day_start)
        )
        or 0
    )
    accepted_today = int(
        db.scalar(
            select(func.count())
            .select_from(Submission)
            .where(Submission.created_at >= day_start, Submission.status == ACCEPTED)
        )
        or 0
    )
    errors_today = int(
        db.scalar(
            select(func.count())
            .select_from(Submission)
            .where(Submission.created_at >= day_start, Submission.status != ACCEPTED)
        )
        or 0
    )
    ai_calls_today = int(
        db.scalar(
            select(func.count()).select_from(AIUsageLog).where(AIUsageLog.created_at >= day_start)
        )
        or 0
    )

    runner, db_flavor, cache_backend = "local", "sqlite", "memory"
    try:
        from app.services import health_service

        deps = health_service.get_deps_health()
        runner, db_flavor, cache_backend = deps.runner.mode, deps.db.flavor, deps.cache.backend
    except Exception as exc:  # noqa: BLE001 - 健康探测失败不影响仪表盘
        logger.warning("依赖健康探测失败: %s", exc)

    return DashboardOut(
        users_total=users_total,
        active_today=active_today,
        submissions_today=submissions_today,
        acceptance_rate=round(accepted_today / submissions_today, 4) if submissions_today else 0.0,
        ai_calls_today=ai_calls_today,
        error_rate=round(errors_today / submissions_today, 4) if submissions_today else 0.0,
        runner=runner,
        db_flavor=db_flavor,
        cache_backend=cache_backend,
    )
