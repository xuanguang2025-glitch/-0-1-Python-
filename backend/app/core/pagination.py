"""分页与排序工具（`docs/API.md` §1.2）。

- `page` 从 1 开始，`page_size` 自动 clamp 到 `[1, 100]`；
- `sort` 走白名单映射，禁止拼接用户字符串，防止注入；
- 统一由 `build_page()` 生成 `PageModel`。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.response import PageModel

# 排序字段白名单：键为对外暴露的 sort 值，值为 ORM 列解析函数
SORT_WHITELIST: dict[str, str] = {
    "created_at": "created_at",
    "-created_at": "-created_at",
    "updated_at": "updated_at",
    "-updated_at": "-updated_at",
    "difficulty": "difficulty",
    "acceptance_rate": "acceptance_rate",
    "level": "level",
    "order_index": "order_index",
    "-order_index": "-order_index",
    "score": "score",
    "-score": "-score",
    "xp": "xp",
    "-xp": "-xp",
    "stage_no": "stage_no",
}

# 难度排序权重（easy < medium < hard < expert）
DIFFICULTY_WEIGHT: dict[str, int] = {"easy": 1, "medium": 2, "hard": 3, "expert": 4}


@dataclass(slots=True)
class PageParams:
    """分页参数容器。"""

    page: int = 1
    page_size: int = 20
    sort: str = "-created_at"

    @property
    def offset(self) -> int:
        """SQL 偏移量。"""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """SQL 取条数。"""
        return self.page_size


def normalize_page_params(page: int = 1, page_size: int = 20, sort: str | None = None) -> PageParams:
    """把用户输入的分页参数规范化（clamp + 排序白名单过滤）。"""
    settings = get_settings()
    safe_page = max(1, int(page or 1))
    safe_size = int(page_size or settings.default_page_size)
    safe_size = max(1, min(settings.max_page_size, safe_size))
    safe_sort = sort if sort in SORT_WHITELIST else "-created_at"
    return PageParams(page=safe_page, page_size=safe_size, sort=safe_sort)


def build_page(items: Sequence[Any], total: int, params: PageParams) -> PageModel[Any]:
    """按总数与分页参数组装 `PageModel`。"""
    pages = (int(total) + params.page_size - 1) // params.page_size if params.page_size else 0
    return PageModel(
        items=list(items),
        total=int(total),
        page=params.page,
        page_size=params.page_size,
        pages=pages,
    )


def apply_sort(stmt: Select[tuple[Any, ...]], sort: str, column_of: Callable[[str], Any]) -> Select[tuple[Any, ...]]:
    """按白名单给查询加排序；`column_of` 负责把列名映射为 ORM 列。

    Args:
        stmt: 待排序的 SELECT 语句。
        sort: 形如 `-created_at` 的排序键（必须在白名单内）。
        column_of: 列名 → ORM 列 的解析函数，未知列名返回 None 时忽略排序。

    Returns:
        附加了 ORDER BY 的语句（未知字段则原样返回）。
    """
    if sort not in SORT_WHITELIST:
        return stmt
    descending = sort.startswith("-")
    column_name = sort.lstrip("-")
    column = column_of(column_name)
    if column is None:
        return stmt
    return stmt.order_by(column.desc() if descending else column.asc())


def paginate(
    db: Session,
    stmt: Select[tuple[Any, ...]],
    params: PageParams,
    *,
    count_stmt: Select[tuple[int]] | None = None,
) -> tuple[list[Any], int]:
    """执行分页查询，返回 `(当前页数据, 总条数)`。

    Args:
        db: 数据库会话。
        stmt: 基础查询语句（不含 offset/limit）。
        params: 分页参数。
        count_stmt: 可选的计数语句；复杂查询（含 join/distinct）时传入以提升准确性。

    Returns:
        元组 `(items, total)`。
    """
    if count_stmt is None:
        count_stmt = select(func.count()).select_from(stmt.subquery())
    total = int(db.scalar(count_stmt) or 0)
    items = list(db.scalars(stmt.offset(params.offset).limit(params.limit)).all())
    return items, total
