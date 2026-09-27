"""游戏化服务 · 成就与解锁。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.constants import XP_REASON_ACHIEVEMENT
from app.core.errors import AppError, ErrorCode
from app.core.pagination import PageParams
from app.models.enums import NotificationType
from app.models.gamification import Achievement, UserAchievement
from app.models.user import User
from app.schemas.gamification import (
    AchievementOut,
    BadgeWallCategory,
    BadgeWallOut,
    UserAchievementOut,
)
from app.services import notification_service
from app.utils.time import now_utc

from .common import count, logger
from .levels import award_xp
from .metrics import build_metrics, satisfied


def unlocked_ids(db: Session, user_id: str) -> dict[str, datetime]:
    """返回用户已解锁成就的 `{achievement_id: unlocked_at}`。"""
    rows = db.scalars(select(UserAchievement).where(UserAchievement.user_id == user_id)).all()
    return {row.achievement_id: row.unlocked_at for row in rows}


def get_achievements(db: Session, user: User, category: str | None = None) -> list[AchievementOut]:
    """全部成就定义（含当前用户的解锁状态），可按分类筛选。"""
    stmt = select(Achievement).where(Achievement.is_active.is_(True))
    if category:
        stmt = stmt.where(Achievement.category == category)
    items = list(db.scalars(stmt.order_by(Achievement.order_index.asc())).all())
    unlocked = unlocked_ids(db, user.id)
    result: list[AchievementOut] = []
    for item in items:
        out = AchievementOut.model_validate(item)
        out.unlocked = item.id in unlocked
        out.unlocked_at = unlocked.get(item.id)
        result.append(out)
    return result


def get_badge_wall(db: Session, user: User) -> BadgeWallOut:
    """徽章墙数据：按分类统计解锁进度 + 全部成就。"""
    achievements = get_achievements(db, user)
    buckets: dict[str, BadgeWallCategory] = {}
    for item in achievements:
        bucket = buckets.setdefault(item.category, BadgeWallCategory(category=item.category))
        bucket.total += 1
        if item.unlocked:
            bucket.unlocked += 1
    return BadgeWallOut(
        total=len(achievements),
        unlocked=sum(1 for item in achievements if item.unlocked),
        categories=[buckets[key] for key in sorted(buckets)],
        achievements=achievements,
    )


def list_my_achievements(
    db: Session, user: User, params: PageParams
) -> tuple[list[UserAchievementOut], int]:
    """分页返回我的成就记录。"""
    total = count(
        db, select(func.count()).select_from(UserAchievement).where(UserAchievement.user_id == user.id)
    )
    rows = list(
        db.scalars(
            select(UserAchievement)
            .where(UserAchievement.user_id == user.id)
            .order_by(UserAchievement.unlocked_at.desc())
            .offset(params.offset)
            .limit(params.limit)
        ).all()
    )
    items: list[UserAchievementOut] = []
    for row in rows:
        out = UserAchievementOut.model_validate(row)
        if row.achievement is not None:
            ach = AchievementOut.model_validate(row.achievement)
            ach.unlocked = True
            ach.unlocked_at = row.unlocked_at
            out.achievement = ach
        items.append(out)
    return items, total


def mark_seen(db: Session, user: User, achievement_id: str) -> None:
    """把某成就标记为已弹窗提示（幂等）。"""
    row = db.scalars(
        select(UserAchievement).where(
            UserAchievement.user_id == user.id, UserAchievement.achievement_id == achievement_id
        )
    ).one_or_none()
    if row is None:
        raise AppError(code=ErrorCode.NOT_FOUND, message="尚未解锁该成就", status_code=404)
    row.mark_seen()
    db.commit()


def check_and_unlock(db: Session, user: User, event: dict[str, Any] | None = None) -> list[str]:
    """**服务端统一解锁入口**（供其他域调用）。

    Args:
        db: 数据库会话。
        user: 目标用户。
        event: 触发事件快照（如 `{"metric": "lessons_completed", "hour": 9}`），可选。

    Returns:
        本次新解锁成就的 `code` 列表（幂等：已解锁不重复发放）。
    """
    metrics = build_metrics(db, user, event)
    unlocked = unlocked_ids(db, user.id)
    achievements = list(
        db.scalars(select(Achievement).where(Achievement.is_active.is_(True)).order_by(Achievement.order_index)).all()
    )
    newly: list[str] = []
    for achievement in achievements:
        if achievement.id in unlocked:
            continue
        if not satisfied(achievement.condition, metrics):
            continue
        db.add(UserAchievement(user_id=user.id, achievement_id=achievement.id))
        db.flush()
        unlocked[achievement.id] = now_utc()
        award_xp(db, user, int(achievement.xp_reward or 0), XP_REASON_ACHIEVEMENT, "achievement", achievement.id)
        notification_service.create(
            db,
            user,
            NotificationType.ACHIEVEMENT.value,
            f"解锁成就：{achievement.name}",
            achievement.description or "",
            link="/achievements",
            icon=achievement.icon,
        )
        newly.append(achievement.code)
    if newly:
        db.commit()
        logger.info("用户 %s 解锁成就：%s", user.id, ",".join(newly))
    return newly


def check_achievements(db: Session, user: User, event: dict[str, Any] | None = None) -> list[str]:
    """兼容入口：内容域 / 判题域以该名称调用成就解锁。

    与 `check_and_unlock` 行为完全一致（真实解锁 + 幂等 + 发 XP + 发通知），
    仅函数名不同。用于消除跨域 `getattr(module, "check_achievements", None)` 的
    静默失效（历史上 `getattr` 兜底会把"函数名写错"吞成永远不报错的空操作）。
    """
    return check_and_unlock(db, user, event)
