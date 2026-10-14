"""代码执行相关 Schema（`docs/API.md` §2.7 与 §3.2 `RunResponse`）。"""

from __future__ import annotations

from pydantic import Field, field_validator

from app.core.constants import SANDBOX_RESERVED_FILENAMES
from app.core.errors import AppError, ErrorCode
from app.schemas.common import ORMModel, StrictModel

#: 单次执行可提交的最大文件数
MAX_FILES: int = 20

#: 保留名判定用的说明（供两处校验器共用，避免文案漂移）
_RESERVED_HINT = "该文件名为沙箱保留名，禁止提交"


def _basename(path: str) -> str:
    """取 POSIX 风格路径的最后一段（文件名）。"""
    return str(path).replace("\\", "/").rstrip("/").split("/")[-1]


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
        for item in value:
            # 保留名（`_plab_guard.py` 等）是沙箱系统文件的身份：曾被整体跳过 AST
            # 校验而形成免检入口（QA 实测 P0）。这里在入口处直接拒绝。
            # 抛 AppError（而非 ValueError）→ 全局异常处理器返回 400 INVALID_PATH，
            # 语义上是「请求了一个被占用的名字」，不是字段格式错误（422）。
            if _basename(item.path) in SANDBOX_RESERVED_FILENAMES:
                raise AppError(
                    code=ErrorCode.INVALID_PATH,
                    message=f"{_RESERVED_HINT}：{_basename(item.path)}",
                    details=item.path,
                )
        return value

    @field_validator("entry")
    @classmethod
    def _entry_not_reserved(cls, value: str | None) -> str | None:
        """入口文件同样不得使用保留名（与 files 校验保持一致，拒绝越早越好）。"""
        if value and _basename(value) in SANDBOX_RESERVED_FILENAMES:
            raise AppError(
                code=ErrorCode.INVALID_PATH,
                message=f"{_RESERVED_HINT}：{_basename(value)}",
                details=value,
            )
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
