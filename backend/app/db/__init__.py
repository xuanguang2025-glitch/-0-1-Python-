"""数据层：声明式基类、引擎/会话、建表、种子数据。

注意：本包 `__init__` 刻意不导入 `session`，避免导入模型时提前创建 Engine；
需要会话时显式 `from app.db.session import SessionLocal`。
"""

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPkMixin, utc_now

__all__ = ["Base", "SoftDeleteMixin", "TimestampMixin", "UUIDPkMixin", "utc_now"]
