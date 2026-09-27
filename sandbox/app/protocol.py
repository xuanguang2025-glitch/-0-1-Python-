"""沙箱执行协议（与 backend/app/sandbox/protocol.py 共享同一份契约）。

入参同时接受 ARCHITECTURE.md 的规范字段名（`timeout_ms` / `memory_limit_mb`）
与简写别名（`timeout` / `memory_mb` / `code`），兼容不同调用方。
出参同时提供 `time_ms` 与 `duration_ms`、`status` 与 `timed_out`。
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

ExecutionStatus = Literal[
    "success",
    "compile_error",
    "runtime_error",
    "timeout",
    "memory_exceeded",
    "output_exceeded",
    "security_error",
    "wrong_answer",
    "internal_error",
]

Comparison = Literal["trimmed", "exact", "float", "custom"]


def new_request_id() -> str:
    """生成请求 ID（uuid4 字符串）。"""
    return str(uuid.uuid4())


class FileSpec(BaseModel):
    """待落盘的文件。path 为相对路径，禁止绝对路径与 `..`。"""

    path: str = Field(default="main.py", min_length=1, max_length=128)
    content: str = ""


class TestCaseSpec(BaseModel):
    """判题用例。"""

    id: str = ""
    input: str = ""
    expected: str = ""
    comparison: Comparison = "trimmed"


class ErrorPayload(BaseModel):
    """结构化错误信息。"""

    type: str = ""
    message: str = ""
    traceback: str = ""
    line: Optional[int] = None


class CaseResult(BaseModel):
    """单个测试用例的执行结果。"""

    test_case_id: str = ""
    passed: bool = False
    actual: str = ""
    expected: str = ""
    time_ms: int = 0
    memory_kb: int = 0
    status: str = "success"
    diff: Optional[str] = None


class ExecutionRequest(BaseModel):
    """执行请求。"""

    request_id: str = ""
    language: str = "python"
    version: Optional[str] = None
    mode: Literal["run", "judge", "batch_run"] = "run"
    files: List[FileSpec] = Field(default_factory=list)
    code: Optional[str] = None            # 简写：单文件代码
    entry: str = "main.py"                # 入口文件
    stdin: str = ""
    test_cases: List[TestCaseSpec] = Field(default_factory=list)
    timeout_ms: Optional[int] = None
    timeout: Optional[int] = None         # 别名
    memory_limit_mb: Optional[int] = None
    memory_mb: Optional[int] = None       # 别名
    cpu_limit_ms: Optional[int] = None
    max_output_bytes: Optional[int] = None
    allow_network: Optional[bool] = None
    env: Dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        """把 dict 形式的 files 与裸 code 归一化。"""
        if not isinstance(data, dict):
            return data
        payload = dict(data)
        files = payload.get("files")
        if isinstance(files, dict):
            payload["files"] = [{"path": key, "content": value} for key, value in files.items()]
        elif isinstance(files, str):
            payload["files"] = [{"path": payload.get("entry", "main.py"), "content": files}]
        return payload

    @model_validator(mode="after")
    def _fill_defaults(self) -> "ExecutionRequest":
        """填充 request_id，并把 code 折叠成 files。"""
        if not self.request_id:
            self.request_id = new_request_id()
        if not self.files and self.code is not None:
            self.files = [FileSpec(path=self.entry or "main.py", content=self.code)]
        if not self.files:
            self.files = [FileSpec(path=self.entry or "main.py", content="")]
        for index, case in enumerate(self.test_cases, start=1):
            if not case.id:
                case.id = f"tc{index}"
        return self

    def normalized(self, settings: Any) -> "ExecutionRequest":
        """按服务端配置钳制限额，返回规范化后的请求（服务端配置优先）。"""
        self.timeout_ms = settings.clamp_timeout(self.timeout_ms or self.timeout)
        self.timeout = self.timeout_ms
        self.memory_limit_mb = settings.clamp_memory(self.memory_limit_mb or self.memory_mb)
        self.memory_mb = self.memory_limit_mb
        self.max_output_bytes = settings.clamp_output(self.max_output_bytes)
        if self.cpu_limit_ms is None or self.cpu_limit_ms <= 0:
            self.cpu_limit_ms = min(settings.default_cpu_limit_ms, self.timeout_ms)
        self.allow_network = bool(self.allow_network) and bool(settings.allow_network)
        if self.mode == "judge":
            self.test_cases = self.test_cases[: int(settings.max_test_cases)]
        return self


class ExecutionResponse(BaseModel):
    """执行响应。"""

    request_id: str = ""
    status: ExecutionStatus = "success"
    exit_code: Optional[int] = 0
    stdout: str = ""
    stderr: str = ""
    truncated: bool = False
    time_ms: int = 0
    duration_ms: int = 0                 # time_ms 别名
    memory_kb: int = 0
    timed_out: bool = False
    results: List[CaseResult] = Field(default_factory=list)
    passed_cases: int = 0
    total_cases: int = 0
    error: Optional[ErrorPayload] = None
    runner: str = "sandbox"
    degraded: bool = False
    security_level: str = "degraded"

    def sync_aliases(self) -> "ExecutionResponse":
        """同步 time_ms/duration_ms 与 timed_out 等别名。"""
        self.duration_ms = self.time_ms
        self.timed_out = self.status == "timeout"
        return self


def ok_response(request_id: str, **fields: Any) -> ExecutionResponse:
    """构造成功响应并同步别名字段。"""
    response = ExecutionResponse(request_id=request_id, **fields)
    return response.sync_aliases()
