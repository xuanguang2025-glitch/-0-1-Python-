"""游戏化服务 · 公共常量与工具。"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.enums import SubmissionStatus

logger = logging.getLogger("pythonlab.gamification")

ACCEPTED: str = SubmissionStatus.ACCEPTED.value

#: 7 级等级名称（与 `docs/API.md` 需求一致）
LEVEL_NAMES: tuple[str, ...] = (
    "Python Rookie",
    "Beginner",
    "Coder",
    "Developer",
    "Python Developer",
    "Advanced Developer",
    "Python Master",
)

#: 每日任务指标 → 指标计算键 的映射
DAILY_METRIC_KEYS: dict[str, str] = {
    "login": "login",
    "lessons": "lessons_today",
    "submissions": "submissions_today",
    "accepted": "accepted_today",
    "study_minutes": "study_minutes",
    "ai_messages": "ai_messages",
    "mistake_reviews": "mistake_reviews",
    "accepted_no_hint": "accepted_today",
}


def count(db: Session, stmt: Any) -> int:
    """执行 count 语句并返回 int。"""
    return int(db.scalar(stmt) or 0)
