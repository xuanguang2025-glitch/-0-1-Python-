"""Schema 公共基类与通用字段类型（Pydantic v2）。

约定：
- 所有响应模型继承 `ORMModel`（`from_attributes=True`），可直接 `model_validate(orm_obj)`；
- 分页统一 `PageModel[T]`（定义在 `app.core.response`，此处再导出便于端点引用）；
- 所有对外展示的 id 一律字符串（UUID 文本）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from app.core.response import ErrorDetail, PageModel, ResponseModel

T = TypeVar("T")

#: 对外 id 类型（uuid4 字符串）
IdStr = Annotated[str, Field(min_length=1, max_length=64)]


class ORMModel(BaseModel):
    """可作为 ORM 对象映射源的基类。"""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, str_strip_whitespace=True)


class StrictModel(BaseModel):
    """请求体基类：禁止未声明字段，避免前端误传被静默忽略。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class MessageOut(ORMModel):
    """通用「操作成功」响应体（data 为 null 时可省略）。"""

    message: str = Field(default="", description="提示文案")


class IdOut(ORMModel):
    """仅返回新建资源 id 的响应体。"""

    id: IdStr


class CountOut(ORMModel):
    """计数类响应体，如未读通知数。"""

    count: int = Field(default=0, ge=0)


class OkOut(ORMModel):
    """布尔结果响应体。"""

    ok: bool = Field(default=True)


class PaginationQuery(ORMModel):
    """分页查询参数（与 `app.core.pagination.PageParams` 对齐，供文档/前端参考）。"""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    sort: str = Field(default="-created_at")


def as_list(value: Any) -> list[Any]:
    """把 None / 单值 / 列表统一为列表（用于 JSON 字段宽松解析）。"""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def ensure_utc(value: datetime | None) -> datetime | None:
    """把 datetime 统一为带时区的 UTC（供 Schema 校验器复用）。"""
    if value is None:
        return None
    if value.tzinfo is None:
        from datetime import timezone

        return value.replace(tzinfo=timezone.utc)
    return value


__all__ = [
    "CountOut",
    "ErrorDetail",
    "Generic",
    "IdOut",
    "IdStr",
    "MessageOut",
    "ORMModel",
    "OkOut",
    "PageModel",
    "PaginationQuery",
    "ResponseModel",
    "StrictModel",
    "T",
    "as_list",
    "ensure_utc",
]
