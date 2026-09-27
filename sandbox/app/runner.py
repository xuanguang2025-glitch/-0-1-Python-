"""执行器：把一次沙箱请求落盘、执行、收集输出并组装响应。

安全层级：
1. 静态源码检查（`security.py`）
2. 资源限额（Linux `resource.setrlimit` / Windows psutil 轮询 RSS）
3. 进程树超时 kill
4. 输出字节截断
5. 子进程内运行时守卫（`guard.py`，通过 `-c` 注入）
6. 可选网络命名空间隔离（Linux `unshare -n`，探测成功才启用）
"""

from __future__ import annotations

import difflib
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import security
from .config import Settings
from .guard import GuardViolation  # 仅用于类型/异常名比对（子进程内同名异常）
from .limits import (
    MemoryWatcher,
    build_preexec_fn,
    kill_process_tree,
    max_rss_kb,
    platform_capabilities,
    popen_kwargs,
)
from .logging import get_logger
from .protocol import (
    CaseResult,
    ErrorPayload,
    ExecutionRequest,
    ExecutionResponse,
    ExecutionStatus,
    new_request_id,
)

LOGGER = get_logger("sandbox.runner")

CHUNK_SIZE = 65536
RESERVED_PREFIX = "_plab_"
GUARD_MODULE_NAME = "_plab_guard.py"

BOOTSTRAP_TEMPLATE = """\
import os as _os
import sys as _sys
# 先导入 runpy（它内部会 import importlib），再装守卫，避免守卫误伤引导流程
import runpy as _runpy
_workdir = {workdir!r}
if _workdir not in _sys.path:
    _sys.path.insert(0, _workdir)
import _plab_guard as _guard
_guard.install(
    workdir=_workdir,
    import_mode={import_mode!r},
    allowed_imports={allowed_imports!r},
    blocked_imports={blocked_imports!r},
    allow_network={allow_network!r},
    recursion_limit={recursion_limit!r},
    output_limit_bytes={output_limit!r},
)
_entry = _sys.argv[1] if len(_sys.argv) > 1 else _os.path.join(_workdir, "main.py")
_sys.argv = [_entry]
_runpy.run_path(_entry, run_name="__main__")
"""


@dataclass
class RunOutcome:
    """单次进程执行结果。"""

    status: ExecutionStatus = "success"
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    truncated: bool = False
    time_ms: int = 0
    memory_kb: int = 0
    error: Optional[ErrorPayload] = None
    timed_out: bool = False


class _StreamPump(threading.Thread):
    """按字节预算读取子进程输出流的线程。

    超限时回调 `on_overflow`（用于 kill 进程树），并停止继续读取。
    """

    def __init__(self, stream: Any, cap: int, on_overflow: Any = None) -> None:
        super().__init__(daemon=True, name="plab-stream-pump")
        self.stream = stream
        self.sink = bytearray()
        self.cap = max(1, int(cap))
        self.on_overflow = on_overflow
        self.overflowed = False

    def run(self) -> None:
        """持续读取直到流结束、预算耗尽或流被关闭。"""
        try:
            while True:
                chunk = self.stream.read(CHUNK_SIZE)
                if not chunk:
                    break
                room = self.cap - len(self.sink)
                if room <= 0:
                    self._overflow()
                    break
                if len(chunk) > room:
                    self.sink.extend(chunk[:room])
                    self._overflow()
                    break
                self.sink.extend(chunk)
        except Exception:  # noqa: BLE001 - 管道关闭时正常结束
            pass
        finally:
            try:
                self.stream.close()
            except Exception:  # noqa: BLE001
                pass

    def _overflow(self) -> None:
        """标记超限并触发回调。"""
        self.overflowed = True
        if callable(self.on_overflow):
            try:
                self.on_overflow()
            except Exception:  # noqa: BLE001
                pass

    @property
    def data(self) -> bytes:
        """已读取的字节（最多 cap 字节）。"""
        return bytes(self.sink)


