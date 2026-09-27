"""SQLAlchemy 声明式基类与通用 Mixin。

可移植性红线（docs/ARCHITECTURE.md §1.3）：
1. 主键统一 `String(36)` + `uuid4()` 字符串（不用 PG 的 UUID 类型）；
2. 时间统一 `DateTime(timezone=True)`，值一律 UTC；
3. 数组/字典统一 `sa.JSON`（SQLite 落 TEXT），关联表显式建模，不用 ARRAY。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, MetaData, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.utils.ids import new_uuid

# 统一约束命名规范：让 SQLite / PostgreSQL / Alembic 生成一致的约束名
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def utc_now() -> datetime:
    """返回当前 UTC 时间（带时区）。"""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """全库声明式基类。"""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    def __repr__(self) -> str:
        """统一调试输出：`ClassName(id=...)`。"""
        identifier = getattr(self, "id", None)
        return f"{self.__class__.__name__}(id={identifier!r})"

    def to_dict(self, *, exclude: set[str] | None = None) -> dict[str, Any]:
        """把实例转换为普通字典（不含关系属性），便于日志与审计快照。"""
        skip = exclude or set()
        return {
            column.key: getattr(self, column.key)
            for column in self.__table__.columns
            if column.key not in skip
        }


class UUIDPkMixin:
    """主键 Mixin：`id CHAR(36)`，默认 uuid4 字符串。"""

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_uuid,
        nullable=False,
        doc="主键（uuid4 字符串，跨 SQLite/PostgreSQL 可移植）",
    )


class TimestampMixin:
    """时间戳 Mixin：`created_at` / `updated_at`（UTC，自动维护）。"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        doc="创建时间（UTC）",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
        doc="更新时间（UTC）",
    )


class SoftDeleteMixin:
    """软删除 Mixin：`deleted_at` 为空表示未删除。"""

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        doc="软删除时间（UTC），NULL 表示未删除",
    )

    @property
    def is_deleted(self) -> bool:
        """是否已被软删除。"""
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        """标记为已删除（不物理删除记录）。"""
        self.deleted_at = utc_now()

    def restore(self) -> None:
        """恢复被软删除的记录。"""
        self.deleted_at = None
