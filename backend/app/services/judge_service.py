"""判题服务：题型分流、状态映射、逐用例落库与学习副作用（`docs/SANDBOX.md` §1.2）。

流程：
1. 客观题（choice/judge/blank）直接比对答案，无需沙箱；
2. 编程类（completion/coding/debug/algorithm）逐用例走沙箱客户端执行；
3. 按 SANDBOX.md §1.2 映射提交状态（Accepted / Wrong Answer / Runtime Error /
   Time Limit Exceeded / Memory Limit Exceeded / Compile Error / Security Error / System Error）；
4. 落库 `submissions` + `submission_results`；更新题目统计、掌握度、XP、连续学习天数；
5. WA/RE 等失败自动写入错题本；通过则把相关知识点标记为已掌握。

实现被拆分为：`judge_types.py`（状态映射与结论数据类）、`judge_objective.py`（客观题判分）、
`judge_coding.py`（编程题判题）、`judge_effects.py`（学习副作用）。本模块保留判题主流程
（`judge_submission` / `rejudge`），并继续导出全部既有符号，既有调用方无需改动。
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.constants import MAX_ERROR_MESSAGE_CHARS
from app.core.errors import AppError, ErrorCode
from app.db.base import utc_now
from app.models.enums import SubmissionStatus
from app.models.problem import Problem
from app.models.submission import Submission
from app.models.user import User
from app.utils.text import truncate

from app.services.judge_coding import (
    _case_message,
    _judge_coding,
    _load_cases,
    _outcome_from_cases,
    _outcome_from_single,
    _short,
)
from app.services.judge_effects import (
    _award_ac_xp,
    _mistake_error_type,
    _post_judge_effects,
    _record_mistake,
    _resolve_mistakes,
    _topics_for,
    _touch_streak,
    _update_lesson_progress,
    _update_mastery,
    _update_problem_stats,
)
from app.services.judge_objective import (
    _as_bool,
    _as_index,
    _collapse,
    _judge_objective,
    _norm,
    _objective_correct,
)
from app.services.judge_types import (
    ACCEPTED,
    COMPILE_ERROR,
    INTERNAL_ERROR,
    MEMORY_LIMIT,
    OBJECTIVE_TYPES,
    RUNTIME_ERROR,
    SECURITY_ERROR,
    TIME_LIMIT,
    WRONG_ANSWER,
    JudgeOutcome,
    _STATUS_LABELS,
    _STATUS_TO_SUBMISSION,
    _error_type_for,
    _map_status,
    _status_label,
    is_objective,
)

logger = logging.getLogger("pythonlab.judge")

__all__ = [
    "ACCEPTED",
    "COMPILE_ERROR",
    "INTERNAL_ERROR",
    "JudgeOutcome",
    "MEMORY_LIMIT",
    "OBJECTIVE_TYPES",
    "RUNTIME_ERROR",
    "SECURITY_ERROR",
    "TIME_LIMIT",
    "WRONG_ANSWER",
    "is_objective",
    "judge_submission",
    "rejudge",
]


# --------------------------------------------------------------------- 入口
def judge_submission(
    db: Session,
    user: User,
    *,
    problem: Problem,
    code: str = "",
    language: str = "python",
    lesson_id: str | None = None,
    answer: object | None = None,
    ip: str | None = None,
) -> Submission:
    """执行一次同步判题并落库（含学习副作用）。

    Args:
        db: 数据库会话。
        user: 提交用户。
        problem: 目标题目（必须存在）。
        code: 用户代码 / 答案文本。
        language: 语言（当前仅 python）。
        lesson_id: 关联课时（随堂练习）。
        answer: 客观题答案（优先于 code）。
        ip: 客户端 IP（记录用）。

    Returns:
        已完成判题的 `Submission`。
    """
    submission = Submission(
        user_id=user.id,
        problem_id=problem.id,
        lesson_id=lesson_id,
        language=language or "python",
        code=code or "",
        status=SubmissionStatus.JUDGING.value,
        ip=ip,
    )
    db.add(submission)
    db.flush()

    if problem.is_objective:
        outcome = _judge_objective(problem, answer if answer is not None else code)
    else:
        outcome = _judge_coding(problem, code or "")

    _apply_outcome(submission, outcome)
    db.commit()
    db.refresh(submission)

    _post_judge_effects(db, user, problem, submission, outcome)
    db.commit()
    db.refresh(submission)
    return submission


def rejudge(db: Session, submission: Submission) -> Submission:
    """重判已有提交（不重复发放 XP）。"""
    problem = db.get(Problem, submission.problem_id) if submission.problem_id else None
    if problem is None:
        raise AppError(code=ErrorCode.BAD_REQUEST, message="提交未关联题目，无法重判")
    for item in list(submission.results):
        db.delete(item)
    db.flush()

    outcome = (
        _judge_objective(problem, submission.code)
        if problem.is_objective
        else _judge_coding(problem, submission.code or "")
    )
    submission.status = SubmissionStatus.JUDGING.value
    _apply_outcome(submission, outcome)
    db.commit()
    db.refresh(submission)
    return submission


# ------------------------------------------------------------------ 落库
def _apply_outcome(submission: Submission, outcome: JudgeOutcome) -> None:
    """把判题结论写回提交对象。"""
    submission.status = outcome.status
    submission.score = int(outcome.score or 0)
    submission.passed_cases = int(outcome.passed_cases or 0)
    submission.total_cases = int(outcome.total_cases or 0)
    submission.time_ms = int(outcome.time_ms or 0)
    submission.memory_kb = int(outcome.memory_kb or 0)
    submission.runner = outcome.runner
    submission.judged_by = outcome.judged_by
    submission.error_type = outcome.error_type
    submission.error_message = truncate(outcome.error_message or "", MAX_ERROR_MESSAGE_CHARS) or None
    submission.finished_at = utc_now()
    submission.results = list(outcome.results)
