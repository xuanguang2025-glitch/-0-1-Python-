"""兼容层：`docs/ARCHITECTURE.md` §2.3 约定的 `services/ai_service.py` 入口。

真正的实现位于 `app.services.ai.tutor` / `app.services.ai.review`，
本模块再导出会话编排、评审与报错分析能力。
"""

from app.services.ai.repository import (  # noqa: F401  (re-export)
    append_message,
    create_conversation,
    delete_conversation,
    get_conversation,
    get_messages,
    list_conversations,
    set_archived,
)
from app.services.ai.review import CodeReviewService, analyze_error_report
from app.services.ai.tutor import TutorService, enforce_practice_constraint

__all__ = [
    "CodeReviewService",
    "TutorService",
    "analyze_error_report",
    "append_message",
    "create_conversation",
    "delete_conversation",
    "enforce_practice_constraint",
    "get_conversation",
    "get_messages",
    "list_conversations",
    "set_archived",
]
