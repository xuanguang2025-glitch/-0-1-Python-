"""题库端点（`docs/API.md` §2.5，7 条路由）。

安全红线：返回前端的任何数据都不得包含非样例测试点的 `expected_output`。
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession, OptionalUser, Pagination
from app.core.pagination import build_page
from app.core.response import PageModel, ResponseModel, success_response
from app.schemas.problem import (
    DiscussionAIOut,
    ProblemBrief,
    ProblemDetail,
    ProblemTagOut,
)
from app.services import problem_service

router = APIRouter(prefix="/problems", tags=["problems"])


@router.get("", response_model=ResponseModel[PageModel[ProblemBrief]], summary="题目列表")
def list_problems(
    user: OptionalUser,
    db: DbSession,
    pagination: Pagination,
    type: str | None = Query(default=None, description="题型 choice/judge/blank/completion/coding/debug/algorithm"),
    difficulty: str | None = Query(default=None, description="easy/medium/hard/expert"),
    category: str | None = Query(default=None, description="分类"),
    tag: str | None = Query(default=None, description="标签 slug"),
    status: str | None = Query(default=None, description="all/solved/unsolved"),
    keyword: str | None = Query(default=None, description="标题 / 题干关键词"),
) -> dict:
    """按题型 / 难度 / 分类 / 标签 / 关键词筛选题目并分页。"""
    problems, total = problem_service.list_problems(
        db,
        user,
        problem_type=type,
        difficulty=difficulty,
        category=category,
        tag=tag,
        status=status,
        keyword=keyword,
        params=pagination,
    )
    briefs = problem_service.build_briefs(db, problems, user)
    return success_response(build_page(briefs, total, pagination))


@router.get("/filters", response_model=ResponseModel[ProblemTagOut], summary="筛选字典")
def problem_filters(db: DbSession) -> dict:
    """返回题型 / 难度 / 分类（含计数）与标签列表。"""
    return success_response(problem_service.get_filters(db))


@router.get("/random", response_model=ResponseModel[ProblemBrief], summary="随机一题")
def random_problem(
    user: OptionalUser,
    db: DbSession,
    difficulty: str | None = Query(default=None),
    category: str | None = Query(default=None),
    exclude_solved: bool = Query(default=True, description="是否排除已解决题目"),
) -> dict:
    """随机返回一道题（登录用户可排除已解决题目）。"""
    problem = problem_service.get_random_problem(
        db, user, difficulty=difficulty, category=category, exclude_solved=exclude_solved
    )
    brief = problem_service.build_briefs(db, [problem], user)[0]
    return success_response(brief)


@router.get("/recommend", response_model=ResponseModel[list[ProblemBrief]], summary="智能推荐")
def recommend_problems(
    current_user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=10, ge=1, le=50),
) -> dict:
    """基于薄弱知识点与未解决题目推荐题目。"""
    problems = problem_service.recommend_problems(db, current_user, limit=limit)
    return success_response(problem_service.build_briefs(db, problems, current_user))


@router.get("/{problem_id}", response_model=ResponseModel[ProblemDetail], summary="题目详情")
def get_problem(problem_id: str, user: OptionalUser, db: DbSession) -> dict:
    """返回题目详情（仅含样例用例；隐藏用例绝不外泄）。"""
    problem = problem_service.get_problem_or_404(db, problem_id)
    return success_response(problem_service.build_detail(db, problem, user))


@router.get("/{problem_id}/similar", response_model=ResponseModel[list[ProblemBrief]], summary="相似题")
def similar_problems(
    problem_id: str,
    user: OptionalUser,
    db: DbSession,
    limit: int = Query(default=5, ge=1, le=20),
) -> dict:
    """推荐与当前题目分类 / 题型相同的相似题。"""
    problem = problem_service.get_problem_or_404(db, problem_id)
    items = problem_service.similar_problems(db, problem, limit=limit)
    return success_response(problem_service.build_briefs(db, items, user))


@router.get("/{problem_id}/discussion-ai", response_model=ResponseModel[DiscussionAIOut], summary="题解要点")
def discussion_ai(problem_id: str, current_user: CurrentUser, db: DbSession) -> dict:
    """生成题解要点（本地模板，无外部 Key 时亦可用）。"""
    problem = problem_service.get_problem_or_404(db, problem_id)
    return success_response(problem_service.discussion_ai(problem))


__all__ = ["router"]
