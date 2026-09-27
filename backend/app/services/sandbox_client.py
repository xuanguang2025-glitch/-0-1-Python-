"""统一代码执行客户端（远程沙箱 ↔ 本机执行器 ↔ stub）。

职责（`docs/SANDBOX.md`）：
- 对上层暴露一个与实现无关的接口：
  `run(files, stdin, ...) -> ExecutionResult` 与 `judge(files, test_cases, ...) -> ExecutionResult`；
- 按 `SANDBOX_MODE` 选择后端：
  - `remote`：HTTP `POST {SANDBOX_URL}/execute`；
  - `local` ：走 `app.sandbox.runner.LocalRunner`（本机降级，超时 kill + 输出截断）；
  - `auto`  ：先探远程 `/health`（默认 1.5s），可用则 remote，否则回落 local；
  - `stub`  ：返回固定结果（供无执行环境的 CI 冒烟）；
- 远程调用异常时**自动回落**本地执行并记录告警，绝不把 500 抛给调用方；
- 返回结构统一且带 `runner` / `degraded` 标记，供提交记录落库。

实现被拆分为：本模块（门面 + 远程/路由/单例）、`sandbox_local.py`（本机后端）、
`sandbox_result.py`（结果模型与状态归一化）。为兼容既有调用方，本模块继续导出
`ExecutionResult` / `CaseResult` / `compare_output` / `normalize_status` / `LOCAL_BOOTSTRAP_NAME`。
"""

from __future__ import annotations

import logging
from typing import Any, Iterable, Mapping

from app.core.config import get_settings
from app.core.errors import AppError, ErrorCode
from app.sandbox.protocol import MAX_OUTPUT_BYTES
from app.services.sandbox_local import (
    LOCAL_BOOTSTRAP_NAME,
    LocalBackend,
    clamp_memory,
    clamp_timeout,
)
from app.services.sandbox_result import (
    STATUS_SUCCESS,
    CaseResult,
    ExecutionResult,
    compare_output,
    from_remote_payload,
    normalize_status,
    stub_result,
)
from app.utils.validators import validate_relative_path

logger = logging.getLogger("pythonlab.sandbox_client")

__all__ = [
    "CaseResult",
    "ExecutionResult",
    "LOCAL_BOOTSTRAP_NAME",
    "SandboxClient",
    "compare_output",
    "get_sandbox_client",
    "normalize_status",
    "reset_sandbox_client",
    "set_sandbox_client",
]


