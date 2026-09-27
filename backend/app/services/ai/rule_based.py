"""离线规则引擎 Provider（无 Key / 远程失败时的降级实现）。

它**不是**一句「请配置 Key」的占位，而是真正可用的本地 AI 能力：

- 报错分析：识别 ≥12 种异常、解析 traceback 定位行号、映射知识点、给出修复步骤与最小复现；
- 代码静态审查：九维度启发式检查（可变默认参数 / 裸 except / 未使用导入 / range(len) 等）；
- 学习建议与练习生成：按知识点模板出题（含答案与解析）、生成学习计划与测试模板；
- 代码解释 / 优化 / 重构建议 / 通用答疑。

所有输出一律 `degraded=True`，前端据此显示「离线助手」徽章。
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.services.ai import knowledge
from app.services.ai.base import AIProvider, AIResponse, ChatMessage, TokenUsage, estimate_tokens
from app.services.ai.error_analysis import analyze_error
from app.services.ai.prompts import LEVEL_LABELS
from app.services.ai.static_analysis import review_code

_CODE_FENCE_RE: re.Pattern[str] = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)
_ERROR_LINE_RE: re.Pattern[str] = re.compile(r"^.*(?:Error|Exception|Traceback)\b.*$", re.MULTILINE)

#: 支持的任务类型
TASKS: list[str] = [
    "tutor",
    "review",
    "error",
    "practice",
    "plan",
    "tests",
    "explain",
    "optimize",
    "refactor",
    "qa",
]


def _last_user_content(messages: list[ChatMessage]) -> str:
    """取最后一条用户消息内容。"""
    for message in reversed(messages):
        if message.role == "user":
            return message.content or ""
    return messages[-1].content if messages else ""


def _extract_code(text: str) -> str:
    """从文本中提取第一个 ```python 代码块（无围栏时返回原文）。"""
    match = _CODE_FENCE_RE.search(text or "")
    if match:
        return match.group(1).strip()
    return ""


def _extract_error(text: str) -> str:
    """从文本中提取报错行（含 Error/Exception/Traceback）。"""
    lines = [line for line in (text or "").splitlines() if _ERROR_LINE_RE.match(line)]
    if lines:
        return lines[-1].strip()
    return ""


def _extract_traceback(text: str) -> str:
    """提取 traceback 主体（含 "Traceback" 或 "File ..." 的段落）。"""
    raw = text or ""
    if "Traceback" not in raw and 'File "' not in raw:
        return ""
    return raw


class RuleBasedProvider(AIProvider):
    """本地规则引擎 Provider（离线降级）。"""

    name = "rule_based"
    supports_streaming = True

    def __init__(self, cfg: Any = None) -> None:  # noqa: ANN401 - 复用基类配置类型
        """初始化（配置可为空，规则引擎不依赖任何远程参数）。"""
        from app.services.ai.base import ProviderConfig

        super().__init__(cfg or ProviderConfig(provider="rule", model="rule-based"))

    @property
    def model(self) -> str:
        """规则引擎的生效模型名恒为 `rule-based`（忽略远程配置的目标模型）。"""
        return "rule-based"

    @property
    def available(self) -> bool:
        """规则引擎始终可用。"""
        return True

    async def health(self) -> bool:
        """规则引擎始终健康。"""
        return True

    async def chat(self, messages: list[ChatMessage], **opts: Any) -> AIResponse:
        """按 `task` 分派到对应规则实现。

        Args:
            messages: 对话消息。
            **opts: 支持 `task`（见 `TASKS`）、`json_mode`、`level`、`mode`、`topic`、
                `difficulty`、`count`、`days` 等。

        Returns:
            `AIResponse`（固定 `degraded=True`）。
        """
        task = str(opts.get("task") or "tutor")
        json_mode = bool(opts.get("json_mode"))
        user_content = _last_user_content(messages)
        content = self._dispatch(task, user_content, messages, opts, json_mode=json_mode)
        return AIResponse(
            content=content,
            model="rule-based",
            provider="rule_based",
            usage=TokenUsage(
                prompt_tokens=estimate_tokens("".join(m.content for m in messages)),
                completion_tokens=estimate_tokens(content),
            ),
            finish_reason="stop",
            degraded=True,
            latency_ms=0,
            raw={"task": task, "offline": True},
        )

    # ------------------------------------------------------------------
    # 分派
    # ------------------------------------------------------------------
    def _dispatch(
        self,
        task: str,
        user_content: str,
        messages: list[ChatMessage],
        opts: dict[str, Any],
        *,
        json_mode: bool,
    ) -> str:
        """按任务类型生成响应内容。"""
        if task == "review":
            return self._do_review(user_content, opts, json_mode=json_mode)
        if task == "error":
            return self._do_error(user_content, opts, json_mode=json_mode)
        if task == "practice":
            return knowledge.generate_practice(
                topic=str(opts.get("topic") or ""),
                difficulty=str(opts.get("difficulty") or "easy"),
                count=int(opts.get("count") or 3),
            )
        if task == "plan":
            return knowledge.generate_plan(
                goal=str(opts.get("goal") or user_content[:40] or "系统掌握 Python"),
                days=int(opts.get("days") or 7),
            )
        if task == "tests":
            return knowledge.generate_tests(_extract_code(user_content))
        if task == "explain":
            return knowledge.explain_code(_extract_code(user_content) or user_content)
        if task == "optimize":
            return knowledge.optimize_suggestions(_extract_code(user_content) or user_content)
        if task == "refactor":
            return knowledge.refactor_suggestions(_extract_code(user_content) or user_content)
        if task == "qa":
            return knowledge.answer_question(user_content)
        return self._do_tutor(user_content, opts)

    # ------------------------------------------------------------------
    # 子任务实现
    # ------------------------------------------------------------------
    def _do_review(self, user_content: str, opts: dict[str, Any], *, json_mode: bool) -> str:
        """代码评审（九维度）。"""
        code = _extract_code(user_content) or user_content
        result = review_code(code)
        if json_mode:
            return json.dumps(result.as_dict(), ensure_ascii=False)
        lines = [
            f"### 代码评审（离线规则）· 评分 {result.score}/100",
            "",
            result.summary_md,
            "",
            "#### 问题清单",
        ]
        if not result.issues:
            lines.append("- 未发现明显问题。")
        for issue in result.issues:
            location = f"第 {issue.line} 行" if issue.line else "整体"
            lines.append(f"- **[{issue.severity}]** {location} · {issue.title}：{issue.suggestion}")
        lines.append("")
        lines.append("#### 维度评估")
        for dimension, status in result.dimensions.items():
            lines.append(f"- {dimension}：{status}")
        if result.improved_code:
            lines.extend(["", "#### 改进后代码", "```python", result.improved_code, "```"])
        return "\n".join(lines)

    def _do_error(self, user_content: str, opts: dict[str, Any], *, json_mode: bool) -> str:
        """报错分析。"""
        code = _extract_code(user_content) or str(opts.get("code") or "")
        error_message = str(opts.get("error_message") or "") or _extract_error(user_content) or user_content
        traceback_text = str(opts.get("traceback") or "") or _extract_traceback(user_content)
        analysis = analyze_error(code, error_message, traceback_text)
        if json_mode:
            payload = analysis.as_dict()
            payload.pop("degraded", None)
            return json.dumps(payload, ensure_ascii=False)
        return analysis.to_markdown()

    def _do_tutor(self, user_content: str, opts: dict[str, Any]) -> str:
        """导师提示/思路/讲解（受 level 控制，不越级给完整答案）。"""
        level = str(opts.get("level") or "hint")
        label = LEVEL_LABELS.get(level, "提示")
        code = _extract_code(user_content)
        topics = self._guess_topics(user_content, code)

        lines = [f"### 离线助手 · {label}", ""]
        if level == "hint":
            lines.append("先别急着写代码，试着回答下面这一步：")
            lines.append(f"- 你能用一句话说清「输入是什么、期望输出是什么」吗？")
            lines.append(f"- 涉及的知识点可能是：{('、'.join(topics) or '基础语法')}。")
            lines.append("")
            lines.append("> 想进一步，就点「给我思路」。")
        elif level == "approach":
            lines.append("解题/排查思路（按顺序）：")
            lines.append(f"1. 明确输入输出与边界（空值、0、负数、多行输入）。")
            lines.append(f"2. 本问题涉及：{('、'.join(topics) or '基础语法')}。")
            lines.append("3. 先写出最小可运行的骨架，再逐步补全。")
            lines.append("4. 用小数据手工验证每一步的中间结果。")
        elif level == "partial":
            lines.append("关键片段（其余留给你完成）：")
            lines.append("```python")
            lines.append("# 先读取输入并转换类型")
            lines.append("data = input().split()  # TODO: 按需处理")
            lines.append("```")
            lines.append("把上面片段补全，再运行看看结果是否符合预期。")
        else:  # full / explain
            lines.append("下面给出完整思路与实现要点：")
            lines.append("```python")
            lines.append("# 参考实现（请对照理解，不要直接提交）")
            lines.append("def solve(data):")
            lines.append("    # TODO: 按题目要求实现")
            lines.append("    ...")
            lines.append("```")
            if level == "explain":
                lines.append("")
                lines.append("进一步思考：时间复杂度、边界条件、是否有更 Pythonic 的写法。")
        if not code and level == "hint":
            lines.append("")
            lines.append(knowledge.answer_question(user_content))
        return "\n".join(lines)

    @staticmethod
    def _guess_topics(text: str, code: str) -> list[str]:
        """根据关键词粗略推断相关知识点。"""
        blob = f"{text}\n{code}".lower()
        mapping = [
            (("for ", "while ", "循环"), "循环与迭代"),
            (("def ", "函数", "参数"), "函数"),
            (("list", "列表", "append"), "列表与元组"),
            (("dict", "字典", "key"), "字典与集合"),
            (("try", "except", "异常"), "异常处理"),
            (("class ", "类", "self"), "面向对象"),
            (("open(", "文件"), "文件与路径"),
            (("input(", "print("), "输入输出"),
        ]
        topics = [topic for keys, topic in mapping if any(k in blob for k in keys)]
        return topics[:3]


__all__ = ["RuleBasedProvider", "TASKS"]
