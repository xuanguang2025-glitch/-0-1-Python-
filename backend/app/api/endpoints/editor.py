"""编辑器与代码运行端点（`docs/API.md` §2.7 `/python/run`、§2.9 `/editor`）。

- `POST /api/python/run`：单段 / 多文件代码运行（Playground、课时代码块）；
- `/api/editor/*`：代码历史快照 / 列表 / 查看 / 恢复 / 对比 / 删除。
"""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.api.deps import client_ip, enforce_rate_limit
from app.core.config import get_settings
from app.core.constants import RATE_LIMITS
from app.core.deps import CurrentUser, DbSession, OptionalUser, Pagination
from app.core.errors import AppError, ErrorCode
from app.core.pagination import build_page
from app.core.response import PageModel, ResponseModel, success_response
from app.schemas.editor import (
    CodeHistoryBrief,
    CodeHistoryOut,
    CompareOut,
    CompareRequest,
    SnapshotCreateRequest,
)
from app.schemas.sandbox import RunRequest, RunResponse
from app.services import code_history_service, editor_service

router = APIRouter(prefix="/editor", tags=["editor"])
python_router = APIRouter(prefix="/python", tags=["python"])


# ------------------------------------------------------------- /python/run
@python_router.post("/run", response_model=ResponseModel[RunResponse], summary="运行代码")
def run_code(payload: RunRequest, request: Request, user: OptionalUser) -> dict:
    """运行单段 / 多文件代码，返回 stdout / stderr / 耗时 / 内存。"""
    settings = get_settings()
    if user is None and not settings.allow_anon_run:
        raise AppError(code=ErrorCode.UNAUTHORIZED, message="请登录后再运行代码", status_code=401)
    limit, window = RATE_LIMITS.get("run", (30, 60))
    identity = str(user.id) if user is not None else (client_ip(request) or "unknown")
    enforce_rate_limit(f"run:{identity}", limit, window)

    result = editor_service.run_code(
        None,
        user,
        files=payload.files,
        entry=payload.entry,
        stdin=payload.stdin,
        timeout_ms=payload.timeout_ms,
        memory_mb=payload.memory_limit_mb,
    )
    return success_response(editor_service.run_result_to_response(result))


# -------------------------------------------------------------- /editor/*
@router.post("/save-snapshot", response_model=ResponseModel[CodeHistoryOut], summary="保存代码快照")
def save_snapshot(payload: SnapshotCreateRequest, current_user: CurrentUser, db: DbSession) -> dict:
    """保存一条代码历史快照，返回新版本。"""
    record = code_history_service.save_snapshot(
        db,
        current_user,
        context_type=payload.context_type,
        context_id=payload.context_id,
        file_path=payload.file_path,
        code=payload.code,
        label=payload.label,
        source=payload.source,
    )
    return success_response(code_history_service.to_out(record), message="已保存快照")


@router.get("/history", response_model=ResponseModel[PageModel[CodeHistoryBrief]], summary="代码历史列表")
def list_history(
    current_user: CurrentUser,
    db: DbSession,
    pagination: Pagination,
    context_type: str | None = Query(default=None),
    context_id: str | None = Query(default=None),
) -> dict:
    """分页返回代码历史（不含完整代码）。"""
    items, total = code_history_service.list_history(
        db, current_user, context_type=context_type, context_id=context_id, params=pagination
    )
    briefs = [code_history_service.to_brief(item) for item in items]
    return success_response(build_page(briefs, total, pagination))


@router.get("/history/{history_id}", response_model=ResponseModel[CodeHistoryOut], summary="历史版本详情")
def get_history(history_id: str, current_user: CurrentUser, db: DbSession) -> dict:
    """返回某个历史版本的完整代码。"""
    record = code_history_service.get_history(db, current_user, history_id)
    return success_response(code_history_service.to_out(record))


@router.post("/history/{history_id}/restore", response_model=ResponseModel[CodeHistoryOut], summary="恢复版本")
def restore_history(history_id: str, current_user: CurrentUser, db: DbSession) -> dict:
    """把历史版本复制为最新版本并返回。"""
    record = code_history_service.restore_snapshot(db, current_user, history_id)
    return success_response(code_history_service.to_out(record), message="已恢复为新版本")


@router.post("/compare", response_model=ResponseModel[CompareOut], summary="版本对比")
def compare_versions(payload: CompareRequest, current_user: CurrentUser, db: DbSession) -> dict:
    """对比两个历史版本，返回 diff 文本与 hunks。"""
    result = code_history_service.compare_versions(db, current_user, payload.left_id, payload.right_id)
    return success_response(result)


@router.delete("/history/{history_id}", response_model=ResponseModel[None], summary="删除历史版本")
def delete_history(history_id: str, current_user: CurrentUser, db: DbSession) -> dict:
    """删除某个历史版本。"""
    code_history_service.delete_history(db, current_user, history_id)
    return success_response(None, message="已删除")


__all__ = ["python_router", "router"]
