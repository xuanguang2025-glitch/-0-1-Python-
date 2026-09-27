"""游戏化服务 · 等级与经验（XP）。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.constants import level_of_xp, next_level_xp
from app.models.enums import NotificationType
from app.models.gamification import XPTransaction
from app.models.user import User
from app.services import notification_service

from .common import LEVEL_NAMES


def level_name(level: int) -> str:
    """把 1-7 的等级映射为名称。"""
    index = min(max(int(level or 1), 1), len(LEVEL_NAMES)) - 1
    return LEVEL_NAMES[index]


def level_info(xp: int) -> dict[str, Any]:
    """返回等级信息：等级、名称、下一级阈值与进度百分比。"""
    thresholds = get_settings().level_threshold_list
    level = level_of_xp(int(xp or 0), thresholds)
    current = thresholds[level - 1] if level - 1 < len(thresholds) else thresholds[-1]
    nxt = next_level_xp(int(xp or 0), thresholds)
    span = max(1, nxt - current)
    percent = 100 if int(xp or 0) >= thresholds[-1] else int(round((int(xp or 0) - current) / span * 100))
    return {
        "level": level,
        "level_name": level_name(level),
        "xp": int(xp or 0),
        "next_level_xp": nxt,
        "progress_percent": max(0, min(100, percent)),
    }


def award_xp(
    db: Session,
    user: User,
    amount: int,
    reason: str,
    ref_type: str | None = None,
    ref_id: str | None = None,
) -> tuple[int, bool]:
    """发放经验值并写入流水，返回 `(实际发放额, 是否升级)`。

    仅当额度 > 0 时生效；**不提交事务**，由调用方统一 commit。
    """
    amount = int(amount)
    if amount <= 0:
        return 0, False
    user.xp = int(user.xp or 0) + amount
    old_level = int(user.level or 1)
    new_level = level_of_xp(user.xp, get_settings().level_threshold_list)
    user.level = new_level
    db.add(
        XPTransaction(
            user_id=user.id,
            amount=amount,
            reason=reason,
            ref_type=ref_type,
            ref_id=ref_id,
            balance_after=user.xp,
        )
    )
    db.flush()
    level_up = new_level > old_level
    if level_up:
        notification_service.create(
            db,
            user,
            NotificationType.SYSTEM.value,
            f"升级！Lv.{new_level} {level_name(new_level)}",
            f"恭喜你升到 Lv.{new_level}「{level_name(new_level)}」，继续加油！",
            link="/me",
        )
    return amount, level_up
