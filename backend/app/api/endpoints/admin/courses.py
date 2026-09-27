"""管理端端点 · 课程 / 章节 / 课时。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Query, Request

from app.core.deps import AdminUser, DbSession, Pagination
from app.core.pagination import build_page
from app.core.response import PageModel, ResponseModel, success_response
from app.schemas.admin import AdminChapterIn, AdminCourseIn, AdminLessonIn
from app.schemas.course import ChapterOut, CourseBrief, LessonBrief
from app.services import admin_service

from ._common import meta

router = APIRouter()


@router.get("/courses", response_model=ResponseModel[PageModel[CourseBrief]], summary="课程列表")
def list_courses(
    db: DbSession, admin: AdminUser, pagination: Pagination, q: str | None = Query(default=None)
) -> dict:
    """课程列表。"""
    items, total = admin_service.list_courses(db, pagination, q=q)
    return success_response(build_page([CourseBrief.model_validate(c) for c in items], total, pagination))


@router.post("/courses", response_model=ResponseModel[CourseBrief], summary="新建课程")
def create_course(payload: AdminCourseIn, request: Request, db: DbSession, admin: AdminUser) -> dict:
    """新建课程。"""
    course = admin_service.create_course(db, admin, payload.model_dump(), meta(request))
    return success_response(CourseBrief.model_validate(course), message="课程已创建")


@router.patch("/courses/{course_id}", response_model=ResponseModel[CourseBrief], summary="更新课程")
def update_course(
    course_id: str, request: Request, db: DbSession, admin: AdminUser, payload: dict[str, Any] = Body(...)
) -> dict:
    """更新课程。"""
    course = admin_service.update_course(db, admin, course_id, payload, meta(request))
    return success_response(CourseBrief.model_validate(course), message="课程已更新")


@router.delete("/courses/{course_id}", response_model=ResponseModel[None], summary="删除课程")
def delete_course(course_id: str, request: Request, db: DbSession, admin: AdminUser) -> dict:
    """删除课程（级联）。"""
    admin_service.delete_course(db, admin, course_id, meta(request))
    return success_response(None, message="课程已删除")


@router.post("/chapters", response_model=ResponseModel[ChapterOut], summary="新建章节")
def create_chapter(payload: AdminChapterIn, request: Request, db: DbSession, admin: AdminUser) -> dict:
    """新建章节。"""
    chapter = admin_service.create_chapter(db, admin, payload.model_dump(), meta(request))
    return success_response(ChapterOut.model_validate(chapter), message="章节已创建")


@router.patch("/chapters/{chapter_id}", response_model=ResponseModel[ChapterOut], summary="更新章节")
def update_chapter(
    chapter_id: str, request: Request, db: DbSession, admin: AdminUser, payload: dict[str, Any] = Body(...)
) -> dict:
    """更新章节。"""
    chapter = admin_service.update_chapter(db, admin, chapter_id, payload, meta(request))
    return success_response(ChapterOut.model_validate(chapter), message="章节已更新")


@router.delete("/chapters/{chapter_id}", response_model=ResponseModel[None], summary="删除章节")
def delete_chapter(chapter_id: str, request: Request, db: DbSession, admin: AdminUser) -> dict:
    """删除章节。"""
    admin_service.delete_chapter(db, admin, chapter_id, meta(request))
    return success_response(None, message="章节已删除")


@router.post("/lessons", response_model=ResponseModel[LessonBrief], summary="新建课时")
def create_lesson(payload: AdminLessonIn, request: Request, db: DbSession, admin: AdminUser) -> dict:
    """新建课时（含知识点关联）。"""
    lesson = admin_service.create_lesson(db, admin, payload.model_dump(), meta(request))
    return success_response(LessonBrief.model_validate(lesson), message="课时已创建")


@router.patch("/lessons/{lesson_id}", response_model=ResponseModel[LessonBrief], summary="更新课时")
def update_lesson(
    lesson_id: str, request: Request, db: DbSession, admin: AdminUser, payload: dict[str, Any] = Body(...)
) -> dict:
    """更新课时。"""
    lesson = admin_service.update_lesson(db, admin, lesson_id, payload, meta(request))
    return success_response(LessonBrief.model_validate(lesson), message="课时已更新")


@router.delete("/lessons/{lesson_id}", response_model=ResponseModel[None], summary="删除课时")
def delete_lesson(lesson_id: str, request: Request, db: DbSession, admin: AdminUser) -> dict:
    """删除课时。"""
    admin_service.delete_lesson(db, admin, lesson_id, meta(request))
    return success_response(None, message="课时已删除")
