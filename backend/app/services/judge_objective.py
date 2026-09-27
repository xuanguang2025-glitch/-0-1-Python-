"""判题服务 · 客观题判分（选择 / 判断 / 填空，直接比对答案，无需沙箱）。"""

from __future__ import annotations

from app.core.constants import MAX_STDOUT_CHARS
from app.models.enums import ProblemType
from app.models.problem import Problem
from app.models.submission import SubmissionResult
from app.utils.text import normalize_output, truncate

from app.services.judge_types import ACCEPTED, WRONG_ANSWER, JudgeOutcome


def _judge_objective(problem: Problem, submitted: object) -> JudgeOutcome:
    """客观题直接比对答案。"""
    correct, standard_display = _objective_correct(problem, submitted)
    status = ACCEPTED if correct else WRONG_ANSWER
    result = SubmissionResult(
        passed=correct,
        actual_output=truncate(str(submitted), MAX_STDOUT_CHARS),
        expected_output=truncate(str(standard_display), MAX_STDOUT_CHARS),
        message=None if correct else "答案不正确",
    )
    return JudgeOutcome(
        status=status,
        score=int(problem.score or 0) if correct else 0,
        passed_cases=1 if correct else 0,
        total_cases=1,
        runner="rule",
        degraded=False,
        judged_by="rule",
        error_type=None if correct else "logic",
        error_message=None if correct else "答案不正确，请再仔细思考一下",
        results=[result],
    )


def _objective_correct(problem: Problem, submitted: object) -> tuple[bool, object]:
    """判断客观题答案是否正确，返回 `(是否正确, 标准答案展示值)`。"""
    standard = problem.answer_json
    text = normalize_output(str(submitted if submitted is not None else "")).strip()
    if problem.problem_type == ProblemType.CHOICE.value:
        index = _as_index(standard)
        options = problem.options_json or []
        if index is not None and isinstance(options, list) and 0 <= index < len(options):
            if text.isdigit():
                return int(text) == index, index
            return text.lower() == str(options[index]).strip().lower(), index
        return text.lower() == _norm(standard), standard
    if problem.problem_type == ProblemType.JUDGE.value:
        return _as_bool(submitted) == _as_bool(standard), standard
    # blank（填空）
    left = _collapse(text)
    right = _collapse(_norm(standard))
    return left == right, standard


def _as_index(value: object) -> int | None:
    """把答案解成选项下标（int / 数字字符串）。"""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip())
    return None


def _as_bool(value: object) -> bool:
    """把答案解成布尔（兼容 true/false、对/错、1/0）。"""
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    return text in ("true", "1", "yes", "t", "对", "正确")


def _norm(value: object) -> str:
    """字符串归一化（去首尾空白）。"""
    return normalize_output(str(value if value is not None else "")).strip()


def _collapse(text: str) -> str:
    """折叠内部空白后再比较（填空容错）。"""
    return " ".join(text.split())
