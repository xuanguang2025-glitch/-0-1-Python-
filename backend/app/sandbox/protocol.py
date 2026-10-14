"""沙箱 JSON 协议定义（backend ↔ sandbox 服务，`docs/SANDBOX.md`）。

契约要点：
- 请求：`{request_id, files[{path, content}], entry, stdin, timeout_ms, memory_limit_mb, allow_network}`
- 响应：`{request_id, status, exit_code, stdout, stderr, truncated, time_ms, memory_kb, error, runner, degraded}`
- `status` 取值：`success / error / timeout / memory_limit_exceeded / security_error / rejected / internal_error`

本模块只定义数据结构与状态常量，不含执行逻辑，便于 backend 与 sandbox 双端复用。
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.core.constants import SANDBOX_BOOTSTRAP_FILENAME, SANDBOX_RESERVED_FILENAMES

#: 执行状态常量
STATUS_SUCCESS = "success"
STATUS_ERROR = "error"
STATUS_TIMEOUT = "timeout"
STATUS_MEMORY = "memory_limit_exceeded"
STATUS_SECURITY = "security_error"
STATUS_REJECTED = "rejected"
STATUS_INTERNAL = "internal_error"

RunStatus = Literal[
    "success",
    "error",
    "timeout",
    "memory_limit_exceeded",
    "security_error",
    "rejected",
    "internal_error",
]

#: 提交到执行器的最大文件数 / 单文件字节
MAX_FILES: int = 20
MAX_FILE_BYTES: int = 200_000
#: 输出上限（超出即截断并置 truncated=True）
MAX_OUTPUT_BYTES: int = 65_536

#: 系统生成的引导文件名（`app/services/sandbox_local.py` 注入，用户代码不可见，
#: 不参与用户代码安全校验）。规范定义在 `app/core/constants.py`，此处转出以便
#: 沙箱层与服务层共同引用，避免循环依赖。
LOCAL_BOOTSTRAP_NAME: str = SANDBOX_BOOTSTRAP_FILENAME

#: 沙箱自身保留的文件名（禁止用户占用）。
#: 只有 `LOCAL_BOOTSTRAP_NAME` 会被 AST 校验跳过（系统生成、每次覆盖）；
#: 其余保留名（如 `_plab_guard.py`）**照常校验** —— 早期版本按 basename 跳过
#: 整个集合，等于给攻击者一个免检入口（QA 实测 P0，回归见
#: `tests/test_sandbox_reserved_name.py`，证据脚本见 `scripts/security/qa_reserved_name.py`）。
RESERVED_FILENAMES: frozenset[str] = SANDBOX_RESERVED_FILENAMES

#: **第二层**字符串黑名单（仅作 AST 白名单之外的补充防线，不再是主要判据）。
#: 历史原因：早期实现只有这张表，被 QA 用 `__import__("os")`（双引号）、
#: `getattr(os, "system")` 等手法绕过。现由 `app/sandbox/ast_guard.py` 承担主判定。
FORBIDDEN_PATTERNS: tuple[str, ...] = (
    "os.system",
    "os.popen",
    "subprocess",
    "shutil.rmtree",
    "ctypes",
    "socket.socket",
    "__import__('os')",
    'eval(input',
    "open('/etc",
    "open('/proc",
    "filecmp",
    "pty.spawn",
    "tempfile.mktemp",
    "multiprocessing",
    "fork(",
    "rm -rf",
)

#: 允许 import 的模块前缀（白名单；实际生效值取 `SANDBOX_ALLOWED_IMPORTS` 配置）
DEFAULT_ALLOWED_MODULES: tuple[str, ...] = (
    "math",
    "json",
    "itertools",
    "collections",
    "re",
    "string",
    "sys",
    "os",
    "io",
    "csv",
    "pathlib",
    "random",
    "datetime",
    "functools",
    "heapq",
    "bisect",
    "typing",
    "decimal",
    "fractions",
    "statistics",
    "textwrap",
    "unicodedata",
    "copy",
    "operator",
    "enum",
    "dataclasses",
    "abc",
    "time",
    "hashlib",
    "base64",
    "secrets",
    "calendar",
    "uuid",
    "keyword",
    "argparse",
    "pprint",
    "numbers",
    "array",
    "queue",
    "struct",
    "zlib",
)


class SandboxFile(BaseModel):
    """待执行文件。"""

    path: str = Field(..., min_length=1, max_length=255)
    content: str = Field(default="", max_length=MAX_FILE_BYTES)


class SandboxRequest(BaseModel):
    """执行请求（backend → runner）。"""

    request_id: str = Field(..., min_length=1, max_length=64)
    files: list[SandboxFile] = Field(..., min_length=1, max_length=MAX_FILES)
    entry: str = Field(default="main.py", max_length=255)
    stdin: str = Field(default="", max_length=100_000)
    timeout_ms: int = Field(default=5000, ge=1000, le=10_000)
    memory_limit_mb: int = Field(default=256, ge=32, le=512)
    allow_network: bool = False

    @field_validator("entry")
    @classmethod
    def _entry_in_files(cls, value: str, info: Any) -> str:
        files = (info.data or {}).get("files") or []
        if files and value not in {item.path for item in files}:
            raise ValueError(f"入口文件 {value} 不在 files 中")
        return value


class SandboxResponse(BaseModel):
    """执行结果（runner → backend）。"""

    request_id: str = ""
    status: RunStatus = "success"
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

    @property
    def ok(self) -> bool:
        """是否执行成功。"""
        return self.status == STATUS_SUCCESS

    def to_dict(self) -> dict[str, Any]:
        """转换为普通字典（便于直接返回给前端）。"""
        return self.model_dump()
