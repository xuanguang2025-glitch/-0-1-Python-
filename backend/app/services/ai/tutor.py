"""AI 导师业务编排（五级递进提示 + 三模式 + 练习模式强制约束）。

职责：
- 组装消息（导师总则 + 模式 + 提示层级 + 题目/代码/报错上下文 + 历史）；
- 调用 Provider（远程或离线规则）并做**输出后置检查**：练习模式下禁止完整答案
  （约束逻辑见 `guardrails.enforce_practice_constraint`）；
- 会话持久化（`repository`）与用量日志；
- 按用户小时配额限流，超限抛 `AI_RATE_LIMITED`；
- 提供能力入口：解释/优化/重构代码、生成测试/练习/学习计划、答疑。

设计取舍：Provider 为异步，端点亦为异步；DB 为同步 Session，短事务就地执行。
所有持久化失败均被兜住（记录告警但不影响返回），保证接口不因副作用 5xx。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError, ErrorCode
from app.models.ai import AIConversation
from app.models.enums import AIMessageRole, AIScene
from app.services.ai import repository
from app.services.ai.base import AIProvider, AIResponse, ChatMessage
from app.services.ai.guardrails import FULL_ANSWER_LEVELS, context_to_dict, enforce_practice_constraint
from app.services.ai.prompts import LEVELS, MODES, SCENES, build_chat_messages
from app.services.ai.registry import get_provider, provider_status

logger = logging.getLogger("pythonlab.ai.tutor")


def normalize_mode(mode: str | None) -> str:
    """规范化讲解模式（非法值回退配置默认）。"""
    if mode in MODES:
        return mode
    default_mode = get_settings().ai_default_mode
    return default_mode if default_mode in MODES else "standard"


def normalize_level(level: str | None) -> str:
    """规范化提示层级（非法值回退 hint）。"""
    return level if level in LEVELS else "hint"


def _level_hint(level: str) -> str:
    """能力入口使用的层级提示前缀。"""
    from app.services.ai.prompts import build_level_instruction

    return build_level_instruction(normalize_level(level))


class TutorService:
    """AI 导师编排服务。"""

    def __init__(self, provider: AIProvider | None = None) -> None:
        """初始化。

        Args:
            provider: 可选注入的 Provider（测试用）；为空时取全局单例。
        """
        self._provider = provider

    # ------------------------------------------------------------------
    # Provider / 配额
    # ------------------------------------------------------------------
    @property
    def provider(self) -> AIProvider:
        """当前 Provider（延迟解析全局单例）。"""
        return self._provider or get_provider()

    def status(self) -> dict[str, Any]:
        """返回 `/ai/status` 所需信息（不含密钥）。"""
        info = provider_status(self.provider)
        info["modes"] = list(MODES)
        info["scenes"] = list(SCENES)
        info["levels"] = list(LEVELS)
        return info

    def quota_key(self, user_id: str) -> str:
        """当前小时的配额缓存键。"""
        bucket = datetime.now(timezone.utc).strftime("%Y%m%d%H")
        return f"ai:quota:{user_id}:{bucket}"

    def consume_quota(self, cache: Any, user_id: str, limit: int) -> int:
        """消耗一次配额并返回剩余额度；超限抛 `AI_RATE_LIMITED`。"""
        if limit <= 0:
            return 0
        used = int(cache.incr(self.quota_key(user_id), 1, ttl=3600))
        if used > limit:
            raise AppError(code=ErrorCode.AI_RATE_LIMITED, message="AI 配额已用尽，请稍后再试。", status_code=429)
        return max(0, limit - used)

    def peek_quota(self, cache: Any, user_id: str, limit: int) -> int:
        """查看剩余配额（不自增）。"""
        if limit <= 0:
            return 0
        used = cache.get(self.quota_key(user_id))
        return max(0, limit - int(used or 0))

    # ------------------------------------------------------------------
    # 核心：聊天
    # ------------------------------------------------------------------
    async def chat(self, db: Session, user: Any, request: Any, *, cache: Any = None) -> dict[str, Any]:
        """处理 `POST /ai/chat`。

        Args:
            db: 数据库会话。
            user: 当前用户（含 id）。
            request: `schemas.ai.ChatRequest`。
            cache: 可选缓存实例（限流用）。

        Returns:
            与 `schemas.ai.ChatOut` 对齐的字典。

        Raises:
            AppError: 配额超限（429）或练习模式请求完整答案（403）。
        """
        settings = get_settings()
        mode = normalize_mode(getattr(request, "mode", None))
        level = normalize_level(getattr(request, "level", None))
        scene = getattr(request, "scene", None) or AIScene.TUTOR.value
        practice_mode = bool(getattr(request, "practice_mode", False))
        allow_full = bool(settings.ai_allow_full_answer_in_drill)
        context = context_to_dict(getattr(request, "context", None))

        if cache is not None:
            self.consume_quota(cache, str(user.id), int(settings.ai_rate_limit_per_hour))

        conversation = self._resolve_conversation(db, user, request, mode=mode, scene=scene)
        self._persist_user_message(db, conversation, request.message, level=level)

        messages = [
            ChatMessage(role=item["role"], content=item["content"])
            for item in build_chat_messages(
                request.message,
                mode=mode,
                level=level,
                practice_mode=practice_mode,
                allow_full_answer=allow_full,
                context=context,
                history=self._safe_history(db, conversation.id),
            )
        ]

        response = await self.provider.chat(messages, task="tutor", level=level, mode=mode)
        content = enforce_practice_constraint(
            response.content, practice_mode=practice_mode, level=level, allow_full_answer=allow_full
        )
        message = self._persist_assistant_message(db, conversation, content, kind=level, response=response)
        self._log_usage(db, user, conversation, response, scene=scene)

        return {
            "conversation_id": conversation.id,
            "message_id": message.id if message else f"{conversation.id}:offline",
            "role": AIMessageRole.ASSISTANT.value,
            "kind": level,
            "content_md": content,
            "degraded": bool(response.degraded),
            "tokens_in": int(response.usage.prompt_tokens),
            "tokens_out": int(response.usage.completion_tokens),
            "latency_ms": int(response.latency_ms),
            "suggestions": self._suggestions(level),
        }

    async def chat_stream(self, db: Session, user: Any, request: Any, *, cache: Any = None):
        """处理 `POST /ai/chat/stream`（异步生成器，产出文本块）。

        非流式/离线场景下 Provider 会自动分块，保证接口始终有输出。
        """
        settings = get_settings()
        mode = normalize_mode(getattr(request, "mode", None))
        level = normalize_level(getattr(request, "level", None))
        practice_mode = bool(getattr(request, "practice_mode", False))
        allow_full = bool(settings.ai_allow_full_answer_in_drill)
        context = context_to_dict(getattr(request, "context", None))

        if cache is not None:
            self.consume_quota(cache, str(user.id), int(settings.ai_rate_limit_per_hour))
        if practice_mode and not allow_full and level in FULL_ANSWER_LEVELS:
            raise AppError(
                code=ErrorCode.AI_FULL_ANSWER_DISABLED, message="练习模式下已禁用完整答案。", status_code=403
            )

        scene = getattr(request, "scene", None) or AIScene.TUTOR.value
        conversation = self._resolve_conversation(db, user, request, mode=mode, scene=scene)
        self._persist_user_message(db, conversation, request.message, level=level)
        messages = [
            ChatMessage(role=item["role"], content=item["content"])
            for item in build_chat_messages(
                request.message, mode=mode, level=level, practice_mode=practice_mode,
                allow_full_answer=allow_full, context=context, history=self._safe_history(db, conversation.id),
            )
        ]

        buffer: list[str] = []
        async for chunk in self.provider.chat_stream(messages, task="tutor", level=level, mode=mode):
            buffer.append(chunk)
            yield chunk

        content = enforce_practice_constraint(
            "".join(buffer), practice_mode=practice_mode, level=level, allow_full_answer=allow_full
        )
        self._persist_assistant_message(db, conversation, content, kind=level, response=None)

    # ------------------------------------------------------------------
    # 能力入口（不持久化，供其他场景复用）
    # ------------------------------------------------------------------
    async def complete(
        self,
        task: str,
        *,
        message: str,
        code: str = "",
        error_message: str = "",
        traceback_text: str | None = None,
        topic: str = "",
        difficulty: str = "easy",
        count: int = 3,
        goal: str = "",
        days: int = 7,
        level: str = "hint",
        json_mode: bool = False,
    ) -> AIResponse:
        """执行一次指定任务（无副作用，供内部与其他服务复用）。"""
        opts: dict[str, Any] = {"task": task, "json_mode": json_mode}
        for key, value in (
            ("topic", topic), ("difficulty", difficulty), ("count", count),
            ("goal", goal), ("days", days), ("error_message", error_message), ("traceback", traceback_text),
        ):
            if value:
                opts[key] = value
        user_content = "\n\n".join(part for part in (_level_hint(level), code, message) if part)
        messages = [
            ChatMessage(role="system", content=f"任务类型：{task}。"),
            ChatMessage(role="user", content=user_content or message),
        ]
        return await self.provider.chat(messages, **opts)

    async def explain_code(self, code: str) -> AIResponse:
        """解释代码。"""
        return await self.complete("explain", message="请解释这段代码", code=code)

    async def optimize_code(self, code: str) -> AIResponse:
        """优化代码。"""
        return await self.complete("optimize", message="请给出优化建议", code=code)

    async def refactor_code(self, code: str) -> AIResponse:
        """重构代码。"""
        return await self.complete("refactor", message="请给出重构建议", code=code)

    async def generate_tests(self, code: str) -> AIResponse:
        """生成单元测试。"""
        return await self.complete("tests", message="请为这段代码生成单元测试", code=code)

    async def generate_practice(self, topic: str = "", difficulty: str = "easy", count: int = 3) -> AIResponse:
        """生成练习。"""
        return await self.complete("practice", message=f"生成{topic or '综合'}练习", topic=topic, difficulty=difficulty, count=count)

    async def generate_plan(self, goal: str = "", days: int = 7) -> AIResponse:
        """生成学习计划。"""
        return await self.complete("plan", message="生成学习计划", goal=goal, days=days)

    async def answer(self, question: str) -> AIResponse:
        """回答 Python 问题。"""
        return await self.complete("qa", message=question)

    # ------------------------------------------------------------------
    # 持久化辅助（失败不影响主流程）
    # ------------------------------------------------------------------
    def _resolve_conversation(self, db: Session, user: Any, request: Any, *, mode: str, scene: str) -> AIConversation:
        """取或建会话；首次提问自动生成标题。"""
        conversation_id = getattr(request, "conversation_id", None)
        if conversation_id:
            conversation = repository.get_conversation(db, str(conversation_id), str(user.id))
            conversation.rename_from_first_message(getattr(request, "message", ""))
            db.commit()
            return conversation
        return repository.create_conversation(
            db,
            str(user.id),
            mode=mode,
            scene=scene,
            context_type=getattr(getattr(request, "context", None), "type", None),
            context_id=getattr(getattr(request, "context", None), "id", None),
        )

    def _persist_user_message(self, db: Session, conversation: AIConversation, message: str, *, level: str) -> None:
        """保存用户消息（失败仅告警）。"""
        try:
            repository.append_message(db, conversation, role=AIMessageRole.USER.value, content_md=message, kind=level)
        except Exception as exc:  # noqa: BLE001 - 持久化失败不阻断回答
            logger.warning("保存用户 AI 消息失败: %s", exc)

    def _persist_assistant_message(
        self, db: Session, conversation: AIConversation, content: str, *, kind: str, response: AIResponse | None
    ) -> Any:
        """保存助手消息（失败仅告警，返回 None）。"""
        try:
            return repository.append_message(
                db, conversation, role=AIMessageRole.ASSISTANT.value, content_md=content, kind=kind, response=response
            )
        except Exception as exc:  # noqa: BLE001 - 持久化失败不阻断回答
            logger.warning("保存助手 AI 消息失败: %s", exc)
            return None

    def _safe_history(self, db: Session, conversation_id: str) -> list[tuple[str, str]]:
        """读取历史（失败返回空列表）。"""
        try:
            return [(item.role, item.content) for item in repository.recent_history(db, conversation_id, limit=10)]
        except Exception as exc:  # noqa: BLE001
            logger.warning("读取 AI 历史失败: %s", exc)
            return []

    def _log_usage(self, db: Session, user: Any, conversation: AIConversation, response: AIResponse, *, scene: str) -> None:
        """写用量日志（失败仅告警）。"""
        try:
            repository.write_usage_log(
                db,
                user_id=str(user.id),
                conversation_id=conversation.id,
                provider=response.provider,
                model=response.model,
                scene=scene,
                usage=response.usage,
                latency_ms=response.latency_ms,
                success=True,
                degraded=response.degraded,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("写 AI 用量日志失败: %s", exc)

    @staticmethod
    def _suggestions(level: str) -> list[str]:
        """按当前层级给出下一步可点选项（五级递进）。"""
        if level in LEVELS:
            index = LEVELS.index(level)
            return [f"进入「{LEVELS[min(index + 1, len(LEVELS) - 1)]}」"] if index < len(LEVELS) - 1 else ["换个问题"]
        return ["给我一个提示", "帮我看看哪里错了", "直接讲解答案"]


__all__ = [
    "TutorService",
    "enforce_practice_constraint",
    "normalize_level",
    "normalize_mode",
]
