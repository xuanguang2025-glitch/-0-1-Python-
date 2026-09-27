"""练习模式护栏与上下文辅助（自 `tutor` 拆出，保持单文件 <400 行）。

- `enforce_practice_constraint`：练习模式输出后置约束（拦截完整答案 + 裁剪完整答案章节）；
- `context_to_dict`：把 `AIContextIn` 转为提示构造器需要的字典。
"""

from __future__ import annotations

from typing import Any

from app.core.errors import AppError, ErrorCode

#: 练习模式下禁止的提示层级（除非显式放开完整答案）
FULL_ANSWER_LEVELS: set[str] = {"full", "explain"}

#: 识别「完整答案」章节的标题关键词
_SOLUTION_HEADING_KEYWORDS = ("完整答案", "完整代码", "参考实现", "完整实现", "参考答案", "解答")


def enforce_practice_constraint(
    content: str,
    *,
    practice_mode: bool,
    level: str,
    allow_full_answer: bool = False,
) -> str:
    """练习模式输出后置约束（纯函数，便于单测）。

    Args:
        content: 模型/规则生成的回答。
        practice_mode: 是否练习模式。
        level: 提示层级。
        allow_full_answer: 是否允许完整答案（配置开关）。

    Returns:
        处理后的内容（练习模式会裁剪完整答案章节）。

    Raises:
        AppError: 练习模式下请求 full/explain 且未放开时，抛 `AI_FULL_ANSWER_DISABLED`。
    """
    if not practice_mode or allow_full_answer:
        return content
    if level in FULL_ANSWER_LEVELS:
        raise AppError(
            code=ErrorCode.AI_FULL_ANSWER_DISABLED,
            message="练习模式下已禁用完整答案，请先自行尝试或切换到非练习模式。",
            status_code=403,
        )
    return _strip_solution_sections(content)


def _strip_solution_sections(content: str) -> str:
    """删除被「完整答案」类标题引导的代码块，避免变相给出完整答案。

    状态机：0 正常 → 1 命中标题（等待其后代码块）→ 2 代码块内。
    若标题后紧接的是普通文本（而非代码块），则保留该文本并回到正常状态。
    """
    lines = (content or "").splitlines()
    output: list[str] = []
    state = 0
    for line in lines:
        stripped = line.strip()
        if state == 0:
            if any(keyword in stripped for keyword in _SOLUTION_HEADING_KEYWORDS):
                state = 1  # 命中完整答案标题，开始跳过
                continue
            output.append(line)
        elif state == 1:
            if not stripped:
                continue  # 跳过剩标题后的空行
            if stripped.startswith("```"):
                state = 2  # 进入代码块，继续跳过直至闭合
                continue
            # 标题后不是代码块而是普通文本：保留并恢复
            state = 0
            output.append(line)
        else:  # state == 2：跳过代码块内容，遇到闭合围栏结束
            if stripped.startswith("```"):
                state = 0
            continue
    text = "\n".join(output).strip()
    if not text:
        text = "练习模式下已省略完整答案。请先按提示自行尝试；确有需要可切换到非练习模式查看解答。"
    return text


def context_to_dict(context: Any) -> dict[str, Any] | None:
    """把 `AIContextIn` 转成提示构造器需要的字典。"""
    if context is None:
        return None
    return {
        "type": getattr(context, "type", None),
        "id": getattr(context, "id", None),
        "code": getattr(context, "code", None),
        "error": getattr(context, "error", None),
    }


__all__ = ["FULL_ANSWER_LEVELS", "context_to_dict", "enforce_practice_constraint"]
