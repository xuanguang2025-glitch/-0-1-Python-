"""沙箱服务配置：全部来自环境变量，带默认值与钳制边界。

约定：`SANDBOX_*` 前缀的变量与 backend 的 `SANDBOX_*` 同名同义，
便于 docker-compose 统一注入。
"""

from __future__ import annotations

import os
import sys
import tempfile
from dataclasses import dataclass, field
from typing import List

IS_POSIX = os.name == "posix"


def _env_str(name: str, default: str) -> str:
    value = os.environ.get(name, "")
    return value.strip() if value.strip() else default


def _env_int(name: str, default: int, minimum: int = 0, maximum: int = 1_000_000) -> int:
    raw = os.environ.get(name, "")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def _env_list(name: str, default: str) -> List[str]:
    raw = os.environ.get(name, "")
    source = raw if raw.strip() else default
    return [item.strip() for item in source.split(",") if item.strip()]


@dataclass
class Settings:
    """沙箱运行时配置（不可变意图：启动后只读）。"""

    service_name: str = "python-lab-sandbox"
    version: str = "1.0.0"
    host: str = "0.0.0.0"
    port: int = 8081
    log_level: str = "INFO"

    # ---- 限额 ----
    default_timeout_ms: int = 5000
    min_timeout_ms: int = 1000
    max_timeout_ms: int = 10000
    default_memory_mb: int = 256
    min_memory_mb: int = 32
    max_memory_mb: int = 512
    default_cpu_limit_ms: int = 4000
    max_output_bytes: int = 65536
    max_total_output_bytes: int = 1_048_576
    allow_network: bool = False

    # ---- judge 模式 ----
    max_test_cases: int = 50
    judge_total_budget_ms: int = 30000

    # ---- 文件 ----
    max_files: int = 25
    max_file_bytes: int = 262144
    max_code_bytes: int = 262144
    max_stdin_bytes: int = 65536

    # ---- 守卫 ----
    recursion_limit: int = 300
    import_mode: str = "blacklist"          # blacklist | whitelist | off
    allowed_imports: List[str] = field(default_factory=list)
    blocked_imports: List[str] = field(default_factory=list)
    static_scan: bool = True
    workdir_root: str = ""
    python_executable: str = field(default_factory=lambda: sys.executable)

    # ---- 平台能力（运行时计算）----
    security_level: str = "degraded"

    @classmethod
    def from_env(cls) -> "Settings":
        """从环境变量构造配置，并计算平台安全等级。"""
        workdir_root = _env_str("SANDBOX_WORKDIR_ROOT", "")
        if not workdir_root:
            workdir_root = os.path.join(tempfile.gettempdir(), "pythonlab-sandbox")
        settings = cls(
            service_name=_env_str("SANDBOX_SERVICE_NAME", "python-lab-sandbox"),
            version=_env_str("SANDBOX_VERSION", "1.0.0"),
            host=_env_str("SANDBOX_HOST", "0.0.0.0"),
            port=_env_int("SANDBOX_PORT", 8081, 1, 65535),
            log_level=_env_str("LOG_LEVEL", "INFO").upper(),
            default_timeout_ms=_env_int("SANDBOX_TIMEOUT_MS", 5000, 100, 60000),
            min_timeout_ms=_env_int("SANDBOX_MIN_TIMEOUT_MS", 1000, 100, 60000),
            max_timeout_ms=_env_int("SANDBOX_MAX_TIMEOUT_MS", 10000, 100, 120000),
            default_memory_mb=_env_int("SANDBOX_MEMORY_MB", 256, 16, 4096),
            min_memory_mb=_env_int("SANDBOX_MIN_MEMORY_MB", 32, 8, 1024),
            max_memory_mb=_env_int("SANDBOX_MAX_MEMORY_MB", 512, 32, 8192),
            default_cpu_limit_ms=_env_int("SANDBOX_CPU_LIMIT_MS", 4000, 100, 60000),
            max_output_bytes=_env_int("SANDBOX_MAX_OUTPUT_BYTES", 65536, 1024, 4194304),
            max_total_output_bytes=_env_int("SANDBOX_MAX_TOTAL_OUTPUT_BYTES", 1048576, 65536, 16777216),
            allow_network=_env_bool("SANDBOX_ALLOW_NETWORK", False),
            max_test_cases=_env_int("SANDBOX_MAX_TEST_CASES", 50, 1, 500),
            judge_total_budget_ms=_env_int("SANDBOX_JUDGE_BUDGET_MS", 30000, 1000, 120000),
            max_files=_env_int("SANDBOX_MAX_FILES", 25, 1, 200),
            max_file_bytes=_env_int("SANDBOX_MAX_FILE_BYTES", 262144, 1024, 10485760),
            max_code_bytes=_env_int("SANDBOX_MAX_CODE_BYTES", 262144, 1024, 10485760),
            max_stdin_bytes=_env_int("SANDBOX_MAX_STDIN_BYTES", 65536, 256, 1048576),
            recursion_limit=_env_int("SANDBOX_RECURSION_LIMIT", 300, 50, 2000),
            import_mode=_env_str("SANDBOX_IMPORT_MODE", "blacklist").lower(),
            allowed_imports=_env_list(
                "SANDBOX_ALLOWED_IMPORTS",
                "math,json,itertools,collections,re,string,sys,random,datetime,functools,"
                "heapq,bisect,typing,statistics,decimal,fractions,copy,enum,abc,dataclasses,"
                "textwrap,unicodedata,time,numpy,pandas",
            ),
            blocked_imports=_env_list(
                "SANDBOX_BLOCKED_IMPORTS",
                "subprocess,multiprocessing,ctypes,cffi,pty,resource,mmap,telnetlib,ftplib,"
                "smtplib,poplib,imaplib,webbrowser,tkinter,turtle,pdb,compileall,"
                "py_compile,venv,ensurepip,pip,setuptools,distutils",
            ),
            static_scan=_env_bool("SANDBOX_STATIC_SCAN", True),
            workdir_root=workdir_root,
        )
        settings.python_executable = _env_str("SANDBOX_PYTHON", sys.executable)
        settings.security_level = "hardened" if IS_POSIX else "degraded"
        try:
            os.makedirs(settings.workdir_root, exist_ok=True)
        except OSError:  # 目录不可写时退化为系统临时目录
            settings.workdir_root = tempfile.gettempdir()
        return settings

    def clamp_timeout(self, timeout_ms: int | None) -> int:
        """把超时钳制到 [min_timeout_ms, max_timeout_ms]。"""
        value = timeout_ms if timeout_ms and timeout_ms > 0 else self.default_timeout_ms
        return max(self.min_timeout_ms, min(self.max_timeout_ms, int(value)))

    def clamp_memory(self, memory_mb: int | None) -> int:
        """把内存上限钳制到 [min_memory_mb, max_memory_mb]。"""
        value = memory_mb if memory_mb and memory_mb > 0 else self.default_memory_mb
        return max(self.min_memory_mb, min(self.max_memory_mb, int(value)))

    def clamp_output(self, max_output_bytes: int | None) -> int:
        """把单用例输出上限钳制到 [1024, max_total_output_bytes]。"""
        value = max_output_bytes if max_output_bytes and max_output_bytes > 0 else self.max_output_bytes
        return max(1024, min(self.max_total_output_bytes, int(value)))

    def limits_snapshot(self) -> dict:
        """供 `/health` 与 `/limits` 输出的限额快照。"""
        return {
            "timeout_ms": self.default_timeout_ms,
            "timeout_range_ms": [self.min_timeout_ms, self.max_timeout_ms],
            "memory_mb": self.default_memory_mb,
            "memory_range_mb": [self.min_memory_mb, self.max_memory_mb],
            "cpu_limit_ms": self.default_cpu_limit_ms,
            "max_output_bytes": self.max_output_bytes,
            "max_files": self.max_files,
            "max_file_bytes": self.max_file_bytes,
            "allow_network": self.allow_network,
            "recursion_limit": self.recursion_limit,
            "import_mode": self.import_mode,
            "static_scan": self.static_scan,
        }
