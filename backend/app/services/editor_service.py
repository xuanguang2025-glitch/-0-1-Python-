"""编辑器服务：代码运行 + 复用代码历史能力（`docs/API.md` §2.7、§2.9）。

- `run_code()`：单段 / 多文件代码运行（Playground、课时代码块），走统一沙箱客户端；
- 代码历史相关能力集中在 `code_history_service`，此处仅做再导出，避免重复实现。
"""

from __future__ import annotations

import logging
import re
from typing import Any, Iterable, Mapping

from sqlalchemy.orm import Session

from app.core.errors import AppError, ErrorCode
from app.models.user import User
from app.services.code_history_service import (  # noqa: F401 - 再导出供端点使用
    compare_versions,
    delete_history,
    get_history,
    list_history,
    restore_snapshot,
    save_snapshot,
    to_brief,
    to_out,
)
from app.services.sandbox_client import ExecutionResult, get_sandbox_client
from app.utils.text import truncate
from app.utils.validators import validate_code_size, validate_relative_path

logger = logging.getLogger("pythonlab.editor")

#: 单个项目允许的最大文件数
MAX_PROJECT_FILES: int = 20
#: 单文件代码大小上限（字符 / 字节）
MAX_SOURCE_BYTES: int = 200_000


def ensure_supported_language(language: str | None) -> str:
    """校验语言：当前仅支持 python。"""
    value = (language or "python").strip().lower()
    if value not in ("python", "python3", "py"):
        raise AppError(
            code=ErrorCode.BAD_REQUEST,
            message=f"暂不支持的语言：{language}（当前仅支持 python）",
            details={"language": language},
        )
    return "python"


def normalize_project_files(files: Mapping[str, Any]) -> dict[str, str]:
    """校验并规范化项目文件集 `{路径: 内容}`（防路径遍历 + 体积上限）。"""
    if not isinstance(files, Mapping) or not files:
        raise AppError(code=ErrorCode.BAD_REQUEST, message="files 不能为空")
    if len(files) > MAX_PROJECT_FILES:
        raise AppError(
            code=ErrorCode.BAD_REQUEST,
            message=f"文件数量超限（{len(files)} / {MAX_PROJECT_FILES}）",
        )
    safe: dict[str, str] = {}
    for path, content in files.items():
        safe_path = validate_relative_path(str(path))
        text = "" if content is None else str(content)
        validate_code_size(text, limit=MAX_SOURCE_BYTES)
        safe[safe_path] = text
    return safe


def run_code(
    db: Session | None,
    user: User | None,
    *,
    files: Mapping[str, Any] | str | Iterable[Any],
    entry: str | None = None,
    stdin: str = "",
    timeout_ms: int | None = None,
    memory_mb: int | None = None,
) -> ExecutionResult:
    """运行一段代码或一个多文件项目，返回统一执行结果。

    `db` / `user` 目前仅用于调用签名统一（运行本身不落库），可为 None。
    """
    if isinstance(files, str):
        normalized: dict[str, str] = {"main.py": files}
    elif isinstance(files, Mapping):
        normalized = normalize_project_files(files)
    else:
        collected: dict[str, Any] = {}
        for item in files:
            path = item.get("path") if isinstance(item, Mapping) else getattr(item, "path", None)
            content = item.get("content") if isinstance(item, Mapping) else getattr(item, "content", "")
            if path:
                collected[str(path)] = content
        normalized = normalize_project_files(collected)

    entry_file = _resolve_entry(normalized, entry)
    client = get_sandbox_client()
    result = client.run(normalized, stdin=stdin or "", entry=entry_file, timeout_ms=timeout_ms, memory_mb=memory_mb)
    if result.truncated:
        logger.info("执行输出被截断 request_id=%s", result.request_id)
    return result


def run_result_to_response(result: ExecutionResult, *, request_id: str | None = None) -> dict[str, Any]:
    """把执行结果转换为 `RunResponse` 兼容字典。"""
    return {
        "request_id": request_id or result.request_id,
        "status": result.status,
        "exit_code": int(result.exit_code or 0),
        "stdout": truncate(result.stdout or "", 65_536, suffix="\n...(输出被截断)"),
        "stderr": truncate(result.stderr or "", 16_384, suffix="\n...(stderr 被截断)"),
        "truncated": bool(result.truncated),
        "time_ms": int(result.time_ms or 0),
        "memory_kb": int(result.memory_kb or 0),
        "error": result.error,
        "error_type": result.error_type,
        "runner": result.runner,
        "degraded": bool(result.degraded),
    }


def _resolve_entry(files: Mapping[str, str], entry: str | None) -> str:
    """解析入口文件（显式指定 → main.py → 第一个文件）。"""
    if entry:
        candidate = entry.replace("\\", "/").lstrip("./")
        if candidate in files:
            return candidate
        # 允许带目录的写法：只要规范化后匹配即可
        for path in files:
            if path.endswith(candidate):
                return path
        raise AppError(
            code=ErrorCode.BAD_REQUEST,
            message=f"入口文件不存在：{entry}",
            details={"entry": entry, "files": list(files.keys())},
        )
    if "main.py" in files:
        return "main.py"
    return next(iter(files))


def sanitize_filename(name: str) -> str:
    """把任意文本转换为安全的文件名片段（用于下载 / 快照命名）。"""
    return re.sub(r"[^A-Za-z0-9_.-]", "_", name or "snippet")[:80] or "snippet"


__all__ = [
    "MAX_PROJECT_FILES",
    "compare_versions",
    "delete_history",
    "ensure_supported_language",
    "get_history",
    "list_history",
    "normalize_project_files",
    "restore_snapshot",
    "run_code",
    "run_result_to_response",
    "sanitize_filename",
    "save_snapshot",
    "to_brief",
    "to_out",
]
