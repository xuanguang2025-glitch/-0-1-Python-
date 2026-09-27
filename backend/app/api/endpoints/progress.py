"""学习进度端点（`docs/API.md` §2.11 + 看板 / 学习会话）。

路由数：11（契约 6 + 看板 1 + 单知识点读取 1 + 学习会话 3）。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession
from app.core.response import ResponseModel, success_response
from app.schemas.progress import (
    CourseProgressOut,
    HeatmapOut,
    KnowledgeMasteryOut,
    LearningDashboardOut,
    LearningSessionEndRequest,
    LearningSessionHeartbeatRequest,
    LearningSessionOut,
    LearningSessionStartRequest,
    MasteryOverviewOut,
    MasteryPracticeRequest,
    ModeOut,
    ModeUpdateRequest,
    ProgressOverviewOut,
)
from app.services import mastery_service, progress_service, session_service

router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("", response_model=ResponseModel[ProgressOverviewOut], summary="学习进度总览")
def get_progress(db: DbSession, current_user: CurrentUser) -> dict:
    """进度总览：各阶段完成度 + 汇总 + 当前阶段。"""
    return success_response(progress_service.get_overview(db, current_user))


@router.get("/dashboard", response_model=ResponseModel[LearningDashboardOut], summary="学习看板")
def get_dashboard(db: DbSession, current_user: CurrentUser) -> dict:
    """学习看板：今日/本周时长、连续天数、等级 XP、课程完成度、题目与项目数。"""
    return success_response(progress_service.get_dashboard(db, current_user))


@router.get(
    "/courses/{course_id}",
    response_model=ResponseModel[CourseProgressOut],
    summary="单课程进度明细",
)
def get_course_progress(course_id: str, db: DbSession, current_user: CurrentUser) -> dict:
    """单课程进度：完成课时 id 列表 + 百分比 + 继续学习课时。"""
    return success_response(progress_service.get_course_progress(db, current_user, course_id))


@router.get("/mastery", response_model=ResponseModel[MasteryOverviewOut], summary="知识点掌握度")
def get_mastery(
    db: DbSession,
    current_user: CurrentUser,
    parent_topic_id: Annotated[str | None, Query(description="按父知识点过滤")] = None,
) -> dict:
    """我的知识点掌握度列表（含薄弱知识点与平均分）。"""
    return success_response(mastery_service.list_mastery(db, current_user, parent_topic_id))


@router.get(
    "/mastery/{topic_id}",
    response_model=ResponseModel[KnowledgeMasteryOut],
    summary="单知识点掌握度",
)
def get_topic_mastery(topic_id: str, db: DbSession, current_user: CurrentUser) -> dict:
    """读取单个知识点掌握度（无记录返回零值）。"""
    return success_response(mastery_service.get_topic_mastery(db, current_user, topic_id))


@router.post(
    "/mastery/{topic_id}",
    response_model=ResponseModel[KnowledgeMasteryOut],
    summary="更新知识点掌握度",
)
def practice_mastery(
    topic_id: str,
    payload: MasteryPracticeRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """按一次答题结果更新掌握度（SM-2 简化算法）。"""
    return success_response(mastery_service.apply_practice(db, current_user, topic_id, payload.correct))


@router.get("/heatmap", response_model=ResponseModel[HeatmapOut], summary="学习热力图")
def get_heatmap(
    db: DbSession,
    current_user: CurrentUser,
    days: Annotated[int, Query(ge=1, le=366, description="统计天数")] = 180,
) -> dict:
    """学习热力图（按天聚合会话次数与分钟数）。"""
    return success_response(progress_service.get_heatmap(db, current_user, days))


@router.put("/mode", response_model=ResponseModel[ModeOut], summary="切换学习模式")
def set_mode(payload: ModeUpdateRequest, db: DbSession, current_user: CurrentUser) -> dict:
    """切换学习模式（写入 profile.learning_mode）。"""
    return success_response(progress_service.set_mode(db, current_user, payload.learning_mode), message="模式已切换")


@router.post("/sessions", response_model=ResponseModel[LearningSessionOut], summary="开始学习会话")
def start_session(
    payload: LearningSessionStartRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """开始一次学习会话（用于时长统计与热力图）。"""
    return success_response(session_service.start_session(db, current_user, payload))


@router.post(
    "/sessions/{session_id}/heartbeat",
    response_model=ResponseModel[LearningSessionOut],
    summary="学习会话心跳",
)
def session_heartbeat(
    session_id: str,
    payload: LearningSessionHeartbeatRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """会话心跳：累加时长 / 行为数 / 经验（仅本人，越权返回 403）。"""
    return success_response(session_service.heartbeat(db, current_user, session_id, payload))


@router.post(
    "/sessions/{session_id}/end",
    response_model=ResponseModel[LearningSessionOut],
    summary="结束学习会话",
)
def end_session(
    session_id: str,
    payload: LearningSessionEndRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """结束会话并结算时长（仅本人，越权返回 403）。"""
    return success_response(session_service.end_session(db, current_user, session_id, payload))
