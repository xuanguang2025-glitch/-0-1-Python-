"""代码执行器：远程沙箱 ↔ 本机 LocalRunner 自动降级。

- `SANDBOX_MODE=remote|auto`：优先调用远程沙箱服务（HTTP JSON 协议）；
- 远程不可用时（auto 模式）自动降级为 `LocalRunner`，响应中 `degraded=True`；
- LocalRunner 用「子进程 + 超时 kill + 输出截断 + psutil 轮询 RSS」在本机安全执行，
  适配 Windows（无 `resource.setrlimit`）。
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Mapping

from app.core.config import get_settings
from app.sandbox.ast_guard import GuardViolation, check_files
from app.sandbox.protocol import (
    FORBIDDEN_PATTERNS,
    LOCAL_BOOTSTRAP_NAME,
    MAX_OUTPUT_BYTES,
    STATUS_ERROR,
    STATUS_INTERNAL,
    STATUS_MEMORY,
    STATUS_REJECTED,
    STATUS_SECURITY,
    STATUS_SUCCESS,
    STATUS_TIMEOUT,
    SandboxRequest,
    SandboxResponse,
)
from app.utils.files import cleanup_dir, make_temp_dir, write_files

logger = logging.getLogger("pythonlab.runner")


def scan_source(files: Mapping[str, str], *, skip_paths: frozenset[str] | set[str] | None = None) -> GuardViolation | None:
    """扫描源码中的危险构造，命中返回 `GuardViolation`，否则返回 None。

    主判定是 **AST 白名单**（`app/sandbox/ast_guard.py`）：字符串黑名单在 Python 上
    必然可绕过（QA 实测 `__import__("os")`、`getattr(os, "system")` 均可逃逸），
    因此这里再叠加一层历史黑名单只作为补充防线。

    Args:
        files: `{相对路径: 源码}`。
        skip_paths: 跳过校验的文件名。**只允许**系统生成的引导文件
            `__plab_boot__.py`（内容由 `sandbox_local.bootstrap_code()` 产生且
            每次覆盖）。保留名（如 `_plab_guard.py`）曾被整体跳过，形成免检入口，
            现在必须照常校验；提交侧由 schema / 路径校验层直接拒绝（HTTP 400）。
    """
    skip = set(skip_paths or ())
    violation = check_files(files, skip_paths=skip)
    if violation is not None:
        return violation

    # 第二层：历史字符串黑名单（保留以覆盖 AST 之外的形态，如文档字符串里的痕迹）
    for path, content in files.items():
        name = str(path).replace("\\", "/").split("/")[-1]
        if path in skip or name in skip:
            continue
        for pattern in FORBIDDEN_PATTERNS:
            if pattern in (content or ""):
                return GuardViolation(
                    "forbidden_pattern", f"源码包含被禁止的内容：{pattern}", 0, str(path)
                )
    return None


def _guard_response(
    request: SandboxRequest, violation: GuardViolation, *, runner_name: str, degraded: bool
) -> SandboxResponse:
    """把 AST 违规转成执行响应。

    两类违规要区别对待：

    - **安全类**（`dangerous_*` / `import_*` / `open_*` / `path_literal` /
      `shell_injection` / `dunder_*` / `forbidden_pattern`）→ `security_error`，
      绝不执行；
    - **语法类**（`syntax_error`）→ 同样是「**不执行**」，但状态表达为
      `error` + `SyntaxError`（由 `sandbox_result.normalize_status` 归一化为
      `compile_error`）。因为对学习者来说「代码写错了」是判题结论（CE），
      不是安全事件；若报成 `security_error` 会误导用户，也破坏判题链路语义。
    """
    if violation.rule == "syntax_error":
        return SandboxResponse(
            request_id=request.request_id,
            status=STATUS_ERROR,
            exit_code=1,
            stdout="",
            stderr=f"SyntaxError: {violation.message}",
            error=violation.describe(),
            error_type="SyntaxError",
            runner=runner_name,
            degraded=degraded,
        )
    return SandboxResponse(
        request_id=request.request_id,
        status=STATUS_SECURITY,
        exit_code=-1,
        stdout="",
        stderr=violation.describe(),
        error=violation.describe(),
        error_type="SecurityError",
        runner=runner_name,
        degraded=degraded,
    )


class LocalRunner:
    """本机执行器（降级实现，功能不中断）。"""

    name = "local"

    def __init__(self, python_executable: str | None = None) -> None:
        self._python = python_executable or sys.executable

    def run(self, request: SandboxRequest) -> SandboxResponse:
        """在本机子进程中执行入口文件并返回结果。"""
        files = {item.path: item.content for item in request.files}
        # 只跳过系统生成的引导文件；保留名（`_plab_guard.py` 等）照常 AST 校验，
        # 否则攻击者可用保留名作入口完全绕过安全门（QA 实测 P0）。
        hit = scan_source(files, skip_paths={LOCAL_BOOTSTRAP_NAME})
        if hit is not None:
            logger.warning("源码安全校验拒绝 request_id=%s rule=%s", request.request_id, hit.rule)
            return _guard_response(request, hit, runner_name=self.name, degraded=True)

        workdir = make_temp_dir("plab_run_")
        try:
            # allow_reserved：引导文件 `__plab_boot__.py` 由 `sandbox_local` 注入，
            # 且上方 AST 校验只对它免检（其余保留名照常校验），此处必须放行写入。
            write_files(workdir, files, allow_reserved=True)
            entry = workdir / request.entry
            if not entry.exists():
                return SandboxResponse(
                    request_id=request.request_id,
                    status=STATUS_REJECTED,
                    error=f"入口文件不存在：{request.entry}",
                    error_type="FileNotFoundError",
                    runner=self.name,
                    degraded=True,
                )
            return self._execute(entry, workdir, request)
        except Exception as exc:  # noqa: BLE001 - 执行器不得把异常抛给调用方
            logger.exception("本地执行失败: %s", exc)
            return SandboxResponse(
                request_id=request.request_id,
                status=STATUS_INTERNAL,
                error=str(exc),
                error_type=type(exc).__name__,
                runner=self.name,
                degraded=True,
            )
        finally:
            cleanup_dir(workdir)

    def _execute(self, entry: Path, workdir: Path, request: SandboxRequest) -> SandboxResponse:
        """真正跑子进程：超时 kill + 输出截断 + 峰值内存采样。"""
        started = time.perf_counter()
        env = self._build_env(workdir)
        creation_flags = 0
        if os.name == "nt":  # Windows：不弹窗
            creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        proc = subprocess.Popen(  # noqa: S603 - 参数为白名单后的固定值
            [self._python, "-I", "-X", "utf8", str(entry)],
            cwd=str(workdir),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            creationflags=creation_flags,
        )

        peak_kb = 0
        timed_out = False
        over_memory = False
        try:
            stdin_bytes = (request.stdin or "").encode("utf-8")
            # 通过 communicate 一次性写入并在超时后 kill
            try:
                stdout_bytes, stderr_bytes = proc.communicate(
                    input=stdin_bytes, timeout=request.timeout_ms / 1000.0
                )
            except subprocess.TimeoutExpired:
                timed_out = True
                proc.kill()
                stdout_bytes, stderr_bytes = proc.communicate()
            peak_kb = self._peak_memory_kb(proc)
            if peak_kb > request.memory_limit_mb * 1024:
                over_memory = True
        finally:
            if proc.poll() is None:
                proc.kill()

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        stdout, stdout_truncated = _decode_capped(stdout_bytes)
        stderr, stderr_truncated = _decode_capped(stderr_bytes)
        exit_code = proc.returncode if proc.returncode is not None else -1

        if timed_out:
            status = STATUS_TIMEOUT
            error = f"执行超时（>{request.timeout_ms}ms）"
            error_type = "TimeoutError"
        elif over_memory:
            status = STATUS_MEMORY
            error = f"内存超限（峰值 {peak_kb} KB > {request.memory_limit_mb} MB）"
            error_type = "MemoryError"
        elif exit_code != 0:
            status = STATUS_ERROR
            error = _extract_exception(stderr) or f"进程以退出码 {exit_code} 结束"
            error_type = _extract_exception_type(stderr)
        else:
            status = STATUS_SUCCESS
            error = None
            error_type = None

        return SandboxResponse(
            request_id=request.request_id,
            status=status,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            truncated=stdout_truncated or stderr_truncated,
            time_ms=elapsed_ms,
            memory_kb=peak_kb,
            error=error,
            error_type=error_type,
            runner=self.name,
            degraded=True,
        )

    def _build_env(self, workdir: Path) -> dict[str, str]:
        """构造受限环境变量：禁网络代理、固定 PATH、UTF-8。"""
        base = {
            "PATH": os.environ.get("PATH", ""),
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
            "TEMP": str(workdir),
            "TMP": str(workdir),
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
        }
        if not get_settings().sandbox_allow_network:
            browser_proxy = "127.0.0.1:9"  # 指向不可达端口，等效断网
            base.update(
                {
                    "HTTP_PROXY": browser_proxy,
                    "HTTPS_PROXY": browser_proxy,
                    "http_proxy": browser_proxy,
                    "https_proxy": browser_proxy,
                    "NO_PROXY": "",
                }
            )
        return base

    @staticmethod
    def _peak_memory_kb(proc: subprocess.Popen[bytes]) -> int:
        """采样子进程峰值内存（KB）；psutil 不可用时返回 0。"""
        try:
            import psutil

            process = psutil.Process(proc.pid)
            memory_info = process.memory_info()
            return int(memory_info.rss // 1024)
        except Exception:  # noqa: BLE001 - 采样失败不影响判题
            return 0


class RemoteRunner:
    """远程沙箱执行器（HTTP JSON 协议）。"""

    name = "sandbox"

    def __init__(self, base_url: str, timeout_seconds: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    def run(self, request: SandboxRequest) -> SandboxResponse:
        """调用远程沙箱 `/run`，失败返回 `internal_error`（由上层决定是否降级）。"""
        import httpx

        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(f"{self._base_url}/run", json=request.model_dump())
                response.raise_for_status()
                payload = response.json()
            return SandboxResponse(
                request_id=payload.get("request_id", request.request_id),
                status=payload.get("status", STATUS_SUCCESS),
                exit_code=int(payload.get("exit_code", 0) or 0),
                stdout=payload.get("stdout", ""),
                stderr=payload.get("stderr", ""),
                truncated=bool(payload.get("truncated", False)),
                time_ms=int(payload.get("time_ms", 0) or 0),
                memory_kb=int(payload.get("memory_kb", 0) or 0),
                error=payload.get("error"),
                error_type=payload.get("error_type"),
                runner=self.name,
                degraded=False,
            )
        except Exception as exc:  # noqa: BLE001 - 交由上层降级
            logger.warning("远程沙箱调用失败: %s", exc)
            return SandboxResponse(
                request_id=request.request_id,
                status=STATUS_INTERNAL,
                error=f"远程沙箱不可用：{exc}",
                error_type=type(exc).__name__,
                runner=self.name,
                degraded=False,
            )

    def ping(self) -> bool:
        """探测远程沙箱健康状态。"""
        import httpx

        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.get(f"{self._base_url}/health")
            return response.status_code < 400
        except Exception:  # noqa: BLE001 - 健康检查不抛错
            return False


class RunnerFacade:
    """执行器门面：按配置选择实现，并在 remote 失败时自动降级。"""

    def __init__(self) -> None:
        settings = get_settings()
        self._mode = (settings.sandbox_mode or "auto").lower()
        self._remote: RemoteRunner | None = None
        self._local = LocalRunner()
        self._remote_ok = False

        if self._mode in ("auto", "remote"):
            probe_timeout = max(0.2, settings.sandbox_probe_timeout_ms / 1000.0)
            self._remote = RemoteRunner(settings.sandbox_url, timeout_seconds=probe_timeout)
            self._remote_ok = self._remote.ping()
            if not self._remote_ok:
                logger.warning("远程沙箱不可用（%s），降级为本机执行器", settings.sandbox_url)

    @property
    def mode(self) -> str:
        """当前生效的执行器模式：`remote` / `local`。"""
        return "remote" if (self._mode == "remote" or self._remote_ok) else "local"

    @property
    def degraded(self) -> bool:
        """是否处于降级状态（本机执行）。"""
        return self.mode != "remote"

    def is_ok(self) -> bool:
        """执行器是否可用（local 始终可用，除非被显式关闭）。"""
        if self.mode == "remote":
            return True
        return bool(get_settings().local_runner_enabled)

    def run(self, request: SandboxRequest) -> SandboxResponse:
        """执行代码：先做 AST 安全校验，再 remote 优先，失败或不可用时回退 local。"""
        violation = scan_source(
            {item.path: item.content for item in request.files},
            # 同上：仅引导文件免检，保留名必须照常校验（纵深防御的最后一层）。
            skip_paths={LOCAL_BOOTSTRAP_NAME},
        )
        if violation is not None:
            # 远程沙箱与本机执行器共用同一道门：避免 remote 模式绕过校验
            logger.warning("源码安全校验拒绝 request_id=%s rule=%s", request.request_id, violation.rule)
            return _guard_response(
                request, violation, runner_name=self.mode, degraded=self.degraded
            )

        if self.mode == "remote" and self._remote is not None:
            result = self._remote.run(request)
            if result.status != STATUS_INTERNAL:
                return result
            logger.warning("远程执行失败，降级本机执行 request_id=%s", request.request_id)
        if not get_settings().local_runner_enabled:
            return SandboxResponse(
                request_id=request.request_id,
                status=STATUS_REJECTED,
                error="本机执行器已关闭，且远程沙箱不可用",
                runner="none",
                degraded=True,
            )
        return self._local.run(request)


_runner: RunnerFacade | None = None


def get_runner() -> RunnerFacade:
    """获取全局执行器（首次调用时构建并探测远程沙箱）。"""
    global _runner
    if _runner is None:
        _runner = RunnerFacade()
    return _runner


def reset_runner() -> None:
    """重置执行器（测试用）。"""
    global _runner
    _runner = None


def new_request_id() -> str:
    """生成一次执行请求的 id。"""
    return f"run-{uuid.uuid4().hex[:16]}"


def _decode_capped(raw: bytes | None) -> tuple[str, bool]:
    """解码输出并按 `MAX_OUTPUT_BYTES` 截断，返回 `(文本, 是否被截断)`。"""
    if not raw:
        return "", False
    truncated = len(raw) > MAX_OUTPUT_BYTES
    payload = raw[:MAX_OUTPUT_BYTES] if truncated else raw
    return payload.decode("utf-8", errors="replace"), truncated


def _extract_exception(stderr: str) -> str | None:
    """从 stderr 中提取异常信息最后一行。"""
    lines = [line for line in (stderr or "").strip().splitlines() if line.strip()]
    return lines[-1][:500] if lines else None


def _extract_exception_type(stderr: str) -> str | None:
    """从 stderr 中提取异常类型名（形如 `ValueError: xxx` → `ValueError`）。"""
    message = _extract_exception(stderr)
    if not message or ":" not in message:
        return None
    candidate = message.split(":", 1)[0].strip()
    return candidate if candidate.endswith("Error") or candidate.endswith("Exception") else None
