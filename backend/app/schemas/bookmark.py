"""收藏 / 代码片段 Schema（`docs/API.md` §2.17）。"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.common import IdStr, ORMModel, StrictModel


class BookmarkCreateRequest(StrictModel):
    """新建收藏请求体。"""

    kind: str = Field(default="problem", description="problem/lesson/project/snippet/challenge")
    ref_id: IdStr | None = None
    title: str = Field(default="", max_length=200)
    description: str | None = Field(default=None, max_length=500)
    code_snippet: str | None = Field(default=None, max_length=100_000)
    language: str = "python"
    collection: str = Field(default="default", max_length=50)
    tags: list[str] = Field(default_factory=list, max_length=20)


class BookmarkUpdateRequest(StrictModel):
    """更新收藏请求体。"""

    title: str | None = Field(default=None, max_length=200)
    note: str | None = Field(default=None, max_length=2000, description="映射到 description 字段")
    collection: str | None = Field(default=None, max_length=50)
    tags: list[str] | None = None


class BookmarkOut(ORMModel):
    """收藏响应体。"""

    id: IdStr
    kind: str = "problem"
    ref_id: str | None = None
    title: str = ""
    description: str | None = None
    code_snippet: str | None = None
    language: str = "python"
    collection: str = "default"
    tags: list[str] = Field(default_factory=list)
    created_at: datetime | None = None


class CollectionOut(ORMModel):
    """收藏集合统计。"""

    name: str
    count: int = 0


class CollectionListOut(ORMModel):
    """集合列表响应体。"""

    collections: list[CollectionOut] = Field(default_factory=list)
