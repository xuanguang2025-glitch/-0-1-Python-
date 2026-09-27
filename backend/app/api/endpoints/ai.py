"""AI 端点（`docs/API.md` §2.10，9 条路由）。

- `POST   /ai/chat`                      AI 导师对话（五级递进 + 三模式 + 练习约束）
- `POST   /ai/chat/stream`               SSE 流式对话
- `POST   /ai/review`                    九维度代码评审
- `POST   /ai/analyze-error`             报错分析
- `GET    /ai/conversations`             会话列表（分页）
- `POST   /ai/conversations`             新建会话
- `GET    /ai/conversations/{id}`        会话详情
- `DELETE /ai/conversations/{id}`        删除会话
- `POST   /ai/conversations/{id}/archive` 归档切换
- `GET    /ai/status`                    Provider 状态与剩余配额

统一响应结构见 `docs/API.md` §1.1；AI 配额按 `AI_RATE_LIMIT_PER_HOUR` 计，超限 429。
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.core.cache import get_cache_instance
from app.core.config import get_settings
from app.core.deps import CurrentUser, DbSession, Pagination
from app.core.errors import AppError
from app.core.pagination import build_page
from app.core.response import PageModel, ResponseModel, success_response
from app.schemas.ai import (
    AIConversationBrief,
    AIConversationCreateRequest,
    AIConversationDetail,
    AIConversationOut,
    AIMessageOut,
    AIStatusOut,
    AnalyzeErrorRequest,
    ArchiveRequest,
    ChatOut,
    ChatRequest,
    ErrorAnalysisOut,
    ReviewOut,
    ReviewRequest,
)
from app.services.ai import CodeReviewService, TutorService, analyze_error_report
from app.services.ai import repository

router = APIRouter(prefix="/ai", tags=["ai"])


# ---------------------------------------------------------------------------
# 对话与评审
# ---------------------------------------------------------------------------


@router.post("/chat", response_model=ResponseModel[ChatOut], summary="AI 导师对话")
async def chat(payload: ChatRequest, current_user: CurrentUser, db: DbSession) -> dict:
    """AI 导师对话（`level` 控制提示层级，`practice_mode` 强制不给完整答案）。"""
    service = TutorService()
    data = await service.chat(db, current_user, payload, cache=get_cache_instance())
    return success_response(ChatOut(**data))


@router.post("/chat/stream", summary="AI 导师对话（SSE 流式）")
async def chat_stream(payload: ChatRequest, current_user: CurrentUser, db: DbSession) -> StreamingResponse:
    """SSE 流式对话；每块形如 `data: {"type":"delta","content":"..."}`，结束发 `[DONE]`。"""
    service = TutorService()

    async def event_source() -> AsyncIterator[str]:
        try:
            async for chunk in service.chat_stream(db, current_user, payload, cache=get_cache_instance()):
                yield f"data: {json.dumps({'type': 'delta', 'content': chunk}, ensure_ascii=False)}\n\n"
        except AppError as exc:
            payload_err = {"type": "error", "error": {"code": exc.code, "message": exc.message}}
            yield f"data: {json.dumps(payload_err, ensure_ascii=False)}\n\n"
        except Exception:  # noqa: BLE001 - 流式过程中不得抛出未处理异常
            payload_err = {"type": "error", "error": {"code": "INTERNAL_ERROR", "message": "服务异常"}}
            yield f"data: {json.dumps(payload_err, ensure_ascii=False)}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/review", response_model=ResponseModel[ReviewOut], summary="代码评审（九维度）")
async def review(payload: ReviewRequest, current_user: CurrentUser, db: DbSession) -> dict:
    """对代码做九维度评审，返回结构化问题列表、评分与改进代码。"""
    service = CodeReviewService()
    data = await service.review(payload, db=db, user=current_user)
    return success_response(ReviewOut(**data))


@router.post("/analyze-error", response_model=ResponseModel[ErrorAnalysisOut], summary="报错分析")
async def analyze_error(payload: AnalyzeErrorRequest, current_user: CurrentUser, db: DbSession) -> dict:
    """分析 Python 报错：错误位置 / 原因 / 知识点 / 修复步骤 / 最小复现。"""
    data = await analyze_error_report(
        None,
        code=payload.code,
        error_message=payload.error_message,
        traceback_text=payload.traceback,
        db=db,
        user=current_user,
    )
    return success_response(ErrorAnalysisOut(**data))


# ---------------------------------------------------------------------------
# 会话管理
# ---------------------------------------------------------------------------


@router.get("/conversations", response_model=ResponseModel[PageModel[AIConversationBrief]], summary="会话列表")
def list_conversations(
    current_user: CurrentUser,
    db: DbSession,
    pagination: Pagination,
    scene: str | None = Query(default=None, description="按场景筛选 tutor/review/error/exam/free"),
) -> dict:
    """分页返回当前用户的会话（按更新时间倒序）。"""
    items, total = repository.list_conversations(
        db, str(current_user.id), scene=scene, offset=pagination.offset, limit=pagination.limit
    )
    page = build_page([AIConversationBrief.model_validate(item) for item in items], total, pagination)
    return success_response(page)


@router.post("/conversations", response_model=ResponseModel[AIConversationOut], summary="新建会话")
def create_conversation(payload: AIConversationCreateRequest, current_user: CurrentUser, db: DbSession) -> dict:
    """新建一个 AI 会话。"""
    settings = get_settings()
    conversation = repository.create_conversation(
        db,
        str(current_user.id),
        title=payload.title or "新对话",
        mode=payload.mode or settings.ai_default_mode,
        scene=payload.scene or "free",
        context_type=payload.context_type,
        context_id=payload.context_id,
    )
    return success_response(AIConversationOut.model_validate(conversation), message="会话已创建")


@router.get("/conversations/{conversation_id}", response_model=ResponseModel[AIConversationDetail], summary="会话详情")
def get_conversation(conversation_id: str, current_user: CurrentUser, db: DbSession) -> dict:
    """返回会话信息与全部消息。"""
    conversation = repository.get_conversation(db, conversation_id, str(current_user.id))
    messages = repository.get_messages(db, conversation.id)
    detail = AIConversationDetail(
        conversation=AIConversationOut.model_validate(conversation),
        messages=[AIMessageOut.model_validate(message) for message in messages],
    )
    return success_response(detail)


@router.delete("/conversations/{conversation_id}", response_model=ResponseModel[None], summary="删除会话")
def delete_conversation(conversation_id: str, current_user: CurrentUser, db: DbSession) -> dict:
    """删除会话（级联删除消息）。"""
    conversation = repository.get_conversation(db, conversation_id, str(current_user.id))
    repository.delete_conversation(db, conversation)
    return success_response(None, message="会话已删除")


@router.post(
    "/conversations/{conversation_id}/archive",
    response_model=ResponseModel[AIConversationOut],
    summary="归档 / 取消归档",
)
def archive_conversation(
    conversation_id: str, payload: ArchiveRequest, current_user: CurrentUser, db: DbSession
) -> dict:
    """切换会话归档状态。"""
    conversation = repository.get_conversation(db, conversation_id, str(current_user.id))
    conversation = repository.set_archived(db, conversation, payload.is_archived)
    return success_response(AIConversationOut.model_validate(conversation))


# ---------------------------------------------------------------------------
# 状态
# ---------------------------------------------------------------------------


@router.get("/status", response_model=ResponseModel[AIStatusOut], summary="AI 状态")
def status(current_user: CurrentUser) -> dict:
    """返回当前 Provider 名、模型、是否降级与剩余配额（**不含密钥**）。"""
    settings = get_settings()
    service = TutorService()
    info = service.status()
    remaining = service.peek_quota(get_cache_instance(), str(current_user.id), int(settings.ai_rate_limit_per_hour))
    return success_response(
        AIStatusOut(
            provider=info["provider"],
            model=info["model"],
            degraded=bool(info["degraded"]),
            remaining_quota=int(remaining),
            modes=list(info["modes"]),
            scenes=list(info["scenes"]),
            configured_provider=info.get("configured_provider"),
            configured_model=info.get("configured_model"),
        )
    )


__all__ = ["router"]
