"""判题类型与状态映射（`docs/SANDBOX.md` §1.2）。

从 `judge_service.py` 拆出：提交状态常量、执行状态→提交状态映射、判题结论数据类
与题型判定工具。供 `judge_objective` / `judge_coding` / `judge_effects` 与门面
`judge_service` 共用。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.enums import ProblemType, SubmissionStatus
from app.models.submission import SubmissionResult

ACCEPTED = SubmissionStatus.ACCEPTED.value
WRONG_ANSWER = SubmissionStatus.WRONG_ANSWER.value
RUNTIME_ERROR = SubmissionStatus.RUNTIME_ERROR.value
TIME_LIMIT = SubmissionStatus.TIME_LIMIT_EXCEEDED.value
MEMORY_LIMIT = SubmissionStatus.MEMORY_LIMIT_EXCEEDED.value
COMPILE_ERROR = SubmissionStatus.COMPILE_ERROR.value
SECURITY_ERROR = SubmissionStatus.SECURITY_ERROR.value
INTERNAL_ERROR = SubmissionStatus.INTERNAL_ERROR.value

#: 客观题题型
OBJECTIVE_TYPES: frozenset[str] = frozenset(
    {ProblemType.CHOICE.value, ProblemType.JUDGE.value, ProblemType.BLANK.value}
)

#: 智能执行状态 → 提交状态
_STATUS_TO_SUBMISSION = {
    "success": ACCEPTED,
    "wrong_answer": WRONG_ANSWER,
    "timeout": TIME_LIMIT,
    "memory_limit_exceeded": MEMORY_LIMIT,
    "security_error": SECURITY_ERROR,
    "output_exceeded": WRONG_ANSWER,
    "compile_error": COMPILE_ERROR,
    "runtime_error": RUNTIME_ERROR,
    "internal_error": INTERNAL_ERROR,
}

_STATUS_LABELS = {
    ACCEPTED: "通过",
    WRONG_ANSWER: "答案错误",
    RUNTIME_ERROR: "运行时错误",
    TIME_LIMIT: "超出时间限制",
    MEMORY_LIMIT: "超出内存限制",
    COMPILE_ERROR: "编译错误",
    SECURITY_ERROR: "代码包含禁用语法",
    INTERNAL_ERROR: "系统错误",
}


@dataclass(slots=True)
class JudgeOutcome:
    """一次判题的结构化结果。"""

    status: str
    score: int = 0
    passed_cases: int = 0
    total_cases: int = 0
    time_ms: int = 0
    memory_kb: int = 0
    runner: str = "rule"
    degraded: bool = True
    judged_by: str = "rule"
    error_type: str | None = None
    error_message: str | None = None
    results: list[SubmissionResult] = field(default_factory=list)


def is_objective(problem_type: str) -> bool:
    """判断题型是否为客观题。"""
    return problem_type in OBJECTIVE_TYPES


def _map_status(sandbox_status: str, passed: int, total: int) -> str:
    """按 SANDBOX.md §1.2 映射执行状态 → 提交状态。"""
    if sandbox_status == "success":
        return ACCEPTED if (total > 0 and passed == total) else WRONG_ANSWER
    return _STATUS_TO_SUBMISSION.get(sandbox_status, INTERNAL_ERROR)


def _error_type_for(status: str) -> str:
    """提交状态 → 错误类型（用于错题本分类）。"""
    return {
        WRONG_ANSWER: "output",
        RUNTIME_ERROR: "runtime_error",
        COMPILE_ERROR: "syntax_error",
        TIME_LIMIT: "timeout",
        MEMORY_LIMIT: "memory_error",
        SECURITY_ERROR: "security_error",
        INTERNAL_ERROR: "internal_error",
    }.get(status, "logic")


def _status_label(status: str) -> str:
    """状态 → 中文提示。"""
    return _STATUS_LABELS.get(status, "判题失败")