class SandboxClient:
    """代码执行门面：统一 remote / local / auto / stub 四种后端。"""

    def __init__(
        self,
        *,
        mode: str | None = None,
        url: str | None = None,
        probe_timeout_ms: int | None = None,
        timeout_ms: int | None = None,
        memory_mb: int | None = None,
        max_output_bytes: int | None = None,
    ) -> None:
        """构造客户端；缺省值从全局配置读取，便于测试显式覆盖。"""
        settings = get_settings()
        candidate = str(mode or settings.sandbox_mode or "auto").lower()
        self._mode = candidate if candidate in {"auto", "remote", "local", "stub"} else "auto"
        self._url = (url or settings.sandbox_url).rstrip("/")
        self._probe_timeout_ms = int(probe_timeout_ms or settings.sandbox_probe_timeout_ms)
        self._default_timeout_ms = int(timeout_ms or settings.sandbox_timeout_ms)
        self._default_memory_mb = int(memory_mb or settings.sandbox_memory_mb)
        self._max_output_bytes = int(max_output_bytes or settings.sandbox_max_output_bytes or MAX_OUTPUT_BYTES)
        self._local = LocalBackend(
            timeout_ms=self._default_timeout_ms,
            memory_mb=self._default_memory_mb,
            max_output_bytes=self._max_output_bytes,
        )
        self._auto_probed = False
        self._remote_available = False

    # ------------------------------------------------------------------ 属性
    @property
    def configured_mode(self) -> str:
        """配置声明的模式（`auto` / `remote` / `local` / `stub`）。"""
        return self._mode

    @property
    def mode(self) -> str:
        """当前生效的后端（`remote` / `local` / `stub`）。"""
        return self._effective_mode()

    @property
    def degraded(self) -> bool:
        """是否处于降级执行（非 hardened 远程沙箱）。"""
        return self._effective_mode() != "remote"

    # ------------------------------------------------------------------ 执行
    def run(
        self,
        code_or_files: str | Mapping[str, str] | Iterable[Any],
        stdin: str = "",
        *,
        entry: str | None = None,
        timeout_ms: int | None = None,
        memory_mb: int | None = None,
    ) -> ExecutionResult:
        """单段代码 / 多文件项目运行。"""
        files = self._prepare_files(code_or_files)
        resolved_entry = _resolve_entry(files, entry)
        mode = self._effective_mode()

        if mode == "stub":
            return stub_result(self._new_request_id(), "stub")

        if mode == "remote":
            remote = self._remote_execute(files, resolved_entry, stdin, timeout_ms, memory_mb, mode="run")
            if remote is not None:
                return remote
            logger.warning("远程沙箱执行失败，降级为本机执行（mode=remote→local）")

        return self._local.run(files, resolved_entry, stdin, timeout_ms, memory_mb)

    def judge(
        self,
        code_or_files: str | Mapping[str, str] | Iterable[Any],
        test_cases: Iterable[Mapping[str, Any]],
        *,
        entry: str | None = None,
        timeout_ms: int | None = None,
        memory_mb: int | None = None,
    ) -> ExecutionResult:
        """按测试用例集合判题。

        Args:
            code_or_files: 待判代码（单文件字符串 / `{path: content}` / 文件对象列表）。
            test_cases: 用例字典序列，字段 `id/input/expected/comparison/tolerance/timeout_ms`。
            entry: 入口文件。
            timeout_ms: 单用例默认超时（用例级 `timeout_ms` 优先）。
            memory_mb: 内存上限。

        Returns:
            `ExecutionResult`，`results` 为逐用例结果。
        """
        cases = [dict(case) for case in test_cases]
        files = self._prepare_files(code_or_files)
        resolved_entry = _resolve_entry(files, entry)
        if not cases:
            return self.run(files, entry=resolved_entry, timeout_ms=timeout_ms, memory_mb=memory_mb)

        mode = self._effective_mode()
        if mode == "stub":
            return self._stub_judge(files, cases, resolved_entry, timeout_ms, memory_mb)

        if mode == "remote":
            remote = self._remote_execute(
                files, resolved_entry, "", timeout_ms, memory_mb, mode="judge", test_cases=cases
            )
            if remote is not None and remote.results:
                return remote
            logger.warning("远程判题失败或返回空结果，降级为本机逐用例判题")

        return self._local.judge(files, cases, resolved_entry, timeout_ms, memory_mb)

    # -------------------------------------------------------------- 内部实现
    def _effective_mode(self) -> str:
        """解析 `auto` 模式：探测远程 /health 成功用远程，否则本地。"""
        if self._mode in ("local", "stub", "remote"):
            return self._mode
        if not self._auto_probed:
            self._remote_available = self._probe_remote()
            self._auto_probed = True
        return "remote" if self._remote_available else "local"

    def _probe_remote(self) -> bool:
        """探测远程沙箱健康状态（超时即视为不可用）。"""
        timeout_seconds = max(0.2, self._probe_timeout_ms / 1000.0)
        try:
            import httpx

            with httpx.Client(timeout=timeout_seconds) as client:
                response = client.get(f"{self._url}/health")
            return response.status_code < 400
        except Exception as exc:  # noqa: BLE001 - 探测失败即回落本地
            logger.warning("远程沙箱 %s 不可用（%s），回落本机执行器", self._url, exc)
            return False

    def _remote_execute(
        self,
        files: dict[str, str],
        entry: str,
        stdin: str,
        timeout_ms: int | None,
        memory_mb: int | None,
        *,
        mode: str,
        test_cases: list[dict[str, Any]] | None = None,
    ) -> ExecutionResult | None:
        """调用远程沙箱 `/execute`；任何异常返回 None 交由调用方降级。"""
        timeout = clamp_timeout(timeout_ms, self._default_timeout_ms)
        payload: dict[str, Any] = {
            "request_id": self._new_request_id(),
            "language": "python",
            "mode": mode,
            "files": [{"path": path, "content": content} for path, content in files.items()],
            "entry": entry,
            "stdin": stdin or "",
            "timeout_ms": timeout,
            "memory_limit_mb": clamp_memory(memory_mb, self._default_memory_mb),
            "max_output_bytes": self._max_output_bytes,
            "allow_network": False,
        }
        if test_cases:
            payload["test_cases"] = test_cases
        try:
            import httpx

            with httpx.Client(timeout=max(5.0, timeout / 1000.0 * 2)) as client:
                response = client.post(f"{self._url}/execute", json=payload)
                response.raise_for_status()
                data = response.json()
            return from_remote_payload(data, mode=mode)
        except Exception as exc:  # noqa: BLE001 - 由上层决定降级
            logger.warning("远程沙箱调用异常（%s），将回落本机: %s", self._url, exc)
            return None

    def _stub_judge(
        self,
        files: dict[str, str],
        cases: list[dict[str, Any]],
        entry: str,
        timeout_ms: int | None,
        memory_mb: int | None,
    ) -> ExecutionResult:
        """stub 模式判题：用空输出确定性比对，保证 CI 无执行环境也能跑通链路。"""
        results: list[CaseResult] = []
        passed_count = 0
        for case in cases:
            expected = str(case.get("expected") or "")
            passed = compare_output("", expected, str(case.get("comparison") or "trimmed"))
            if passed:
                passed_count += 1
            results.append(
                CaseResult(
                    test_case_id=case.get("id"),
                    passed=passed,
                    actual="",
                    expected=expected,
                    status=STATUS_SUCCESS,
                    message=None if passed else "stub 模式未实际执行代码",
                )
            )
        return ExecutionResult(
            request_id=self._new_request_id(),
            status=STATUS_SUCCESS,
            stdout="",
            stderr="",
            runner="stub",
            degraded=True,
            results=results,
            passed_cases=passed_count,
            total_cases=len(cases),
        )

    # ---------------------------------------------------------------- 工具
    def _prepare_files(self, code_or_files: str | Mapping[str, str] | Iterable[Any]) -> dict[str, str]:
        """把多种输入形态归一化为 `{路径: 内容}` 并通过路径安全校验。"""
        raw = _normalize_files(code_or_files)
        if not raw:
            raise AppError(code=ErrorCode.BAD_REQUEST, message="执行文件不能为空")
        safe: dict[str, str] = {}
        for path, content in raw.items():
            safe[validate_relative_path(path)] = content
        return safe

    def _new_request_id(self) -> str:
        """生成一次执行请求 id（用于日志串联）。"""
        import uuid

        return f"run-{uuid.uuid4().hex[:16]}"


