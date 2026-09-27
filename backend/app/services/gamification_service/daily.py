"""游戏化服务 · 每日任务。"""

from __future__ import annotations

from datetime import date as DateType

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError, ErrorCode
from app.models.enums import NotificationType
from app.models.gamification import DailyTask, UserDailyTask
from app.models.user import User
from app.schemas.gamification import DailyTaskCheckOut, UserDailyTaskOut
from app.services import notification_service
from app.utils.time import now_utc, today_utc

from .common import DAILY_METRIC_KEYS
from .levels import award_xp
from .metrics import build_metrics


def ensure_daily_tasks(db: Session, user: User, target: DateType) -> list[UserDailyTask]:
    """确保当天每个启用任务都有用户进度行（幂等）。"""
    tasks = list(
        db.scalars(select(DailyTask).where(DailyTask.is_active.is_(True)).order_by(DailyTask.order_index)).all()
    )
    existing = {
        row.daily_task_id: row
        for row in db.scalars(
            select(UserDailyTask).where(UserDailyTask.user_id == user.id, UserDailyTask.date == target)
        ).all()
    }
    for task in tasks:
        if task.id not in existing:
            row = UserDailyTask(user_id=user.id, daily_task_id=task.id, date=target, progress=0, completed=False)
            db.add(row)
            existing[task.id] = row
    db.flush()
    return [existing[task.id] for task in tasks]


def get_daily_tasks(db: Session, user: User, target: DateType | None = None) -> list[UserDailyTaskOut]:
    """`GET /achievements/daily-tasks`：当天任务列表（含进度）。"""
    target = target or today_utc()
    rows = ensure_daily_tasks(db, user, target)
    db.commit()
    result: list[UserDailyTaskOut] = []
    for row in rows:
        task = row.daily_task
        result.append(
            UserDailyTaskOut(
                id=row.id,
                daily_task_id=row.daily_task_id,
                date=row.date,
                progress=int(row.progress or 0),
                target=int(task.target_count or 1) if task else 1,
                completed=bool(row.completed),
                completed_at=row.completed_at,
                xp_reward=int(task.xp_reward or 0) if task else 0,
                title=task.title if task else "",
                code=task.code if task else "",
            )
        )
    return result


def check_daily_task(db: Session, user: User, user_task_id: str) -> DailyTaskCheckOut:
    """`POST /achievements/daily-tasks/{id}/check`：按实时指标推进并结算 XP（幂等）。"""
    row = db.get(UserDailyTask, user_task_id)
    if row is None or row.user_id != user.id:
        raise AppError(code=ErrorCode.NOT_FOUND, message="每日任务不存在", status_code=404)
    task = row.daily_task
    metric_key = DAILY_METRIC_KEYS.get(task.metric if task else "", "submissions_today")
    metrics = build_metrics(db, user)
    value = int(metrics.get(metric_key, 0))
    target = int(task.target_count or 1) if task else 1
    row.progress = max(int(row.progress or 0), value)

    xp_earned = 0
    if not row.completed and row.progress >= target:
        row.completed = True
        row.completed_at = now_utc()
        xp_earned, _ = award_xp(
            db, user, int(task.xp_reward or 0) if task else 0, "daily_task", "daily_task", row.daily_task_id
        )
        notification_service.create(
            db,
            user,
            NotificationType.DAILY.value,
            f"每日任务完成：{task.title if task else ''}",
            f"获得 {xp_earned} XP",
            link="/achievements",
        )
    db.commit()
    return DailyTaskCheckOut(
        progress=int(row.progress or 0),
        target=target,
        completed=bool(row.completed),
        xp_earned=xp_earned,
    )
