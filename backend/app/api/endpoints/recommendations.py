"""推荐端点（`docs/API.md` 学习推荐能力，4 条路由）。

- 下一节课程推荐、适合题目推荐、复习内容推荐、学习建议。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession
from app.core.response import ResponseModel, success_response
from app.schemas.course import LessonBrief
from app.schemas.problem import ProblemBrief
from app.schemas.statistics import RecommendationItem
from app.services import recommend_service

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("/next-lesson", response_model=ResponseModel[LessonBrief | None], summary="下一节课程推荐")
def next_lesson(db: DbSession, current_user: CurrentUser) -> dict:
    """推荐下一节课时（最近报名课程的第一个未完成课时）。"""
    return success_response(recommend_service.recommend_next_lesson(db, current_user))


@router.get("/problems", response_model=ResponseModel[list[ProblemBrief]], summary="适合题目推荐")
def recommend_problems(
    db: DbSession,
    current_user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> dict:
    """推荐适合题目（排除已通过，按通过率与难度排序）。"""
    return success_response(recommend_service.recommend_problems(db, current_user, limit))


@router.get("/review", response_model=ResponseModel[list[RecommendationItem]], summary="复习内容推荐")
def recommend_review(
    db: DbSession,
    current_user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> dict:
    """复习内容推荐（到期复习 / 薄弱知识点 / 未解决错题）。"""
    return success_response(recommend_service.recommend_review(db, current_user, limit))


@router.get("/advice", response_model=ResponseModel[list[RecommendationItem]], summary="学习建议")
def recommend_advice(db: DbSession, current_user: CurrentUser) -> dict:
    """学习建议（基于学习记录 / 错题 / 课程完成度）。"""
    return success_response(recommend_service.recommend_advice(db, current_user))
