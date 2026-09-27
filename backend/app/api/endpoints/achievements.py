"""成就 / 每日任务 / XP 端点（`docs/API.md` §2.13，6 条路由 + 徽章墙）。

- `GET  /achievements`                    成就列表（分类筛选 + 解锁状态）
- `GET  /achievements/badge-wall`         徽章墙数据（按分类聚合）
- `GET  /achievements/mine`               我的成就（分页）
- `POST /achievements/{id}/seen`          标记成就已提示
- `GET  /achievements/daily-tasks`        每日任务列表
- `POST /achievements/daily-tasks/{id}/check` 推进并结算每日任务
- `GET  /achievements/xp`                 经验流水（分页）
"""

from __future__ import annotations

from datetime import date as DateType

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession, Pagination
from app.core.pagination import build_page
from app.core.response import PageModel, ResponseModel, success_response
from app.schemas.gamification import (
    AchievementOut,
    BadgeWallOut,
    DailyTaskCheckOut,
    UserAchievementOut,
    UserDailyTaskOut,
    XPTransactionOut,
)
from app.services import gamification_service

router = APIRouter(prefix="/achievements", tags=["achievements"])


@router.get("", response_model=ResponseModel[list[AchievementOut]], summary="成就列表")
def list_achievements(
    db: DbSession,
    current_user: CurrentUser,
    category: str | None = Query(default=None, description="learning/practice/streak/project/social/special"),
) -> dict:
    """全部成就（含当前用户解锁状态），可分类筛选。"""
    return success_response(gamification_service.get_achievements(db, current_user, category=category))


@router.get("/badge-wall", response_model=ResponseModel[BadgeWallOut], summary="徽章墙")
def badge_wall(db: DbSession, current_user: CurrentUser) -> dict:
    """徽章墙数据：按分类统计解锁进度 + 全部成就。"""
    return success_response(gamification_service.get_badge_wall(db, current_user))


@router.get("/mine", response_model=ResponseModel[PageModel[UserAchievementOut]], summary="我的成就")
def list_my_achievements(db: DbSession, current_user: CurrentUser, pagination: Pagination) -> dict:
    """分页返回我已解锁的成就记录。"""
    items, total = gamification_service.list_my_achievements(db, current_user, pagination)
    page = build_page([UserAchievementOut.model_validate(item) for item in items], total, pagination)
    return success_response(page)


@router.post("/{achievement_id}/seen", response_model=ResponseModel[None], summary="标记成就已提示")
def mark_seen(achievement_id: str, db: DbSession, current_user: CurrentUser) -> dict:
    """前端弹窗后调用（幂等）。"""
    gamification_service.mark_seen(db, current_user, achievement_id)
    return success_response(None)


@router.get("/daily-tasks", response_model=ResponseModel[list[UserDailyTaskOut]], summary="每日任务")
def list_daily_tasks(
    db: DbSession,
    current_user: CurrentUser,
    date: str | None = Query(default=None, description="YYYY-MM-DD，缺省为今天"),
) -> dict:
    """当天每日任务列表（自动补齐进度行）。"""
    target: DateType | None = None
    if date:
        try:
            target = DateType.fromisoformat(date)
        except ValueError:
            target = None
    return success_response(gamification_service.get_daily_tasks(db, current_user, target))


@router.post(
    "/daily-tasks/{task_id}/check",
    response_model=ResponseModel[DailyTaskCheckOut],
    summary="推进每日任务",
)
def check_daily_task(task_id: str, db: DbSession, current_user: CurrentUser) -> dict:
    """按实时指标推进任务进度，达标即发放 XP（幂等，不重复发放）。"""
    return success_response(gamification_service.check_daily_task(db, current_user, task_id))


@router.get("/xp", response_model=ResponseModel[PageModel[XPTransactionOut]], summary="经验流水")
def list_xp(db: DbSession, current_user: CurrentUser, pagination: Pagination) -> dict:
    """分页返回经验获取明细。"""
    items, total = gamification_service.list_xp_transactions(db, current_user, pagination)
    page = build_page([XPTransactionOut.model_validate(item) for item in items], total, pagination)
    return success_response(page)
