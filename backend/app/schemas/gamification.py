"""成就 / 每日任务 / XP Schema（`docs/API.md` §2.13）。"""

from __future__ import annotations

from datetime import date as DateType
from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.common import IdStr, ORMModel


class AchievementOut(ORMModel):
    """成就定义（含我的解锁状态）。"""

    id: IdStr
    code: str
    name: str
    description: str | None = None
    icon: str | None = None
    category: str = "learning"
    condition_json: Any | None = None
    xp_reward: int = 10
    badge_color: str = "blue"
    is_secret: bool = False
    order_index: int = 0
    unlocked: bool = False
    unlocked_at: datetime | None = None


class UserAchievementOut(ORMModel):
    """我的成就记录。"""

    id: IdStr
    achievement_id: IdStr
    unlocked_at: datetime | None = None
    seen: bool = False
    achievement: AchievementOut | None = None


class DailyTaskOut(ORMModel):
    """每日任务定义。"""

    id: IdStr
    code: str
    title: str
    description: str | None = None
    metric: str = ""
    target_count: int = 1
    xp_reward: int = 10
    order_index: int = 0


class UserDailyTaskOut(ORMModel):
    """我某天的任务进度。"""

    id: IdStr
    daily_task_id: IdStr
    date: DateType | None = None
    progress: int = 0
    target: int = 1
    completed: bool = False
    completed_at: datetime | None = None
    xp_reward: int = 0
    title: str = ""
    code: str = ""


class DailyTaskCheckOut(ORMModel):
    """`POST /achievements/daily-tasks/{id}/check` 响应体。"""

    progress: int = 0
    target: int = 1
    completed: bool = False
    xp_earned: int = 0


class XPTransactionOut(ORMModel):
    """经验流水项。"""

    id: IdStr
    amount: int = 0
    reason: str = ""
    ref_type: str | None = None
    ref_id: str | None = None
    balance_after: int = 0
    created_at: datetime | None = None


class BadgeWallCategory(ORMModel):
    """徽章墙按分类的解锁进度。"""

    category: str = "learning"
    total: int = 0
    unlocked: int = 0


class BadgeWallOut(ORMModel):
    """徽章墙数据（`GET /achievements` 的汇总视图）。"""

    total: int = 0
    unlocked: int = 0
    categories: list[BadgeWallCategory] = Field(default_factory=list)
    achievements: list[AchievementOut] = Field(default_factory=list)
