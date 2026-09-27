"""判题服务：题型分流、状态映射、逐用例落库与学习副作用（`docs/SANDBOX.md` §1.2）。

流程：
1. 客观题（choice/judge/blank）直接比对答案，无需沙箱；
2. 编程类（completion/coding/debug/algorithm）逐用例走沙箱客户端执行；
3. 按 SANDBOX.md §1.2 映射提交状态（Accepted / Wrong Answer / Runtime Error /
   Time Limit Exceeded / Memory Limit Exceeded / Compile Error / Security Error / System Error）；
4. 落库 `submissions` + `submission_results`；更新题目统计、掌握度、XP、连续学习天数；
5. WA/RE 等失败自动写入错题本；通过则把相关知识点标记为已掌握。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.constants import (
    MAX_ERROR_MESSAGE_CHARS,
    MAX_STDOUT_CHARS,
    XP_REASON_AC,
    level_of_xp,
    mastery_level_of,
)
from app.core.errors import AppError, ErrorCode
from app.db.base import utc_now
from app.models.course import LessonTopic, Topic
from app.models.enums import MasteryLevel, MistakeErrorType, ProblemType, SubmissionStatus
from app.models.gamification import XPTransaction
from app.models.learning import KnowledgeMastery, LearningProgress, Mistake
from app.models.problem import Problem, ProblemTag, Tag
from app.models.submission import Submission, SubmissionResult
from app.models.user import User
from app.services.sandbox_client import ExecutionResult, compare_output, get_sandbox_client
from app.utils.text import normalize_output, truncate
from app.utils.time import to_utc

logger = logging.getLogger("pythonlab.judge")

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


def is_objective(problem_type: str) -> bool:
    """判断题型是否为客观题。"""
    return problem_type in OBJECTIVE_TYPES


# ------------------------------------------------------------- 客观题判分
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


# ------------------------------------------------------------- 编程题判题
def _judge_coding(problem: Problem, code: str) -> JudgeOutcome:
    """编程类逐用例走沙箱判题。"""
    cases = _load_cases(problem)
    client = get_sandbox_client()
    files = {"main.py": code}
    if not cases:
        result = client.run(
            files,
            stdin=problem.sample_input or "",
            entry="main.py",
            timeout_ms=problem.time_limit_ms,
            memory_mb=problem.memory_limit_mb,
        )
        return _outcome_from_single(problem, result)
    payload = [
        {
            "id": case["id"],
            "input": case["input"],
            "expected": case["expected"],
            "comparison": case["comparison"],
            "tolerance": case["tolerance"],
            "timeout_ms": case["timeout_ms"],
        }
        for case in cases
    ]
    result = client.judge(
        files, payload, entry="main.py", timeout_ms=problem.time_limit_ms, memory_mb=problem.memory_limit_mb
    )
    return _outcome_from_cases(problem, cases, result)


def _load_cases(problem: Problem) -> list[dict[str, object]]:
    """读取题目用例（按顺序），返回判题所需的纯数据。"""
    ordered = sorted(problem.test_cases or [], key=lambda item: (item.order_index, item.created_at or utc_now()))
    return [
        {
            "id": case.id,
            "index": index,
            "input": case.input or "",
            "expected": case.expected_output or "",
            "comparison": case.comparison or "trimmed",
            "tolerance": float(case.float_tolerance or 1e-6),
            "timeout_ms": case.timeout_ms,
            "is_sample": bool(case.is_sample),
            "is_hidden": bool(case.is_hidden),
            "weight": int(case.weight or 1),
        }
        for index, case in enumerate(ordered, start=1)
    ]


def _outcome_from_cases(problem: Problem, cases: list[dict[str, object]], result: ExecutionResult) -> JudgeOutcome:
    """把沙箱逐用例结果转换为判题结论并落库结果行。"""
    by_id = {case_result.test_case_id: case_result for case_result in result.results}
    ordered_results: list[SubmissionResult] = []
    passed_count = 0
    passed_weight = 0
    total_weight = 0
    first_failure: str | None = None

    for case in cases:
        weight = int(case["weight"] or 1)
        total_weight += weight
        case_result = by_id.get(case["id"])
        if case_result is None:
            ordered_results.append(
                SubmissionResult(
                    test_case_id=case["id"],
                    passed=False,
                    expected_output=truncate(str(case["expected"]), MAX_STDOUT_CHARS),
                    message="未执行（前序用例失败）",
                )
            )
            if first_failure is None:
                first_failure = f"第 {case['index']} 个测试点未通过"
            continue
        if case_result.passed:
            passed_count += 1
            passed_weight += weight
        message = _case_message(case, case_result)
        if not case_result.passed and first_failure is None:
            first_failure = message
        ordered_results.append(
            SubmissionResult(
                test_case_id=case["id"],
                passed=bool(case_result.passed),
                actual_output=truncate(case_result.actual or "", MAX_STDOUT_CHARS),
                expected_output=truncate(str(case["expected"]), MAX_STDOUT_CHARS),
                stdout=truncate(case_result.actual or "", MAX_STDOUT_CHARS),
                stderr=truncate(case_result.stderr or "", MAX_STDOUT_CHARS) or None,
                diff=truncate(case_result.diff or "", MAX_STDOUT_CHARS) or None,
                time_ms=int(case_result.time_ms or 0),
                memory_kb=int(case_result.memory_kb or 0),
                message=truncate(message or "", 300) or None,
            )
        )

    status = _map_status(result.status, passed_count, len(cases))
    if status == ACCEPTED:
        score = int(problem.score or 0)
    elif total_weight:
        score = int(round(int(problem.score or 0) * passed_weight / total_weight))
    else:
        score = 0
    return JudgeOutcome(
        status=status,
        score=score,
        passed_cases=passed_count,
        total_cases=len(cases),
        time_ms=int(result.time_ms or 0),
        memory_kb=int(result.memory_kb or 0),
        runner=result.runner,
        degraded=bool(result.degraded),
        judged_by=result.runner,
        error_type=None if status == ACCEPTED else _error_type_for(status),
        error_message=None if status == ACCEPTED else (first_failure or _status_label(status)),
        results=ordered_results,
    )


def _outcome_from_single(problem: Problem, result: ExecutionResult) -> JudgeOutcome:
    """无测试用例时的退化判题：用样例输入运行一次并按样例输出比对。"""
    if result.status != "success":
        status = _map_status(result.status, 0, 0)
        return JudgeOutcome(
            status=status,
            score=0,
            passed_cases=0,
            total_cases=1,
            time_ms=int(result.time_ms or 0),
            memory_kb=int(result.memory_kb or 0),
            runner=result.runner,
            degraded=bool(result.degraded),
            judged_by=result.runner,
            error_type=_error_type_for(status),
            error_message=result.error or _status_label(status),
            results=[
                SubmissionResult(
                    passed=False,
                    actual_output=truncate(result.stdout or "", MAX_STDOUT_CHARS),
                    stderr=truncate(result.stderr or "", MAX_STDOUT_CHARS) or None,
                    message=truncate(result.error or _status_label(status), 300),
                )
            ],
        )
    expected = problem.sample_output or ""
    passed = compare_output(result.stdout or "", expected, "trimmed") if expected.strip() else True
    status = ACCEPTED if passed else WRONG_ANSWER
    return JudgeOutcome(
        status=status,
        score=int(problem.score or 0) if passed else 0,
        passed_cases=1 if passed else 0,
        total_cases=1,
        time_ms=int(result.time_ms or 0),
        memory_kb=int(result.memory_kb or 0),
        runner=result.runner,
        degraded=bool(result.degraded),
        judged_by=result.runner,
        error_type=None if passed else "output",
        error_message=None if passed else "输出与样例不符",
        results=[
            SubmissionResult(
                passed=passed,
                actual_output=truncate(result.stdout or "", MAX_STDOUT_CHARS),
                expected_output=truncate(expected, MAX_STDOUT_CHARS),
                message=None if passed else "输出与样例不符",
            )
        ],
    )


def _case_message(case: dict[str, object], case_result: object) -> str:
    """生成单用例的人类可读提示（隐藏用例不泄露期望值）。"""
    status = getattr(case_result, "status", "success")
    visible = bool(case["is_sample"]) and not bool(case["is_hidden"])
    if not visible:
        return f"第 {case['index']} 个测试点未通过"
    if status == "timeout":
        return f"第 {case['index']} 个测试点超时"
    if status == "memory_limit_exceeded":
        return f"第 {case['index']} 个测试点内存超限"
    if status in ("runtime_error", "compile_error"):
        detail = getattr(case_result, "message", None) or getattr(case_result, "stderr", "") or ""
        return f"第 {case['index']} 个测试点运行出错：{str(detail).strip().splitlines()[-1][:120] if detail else ''}"
    expected = _short(str(case["expected"]))
    actual = _short(getattr(case_result, "actual", "") or "")
    return f"第 {case['index']} 个测试点未通过：期望 {expected}，实际 {actual}"


def _short(text: str, limit: int = 60) -> str:
    """把多行输出压缩为单行短文本。"""
    single = " ".join((text or "").split())
    return single if len(single) <= limit else single[:limit] + "…"


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


# ------------------------------------------------------------- 学习副作用
def _post_judge_effects(
    db: Session, user: User, problem: Problem, submission: Submission, outcome: JudgeOutcome
) -> None:
    """更新题目统计、掌握度、XP、连续学习天数与错题本。"""
    _update_problem_stats(problem, submission)
    topics = _topics_for(db, problem, submission.lesson_id)
    accepted = submission.status == ACCEPTED

    if accepted:
        _award_ac_xp(db, user, problem, submission)
        _resolve_mistakes(db, user, problem)
    for topic_id, _weight in topics:
        _update_mastery(db, user, topic_id, accepted)
    if not accepted:
        primary_topic = topics[0][0] if topics else None
        _record_mistake(db, user, problem, submission, primary_topic)
    if submission.lesson_id:
        _update_lesson_progress(db, user, submission)
    _touch_streak(db, user)
    db.flush()


def _update_problem_stats(problem: Problem, submission: Submission) -> None:
    """更新题目提交 / 通过计数与通过率。"""
    problem.submission_count = int(problem.submission_count or 0) + 1
    if submission.status == ACCEPTED:
        problem.accepted_count = int(problem.accepted_count or 0) + 1
    problem.refresh_acceptance_rate()
    if submission.time_ms:
        problem.avg_time_ms = int(submission.time_ms or 0)


def _award_ac_xp(db: Session, user: User, problem: Problem, submission: Submission) -> None:
    """首次通过该题时发放 XP 并写流水。"""
    prior = db.scalar(
        select(func.count())
        .select_from(Submission)
        .where(
            Submission.user_id == user.id,
            Submission.problem_id == problem.id,
            Submission.status == ACCEPTED,
            Submission.id != submission.id,
        )
    )
    if prior:
        return
    amount = int(problem.xp_reward or 0)
    if amount <= 0:
        return
    user.xp = int(user.xp or 0) + amount
    user.level = level_of_xp(int(user.xp), get_settings().level_threshold_list)
    db.add(
        XPTransaction(
            user_id=user.id,
            amount=amount,
            reason=XP_REASON_AC,
            ref_type="problem",
            ref_id=problem.id,
            balance_after=int(user.xp),
        )
    )


def _topics_for(db: Session, problem: Problem, lesson_id: str | None) -> list[tuple[str, float]]:
    """汇总题目关联知识点：课时主/次知识点 + 标签同名知识点。"""
    weights: dict[str, float] = {}
    if lesson_id:
        for link in db.scalars(select(LessonTopic).where(LessonTopic.lesson_id == lesson_id)).all():
            weights[link.topic_id] = 1.0 if link.is_primary else 0.5
    tag_slugs = list(
        db.scalars(
            select(Tag.slug).join(ProblemTag, ProblemTag.tag_id == Tag.id).where(ProblemTag.problem_id == problem.id)
        ).all()
    )
    if tag_slugs:
        for topic in db.scalars(select(Topic).where(Topic.slug.in_(tag_slugs))).all():
            weights.setdefault(topic.id, 1.0)
    return list(weights.items())


def _update_mastery(db: Session, user: User, topic_id: str, correct: bool) -> None:
    """更新单个知识点掌握度；通过时标记为已掌握。"""
    mastery = db.scalars(
        select(KnowledgeMastery).where(
            KnowledgeMastery.user_id == user.id, KnowledgeMastery.topic_id == topic_id
        )
    ).one_or_none()
    if mastery is None:
        mastery = KnowledgeMastery(
            user_id=user.id, topic_id=topic_id, mastery_score=0.0, mastery_level=MasteryLevel.NONE.value
        )
        db.add(mastery)
    mastery.apply_result(correct)
    if correct:
        mastery.mastery_score = max(float(mastery.mastery_score or 0.0), 90.0)
        mastery.mastery_level = mastery_level_of(mastery.mastery_score)
    db.flush()


def _resolve_mistakes(db: Session, user: User, problem: Problem) -> None:
    """答对该题后，把该用户该题所有未解决的错题条目标记为已掌握（幂等）。

    仅修改 `resolved` 状态，保留 `review_count` 与 `user_answer` 等学习记录；
    重复 AC 不会报错，也不会触碰已解决的条目。
    """
    unresolved = db.scalars(
        select(Mistake).where(
            Mistake.user_id == user.id,
            Mistake.problem_id == problem.id,
            Mistake.resolved.is_(False),
        )
    ).all()
    for mistake in unresolved:
        mistake.resolve(True)
    if unresolved:
        db.flush()


def _record_mistake(
    db: Session, user: User, problem: Problem, submission: Submission, topic_id: str | None
) -> None:
    """写入 / 更新错题本条目（同一题未掌握时累加错误次数）。"""
    error_type = _mistake_error_type(submission.status)
    existing = db.scalars(
        select(Mistake)
        .where(
            Mistake.user_id == user.id,
            Mistake.problem_id == problem.id,
            Mistake.resolved.is_(False),
        )
        .order_by(Mistake.updated_at.desc())
    ).first()
    answer = truncate(submission.code or "", MAX_STDOUT_CHARS)
    if existing is not None:
        existing.review_count = int(existing.review_count or 0) + 1
        existing.user_answer = answer
        existing.error_type = error_type
        existing.error_message = submission.error_message
        existing.submission_id = submission.id
        if topic_id:
            existing.topic_id = topic_id
        existing.schedule_review(1)
        return
    mistake = Mistake(
        user_id=user.id,
        problem_id=problem.id,
        submission_id=submission.id,
        lesson_id=submission.lesson_id,
        topic_id=topic_id,
        title=problem.title or "错题",
        question_snapshot_md=problem.statement_md,
        user_answer=answer,
        correct_answer=None,
        error_type=error_type,
        error_message=submission.error_message,
        review_count=1,
    )
    mistake.schedule_review(1)
    db.add(mistake)


def _mistake_error_type(status: str) -> str:
    """提交状态 → 错题错误类型。"""
    return {
        WRONG_ANSWER: MistakeErrorType.OUTPUT.value,
        RUNTIME_ERROR: MistakeErrorType.RUNTIME.value,
        COMPILE_ERROR: MistakeErrorType.SYNTAX.value,
        TIME_LIMIT: MistakeErrorType.TIMEOUT.value,
        MEMORY_LIMIT: MistakeErrorType.RUNTIME.value,
        SECURITY_ERROR: MistakeErrorType.CONCEPT.value,
    }.get(status, MistakeErrorType.LOGIC.value)


def _update_lesson_progress(db: Session, user: User, submission: Submission) -> None:
    """更新随堂练习课时进度（次数 + 代码快照）。"""
    progress = db.scalars(
        select(LearningProgress).where(
            LearningProgress.user_id == user.id, LearningProgress.lesson_id == submission.lesson_id
        )
    ).one_or_none()
    if progress is None:
        progress = LearningProgress(user_id=user.id, lesson_id=str(submission.lesson_id))
        db.add(progress)
    progress.attempt_count = int(progress.attempt_count or 0) + 1
    progress.code_snapshot = truncate(submission.code or "", MAX_STDOUT_CHARS)
    if progress.started_at is None:
        progress.started_at = utc_now()


def _touch_streak(db: Session, user: User) -> None:
    """按 UTC 日期维护连续学习天数。"""
    now = utc_now()
    today = now.date()
    last = user.last_active_at
    if last is None:
        user.streak_days = 1
    else:
        delta = (today - to_utc(last).date()).days
        if delta == 0:
            user.streak_days = int(user.streak_days or 0) or 1
        elif delta == 1:
            user.streak_days = int(user.streak_days or 0) + 1
        else:
            user.streak_days = 1
    if int(user.streak_days or 0) > int(user.max_streak_days or 0):
        user.max_streak_days = int(user.streak_days)
    user.last_active_at = now


__all__ = [
    "JudgeOutcome",
    "OBJECTIVE_TYPES",
    "is_objective",
    "judge_submission",
    "rejudge",
]
