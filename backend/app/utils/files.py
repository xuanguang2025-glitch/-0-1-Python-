"""文件与临时目录工具（跨平台）。

- 临时目录统一 `tempfile.mkdtemp()`，退出即清理；
- ZIP 打包用于项目/代码导出（跨平台，Windows 亦可）。
"""

from __future__ import annotations

import io
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable, Mapping

from app.utils.validators import validate_relative_path


def make_temp_dir(prefix: str = "plab_") -> Path:
    """创建独立临时目录（调用方负责清理）。"""
    return Path(tempfile.mkdtemp(prefix=prefix))


def cleanup_dir(path: str | Path) -> None:
    """递归删除目录，任何异常都忽略（用于 finally 清理）。"""
    try:
        shutil.rmtree(path, ignore_errors=True)
    except Exception:  # noqa: BLE001 - 清理失败不影响主流程
        pass


def write_files(base_dir: str | Path, files: Mapping[str, str]) -> list[Path]:
    """把 `{相对路径: 内容}` 落盘到临时目录，返回写入的绝对路径列表。"""
    root = Path(base_dir)
    written: list[Path] = []
    for rel_path, content in files.items():
        safe_path = validate_relative_path(rel_path)
        target = root / safe_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content or "", encoding="utf-8")
        written.append(target)
    return written


def read_text(path: str | Path, default: str = "") -> str:
    """读取文本文件，失败返回默认值。"""
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError:
        return default


def build_zip(files: Mapping[str, str], *, extra: Mapping[str, bytes] | None = None) -> bytes:
    """把文件字典打包为 ZIP 二进制内容（用于导出下载）。

    Args:
        files: `{相对路径: 文本内容}`。
        extra: 额外的二进制文件 `{相对路径: 字节内容}`。

    Returns:
        ZIP 文件的字节内容。
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for rel_path, content in files.items():
            archive.writestr(validate_relative_path(rel_path), content or "")
        for rel_path, payload in (extra or {}).items():
            archive.writestr(validate_relative_path(rel_path), payload)
    return buffer.getvalue()


def zip_directory(source_dir: str | Path, *, skip: Iterable[str] = ()) -> bytes:
    """把整个目录打包为 ZIP（跳过 `skip` 中的目录名）。"""
    root = Path(source_dir)
    buffer = io.BytesIO()
    skip_set = set(skip)
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for item in root.rglob("*"):
            if item.is_dir():
                continue
            if any(part in skip_set for part in item.relative_to(root).parts):
                continue
            archive.write(item, arcname=str(item.relative_to(root)))
    return buffer.getvalue()


def ensure_dir(path: str | Path) -> Path:
    """确保目录存在并返回绝对路径。"""
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    return target.resolve()


def safe_join(root: str | Path, rel_path: str) -> Path:
    """把相对路径安全地拼接到根目录，并校验结果仍在根目录内。"""
    base = Path(root).resolve()
    safe_rel = validate_relative_path(rel_path)
    target = (base / safe_rel).resolve()
    if not str(target).startswith(str(base)):
        raise ValueError(f"路径越界: {rel_path}")
    return target
