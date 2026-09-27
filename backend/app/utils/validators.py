"""通用校验器：文件路径、代码大小、上传文件、JSON 结构。

安全相关：本地执行器与项目文件编辑都必须先过 `validate_relative_path()`，
防止 `../` 路径遍历。
"""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath

from fastapi import UploadFile

from app.core.constants import (
    ALLOWED_FILE_EXTENSIONS,
    AVATAR_MAX_BYTES,
    AVATAR_MIME_TYPES,
    IMPORT_MAX_BYTES,
    MAX_CODE_BYTES,
)
from app.core.errors import AppError, ErrorCode

_WINDOWS_DRIVE_RE = r"^[A-Za-z]:"
_ABSOLUTE_PREFIXES = ("/", "\\")


def validate_relative_path(path: str, *, allow_hidden: bool = False) -> str:
    """校验并返回安全的相对路径（禁止绝对路径、盘符、`..` 与隐藏目录）。

    Args:
        path: 用户提供的文件路径，如 `utils/helper.py`。
        allow_hidden: 是否允许以 `.` 开头的路径段。

    Returns:
        规范化后的相对路径（POSIX 分隔符）。

    Raises:
        AppError: 路径非法时抛 `INVALID_PATH`。
    """
    raw = (path or "").strip()
    if not raw:
        raise AppError(code=ErrorCode.INVALID_PATH, message="文件路径不能为空")
    if raw.startswith(_ABSOLUTE_PREFIXES) or (len(raw) > 1 and raw[1] == ":"):
        raise AppError(code=ErrorCode.INVALID_PATH, message="文件路径必须为相对路径", details=raw)
    if ".." in PurePosixPath(raw.replace("\\", "/")).parts:
        raise AppError(code=ErrorCode.INVALID_PATH, message="文件路径不允许包含 ..", details=raw)
    if "\x00" in raw:
        raise AppError(code=ErrorCode.INVALID_PATH, message="文件路径包含非法字符", details=raw)

    normalized = PurePosixPath(raw.replace("\\", "/"))
    if not allow_hidden and any(part.startswith(".") for part in normalized.parts):
        raise AppError(code=ErrorCode.INVALID_PATH, message="不允许访问隐藏目录", details=raw)
    return normalized.as_posix()


def validate_file_extension(filename: str, allowed: tuple[str, ...] = ALLOWED_FILE_EXTENSIONS) -> str:
    """校验文件扩展名是否在白名单内。"""
    suffix = Path(filename or "").suffix.lower()
    if suffix not in allowed:
        raise AppError(
            code=ErrorCode.INVALID_FILE_TYPE,
            message=f"不支持的文件类型：{suffix or '(无扩展名)'}",
            details={"allowed": list(allowed)},
        )
    return suffix


def validate_code_size(code: str, *, limit: int = MAX_CODE_BYTES) -> str:
    """校验代码体积（按 UTF-8 字节计），超限抛 `FILE_TOO_LARGE`。"""
    size = len((code or "").encode("utf-8"))
    if size > limit:
        raise AppError(
            code=ErrorCode.FILE_TOO_LARGE,
            message=f"代码体积超限（{size} / {limit} 字节）",
        )
    return code


async def validate_upload(
    file: UploadFile,
    *,
    max_bytes: int = IMPORT_MAX_BYTES,
    allowed_types: tuple[str, ...] | None = None,
    allowed_extensions: tuple[str, ...] = ALLOWED_FILE_EXTENSIONS,
) -> bytes:
    """读取并校验上传文件，返回文件内容字节。

    Args:
        file: FastAPI 上传文件对象。
        max_bytes: 大小上限。
        allowed_types: MIME 白名单（头像场景传入图片类型）。
        allowed_extensions: 扩展名白名单。

    Returns:
        文件内容字节。

    Raises:
        AppError: 类型或大小不合法。
    """
    filename = file.filename or ""
    validate_file_extension(filename, allowed_extensions)
    if allowed_types and file.content_type and file.content_type not in allowed_types:
        raise AppError(
            code=ErrorCode.INVALID_FILE_TYPE,
            message=f"不支持的文件格式：{file.content_type}",
            details={"allowed": list(allowed_types)},
        )

    content = await file.read()
    if len(content) > max_bytes:
        raise AppError(
            code=ErrorCode.FILE_TOO_LARGE,
            message=f"文件过大（{len(content)} / {max_bytes} 字节）",
        )
    return content


def validate_avatar(file: UploadFile) -> tuple[str, ...]:
    """返回头像上传的校验参数元组 `(max_bytes, mime_types)` 供调用方使用。"""
    return AVATAR_MAX_BYTES, AVATAR_MIME_TYPES


def clamp_int(value: int | None, default: int, low: int, high: int) -> int:
    """把整数限制在 `[low, high]` 区间，空值返回默认值。"""
    if value is None:
        return default
    return max(low, min(high, int(value)))


def is_safe_filename(filename: str) -> bool:
    """判断文件名是否仅包含安全字符（不含路径分隔符与控制字符）。"""
    if not filename or len(filename) > 200:
        return False
    if os.sep in filename or (os.altsep and os.altsep in filename):
        return False
    return all(ord(ch) >= 32 and ch not in '<>:"|?*' for ch in filename)
