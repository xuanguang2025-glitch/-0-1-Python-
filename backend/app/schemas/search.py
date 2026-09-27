"""全局搜索 Schema（`docs/API.md` §2.16）。"""

from __future__ import annotations

from pydantic import Field

from app.schemas.common import ORMModel


class SearchItem(ORMModel):
    """单条搜索结果。"""

    id: str
    title: str
    subtitle: str = ""
    url: str = ""
    highlight: str = ""


class SearchGroup(ORMModel):
    """按类型分组的结果。"""

    type: str = "course"
    label: str = ""
    items: list[SearchItem] = Field(default_factory=list)


class SearchOut(ORMModel):
    """搜索结果聚合体。"""

    groups: list[SearchGroup] = Field(default_factory=list)
    total: int = 0
    keyword: str = ""


class SuggestItem(ORMModel):
    """搜索联想项。"""

    text: str
    type: str = "keyword"
    url: str = ""


class SuggestOut(ORMModel):
    """联想结果。"""

    suggestions: list[SuggestItem] = Field(default_factory=list)
