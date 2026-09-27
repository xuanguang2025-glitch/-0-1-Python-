"""游戏化服务：XP / 等级（7 级）/ 成就 / 每日任务 / 徽章墙（`docs/API.md` §2.13）。

- 等级阈值集中由 `Settings.level_threshold_list` 管理，等级名见 `LEVEL_NAMES`；
- `check_and_unlock(db, user, event)` 是**服务端统一解锁入口**，供其他域在
  完成课时 / 通过题目 / 升级 / 完成项目等时机调用，幂等（已解锁不再重复发放）。

本包按职责拆分，`__init__` 统一重导出公共 API（`from app.services import gamification_service`）。
"""

from __future__ import annotations

from .common import ACCEPTED, DAILY_METRIC_KEYS, LEVEL_NAMES, count as _count
from .levels import award_xp, level_info, level_name
from .metrics import build_metrics, satisfied as _satisfied
from .achievements import (
    check_achievements,
    check_and_unlock,
    get_achievements,
    get_badge_wall,
    list_my_achievements,
    mark_seen,
    unlocked_ids as _unlocked_ids,
)
from .xp import list_xp_transactions
from .daily import check_daily_task, ensure_daily_tasks as _ensure_daily_tasks, get_daily_tasks

__all__ = [
    "LEVEL_NAMES",
    "DAILY_METRIC_KEYS",
    "ACCEPTED",
    "level_name",
    "level_info",
    "award_xp",
    "build_metrics",
    "get_achievements",
    "get_badge_wall",
    "list_my_achievements",
    "mark_seen",
    "check_and_unlock",
    "check_achievements",
    "list_xp_transactions",
    "get_daily_tasks",
    "check_daily_task",
]
