"""执行结果的数据模型、输出比对与状态归一化（`sandbox_client` 的纯数据层）。

该模块不依赖任何具体执行后端，仅负责：
- 定义统一的 `ExecutionResult` / `CaseResult`；
- 实现 exact / trimmed / float / custom 四种输出比对；
- 把本地 `LocalRunner` 响应与远程沙箱响应归一化为统一结果；
- 把 sandbox 原始状态归一化为 `judge_service` 使用的状态集合。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from app.sandbox.protocol import (
    STATUS_INTERNAL,
    STATUS_MEMORY,
    STATUS_REJECTED,
    STATUS_SECURITY,
    STATUS_SUCCESS,
    STATUS_TIMEOUT,
    SandboxResponse,
)
from app.utils.text import normalize_output

#: 归一化后的执行状态（judge_service 依赖该取值集合）
STATUS_WRONG_ANSWER = "wrong_answer"
STATUS_OUTPUT_EXCEEDED = "output_exceeded"
STATUS_COMPILE = "compile_error"
STATUS_RUNTIME = "runtime_error"


@dataclass(slots=True)
class CaseResult:
    """单个用例的执行结果。"""

    test_case_id: str | None = None
    passed: bool = False
    actual: str = ""
    expected: str = ""
    stderr: str = ""
    time_ms: int = 0
    memory_kb: int = 0
    status: str = STATUS_SUCCESS
    diff: str | None = None
    message: str | None = None


@dataclass(slots=True)
class ExecutionResult:
    """统一的执行结果（run 与 judge 共用）。"""

    request_id: str
    status: str = STATUS_SUCCESS
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    truncated: bool = False
    time_ms: int = 0
    memory_kb: int = 0
    error: str | None = None
    error_type: str | None = None
    runner: str = "local"
    degraded: bool = True
    results: list[CaseResult] = field(default_factory=list)
    passed_cases: int = 0
    total_cases: int = 0

    @property
    def ok(self) -> bool:
        """是否执行成功（不含输出比对）。"""
        return self.status == STATUS_SUCCESS

    @property
    def all_passed(self) -> bool:
        """是否所有用例通过（仅 judge 有意义）。"""
        return bool(self.results) and self.total_cases > 0 and self.passed_cases == self.total_cases


def compare_output(actual: str, expected: str, mode: str = "trimmed", tolerance: float = 1e-6) -> bool:
    """按对比模式判定两段输出是否一致。

    Args:
        actual: 程序实际输出。
        expected: 期望输出。
        mode: `exact` / `trimmed`（默认）/ `float` / `custom`。
        tolerance: `float` 模式的绝对/相对容差。

    Returns:
        是否一致。
    """
    if mode == "exact":
        return (actual or "") == (expected or "")
    if mode == "float":
        return _compare_float(actual, expected, tolerance)
    # trimmed 与 custom 均按「统一换行 + 去行尾空白 + 去首尾空行」比较
    return normalize_output(actual) == normalize_output(expected)


def _compare_float(actual: str, expected: str, tolerance: float) -> bool:
    """按空白分词后逐个浮点比较（非数字时退化为 trimmed 比较）。"""
    left = normalize_output(actual).split()
    right = normalize_output(expected).split()
    if len(left) != len(right):
        return False
    for a_token, e_token in zip(left, right):
        try:
            a_val, e_val = float(a_token), float(e_token)
        except ValueError:
            return normalize_output(actual) == normalize_output(expected)
        if a_val != e_val and abs(a_val - e_val) > tolerance * max(1.0, abs(e_val)):
            return False
    return True


def _looks_like_syntax_error(stderr: str) -> bool:
    """根据 stderr 判断是否为编译期错误（语法 / 缩进 / 制表符混用）。"""
    text = stderr or ""
    return any(marker in text for marker in ("SyntaxError", "IndentationError", "TabError"))


def normalize_status(raw: str, stderr: str = "") -> str:
    """把 sandbox 原始状态归一化为 judge_service 使用的状态集合。"""
    value = (raw or "").lower()
    if value in ("timeout", "timed_out"):
        return STATUS_TIMEOUT
    if value in ("memory_exceeded", "memory_limit_exceeded"):
        return STATUS_MEMORY
    if value == "security_error":
        return STATUS_SECURITY
    if value == "rejected":
        return STATUS_REJECTED
    if value == "output_exceeded":
        return STATUS_OUTPUT_EXCEEDED
    if value == STATUS_WRONG_ANSWER:
        return STATUS_WRONG_ANSWER
    if value == "internal_error":
        return STATUS_INTERNAL
    if value == STATUS_COMPILE:
        return STATUS_COMPILE
    if value in ("error", STATUS_RUNTIME):
        return STATUS_COMPILE if _looks_like_syntax_error(stderr) else STATUS_RUNTIME
    return STATUS_SUCCESS


def from_sandbox_response(response: SandboxResponse, *, runner: str) -> ExecutionResult:
    """把 `LocalRunner` 的响应转换为统一结果。"""
    status = normalize_status(response.status, response.stderr)
    return ExecutionResult(
        request_id=response.request_id,
        status=status,
        exit_code=int(response.exit_code or 0),
        stdout=response.stdout or "",
        stderr=response.stderr or "",
        truncated=bool(response.truncated),
        time_ms=int(response.time_ms or 0),
        memory_kb=int(response.memory_kb or 0),
        error=response.error,
        error_type=response.error_type,
        runner=runner,
        degraded=True,
    )


def from_remote_payload(data: Mapping[str, Any], *, mode: str) -> ExecutionResult:
    """把远程沙箱响应转换为统一结果（含逐用例）。"""
    status = normalize_status(str(data.get("status") or STATUS_SUCCESS), str(data.get("stderr") or ""))
    if data.get("timed_out") and status == STATUS_SUCCESS:
        status = STATUS_TIMEOUT
    raw_results = data.get("results") or []
    case_results: list[CaseResult] = []
    for item in raw_results:
        item_status = normalize_status(
            str(item.get("status") or STATUS_SUCCESS), str(item.get("stderr") or item.get("error") or "")
        )
        case_results.append(
            CaseResult(
                test_case_id=item.get("test_case_id") or item.get("id"),
                passed=bool(item.get("passed")),
                actual=str(item.get("actual") or ""),
                expected=str(item.get("expected") or ""),
                stderr=str(item.get("stderr") or ""),
                time_ms=int(item.get("time_ms") or 0),
                memory_kb=int(item.get("memory_kb") or 0),
                status=item_status,
                diff=item.get("diff"),
                message=item.get("message"),
            )
        )
    passed_cases = int(data.get("passed_cases") or sum(1 for item in case_results if item.passed))
    total_cases = int(data.get("total_cases") or len(case_results))
    if mode == "judge" and case_results and status == STATUS_SUCCESS and passed_cases < total_cases:
        status = STATUS_WRONG_ANSWER
    error = data.get("error")
    if isinstance(error, Mapping):
        error = error.get("message") or str(error)
    return ExecutionResult(
        request_id=str(data.get("request_id") or ""),
        status=status,
        exit_code=int(data.get("exit_code") or 0),
        stdout=str(data.get("stdout") or ""),
        stderr=str(data.get("stderr") or ""),
        truncated=bool(data.get("truncated")),
        time_ms=int(data.get("time_ms") or data.get("duration_ms") or 0),
        memory_kb=int(data.get("memory_kb") or 0),
        error=error,
        error_type=data.get("error_type"),
        runner="sandbox",
        degraded=bool(data.get("degraded", False)),
        results=case_results,
        passed_cases=passed_cases,
        total_cases=total_cases,
    )


def stub_result(request_id: str, runner: str) -> ExecutionResult:
    """stub 模式的固定运行结果。"""
    return ExecutionResult(
        request_id=request_id,
        status=STATUS_SUCCESS,
        exit_code=0,
        stdout="",
        stderr="",
        runner=runner,
        degraded=True,
    )


def case_error_message(status: str, response: ExecutionResult, index: int) -> str | None:
    """为致命错误生成可读信息（供可见用例展示）。"""
    if status == STATUS_SUCCESS:
        return None
    if status == STATUS_TIMEOUT:
        return "执行超时"
    if status == STATUS_MEMORY:
        return "内存超限"
    if status == STATUS_SECURITY:
        return response.error or "代码包含禁用语法"
    if status == STATUS_OUTPUT_EXCEEDED:
        return "输出超出上限被截断"
    if status == STATUS_COMPILE:
        return "编译错误（语法/缩进）"
    if status == STATUS_RUNTIME:
        return response.error or "运行时错误"
    return response.error or "执行失败"


__all__ = [
    "CaseResult",
    "ExecutionResult",
    "STATUS_COMPILE",
    "STATUS_OUTPUT_EXCEEDED",
    "STATUS_RUNTIME",
    "STATUS_WRONG_ANSWER",
    "case_error_message",
    "compare_output",
    "from_remote_payload",
    "from_sandbox_response",
    "normalize_status",
    "stub_result",
]
