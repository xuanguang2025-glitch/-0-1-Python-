"""课程端点（`docs/API.md` §2.3 + 我的课程 / 取消报名）。

路由数：9（契约 7 + 我的课程 1 + 取消报名 1）。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession, OptionalUser, Pagination
from app.core.response import PageModel, ResponseModel, success_response
from app.schemas.common import MessageOut
from app.schemas.course import (
    ChapterOut,
    CourseBrief,
    CourseDetail,
    CourseEnrollmentOut,
    LessonBrief,
    LessonDetail,
    StageOut,
)
from app.services import course_service, lesson_service

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("", response_model=ResponseModel[PageModel[CourseBrief]], summary="课程列表")
def list_courses(
    db: DbSession,
    params: Pagination,
    viewer: OptionalUser = None,
    level: Annotated[str | None, Query(description="beginner/intermediate/advanced")] = None,
    stage_no: Annotated[int | None, Query(ge=1, le=18, description="阶段序号 1..18")] = None,
    keyword: Annotated[str | None, Query(max_length=120, description="标题 / 副标题 / slug 模糊搜索")] = None,
) -> dict:
    """课程列表：支持难度 / 阶段筛选、关键词搜索、分页与排序白名单；已登录时附我的进度。"""
    page = course_service.list_courses(
        db, params, level=level, stage_no=stage_no, keyword=keyword, user=viewer
    )
    return success_response(page)


@router.get("/stages", response_model=ResponseModel[list[StageOut]], summary="18 阶段概览")
def list_stages(db: DbSession, viewer: OptionalUser = None) -> dict:
    """18 阶段路线图（含我的进度与当前阶段标记）。"""
    return success_response(course_service.list_stages(db, viewer))


@router.get("/mine", response_model=ResponseModel[PageModel[CourseBrief]], summary="我的课程")
def my_courses(db: DbSession, params: Pagination, current_user: CurrentUser) -> dict:
    """我已报名的课程（按报名时间倒序，含进度）。"""
    return success_response(course_service.my_courses(db, current_user, params))


@router.post("/{course_id}/enroll", response_model=ResponseModel[CourseEnrollmentOut], summary="报名课程")
def enroll_course(course_id: str, db: DbSession, current_user: CurrentUser) -> dict:
    """报名课程；重复报名返回 409 `ALREADY_ENROLLED`。"""
    return success_response(course_service.enroll(db, current_user, course_id), message="报名成功")


@router.delete("/{course_id}/enroll", response_model=ResponseModel[MessageOut], summary="取消报名")
def cancel_enroll(course_id: str, db: DbSession, current_user: CurrentUser) -> dict:
    """取消报名；未报名返回 404。"""
    course_service.cancel_enroll(db, current_user, course_id)
    return success_response(MessageOut(message="已取消报名"), message="已取消报名")


@router.get("/{slug}", response_model=ResponseModel[CourseDetail], summary="课程详情")
def get_course(slug: str, db: DbSession, viewer: OptionalUser = None) -> dict:
    """课程详情：含完整章节树与我的进度。"""
    course = course_service.get_course_by_slug(db, slug)
    return success_response(course_service.build_course_detail(db, course, viewer))


@router.get("/{slug}/chapters", response_model=ResponseModel[list[ChapterOut]], summary="课程章节目录")
def list_chapters(slug: str, db: DbSession, viewer: OptionalUser = None) -> dict:
    """课程章节目录（含各章节的课时列表）。"""
    course = course_service.get_course_by_slug(db, slug)
    return success_response(course_service.list_chapters(db, course, viewer))


@router.get("/{slug}/lessons", response_model=ResponseModel[list[LessonBrief]], summary="课程课时列表")
def list_lessons(slug: str, db: DbSession, viewer: OptionalUser = None) -> dict:
    """课程全部课时（扁平列表）。"""
    course = course_service.get_course_by_slug(db, slug)
    return success_response(course_service.list_lessons(db, course, viewer))


@router.get(
    "/{slug}/lessons/{lesson_id}",
    response_model=ResponseModel[LessonDetail],
    summary="课程内课时详情",
)
def get_course_lesson(slug: str, lesson_id: str, db: DbSession, viewer: OptionalUser = None) -> dict:
    """按课程 slug + 课时 id 取课时详情（含完整目录）。"""
    lesson = lesson_service.get_lesson(db, lesson_id)
    return success_response(lesson_service.build_lesson_detail(db, lesson, viewer))
