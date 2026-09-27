"""统一响应结构（`docs/API.md` §1.1）。

成功：`{"success": true, "data": ..., "message": "", "error": null}`
失败：`{"success": false, "data": null, "message": "...", "error": {"code": "...", "details": ...}}`
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """错误详情：机器可读的错误码 + 可选的补充信息。"""

    code: str = Field(..., description="错误码，见 docs/API.md §4")
    details: Any | None = Field(default=None, description="补充信息（字段错误数组 / 定位信息）")


class ResponseModel(BaseModel, Generic[T]):
    """所有接口的统一外层结构。端点用 `response_model=ResponseModel[X]` 声明。"""

    success: bool = Field(default=True, description="请求是否成功")
    data: T | None = Field(default=None, description="业务数据")
    message: str = Field(default="", description="面向用户的提示文案")
    error: ErrorDetail | None = Field(default=None, description="失败时的错误详情")

    model_config = ConfigDict(from_attributes=True)


class PageModel(BaseModel, Generic[T]):
    """分页结构：`{items, total, page, page_size, pages}`。"""

    items: list[T] = Field(default_factory=list)
    total: int = Field(default=0, description="总记录数")
    page: int = Field(default=1, description="当前页码（从 1 开始）")
    page_size: int = Field(default=20, description="每页条数")
    pages: int = Field(default=0, description="总页数")

    model_config = ConfigDict(from_attributes=True)


def success_response(data: Any = None, message: str = "") -> dict[str, Any]:
    """构造成功响应体。分页数据请配合 `build_page()` 生成的 `PageModel`。"""
    return {"success": True, "data": data, "message": message, "error": None}


def error_response(code: str, message: str, details: Any | None = None) -> dict[str, Any]:
    """构造失败响应体。"""
    return {
        "success": False,
        "data": None,
        "message": message,
        "error": {"code": code, "details": details},
    }
