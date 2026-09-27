"""代码执行相关 Schema（`docs/API.md` §2.7 与 §3.2 `RunResponse`）。"""

from __future__ import annotations

from pydantic import Field, field_validator

from app.schemas.common import ORMModel, StrictModel

#: 单次执行可提交的最大文件数
MAX_FILES: int = 20


class RunFileIn(StrictModel):
    """待执行文件。"""

    path: str = Field(..., min_length=1, max_length=255, description="相对路径，如 main.py")
    content: str = Field(default="", max_length=200_000)


class RunRequest(StrictModel):
    """`POST /api/python/run` 请求体。"""

    files: list[RunFileIn] = Field(default_factory=list, max_length=MAX_FILES)
    entry: str | None = Field(default=None, max_length=255, description="入口文件，默认 main.py")
    stdin: str = Field(default="", max_length=100_000, description="标准输入")
    timeout_ms: int | None = Field(default=None, ge=1000, le=10_000)
    memory_limit_mb: int | None = Field(default=None, ge=32, le=512)

    @field_validator("files")
    @classmethod
    def _require_files(cls, value: list[RunFileIn]) -> list[RunFileIn]:
        if not value:
            raise ValueError("files 不能为空")
        return value

    def as_mapping(self) -> dict[str, str]:
        """转换为 `{相对路径: 代码}` 字典。"""
        return {item.path: item.content for item in self.files}


class RunResponse(ORMModel):
    """执行结果（本地执行器与远程沙箱结构一致）。"""

    request_id: str
    status: str = Field(default="success", description="success/error/timeout/security_error/rejected")
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    truncated: bool = False
    time_ms: int = 0
    memory_kb: int = 0
    error: str | None = None
    error_type: str | None = None
    runner: str = Field(default="local", description="local/sandbox")
    degraded: bool = True


class SandboxProtocolRequest(StrictModel):
    """backend → sandbox 服务 的内部协议请求（`docs/SANDBOX.md`）。"""

    request_id: str
    files: list[RunFileIn]
    entry: str = "main.py"
    stdin: str = ""
    timeout_ms: int = 5000
    memory_limit_mb: int = 256
    allow_network: bool = False


class SandboxStatusOut(ORMModel):
    """执行器状态（健康检查用）。"""

    mode: str = Field(default="local", description="remote/local/stub")
    ok: bool = True
    url: str | None = None
    detail: str | None = None
