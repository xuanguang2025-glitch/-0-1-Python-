"""AI 会话持久化仓储层（隔离 ORM 依赖，保证 Provider 层可独立测试）。

集中封装对 `ai_conversations` / `ai_messages` / `ai_usage_logs` 的访问，
业务编排层（tutor / review）只调用本模块，不直接拼 SQL。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError, ErrorCode
from app.models.ai import AIConversation, AIMessage, AIUsageLog
from app.models.enums import AIMessageRole
from app.services.ai.base import AIResponse, ChatMessage, TokenUsage
from app.utils.ids import new_uuid


def create_conversation(
    db: Session,
    user_id: str,
    *,
    title: str = "新对话",
    mode: str = "standard",
    scene: str = "free",
    context_type: str | None = None,
    context_id: str | None = None,
) -> AIConversation:
    """新建会话并提交。"""
    conversation = AIConversation(
        user_id=user_id,
        title=title or "新对话",
        mode=mode,
        scene=scene,
        context_type=context_type,
        context_id=context_id,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def get_conversation(db: Session, conversation_id: str, user_id: str) -> AIConversation:
    """按 id 取会话并校验归属（不存在或非本人 → CONVERSATION_NOT_FOUND）。"""
    conversation = db.get(AIConversation, conversation_id)
    if conversation is None or conversation.user_id != user_id:
        raise AppError(code=ErrorCode.CONVERSATION_NOT_FOUND, message="会话不存在", status_code=404)
    return conversation


def list_conversations(
    db: Session,
    user_id: str,
    *,
    scene: str | None = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[AIConversation], int]:
    """分页列出用户的会话（按更新时间倒序）。返回 `(items, total)`。"""
    conditions = [AIConversation.user_id == user_id]
    if scene:
        conditions.append(AIConversation.scene == scene)
    total = int(db.scalar(select(func.count()).select_from(AIConversation).where(*conditions)) or 0)
    stmt = (
        select(AIConversation)
        .where(*conditions)
        .order_by(AIConversation.updated_at.desc())
        .offset(max(0, offset))
        .limit(max(1, limit))
    )
    return list(db.scalars(stmt).all()), total


def get_messages(db: Session, conversation_id: str) -> list[AIMessage]:
    """取会话内全部消息（按创建时间升序）。"""
    stmt = (
        select(AIMessage)
        .where(AIMessage.conversation_id == conversation_id)
        .order_by(AIMessage.created_at.asc())
    )
    return list(db.scalars(stmt).all())


def recent_history(db: Session, conversation_id: str, limit: int = 10) -> list[ChatMessage]:
    """取最近 `limit` 轮消息（user/assistant），返回时间升序的 `ChatMessage` 列表。"""
    stmt = (
        select(AIMessage)
        .where(
            AIMessage.conversation_id == conversation_id,
            AIMessage.role.in_([AIMessageRole.USER.value, AIMessageRole.ASSISTANT.value]),
        )
        .order_by(AIMessage.created_at.desc())
        .limit(max(1, limit))
    )
    rows = list(db.scalars(stmt).all())
    rows.reverse()
    return [ChatMessage(role=row.role, content=row.content_md) for row in rows]


def append_message(
    db: Session,
    conversation: AIConversation,
    *,
    role: str,
    content_md: str,
    kind: str | None = None,
    response: AIResponse | None = None,
    meta_json: dict[str, Any] | None = None,
) -> AIMessage:
    """追加一条消息并更新会话计数。

    Args:
        db: 会话。
        conversation: 所属会话。
        role: system/user/assistant。
        content_md: 消息内容（Markdown）。
        kind: 消息类型（hint/... /review/...）。
        response: 若为 assistant，携带用量 / 降级标记。
        meta_json: 附加元数据。

    Returns:
        新建的 `AIMessage`。
    """
    usage = response.usage if response else TokenUsage()
    message = AIMessage(
        conversation_id=conversation.id,
        role=role,
        content_md=content_md or "",
        kind=kind,
        tokens_in=int(usage.prompt_tokens),
        tokens_out=int(usage.completion_tokens),
        latency_ms=int(response.latency_ms) if response else 0,
        degraded=bool(response.degraded) if response else False,
        meta_json=meta_json,
    )
    message.id = message.id or new_uuid()
    db.add(message)
    conversation.count_message(tokens=usage.total_tokens)
    db.commit()
    db.refresh(message)
    db.refresh(conversation)
    return message


def set_archived(db: Session, conversation: AIConversation, is_archived: bool) -> AIConversation:
    """切换会话归档状态。"""
    conversation.is_archived = bool(is_archived)
    db.commit()
    db.refresh(conversation)
    return conversation


def delete_conversation(db: Session, conversation: AIConversation) -> None:
    """删除会话（级联删除消息）。"""
    db.delete(conversation)
    db.commit()


def write_usage_log(
    db: Session,
    *,
    user_id: str | None,
    conversation_id: str | None,
    provider: str,
    model: str,
    scene: str | None,
    usage: TokenUsage | None = None,
    latency_ms: int = 0,
    success: bool = True,
    degraded: bool = False,
    error_code: str | None = None,
) -> AIUsageLog:
    """写入一条 AI 用量日志。"""
    log = AIUsageLog(
        user_id=user_id,
        conversation_id=conversation_id,
        provider=provider or "",
        model=model or "",
        scene=scene,
        tokens_in=int((usage or TokenUsage()).prompt_tokens),
        tokens_out=int((usage or TokenUsage()).completion_tokens),
        latency_ms=int(latency_ms),
        success=bool(success),
        degraded=bool(degraded),
        error_code=error_code,
    )
    log.id = log.id or new_uuid()
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


__all__ = [
    "append_message",
    "create_conversation",
    "delete_conversation",
    "get_conversation",
    "get_messages",
    "list_conversations",
    "recent_history",
    "set_archived",
    "write_usage_log",
]
