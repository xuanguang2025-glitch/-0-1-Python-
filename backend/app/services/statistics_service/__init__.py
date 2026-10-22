"""统计报表服务（`docs/API.md` §2.12）。

所有聚合一律走 SQL（`func.count/sum/avg + group_by`），**不在 Python 里全表遍历**。
排行榜 / 名次只返回本人名次，绝不暴露他人隐私字段。

本包按职责拆分，`__init__` 统一重导出公共 API（`from app.services import statistics_service`）。
"""

from __future__ import annotations

from .activity import heatmap, trend
from .categories import categories
from .common import (
    ACCEPTED,
    TREND_METRICS,
)
from .common import (
    daily_map as _daily_map,
)
from .common import (
    mastery_topics as _mastery_topics,
)
from .common import (
    rank_stats as _rank_stats,
)
from .common import (
    solved_count as _solved_count,
)
from .common import (
    submit_stats as _submit_stats,
)
from .common import (
    total_seconds as _total_seconds,
)
from .common import (
    window as _window,
)
from .export import dump as _dump
from .export import export
from .export import report_markdown as _report_markdown
from .overview import overview, ranking
from .report import build_recommendations as _build_recommendations
from .report import report

__all__ = [
    "overview",
    "ranking",
    "trend",
    "heatmap",
    "categories",
    "report",
    "export",
]
