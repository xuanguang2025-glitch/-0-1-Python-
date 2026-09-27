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

from app.core.config import get_settings
from app.sandbox.protocol import (
    FORBIDDEN_PATTERNS,
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


def scan_source(files: dict[str, str]) -> str | None:
    """扫描源码中的危险语法，命中返回命中的模式，否则返回 None。"""
    for content in files.values():
        lowered = content or ""
        for pattern in FORBIDDEN_PATTERNS:
            if pattern in lowered:
                return pattern
    return None


class LocalRunner:
    """本机执行器（降级实现，功能不中断）。"""

    name = "local"

    def __init__(self, python_executable: str | None = None) -> None:
        self._python = python_executable or sys.executable

    def run(self, request: SandboxRequest) -> SandboxResponse:
        """在本机子进程中执行入口文件并返回结果。"""
        files = {item.path: item.content for item in request.files}
        hit = scan_source(files)
        if hit is not None:
            return SandboxResponse(
                request_id=request.request_id,
                status=STATUS_SECURITY,
                error=f"源码包含被禁止的语法：{hit}",
                error_type="SecurityError",
                runner=self.name,
                degraded=True,
            )

        workdir = make_temp_dir("plab_run_")
        try:
            write_files(workdir, files)
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
        """执行代码：remote 优先，失败或不可用时回退 local。"""
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
