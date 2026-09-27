"""考试服务 · 判分（客观题直接判；代码题优先调用 judge_service，缺失回退本机）。"""

from __future__ import annotations

import inspect
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.problem import Problem, TestCase
from app.utils.text import normalize_output

from .common import OBJECTIVE_TYPES

logger = logging.getLogger("pythonlab.exam")

#: judge_service 中「纯判分」入口候选名（需满足 `(db, problem, code) -> dict` 签名）
CANDIDATE_JUDGE_ENTRYPOINTS: tuple[str, ...] = (
    "judge_submission",
    "judge",
    "grade",
    "judge_code",
    "run_judge",
)


def accepts_db_problem_code(func_obj: Any) -> bool:
    """判断函数能否以 `(db, problem, code)` 三个位置参数调用。

    用于在动态绑定 judge_service 时排除「签名不兼容」的入口（例如持久化的
    `judge_submission(db, user, *, problem, code)`），避免 `getattr` + 默认值
    把"绑错函数"变成永远不报错的静默失效。
    """
    try:
        signature = inspect.signature(func_obj)
    except (TypeError, ValueError):
        return False
    positional = [
        param
        for param in signature.parameters.values()
        if param.kind in (param.POSITIONAL_ONLY, param.POSITIONAL_OR_KEYWORD)
    ]
    has_varargs = any(param.kind == param.VAR_POSITIONAL for param in signature.parameters.values())
    return len(positional) >= 3 or has_varargs


def normalize(value: Any) -> str:
    """把答案归一化为可比较字符串。"""
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return str(value).strip().lower()


def to_bool(value: Any) -> bool:
    """把答案宽松地转换为布尔（判断题型用）。"""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "t", "对", "正确")
    if isinstance(value, (int, float)):
        return bool(value)
    return False


def check_objective(problem: Problem, answer: Any) -> bool:
    """客观题判分（选择 / 判断 / 填空 / 补全）。"""
    expected = problem.answer_json
    ptype = problem.problem_type

    if ptype == "choice":
        options = problem.options_json or []
        try:
            index = int(expected) if expected is not None else None
        except (TypeError, ValueError):
            index = None
        if index is not None:
            if isinstance(answer, bool):
                return False
            if isinstance(answer, int):
                return answer == index
            if isinstance(answer, str) and answer.strip().isdigit():
                return int(answer.strip()) == index
            if isinstance(answer, str) and 0 <= index < len(options):
                return answer.strip() == str(options[index]).strip()
        return normalize(answer) == normalize(expected)

    if ptype == "judge":
        return to_bool(answer) == to_bool(expected)

    return normalize(answer) == normalize(expected)


def external_judge(db: Session, problem: Problem, code: str) -> dict[str, Any] | None:
    """尝试调用同事的 `judge_service`（延迟导入，缺失/不兼容时返回 None）。

    约定：本处只消费**纯判分**接口（形如 `(db, problem, code) -> dict`，无落库副作用），
    因为考试 / 挑战判分"只取判定结果"，提交落库由考试 / 挑战各自完成，避免重复写库
    与重复发放 XP。

    `judge_service.judge_submission(db, user, *, problem, code) -> Submission` 是
    **持久化入口**（内部会创建 Submission 并触发 XP / 掌握度 / 错题 / 连击等副作用），
    因此**不在此处调用**；若它是唯一入口则回退本机执行器判分（结果等价、无副作用）。

    为避免"函数名写错被 `getattr` 默认值吞掉"的静默失效，这里用签名校验决定是否调用，
    并在 judge_service 存在但无可绑定入口时输出 debug 日志。
    """
    try:
        from app.services import judge_service  # type: ignore
    except Exception:  # noqa: BLE001 - 依赖尚未就绪时回退本地判题
        return None

    for name in CANDIDATE_JUDGE_ENTRYPOINTS:
        func_obj = getattr(judge_service, name, None)
        if not callable(func_obj) or not accepts_db_problem_code(func_obj):
            continue
        try:
            result = func_obj(db, problem, code)
        except Exception:  # noqa: BLE001 - 判题异常不得影响接口，回退本地
            continue
        if isinstance(result, dict):
            return result

    if callable(getattr(judge_service, "judge_submission", None)):
        logger.debug(
            "judge_service 仅提供持久化入口 judge_submission，考试/挑战判分改用本机执行器（无副作用）"
        )
    return None


def local_judge(db: Session, problem: Problem, code: str) -> dict[str, Any]:
    """本地判题兜底：按测试用例在本机执行器上逐例比对（trimmed）。"""
    cases = list(
        db.scalars(
            select(TestCase).where(TestCase.problem_id == problem.id).order_by(TestCase.order_index)
        ).all()
    )
    if not cases:
        return {"passed_cases": 0, "total_cases": 0, "accepted": False}

    try:
        from app.sandbox.protocol import STATUS_SUCCESS, SandboxFile, SandboxRequest
        from app.sandbox.runner import get_runner, new_request_id

        runner = get_runner()
        passed = 0
        for case in cases:
            request = SandboxRequest(
                request_id=new_request_id(),
                files=[SandboxFile(path="main.py", content=code or "")],
                entry="main.py",
                stdin=case.input or "",
                timeout_ms=int(case.timeout_ms or problem.time_limit_ms or 3000),
                memory_limit_mb=int(problem.memory_limit_mb or 128),
            )
            response = runner.run(request)
            if response.status == STATUS_SUCCESS and normalize_output(response.stdout) == normalize_output(
                case.expected_output
            ):
                passed += 1
        return {"passed_cases": passed, "total_cases": len(cases), "accepted": passed == len(cases)}
    except Exception as exc:  # noqa: BLE001 - 判题异常不得影响接口
        logger.warning("本地判题失败 problem_id=%s: %s", problem.id, exc)
        return {"passed_cases": 0, "total_cases": len(cases), "accepted": False}


def grade_problem(db: Session, problem: Problem, answer: Any) -> dict[str, Any]:
    """对单题判分，返回 `{correct, score, expected, passed_cases, total_cases}`。"""
    if problem.problem_type in OBJECTIVE_TYPES:
        correct = check_objective(problem, answer)
        return {
            "correct": correct,
            "score": int(problem.score or 10) if correct else 0,
            "expected": problem.answer_json,
            "passed_cases": 1 if correct else 0,
            "total_cases": 1,
        }

    result = external_judge(db, problem, str(answer or "")) or local_judge(db, problem, str(answer or ""))
    total = int(result.get("total_cases", 0) or 0)
    passed = int(result.get("passed_cases", 0) or 0)
    accepted = bool(result.get("accepted", total > 0 and passed >= total))
    score = int(problem.score or 10) if accepted else (int(problem.score or 10) * passed // total if total else 0)
    return {
        "correct": accepted,
        "score": score,
        "expected": problem.reference_solution,
        "passed_cases": passed,
        "total_cases": total,
    }
