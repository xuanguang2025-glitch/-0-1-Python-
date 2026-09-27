"""模型通用 Mixin 汇总（DATABASE.md §0 约定的文件名）。

实现位于 `app.db.base`（与 `DeclarativeBase` 同处，避免循环导入）；
本模块仅做再导出，保证「一个 Mixin 只有一处实现」。
"""

from app.db.base import (
    Base,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDPkMixin,
    utc_now,
)

__all__ = ["Base", "SoftDeleteMixin", "TimestampMixin", "UUIDPkMixin", "utc_now"]
