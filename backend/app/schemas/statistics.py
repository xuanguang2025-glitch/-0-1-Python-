"""统计报表 Schema（`docs/API.md` §2.12 与 §3.6 `ReportOut`）。"""

from __future__ import annotations

from datetime import date as DateType
from typing import Any

from pydantic import Field

from app.schemas.common import ORMModel


class TrendPoint(ORMModel):
    """趋势折线的单点。"""

    date: DateType
    value: float = 0


class TrendOut(ORMModel):
    """`GET /statistics/trend` 响应体。"""

    metric: str = "submissions"
    points: list[TrendPoint] = Field(default_factory=list)
    total: float = 0


class WeakTopicItem(ORMModel):
    """知识点得分项（薄弱 / 最强知识点共用）。"""

    topic_id: str
    name: str = ""
    score: float = 0.0


class StatisticsOverviewOut(ORMModel):
    """`GET /statistics/overview` 响应体。

    前 9 个字段为 `docs/API.md` 契约字段；其后为向后兼容的附加字段。
    """

    total_minutes: int = 0
    solved: int = 0
    submissions: int = 0
    accepted: int = 0
    acceptance_rate: float = 0.0
    streak_days: int = 0
    xp: int = 0
    level: int = 1
    rank_percentile: float = 0.0
    # ---- 附加字段（不破坏既有契约）----
    run_count: int = 0
    projects: int = 0
    courses: int = 0
    strongest_topic: WeakTopicItem | None = None
    weakest_topic: WeakTopicItem | None = None


class CategoryStat(ORMModel):
    """分类维度统计。"""

    category: str
    solved: int = 0
    total: int = 0
    score: float = 0.0


class CategoryStatsOut(ORMModel):
    """`GET /statistics/categories` 响应体。"""

    categories: list[CategoryStat] = Field(default_factory=list)


class ReportMetrics(ORMModel):
    """周期报告的量化指标。"""

    minutes: int = 0
    lessons: int = 0
    submissions: int = 0
    accepted: int = 0
    acceptance_rate: float = 0.0


class RecommendationItem(ORMModel):
    """学习建议。"""

    type: str = "problem"
    id: str | None = None
    title: str = ""
    reason: str = ""


class ReportOut(ORMModel):
    """`GET /statistics/report` 响应体（`docs/API.md` §3.6）。"""

    period: str = "week"
    start_date: DateType | None = None
    end_date: DateType | None = None
    summary_md: str = ""
    highlights: list[str] = Field(default_factory=list)
    metrics: ReportMetrics = Field(default_factory=ReportMetrics)
    weak_topics: list[WeakTopicItem] = Field(default_factory=list)
    recommendations: list[RecommendationItem] = Field(default_factory=list)
    degraded: bool = False


class RankingOut(ORMModel):
    """`GET /statistics/ranking`：**只返回名次，不暴露他人信息**。"""

    my_rank: int | None = None
    total_users: int = 0
    percentile: float = 0.0
    xp: int = 0


class ExportOut(ORMModel):
    """导出请求的元信息（实际返回文件流）。"""

    filename: str = ""
    content_type: str = "application/octet-stream"
    size_bytes: int = 0


class DashboardOut(ORMModel):
    """管理端仪表盘（`GET /admin/dashboard`）。"""

    users_total: int = 0
    active_today: int = 0
    submissions_today: int = 0
    acceptance_rate: float = 0.0
    ai_calls_today: int = 0
    error_rate: float = 0.0
    runner: str = "local"
    db_flavor: str = "sqlite"
    cache_backend: str = "memory"
    extra: dict[str, Any] = Field(default_factory=dict)
