"""代码执行沙箱层：协议定义 + AST 安全校验 + 远程/本机双实现。"""

from app.sandbox.ast_guard import GuardViolation, check_files, check_source
from app.sandbox.protocol import SandboxFile, SandboxRequest, SandboxResponse
from app.sandbox.runner import LocalRunner, RemoteRunner, RunnerFacade, get_runner, reset_runner, scan_source

__all__ = [
    "GuardViolation",
    "LocalRunner",
    "RemoteRunner",
    "RunnerFacade",
    "SandboxFile",
    "SandboxRequest",
    "SandboxResponse",
    "check_files",
    "check_source",
    "get_runner",
    "reset_runner",
    "scan_source",
]