def _normalize_files(code_or_files: str | Mapping[str, str] | Iterable[Any]) -> dict[str, str]:
    """把字符串 / 映射 / 文件对象列表统一为 `{路径: 内容}`。"""
    if isinstance(code_or_files, str):
        return {"main.py": code_or_files}
    if isinstance(code_or_files, Mapping):
        return {str(key): ("" if value is None else str(value)) for key, value in code_or_files.items()}
    result: dict[str, str] = {}
    for item in code_or_files:
        if isinstance(item, Mapping):
            path = item.get("path")
            content = item.get("content")
        else:
            path = getattr(item, "path", None)
            content = getattr(item, "content", "")
        if path:
            result[str(path)] = "" if content is None else str(content)
    return result


def _resolve_entry(files: Mapping[str, str], entry: str | None) -> str:
    """解析入口文件：优先显式指定，其次 `main.py`，否则取第一个文件。"""
    if entry and entry in files:
        return entry
    if "main.py" in files:
        return "main.py"
    return next(iter(files))


# --------------------------------------------------------------- 单例容器
_client: SandboxClient | None = None


def get_sandbox_client() -> SandboxClient:
    """获取全局执行客户端（首次调用时按配置构建）。"""
    global _client
    if _client is None:
        _client = SandboxClient()
    return _client


def set_sandbox_client(client: SandboxClient) -> None:
    """替换全局执行客户端（测试用）。"""
    global _client
    _client = client


def reset_sandbox_client() -> None:
    """重置全局执行客户端（下次调用重新按配置构建）。"""
    global _client
    _client = None
