"""AI 提示词集中管理（`docs/AI.md` §6，对应 `ai/prompts/*.md`）。

所有模板集中在此，避免散落在业务代码里。运行期不依赖文件 IO（即使 `ai/prompts/`
目录缺失也能工作），`ai/prompts/*.md` 作为可读文档与之保持同步。

导出：
- 枚举：`MODES` / `LEVELS` / `SCENES` / `REVIEW_DIMENSIONS`；
- 模板：`TUTOR_SYSTEM` / `MODE_PROMPTS` / `LEVEL_PROMPTS` / `PRACTICE_RULE` 等；
- 构造器：`build_system_prompt()` / `build_level_instruction()` /
  `build_review_user_prompt()` / `build_error_user_prompt()` / `build_context_block()`。
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

# ---------------------------------------------------------------------------
# 枚举常量
# ---------------------------------------------------------------------------

MODES: list[str] = ["beginner", "standard", "advanced"]
LEVELS: list[str] = ["hint", "approach", "partial", "full", "explain"]
SCENES: list[str] = ["tutor", "review", "error", "exam", "free"]

#: Level → 中文标签（五级递进：提示 → 思路 → 局部提示 → 完整解释 → 深度讲解）
LEVEL_LABELS: dict[str, str] = {
    "hint": "提示",
    "approach": "思路",
    "partial": "局部提示",
    "full": "完整解释",
    "explain": "深度讲解",
}

#: Code Review 九维度
REVIEW_DIMENSIONS: list[str] = [
    "正确性",
    "可读性",
    "复杂度",
    "命名",
    "重复代码",
    "潜在 Bug",
    "安全问题",
    "Python 风格(PEP 8)",
    "优化建议",
]

# ---------------------------------------------------------------------------
# 系统提示
# ---------------------------------------------------------------------------

TUTOR_SYSTEM: str = (
    "你是「PYTHON LAB」平台的 Python 学习导师，面向中文学习者。\n"
    "总则：\n"
    "1. 使用简体中文，语气鼓励、耐心、结构化；输出使用 Markdown，代码块标注语言。\n"
    "2. 引导优先于代劳：先定位卡点，再给可执行的一小步，鼓励学员自己完成。\n"
    "3. 不编造 Python 不存在的 API；不确定时明确说明并给出验证方法。\n"
    "4. 若题目/代码上下文不足，先用一句话反问澄清，再给提示。"
)

PRACTICE_RULE: str = (
    "【练习模式约束】当前处于练习模式：**禁止直接给出完整可运行答案**。\n"
    "- 只给方向、关键概念、定位方法或小的局部片段（不含完整解题函数/完整程序）；\n"
    "- 不要输出可直接复制提交的最终代码；\n"
    "- 如需示例，用「伪代码」或「填空式片段」（含 TODO/... 占位）。"
)

FULL_ANSWER_RULE: str = (
    "【完整解答许可】用户已显式请求完整解释：可以给出完整代码与逐行说明，"
    "但仍需解释关键点，帮助其理解而非替代思考。"
)

MODE_PROMPTS: dict[str, str] = {
    "beginner": (
        "【初学者模式】用生活类比解释概念，一步一动，避免术语堆砌；"
        "每段只讲一个点，必要时用「先……再……」拆解步骤。"
    ),
    "standard": "【标准模式】概念 + 关键代码 + 一个可练习的小例子，兼顾理解与动手。",
    "advanced": (
        "【进阶模式】突出 Pythonic 惯用法、时间复杂度/空间复杂度、边界条件与性能权衡，"
        "可讨论多种实现方案。"
    ),
}

LEVEL_PROMPTS: dict[str, str] = {
    "hint": "【提示】只给一句方向性提示，不涉及具体代码，让学员自己迈出第一步。",
    "approach": "【思路】给出解题/排查的整体思路与步骤大纲（有序列表），不写完整代码。",
    "partial": "【局部提示】给出关键的一两个局部片段或函数骨架，其余留给学员完成。",
    "full": "【完整解释】给出完整实现，并逐段解释为什么这样做。",
    "explain": "【深度讲解】在完整解释基础上，补充原理、复杂度、易错点与延伸阅读方向。",
}

REVIEW_SYSTEM: str = (
    "你是资深 Python 代码评审专家。请从九个维度评审代码："
    + "、".join(REVIEW_DIMENSIONS)
    + "。\n"
    "必须**只输出一个 JSON 对象**（不要 Markdown 围栏、不要多余文字），结构如下：\n"
    '{"score": <0-100 整数>, "summary_md": "<总体分析 Markdown>",'
    ' "issues": [{"severity": "error|warning|info", "line": <行号或 null>,'
    ' "title": "<问题标题>", "suggestion": "<修复建议>"}],'
    ' "improved_code": "<改进后的完整代码，无法给出时为空字符串>"}\n'
    "要求：问题按严重程度排序；line 使用 1 起始行号；建议要可执行、给出具体改法。"
)

ERROR_ANALYSIS_SYSTEM: str = (
    "你是 Python 报错分析助手。请基于代码与报错信息给出结构化分析，"
    "必须**只输出一个 JSON 对象**：\n"
    '{"error_type": "<异常类名或 runtime>", "cause": "<根本原因>",'
    ' "location": "<文件:行号 或 描述>", "fix_steps": ["<步骤1>", "<步骤2>"],'
    ' "minimal_example": "<最小复现代码>", "related_topics": ["<知识点1>", "<知识点2>"]}\n'
    "要求：先定位再解释；修复步骤要具体到可操作；知识点用中文短词。"
)

EXAM_GENERATOR_SYSTEM: str = (
    "你是 Python 出题助手。请按给定知识点与难度分布生成练习题，"
    "每题包含题干、参考答案与解析；答案与解析放在各题末尾，便于单独收起。"
)


# ---------------------------------------------------------------------------
# 构造器
# ---------------------------------------------------------------------------


def build_system_prompt(
    mode: str = "standard",
    *,
    practice_mode: bool = False,
    allow_full_answer: bool = False,
) -> str:
    """组装系统提示（导师总则 + 模式 + 练习约束）。

    Args:
        mode: 讲解模式（beginner/standard/advanced，非法值回退 standard）。
        practice_mode: 是否练习模式（为真则追加禁止完整答案约束）。
        allow_full_answer: 练习模式下是否允许完整答案（配置开关）。

    Returns:
        拼接后的系统提示字符串。
    """
    parts: list[str] = [TUTOR_SYSTEM, MODE_PROMPTS.get(mode, MODE_PROMPTS["standard"])]
    if practice_mode:
        parts.append(FULL_ANSWER_RULE if allow_full_answer else PRACTICE_RULE)
    return "\n\n".join(parts)


def build_level_instruction(level: str) -> str:
    """返回某级提示对应的指令前缀（非法 level 回退 hint）。"""
    return LEVEL_PROMPTS.get(level, LEVEL_PROMPTS["hint"])


def build_context_block(context: Mapping[str, Any] | None) -> str:
    """把题目/代码/报错等上下文渲染为提示片段。

    Args:
        context: `{type, id, code, error, title, statement}` 等键值。

    Returns:
        Markdown 上下文块；无有效内容时返回空串。
    """
    if not context:
        return ""
    lines: list[str] = ["【当前上下文】"]
    ctx_type = context.get("type")
    if ctx_type:
        lines.append(f"- 场景类型：{ctx_type}")
    if context.get("title"):
        lines.append(f"- 标题：{context['title']}")
    if context.get("statement"):
        lines.append("```text\n" + str(context["statement"]).strip() + "\n```")
    if context.get("code"):
        lines.append("待分析代码：\n```python\n" + str(context["code"]).strip() + "\n```")
    if context.get("error"):
        lines.append("报错信息：\n```text\n" + str(context["error"]).strip() + "\n```")
    return "\n".join(lines) if len(lines) > 1 else ""


def build_chat_messages(
    message: str,
    *,
    mode: str = "standard",
    level: str = "hint",
    practice_mode: bool = False,
    allow_full_answer: bool = False,
    context: Mapping[str, Any] | None = None,
    history: Sequence[tuple[str, str]] | None = None,
    extra_system: str | None = None,
) -> list[dict[str, str]]:
    """组装 OpenAI 风格的 messages 列表。

    顺序：system(总则+模式+约束) → [extra_system] → 历史(最近若干轮) → 上下文 → user。

    Args:
        message: 用户本轮提问。
        mode: 讲解模式。
        level: 提示层级。
        practice_mode: 是否练习模式。
        allow_full_answer: 练习模式是否允许完整答案。
        context: 上下文（题目/代码/报错）。
        history: 历史消息 `(role, content)` 列表（旧 → 新）。
        extra_system: 追加的系统提示（如 Review 专用约束）。

    Returns:
        `[{"role": ..., "content": ...}, ...]`。
    """
    messages: list[dict[str, str]] = [
        {"role": "system", "content": build_system_prompt(mode, practice_mode=practice_mode, allow_full_answer=allow_full_answer)}
    ]
    if extra_system:
        messages.append({"role": "system", "content": extra_system})
    if history:
        for role, content in history:
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})
    context_block = build_context_block(context)
    level_instruction = build_level_instruction(level)
    user_parts = [part for part in (level_instruction, context_block, message) if part]
    messages.append({"role": "user", "content": "\n\n".join(user_parts)})
    return messages


def build_review_user_prompt(code: str, *, focus: str | None = None, language: str = "python") -> str:
    """构造 Code Review 的用户提示。"""
    focus_line = f"\n重点关注：{focus}" if focus else ""
    return (
        f"请评审以下 {language} 代码（九个维度）。{focus_line}\n"
        "```" + language + "\n" + (code or "") + "\n```"
    )


def build_error_user_prompt(code: str, error_message: str, traceback_text: str | None = None) -> str:
    """构造报错分析的用户提示。"""
    parts = ["请分析以下 Python 报错。"]
    if code.strip():
        parts.append("代码：\n```python\n" + code.strip() + "\n```")
    parts.append("报错信息：\n```text\n" + (error_message or "").strip() + "\n```")
    if traceback_text:
        parts.append("完整 traceback：\n```text\n" + traceback_text.strip() + "\n```")
    return "\n".join(parts)


__all__ = [
    "ERROR_ANALYSIS_SYSTEM",
    "EXAM_GENERATOR_SYSTEM",
    "FULL_ANSWER_RULE",
    "LEVEL_LABELS",
    "LEVEL_PROMPTS",
    "LEVELS",
    "MODES",
    "MODE_PROMPTS",
    "PRACTICE_RULE",
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
]