class SandboxRunner:
    """沙箱执行器（线程安全：每次执行独立临时工作目录）。"""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or Settings.from_env()
        self.capabilities = platform_capabilities()
        self.network_isolation = self._resolve_network_isolation()
        self.capabilities["network_isolation_mode"] = self.network_isolation
        self._guard_source = self._load_guard_source()
        os.makedirs(self.settings.workdir_root, exist_ok=True)

    # ------------------------------------------------------------------ 公共入口
    def execute(self, request: ExecutionRequest) -> ExecutionResponse:
        """执行一次请求（run / judge 两种模式）。"""
        request = request.normalized(self.settings)
        started = time.perf_counter()

        if request.language.lower() not in ("python", "python3", "py"):
            return self._fail(
                request, "BAD_REQUEST", f"不支持的语言：{request.language}", started
            )

        invalid = self._validate_limits(request)
        if invalid:
            return self._fail(request, "BAD_REQUEST", invalid, started)

        if self.settings.static_scan:
            scan = security.scan_files(request.files)
            if not scan.blocked and request.stdin:
                scan = security.scan_text_lines(request.stdin)
            if scan.blocked:
                return self._security_error(request, scan.as_message(), started)

        try:
            workdir, entry_abs = self._prepare_workdir(request)
        except (OSError, ValueError) as exc:
            return self._fail(request, "INTERNAL_ERROR", f"工作目录创建失败：{exc}", started)

        try:
            if request.mode == "judge" and request.test_cases:
                return self._run_judge(request, workdir, entry_abs, started)
            outcome = self._run_once(
                workdir=workdir,
                entry_abs=entry_abs,
                stdin_text=request.stdin,
                timeout_ms=request.timeout_ms or self.settings.default_timeout_ms,
                memory_mb=request.memory_limit_mb or self.settings.default_memory_mb,
                cpu_ms=request.cpu_limit_ms or self.settings.default_cpu_limit_ms,
                output_cap=request.max_output_bytes or self.settings.max_output_bytes,
                env_extra=request.env,
            )
            return self._to_response(request, outcome, started)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    # ------------------------------------------------------------------ 校验
    def _validate_limits(self, request: ExecutionRequest) -> str:
        """返回错误信息；通过校验返回空串。"""
        if len(request.files) > self.settings.max_files:
            return f"文件数量超过上限 {self.settings.max_files}"
        for file_spec in request.files:
            size = len(file_spec.content.encode("utf-8", "replace"))
            if size > self.settings.max_file_bytes:
                return f"文件 {file_spec.path} 超过 {self.settings.max_file_bytes} 字节上限"
        total = sum(len(f.content.encode("utf-8", "replace")) for f in request.files)
        if total > self.settings.max_code_bytes:
            return f"代码总量超过 {self.settings.max_code_bytes} 字节上限"
        if len(request.stdin.encode("utf-8", "replace")) > self.settings.max_stdin_bytes:
            return f"stdin 超过 {self.settings.max_stdin_bytes} 字节上限"
        if request.mode == "judge" and not request.test_cases:
            return "judge 模式需要至少 1 个测试用例"
        return ""

    def _safe_relative(self, raw_path: str) -> str:
        """校验并归一化相对路径，阻断路径遍历。"""
        candidate = (raw_path or "").strip().replace("\\", "/")
        if not candidate:
            raise ValueError("空文件路径")
        if candidate.startswith("/") or (len(candidate) > 1 and candidate[1] == ":"):
            raise ValueError(f"禁止绝对路径：{raw_path}")
        parts = [part for part in candidate.split("/") if part not in ("", ".")]
        if any(part == ".." for part in parts):
            raise ValueError(f"禁止路径遍历：{raw_path}")
        if parts and parts[0].startswith(RESERVED_PREFIX):
            raise ValueError(f"保留文件名：{raw_path}")
        return "/".join(parts)

    # ------------------------------------------------------------------ 工作目录
    def _prepare_workdir(self, request: ExecutionRequest) -> Tuple[str, str]:
        """创建临时工作目录、写入源码与守卫模块，返回 (workdir, 入口绝对路径)。"""
        workdir = tempfile.mkdtemp(prefix="plab_", dir=self.settings.workdir_root)
        written: Dict[str, str] = {}
        for file_spec in request.files:
            relative = self._safe_relative(file_spec.path)
            absolute = os.path.join(workdir, relative)
            os.makedirs(os.path.dirname(absolute) or workdir, exist_ok=True)
            with open(absolute, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(file_spec.content)
            written[relative] = absolute

        guard_path = os.path.join(workdir, GUARD_MODULE_NAME)
        with open(guard_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(self._guard_source)

        entry_relative = self._safe_relative(request.entry or "main.py")
        entry_abs = written.get(entry_relative)
        if entry_abs is None:
            entry_abs = os.path.join(workdir, entry_relative)
            if not os.path.exists(entry_abs):
                # 入口缺失时退化为第一个文件，避免无谓失败
                entry_abs = next(iter(written.values()), entry_abs)
        if not os.path.exists(entry_abs):
            raise ValueError(f"入口文件不存在：{entry_relative}")
        return workdir, entry_abs

    # ------------------------------------------------------------------ 单次执行
    def _run_once(
        self,
        *,
        workdir: str,
        entry_abs: str,
        stdin_text: str,
        timeout_ms: int,
        memory_mb: int,
        cpu_ms: int,
        output_cap: int,
        env_extra: Dict[str, str],
    ) -> RunOutcome:
        """启动子进程执行入口文件，收集 stdout/stderr 与资源用量。"""
        bootstrap = BOOTSTRAP_TEMPLATE.format(
            workdir=workdir,
            import_mode=self.settings.import_mode,
            allowed_imports=list(self.settings.allowed_imports),
            blocked_imports=list(self.settings.blocked_imports),
            allow_network=bool(self.settings.allow_network),
            recursion_limit=self.settings.recursion_limit,
            output_limit=output_cap,
        )
        command = [self.settings.python_executable, "-I", "-B", "-c", bootstrap, entry_abs]
        if self.network_isolation == "unshare":
            command = ["unshare", "-n", "--"] + command

        env = self._build_env(workdir, env_extra)
        outcome = RunOutcome()
        timeout_seconds = max(0.2, timeout_ms / 1000.0)
        started = time.perf_counter()

        try:
            process = subprocess.Popen(
                command,
                cwd=workdir,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=build_preexec_fn(memory_mb, cpu_ms),
                **popen_kwargs(),
            )
        except OSError as exc:
            outcome.status = "internal_error"
            outcome.error = ErrorPayload(type="OSError", message=f"进程启动失败：{exc}")
            outcome.time_ms = int((time.perf_counter() - started) * 1000)
            return outcome

        watcher = MemoryWatcher(process, memory_mb)
        watcher.start()

        stdout_pump = _StreamPump(
            stream=process.stdout, cap=output_cap, on_overflow=lambda: kill_process_tree(process)
        )
        stderr_pump = _StreamPump(
            stream=process.stderr,
            cap=max(4096, output_cap // 2),
            on_overflow=lambda: kill_process_tree(process),
        )
        stdout_pump.start()
        stderr_pump.start()

        self._feed_stdin(process, stdin_text)

        deadline = time.monotonic() + timeout_seconds
        timed_out = False
        while True:
            if process.poll() is not None:
                break
            if watcher.exceeded:
                break
            if stdout_pump.overflowed or stderr_pump.overflowed:
                kill_process_tree(process)
                break
            if time.monotonic() >= deadline:
                timed_out = True
                kill_process_tree(process)
                break
            time.sleep(0.02)

        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            kill_process_tree(process)
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass

        stdout_pump.join(timeout=2)
        stderr_pump.join(timeout=2)
        watcher.stop()
        watcher.join(timeout=1)

        outcome.time_ms = int((time.perf_counter() - started) * 1000)
        outcome.exit_code = process.returncode
        outcome.stdout = stdout_pump.data.decode("utf-8", "replace")
        outcome.stderr = stderr_pump.data.decode("utf-8", "replace")
        outcome.timed_out = timed_out
        outcome.truncated = bool(
            stdout_pump.overflowed or len(stdout_pump.data) >= output_cap
        )
        outcome.memory_kb = max(watcher.peak_kb, max_rss_kb())
        outcome.status = self._classify(
            outcome, watcher.exceeded, stdout_pump.overflowed or stderr_pump.overflowed, output_cap
        )
        if outcome.status != "success":
            outcome.error = self._parse_error(outcome.stderr) or ErrorPayload(
                type=outcome.status,
                message={
                    "timeout": f"执行超时（>{timeout_ms} ms）",
                    "memory_exceeded": f"内存超限（>{memory_mb} MB）",
                    "output_exceeded": f"输出超限（>{output_cap} 字节）",
                }.get(outcome.status, "执行失败"),
            )
        return outcome

    def _feed_stdin(self, process: Any, stdin_text: str) -> None:
        """写入标准输入并关闭管道（失败时忽略）。"""
        try:
            if process.stdin is None:
                return
            if stdin_text:
                process.stdin.write(stdin_text.encode("utf-8", "replace"))
            process.stdin.close()
        except Exception:  # noqa: BLE001 - 进程提前退出
            pass

    def _classify(
        self, outcome: RunOutcome, memory_exceeded: bool, output_overflow: bool, output_cap: int
    ) -> ExecutionStatus:
        """根据执行事实判定状态。"""
        if outcome.timed_out:
            return "timeout"
        if memory_exceeded:
            return "memory_exceeded"
        if output_overflow:
            return "output_exceeded"
        if outcome.exit_code not in (0, None):
            stderr = outcome.stderr
            if "GuardViolation" in stderr or "[sandbox]" in stderr and "禁用" in stderr:
                return "security_error"
            for token in ("SyntaxError", "IndentationError", "TabError"):
                if token in stderr:
                    return "compile_error"
            return "runtime_error"
        if len(outcome.stdout.encode("utf-8", "replace")) >= output_cap:
            return "output_exceeded"
        return "success"

    def _parse_error(self, stderr: str) -> Optional[ErrorPayload]:
        """从 traceback 文本中提取错误类型、消息与行号。"""
        if not stderr:
            return None
        lines = [line for line in stderr.strip().splitlines() if line.strip()]
        if not lines:
            return None
        message = lines[-1]
        error_type = message.split(":", 1)[0].strip() or "Error"
        detail = message.split(":", 1)[1].strip() if ":" in message else ""
        line_number: Optional[int] = None
        for candidate in reversed(lines):
            marker = 'line '
            if marker in candidate and candidate.lstrip().startswith("File "):
                try:
                    line_number = int(candidate.split(marker, 1)[1].split(",", 1)[0].strip())
                    break
                except (ValueError, IndexError):
                    continue
        return ErrorPayload(
            type=error_type, message=detail or message, traceback=stderr, line=line_number
        )

    def _build_env(self, workdir: str, extra: Dict[str, str]) -> Dict[str, str]:
        """构造最小化环境变量（白名单注入，避免泄漏宿主密钥）。"""
        env: Dict[str, str] = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": workdir,
            "TEMP": workdir,
            "TMP": workdir,
            "TMPDIR": workdir,
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUNBUFFERED": "1",
            "PYTHONHASHSEED": "0",
            "PLAB_WORKDIR": workdir,
        }
        for key in ("SYSTEMROOT", "SystemDrive", "PATHEXT", "COMSPEC", "WINDIR"):
            value = os.environ.get(key)
            if value:
                env[key] = value
        for key, value in extra.items():
            if key.startswith("PLAB_") and isinstance(value, str):
                env[key] = value[:1024]
        return env

    # ------------------------------------------------------------------ judge
    def _run_judge(
        self, request: ExecutionRequest, workdir: str, entry_abs: str, started: float
    ) -> ExecutionResponse:
        """按用例逐一执行并比对输出。"""
        cases = request.test_cases
        budget_ms = min(
            self.settings.judge_total_budget_ms,
            int(request.timeout_ms or self.settings.default_timeout_ms) * len(cases),
        )
        per_case_timeout = max(
            self.settings.min_timeout_ms, min(request.timeout_ms or 0 or budget_ms,
                                              budget_ms // max(1, len(cases)))
        )
        results: List[CaseResult] = []
        total_time = 0
        peak_memory = 0
        for case in cases:
            outcome = self._run_once(
                workdir=workdir,
                entry_abs=entry_abs,
                stdin_text=case.input,
                timeout_ms=per_case_timeout,
                memory_mb=request.memory_limit_mb or self.settings.default_memory_mb,
                cpu_ms=min(request.cpu_limit_ms or per_case_timeout, per_case_timeout),
                output_cap=request.max_output_bytes or self.settings.max_output_bytes,
                env_extra=request.env,
            )
            total_time += outcome.time_ms
            peak_memory = max(peak_memory, outcome.memory_kb)
            passed = outcome.status == "success" and self._compare(
                outcome.stdout, case.expected, case.comparison
            )
            results.append(
                CaseResult(
                    test_case_id=case.id,
                    passed=passed,
                    actual=outcome.stdout,
                    expected=case.expected,
                    time_ms=outcome.time_ms,
                    memory_kb=outcome.memory_kb,
                    status=outcome.status,
                    diff=None if passed else self._diff(outcome.stdout, case.expected),
                )
            )

        passed_cases = sum(1 for item in results if item.passed)
        failed_statuses = [item.status for item in results if item.status != "success"]
        status: ExecutionStatus = "success" if passed_cases == len(results) else "wrong_answer"
        if failed_statuses:
            status = self._dominant_status(failed_statuses)  # type: ignore[assignment]
        response = ExecutionResponse(
            request_id=request.request_id,
            status=status,
            exit_code=0 if passed_cases == len(results) else 1,
            stdout=results[-1].actual if results else "",
            stderr="",
            truncated=any(item.actual.endswith("\ufffd") for item in results),
            time_ms=total_time,
            memory_kb=peak_memory,
            results=results,
            passed_cases=passed_cases,
            total_cases=len(results),
            error=None
            if passed_cases == len(results)
            else ErrorPayload(type=str(status), message=f"{passed_cases}/{len(results)} 用例通过"),
            runner="sandbox",
            degraded=self.settings.security_level != "hardened",
            security_level=self.settings.security_level,
        )
        LOGGER.info(
            "judge finished",
            extra={"request_id": request.request_id, "status": status,
                   "duration_ms": int((time.perf_counter() - started) * 1000)},
        )
        return response.sync_aliases()

    @staticmethod
    def _dominant_status(statuses: List[str]) -> str:
        """多用例失败时取优先级最高的状态（timeout > security > memory > 其他）。"""
        priority = [
            "timeout",
            "security_error",
            "memory_exceeded",
            "output_exceeded",
            "compile_error",
            "runtime_error",
        ]
        for candidate in priority:
            if candidate in statuses:
                return candidate
        return "runtime_error"

    @staticmethod
    def _compare(actual: str, expected: str, comparison: str) -> bool:
        """按比较模式比对输出。"""
        if comparison == "exact":
            return actual == expected
        if comparison == "float":
            try:
                return abs(float(actual.strip()) - float(expected.strip())) <= 1e-6
            except (TypeError, ValueError):
                return False
        if comparison == "custom":
            return actual.strip() == expected.strip()
        return actual.strip() == expected.strip()

    @staticmethod
    def _diff(actual: str, expected: str) -> str:
        """生成可读差异（unified diff，最多 40 行）。"""
        diff = difflib.unified_diff(
            expected.splitlines(), actual.splitlines(),
            fromfile="expected", tofile="actual", lineterm="", n=1,
        )
        return "\n".join(list(diff)[:40])

    # ------------------------------------------------------------------ 响应组装
    def _to_response(
        self, request: ExecutionRequest, outcome: RunOutcome, started: float
    ) -> ExecutionResponse:
        """把 RunOutcome 转为协议响应。"""
        response = ExecutionResponse(
            request_id=request.request_id,
            status=outcome.status,
            exit_code=outcome.exit_code,
            stdout=outcome.stdout,
            stderr=outcome.stderr,
            truncated=outcome.truncated,
            time_ms=outcome.time_ms,
            memory_kb=outcome.memory_kb,
            results=[],
            passed_cases=0,
            total_cases=0,
            error=outcome.error,
            runner="sandbox",
            degraded=self.settings.security_level != "hardened",
            security_level=self.settings.security_level,
        )
        LOGGER.info(
            "execution finished",
            extra={
                "request_id": request.request_id,
                "mode": request.mode,
                "status": outcome.status,
                "duration_ms": int((time.perf_counter() - started) * 1000),
            },
        )
        return response.sync_aliases()

    def _security_error(
        self, request: ExecutionRequest, message: str, started: float
    ) -> ExecutionResponse:
        """静态检查拦截响应。"""
        LOGGER.warning("static scan blocked", extra={"request_id": request.request_id})
        return ExecutionResponse(
            request_id=request.request_id,
            status="security_error",
            exit_code=None,
            stdout="",
            stderr=message,
            time_ms=int((time.perf_counter() - started) * 1000),
            error=ErrorPayload(type="SecurityViolation", message=message),
            runner="sandbox",
            degraded=self.settings.security_level != "hardened",
            security_level=self.settings.security_level,
        ).sync_aliases()

    def _fail(
        self, request: ExecutionRequest, error_type: str, message: str, started: float
    ) -> ExecutionResponse:
        """参数/内部错误响应。"""
        status: ExecutionStatus = "internal_error" if error_type == "INTERNAL_ERROR" else "runtime_error"
        return ExecutionResponse(
            request_id=request.request_id or new_request_id(),
            status=status,
            exit_code=None,
            stdout="",
            stderr=message,
            time_ms=int((time.perf_counter() - started) * 1000),
            error=ErrorPayload(type=error_type, message=message),
            runner="sandbox",
            degraded=self.settings.security_level != "hardened",
            security_level=self.settings.security_level,
        ).sync_aliases()

    # ------------------------------------------------------------------ 平台探测
    def _resolve_network_isolation(self) -> str:
        """探测 `unshare -n` 是否可用（成功才启用网络命名空间隔离）。"""
        if os.name != "posix" or not shutil.which("unshare"):
            return "none"
        try:
            probe = subprocess.run(
                ["unshare", "-n", "--", sys.executable, "-c", "print('ok')"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=False,
            )
        except Exception:  # noqa: BLE001
            return "none"
        return "unshare" if probe.returncode == 0 else "none"

    def _load_guard_source(self) -> str:
        """读取守卫模块源码，用于写入每个工作目录。"""
        guard_path = Path(__file__).with_name("guard.py")
        try:
            return guard_path.read_text(encoding="utf-8")
        except OSError:
            return "# guard source unavailable\n"

    def health_snapshot(self) -> Dict[str, Any]:
        """返回 /health 所需的运行时快照。"""
        return {
            "security_level": self.settings.security_level,
            "capabilities": dict(self.capabilities),
            "limits": self.settings.limits_snapshot(),
            "workdir_root": self.settings.workdir_root,
            "python_executable": self.settings.python_executable,
        }


__all__ = ["SandboxRunner", "RunOutcome", "GuardViolation"]
