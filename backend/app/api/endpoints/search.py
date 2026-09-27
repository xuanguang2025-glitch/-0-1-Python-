"""全局搜索端点（`docs/API.md` §2.16，2 条路由）。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.core.deps import DbSession
from app.core.response import ResponseModel, success_response
from app.schemas.search import SearchOut, SuggestOut
from app.services import search_service

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=ResponseModel[SearchOut], summary="全局搜索")
def global_search(
    db: DbSession,
    q: Annotated[str, Query(min_length=1, max_length=120, description="搜索关键词")],
    types: Annotated[
        str, Query(description="逗号分隔：course,lesson,problem,project,snippet")
    ] = "course,lesson,problem,project,snippet",
    limit: Annotated[int, Query(ge=1, le=20, description="每组返回条数")] = 5,
) -> dict:
    """跨类型搜索（课程 / 课时 / 题目 / 项目 / 代码示例），按类型分组返回。"""
    wanted = [item.strip() for item in types.split(",") if item.strip()]
    return success_response(search_service.global_search(db, q, wanted, limit))


@router.get("/suggest", response_model=ResponseModel[SuggestOut], summary="搜索联想")
def suggest(
    db: DbSession,
    q: Annotated[str, Query(min_length=1, max_length=120, description="联想关键词")],
) -> dict:
    """搜索联想：返回可跳转的建议项。"""
    return success_response(search_service.suggest(db, q))
