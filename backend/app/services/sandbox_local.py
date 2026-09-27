"""本机执行后端（`LocalRunner` 适配层）。

Windows 无 `rlimit`，本机执行为「超时 kill + 输出截断 + 静态扫描」的降级模式，
结果始终 `degraded=True`。

多文件跨文件 import 的兼容：Python 3.11+ 的 `python -I` 隐含 `-P`（safe_path），
脚本目录不会进入 `sys.path`。因此本后端会在用户文件之外注入一个引导文件
`__plab_boot__.py`，显式把工作目录加入 `sys.path` 后再用 `runpy` 执行入口文件。
"""

from __future__ import annotations

from typing import Any, Mapping

from app.sandbox.protocol import (
    STATUS_INTERNAL,
    STATUS_MEMORY,
    STATUS_REJECTED,
    STATUS_SECURITY,
    STATUS_SUCCESS,
    STATUS_TIMEOUT,
    SandboxFile,
    SandboxRequest,
)
from app.sandbox.runner import LocalRunner
from app.services.sandbox_result import (
    STATUS_COMPILE,
    STATUS_RUNTIME,
    CaseResult,
    ExecutionResult,
    case_error_message,
    compare_output,
    from_sandbox_response,
)

#: 本机多文件执行的引导文件名。
LOCAL_BOOTSTRAP_NAME: str = "__plab_boot__.py"

#: 遇到即短路（不再执行剩余用例）的致命状态。
_FATAL_STATUSES: frozenset[str] = frozenset(
    {
        STATUS_TIMEOUT,
        STATUS_MEMORY,
        STATUS_SECURITY,
        STATUS_REJECTED,
        STATUS_INTERNAL,
        STATUS_COMPILE,
        STATUS_RUNTIME,
    }
)


def clamp_timeout(value: int | None, default: int) -> int:
    """超时收敛到 [1000, 10000] ms。"""
    return max(1000, min(10_000, int(value or default)))


def clamp_memory(value: int | None, default: int) -> int:
    """内存收敛到 [32, 512] MB。"""
    return max(32, min(512, int(value or default)))


def bootstrap_code(entry: str) -> str:
    """生成本机执行的引导代码（注入 sys.path 后用 runpy 跑入口文件）。"""
    safe_entry = entry.replace("\\", "/")
    return (
        "import os, sys\n"
        "sys.path.insert(0, os.getcwd())\n"
        "import runpy\n"
        f"runpy.run_path(os.path.join(os.getcwd(), {safe_entry!r}), run_name='__main__')\n"
    )


class LocalBackend:
    """本机执行后端：单文件运行与逐用例判题。"""

    def __init__(self, *, timeout_ms: int, memory_mb: int, max_output_bytes: int, request_id_prefix: str = "run") -> None:
        """保存默认限额并创建 `LocalRunner`。"""
        self._runner = LocalRunner()
        self._default_timeout_ms = int(timeout_ms)
        self._default_memory_mb = int(memory_mb)
        self._max_output_bytes = int(max_output_bytes)
        self._prefix = request_id_prefix

    # ------------------------------------------------------------------ 执行
    def run(
        self, files: dict[str, str], entry: str, stdin: str, timeout_ms: int | None, memory_mb: int | None
    ) -> ExecutionResult:
        """单文件 / 多文件运行一次（注入引导文件保证跨文件 import 可用）。"""
        wrapped = dict(files)
        wrapped[LOCAL_BOOTSTRAP_NAME] = bootstrap_code(entry)
        request = SandboxRequest(
            request_id=self._new_request_id(),
            files=[SandboxFile(path=path, content=content) for path, content in wrapped.items()],
            entry=LOCAL_BOOTSTRAP_NAME,
            stdin=stdin or "",
            timeout_ms=clamp_timeout(timeout_ms, self._default_timeout_ms),
            memory_limit_mb=clamp_memory(memory_mb, self._default_memory_mb),
            allow_network=False,
        )
        response = self._runner.run(request)
        return from_sandbox_response(response, runner="local")

    def judge(
        self,
        files: dict[str, str],
        cases: list[dict[str, Any]],
        entry: str,
        timeout_ms: int | None,
        memory_mb: int | None,
    ) -> ExecutionResult:
        """逐用例判题；遇到致命错误则短路，避免浪费时间。"""
        overall = STATUS_SUCCESS
        results: list[CaseResult] = []
        total = len(cases)
        passed_count = 0
        max_time = 0
        max_memory = 0
        request_id = self._new_request_id()

        for index, case in enumerate(cases):
            case_timeout = int(case.get("timeout_ms") or timeout_ms or self._default_timeout_ms)
            response = self.run(files, entry, str(case.get("input") or ""), case_timeout, memory_mb)
            case_status = response.status
            actual = response.stdout or ""
            passed = False
            if case_status == STATUS_SUCCESS:
                passed = compare_output(
                    actual,
                    str(case.get("expected") or ""),
                    str(case.get("comparison") or "trimmed"),
                    float(case.get("tolerance") or 1e-6),
                )
            diff = None
            if case_status == STATUS_SUCCESS and not passed:
                from app.utils.diff import unified_diff_text

                diff = unified_diff_text(
                    str(case.get("expected") or ""), actual, left_label="expected", right_label="actual"
                )

            results.append(
                CaseResult(
                    test_case_id=case.get("id"),
                    passed=passed,
                    actual=actual,
                    expected=str(case.get("expected") or ""),
                    stderr=response.stderr or "",
                    time_ms=int(response.time_ms or 0),
                    memory_kb=int(response.memory_kb or 0),
                    status=case_status,
                    diff=diff,
                    message=case_error_message(case_status, response, index),
                )
            )
            if passed:
                passed_count += 1
            max_time = max(max_time, int(response.time_ms or 0))
            max_memory = max(max_memory, int(response.memory_kb or 0))

            if case_status in _FATAL_STATUSES:
                overall = case_status
                # 短路：剩余用例标记为未执行
                for skipped in cases[index + 1 :]:
                    results.append(
                        CaseResult(
                            test_case_id=skipped.get("id"),
                            passed=False,
                            expected=str(skipped.get("expected") or ""),
                            status="skipped",
                            message="未执行（前序用例已失败）",
                        )
                    )
                break

        return ExecutionResult(
            request_id=request_id,
            status=overall,
            stdout=results[0].actual if results else "",
            stderr=results[0].stderr if results else "",
            time_ms=max_time,
            memory_kb=max_memory,
            runner="local",
            degraded=True,
            results=results,
            passed_cases=passed_count,
            total_cases=total,
        )

    # ------------------------------------------------------------------ 工具
    def _new_request_id(self) -> str:
        """生成一次执行请求 id（用于日志串联）。"""
        import uuid

        return f"{self._prefix}-{uuid.uuid4().hex[:16]}"


__all__ = [
    "LOCAL_BOOTSTRAP_NAME",
    "LocalBackend",
    "bootstrap_code",
    "clamp_memory",
    "clamp_timeout",
]
