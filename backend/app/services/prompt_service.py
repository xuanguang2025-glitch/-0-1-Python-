"""兼容层：`docs/ARCHITECTURE.md` §2.3 约定的 `services/prompt_service.py` 入口。

提示词模板集中在 `app.services.ai.prompts`，本模块再导出，并提供
`render_system()` / `render_messages()` 便捷函数（等价于原来的 `prompt_service.render`）。
"""

from typing import Any, Mapping, Sequence

from app.services.ai.prompts import (  # noqa: F401  (re-export)
    ERROR_ANALYSIS_SYSTEM,
    EXAM_GENERATOR_SYSTEM,
    LEVELS,
    MODES,
    REVIEW_DIMENSIONS,
    REVIEW_SYSTEM,
    SCENES,
    TUTOR_SYSTEM,
    build_chat_messages,
    build_context_block,
    build_error_user_prompt,
    build_level_instruction,
    build_review_user_prompt,
    build_system_prompt,
)


def render_system(
    mode: str = "standard",
    *,
    practice_mode: bool = False,
    allow_full_answer: bool = False,
) -> str:
    """渲染系统提示（`render(template, ctx)` 的便捷封装）。"""
    return build_system_prompt(mode, practice_mode=practice_mode, allow_full_answer=allow_full_answer)


def render_messages(
    message: str,
    *,
    mode: str = "standard",
    level: str = "hint",
    context: Mapping[str, Any] | None = None,
    history: Sequence[tuple[str, str]] | None = None,
    practice_mode: bool = False,
    allow_full_answer: bool = False,
) -> list[dict[str, str]]:
    """渲染完整 messages 列表。"""
    return build_chat_messages(
        message,
        mode=mode,
        level=level,
        context=context,
        history=history,
        practice_mode=practice_mode,
        allow_full_answer=allow_full_answer,
    )


__all__ = [
    "ERROR_ANALYSIS_SYSTEM",
    "EXAM_GENERATOR_SYSTEM",
    "LEVELS",
    "MODES",
    "REVIEW_DIMENSIONS",
    "REVIEW_SYSTEM",
    "SCENES",
    "TUTOR_SYSTEM",
    "build_chat_messages",
    "build_context_block",
    "build_error_user_prompt",
    "build_level_instruction",
    "build_review_user_prompt",
    "build_system_prompt",
    "render_messages",
    "render_system",
]
