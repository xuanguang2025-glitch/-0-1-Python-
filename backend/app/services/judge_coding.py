"""判题服务 · 编程题判题（逐用例走沙箱客户端执行）。"""

from __future__ import annotations

from app.core.constants import MAX_STDOUT_CHARS
from app.db.base import utc_now
from app.models.problem import Problem
from app.models.submission import SubmissionResult
from app.services.sandbox_client import ExecutionResult, compare_output, get_sandbox_client
from app.utils.text import truncate

from app.services.judge_types import (
    ACCEPTED,
    WRONG_ANSWER,
    JudgeOutcome,
    _error_type_for,
    _map_status,
    _status_label,
)


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
