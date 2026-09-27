"""挑战端点（`docs/API.md` §2.14，7 条路由）。

排行榜只返回昵称与成绩，绝不包含任何隐私字段。
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession, OptionalUser, Pagination
from app.core.pagination import build_page
from app.core.response import PageModel, ResponseModel, success_response
from app.schemas.challenge import (
    ChallengeBrief,
    ChallengeDetail,
    ChallengeSubmitOut,
    ChallengeSubmitRequest,
    LeaderboardOut,
    UserChallengeOut,
)
from app.schemas.problem import ProblemBrief
from app.services import challenge_service

router = APIRouter(prefix="/challenges", tags=["challenges"])


@router.get("", response_model=ResponseModel[PageModel[ChallengeBrief]], summary="挑战列表")
def list_challenges(
    db: DbSession,
    pagination: Pagination,
    viewer: OptionalUser = None,
    type: str | None = Query(default=None, pattern="^(daily|weekly|monthly|special)$"),
    status: str | None = Query(default=None, pattern="^(active|ended)$"),
) -> dict:
    """挑战列表（按周期类型 / 进行状态筛选，分页）。"""
    items, total = challenge_service.list_challenges(db, viewer, pagination, challenge_type=type, status=status)
    return success_response(build_page(items, total, pagination))


@router.get("/my", response_model=ResponseModel[PageModel[UserChallengeOut]], summary="我的挑战记录")
def my_challenges(db: DbSession, current_user: CurrentUser, pagination: Pagination) -> dict:
    """分页返回我的挑战参与与成绩。"""
    items, total = challenge_service.my_challenges(db, current_user, pagination)
    return success_response(build_page(items, total, pagination))


@router.get("/{challenge_id}", response_model=ResponseModel[ChallengeDetail], summary="挑战详情")
def get_challenge(challenge_id: str, db: DbSession, viewer: OptionalUser = None) -> dict:
    """挑战详情（含题目列表与我的参与记录）。"""
    return success_response(challenge_service.get_challenge(db, viewer, challenge_id))


@router.post("/{challenge_id}/join", response_model=ResponseModel[UserChallengeOut], summary="报名挑战")
def join_challenge(challenge_id: str, db: DbSession, current_user: CurrentUser) -> dict:
    """报名挑战（已结束 400，重复报名 409）。"""
    return success_response(challenge_service.join_challenge(db, current_user, challenge_id), message="报名成功")


@router.get("/{challenge_id}/problems", response_model=ResponseModel[list[ProblemBrief]], summary="挑战题目")
def challenge_problems(challenge_id: str, db: DbSession, current_user: CurrentUser) -> dict:
    """挑战题目列表。"""
    return success_response(challenge_service.challenge_problems(db, current_user, challenge_id))


@router.post("/{challenge_id}/submit", response_model=ResponseModel[ChallengeSubmitOut], summary="提交挑战结果")
def submit_challenge(
    challenge_id: str,
    payload: ChallengeSubmitRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """提交解答并判题计分（结果计入排行榜）。"""
    data = challenge_service.submit_challenge(db, current_user, challenge_id, payload.solutions)
    return success_response(data, message="提交成功")


@router.get("/{challenge_id}/leaderboard", response_model=ResponseModel[LeaderboardOut], summary="排行榜")
def leaderboard(
    challenge_id: str,
    db: DbSession,
    limit: int = Query(default=100, ge=1, le=100),
) -> dict:
    """排行榜（**仅昵称与成绩**）。"""
    return success_response(challenge_service.leaderboard(db, challenge_id, limit=limit))
