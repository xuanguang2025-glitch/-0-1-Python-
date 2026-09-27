"""主键 ID 生成工具。

全库主键统一 `String(36)` + `uuid4()` 字符串，保证 SQLite / PostgreSQL 可移植
（见 docs/ARCHITECTURE.md §1.3 可移植性红线）。
"""

from __future__ import annotations

import uuid


def new_uuid() -> str:
    """生成新的 uuid4 字符串（36 字符）。"""
    return str(uuid.uuid4())


def short_id(length: int = 12) -> str:
    """生成短随机 ID（用于测试用例 id、临时文件名等非主键场景）。"""
    return uuid.uuid4().hex[:length]


def is_uuid(value: str) -> bool:
    """判断字符串是否为合法 UUID 格式（用于路径参数预校验）。"""
    try:
        uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return False
    return True
