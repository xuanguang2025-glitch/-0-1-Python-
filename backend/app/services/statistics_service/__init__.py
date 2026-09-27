"""统计报表服务（`docs/API.md` §2.12）。

所有聚合一律走 SQL（`func.count/sum/avg + group_by`），**不在 Python 里全表遍历**。
排行榜 / 名次只返回本人名次，绝不暴露他人隐私字段。

本包按职责拆分，`__init__` 统一重导出公共 API（`from app.services import statistics_service`）。
"""

from __future__ import annotations

from .common import (
    ACCEPTED,
    TREND_METRICS,
    daily_map as _daily_map,
    mastery_topics as _mastery_topics,
    rank_stats as _rank_stats,
    solved_count as _solved_count,
    submit_stats as _submit_stats,
    total_seconds as _total_seconds,
    window as _window,
)
from .overview import overview, ranking
from .activity import heatmap, trend
from .categories import categories
from .report import build_recommendations as _build_recommendations, report
from .export import export, dump as _dump, report_markdown as _report_markdown

__all__ = [
    "overview",
    "ranking",
    "trend",
    "heatmap",
    "categories",
    "report",
    "export",
]
