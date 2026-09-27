"""统计端点（`docs/API.md` §2.12，7 条路由）。"""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import Response

from app.core.deps import CurrentUser, DbSession
from app.core.response import ResponseModel, success_response
from app.schemas.progress import HeatmapOut
from app.schemas.statistics import (
    CategoryStatsOut,
    RankingOut,
    ReportOut,
    StatisticsOverviewOut,
    TrendOut,
)
from app.services import statistics_service

router = APIRouter(prefix="/statistics", tags=["statistics"])


@router.get("/overview", response_model=ResponseModel[StatisticsOverviewOut], summary="学习数据总览")
def get_overview(db: DbSession, current_user: CurrentUser) -> dict:
    """总学习时长 / 解题数 / 提交数 / 正确率 / 连续天数 / 经验 / 等级 / 名次。"""
    return success_response(statistics_service.overview(db, current_user))


@router.get("/trend", response_model=ResponseModel[TrendOut], summary="学习趋势")
def get_trend(
    db: DbSession,
    current_user: CurrentUser,
    days: int = Query(default=30, ge=1, le=365, description="统计天数，支持 7/30/90 等"),
    metric: str = Query(default="submissions", pattern="^(submissions|accepted|minutes)$"),
) -> dict:
    """学习时长 / 答题趋势（按日聚合，支持 7/30/90 天切换）。"""
    return success_response(statistics_service.trend(db, current_user, days=days, metric=metric))


@router.get("/categories", response_model=ResponseModel[CategoryStatsOut], summary="分类正确率")
def get_categories(db: DbSession, current_user: CurrentUser) -> dict:
    """各题目分类的已解决 / 总数 / 得分。"""
    return success_response(statistics_service.categories(db, current_user))


@router.get("/heatmap", response_model=ResponseModel[HeatmapOut], summary="活跃度热力图")
def get_heatmap(
    db: DbSession,
    current_user: CurrentUser,
    days: int = Query(default=180, ge=1, le=365),
) -> dict:
    """按日聚合活跃次数与学习分钟（供热力图使用）。"""
    return success_response(statistics_service.heatmap(db, current_user, days=days))


@router.get("/report", response_model=ResponseModel[ReportOut], summary="周报 / 月报")
def get_report(
    db: DbSession,
    current_user: CurrentUser,
    period: str = Query(default="week", pattern="^(week|month)$"),
) -> dict:
    """生成周期报告：摘要 / 亮点 / 薄弱知识点 / 推荐。"""
    return success_response(statistics_service.report(db, current_user, period=period))


@router.get("/export", summary="导出学习数据")
def export_data(
    db: DbSession,
    current_user: CurrentUser,
    type: str = Query(default="report", pattern="^(report|submissions|code)$"),
    format: str = Query(default="md", pattern="^(md|csv|json)$"),
) -> Response:
    """导出报告 / 提交记录 / 代码（文件流，带 Content-Disposition）。"""
    filename, content_type, payload = statistics_service.export(db, current_user, export_type=type, fmt=format)
    return Response(
        content=payload,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/ranking", response_model=ResponseModel[RankingOut], summary="我的名次")
def get_ranking(db: DbSession, current_user: CurrentUser) -> dict:
    """**只返回本人名次**，不暴露任何他人信息。"""
    return success_response(statistics_service.ranking(db, current_user))
