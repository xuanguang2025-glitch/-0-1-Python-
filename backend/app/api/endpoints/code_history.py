"""代码历史端点（`docs/API.md` §2.19，3 条路由）。

保存 / 恢复 / 比较走 `/api/editor/*`（同一服务 `code_history_service`，避免重复实现）。
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession, Pagination
from app.core.pagination import build_page
from app.core.response import PageModel, ResponseModel, success_response
from app.schemas.editor import CodeHistoryBrief, CodeHistoryOut
from app.services import code_history_service

router = APIRouter(prefix="/code-history", tags=["code-history"])


@router.get("", response_model=ResponseModel[PageModel[CodeHistoryBrief]], summary="代码历史列表")
def list_code_history(
    current_user: CurrentUser,
    db: DbSession,
    pagination: Pagination,
    context_type: str | None = Query(default=None, description="lesson/problem/project/playground"),
    context_id: str | None = Query(default=None),
) -> dict:
    """分页返回代码历史（不含完整代码）。"""
    items, total = code_history_service.list_history(
        db, current_user, context_type=context_type, context_id=context_id, params=pagination
    )
    briefs = [code_history_service.to_brief(item) for item in items]
    return success_response(build_page(briefs, total, pagination))


@router.get("/{history_id}", response_model=ResponseModel[CodeHistoryOut], summary="历史版本详情")
def get_code_history(history_id: str, current_user: CurrentUser, db: DbSession) -> dict:
    """返回某个历史版本的完整代码。"""
    record = code_history_service.get_history(db, current_user, history_id)
    return success_response(code_history_service.to_out(record))


@router.delete("/{history_id}", response_model=ResponseModel[None], summary="删除历史版本")
def delete_code_history(history_id: str, current_user: CurrentUser, db: DbSession) -> dict:
    """删除某个历史版本。"""
    code_history_service.delete_history(db, current_user, history_id)
    return success_response(None, message="已删除")


__all__ = ["router"]
