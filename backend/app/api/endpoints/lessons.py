"""课时端点（`docs/API.md` §2.4，6 条路由）。"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession, OptionalUser
from app.core.response import ResponseModel, success_response
from app.schemas.course import (
    LessonBrief,
    LessonCompleteOut,
    LessonCompleteRequest,
    LessonDetail,
    LessonProgressRequest,
    LearningProgressOut,
    QuizResultOut,
    QuizSubmitRequest,
    TopicOut,
)
from app.services import lesson_service

router = APIRouter(prefix="/lessons", tags=["lessons"])


@router.get("/{lesson_id}", response_model=ResponseModel[LessonDetail], summary="课时详情")
def get_lesson(lesson_id: str, db: DbSession, viewer: OptionalUser = None) -> dict:
    """课时详情：正文 + 所属课程/章节定位 + 上一节/下一节 + 完整章节目录 + 知识点 + 我的进度。"""
    lesson = lesson_service.get_lesson(db, lesson_id)
    return success_response(lesson_service.build_lesson_detail(db, lesson, viewer))


@router.post(
    "/{lesson_id}/progress",
    response_model=ResponseModel[LearningProgressOut],
    summary="上报课时进度",
)
def update_progress(
    lesson_id: str,
    payload: LessonProgressRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """上报学习进度（写 learning_progress + 同步报名进度）。"""
    lesson = lesson_service.get_lesson(db, lesson_id)
    return success_response(
        lesson_service.update_progress(db, current_user, lesson, payload), message="进度已保存"
    )


@router.post(
    "/{lesson_id}/complete",
    response_model=ResponseModel[LessonCompleteOut],
    summary="标记课时完成",
)
def complete_lesson(
    lesson_id: str,
    payload: LessonCompleteRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """标记完成：写进度 + 发放 XP（可能升级）+ 触发掌握度 + 尝试解锁成就。"""
    lesson = lesson_service.get_lesson(db, lesson_id)
    result = lesson_service.complete_lesson(db, current_user, lesson, payload.time_spent_seconds)
    return success_response(result, message="已完成本节")


@router.post("/{lesson_id}/quiz", response_model=ResponseModel[QuizResultOut], summary="随堂练习判分")
def submit_quiz(
    lesson_id: str,
    payload: QuizSubmitRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """随堂练习判分（返回逐题结果）。"""
    lesson = lesson_service.get_lesson(db, lesson_id)
    return success_response(lesson_service.submit_quiz(db, lesson, payload))


@router.get("/{lesson_id}/next", response_model=ResponseModel[LessonBrief | None], summary="下一节课时")
def get_next_lesson(lesson_id: str, db: DbSession, current_user: CurrentUser) -> dict:
    """课程内下一节课时（无后继返回 null）。"""
    lesson = lesson_service.get_lesson(db, lesson_id)
    return success_response(lesson_service.get_next_lesson(db, lesson, current_user))


@router.get("/{lesson_id}/topics", response_model=ResponseModel[list[TopicOut]], summary="课时知识点")
def list_topics(lesson_id: str, db: DbSession, viewer: OptionalUser = None) -> dict:
    """课时关联知识点（含我的掌握度）。"""
    lesson = lesson_service.get_lesson(db, lesson_id)
    return success_response(lesson_service.list_lesson_topics(db, lesson, viewer))
