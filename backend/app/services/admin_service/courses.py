"""管理端服务 · 课程 / 章节 / 课时。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ErrorCode
from app.core.pagination import PageParams
from app.models.course import Chapter, Course, Lesson, LessonTopic, Topic
from app.models.user import User

from .common import apply_fields, audit, get_or_404, snapshot


def list_courses(db: Session, params: PageParams, q: str | None = None) -> tuple[list[Course], int]:
    """课程列表。"""
    conditions: list[Any] = []
    if q:
        conditions.append(Course.title.ilike(f"%{q.strip()}%"))
    total = int(db.scalar(select(func.count()).select_from(Course).where(*conditions)) or 0)
    rows = list(
        db.scalars(
            select(Course)
            .where(*conditions)
            .order_by(Course.stage_no.asc())
            .offset(params.offset)
            .limit(params.limit)
        ).all()
    )
    return rows, total


def create_course(db: Session, actor: User, payload: dict[str, Any], meta: dict[str, Any]) -> Course:
    """新建课程。"""
    course = Course(**payload)
    course.order_index = int(payload.get("stage_no") or course.order_index or 0)
    db.add(course)
    db.flush()
    audit(db, actor, "admin.course.create", "course", course.id, after={"slug": course.slug}, meta=meta)
    db.commit()
    db.refresh(course)
    return course


def update_course(
    db: Session, actor: User, course_id: str, payload: dict[str, Any], meta: dict[str, Any]
) -> Course:
    """更新课程。"""
    course = get_or_404(db, Course, course_id, ErrorCode.COURSE_NOT_FOUND, "课程不存在")
    before = snapshot(course, ["title", "level", "is_published"])
    apply_fields(course, payload)
    audit(
        db, actor, "admin.course.update", "course", course.id,
        before=before, after=snapshot(course, ["title", "level", "is_published"]), meta=meta,
    )
    db.commit()
    db.refresh(course)
    return course


def delete_course(db: Session, actor: User, course_id: str, meta: dict[str, Any]) -> None:
    """删除课程（级联章节/课时）。"""
    course = get_or_404(db, Course, course_id, ErrorCode.COURSE_NOT_FOUND, "课程不存在")
    before = {"slug": course.slug}
    db.delete(course)
    audit(db, actor, "admin.course.delete", "course", course_id, before=before, meta=meta)
    db.commit()


def create_chapter(db: Session, actor: User, payload: dict[str, Any], meta: dict[str, Any]) -> Chapter:
    """新建章节。"""
    chapter = Chapter(**payload)
    db.add(chapter)
    db.flush()
    audit(db, actor, "admin.chapter.create", "chapter", chapter.id, after={"title": chapter.title}, meta=meta)
    db.commit()
    db.refresh(chapter)
    return chapter


def update_chapter(
    db: Session, actor: User, chapter_id: str, payload: dict[str, Any], meta: dict[str, Any]
) -> Chapter:
    """更新章节。"""
    chapter = get_or_404(db, Chapter, chapter_id, ErrorCode.CHAPTER_NOT_FOUND, "章节不存在")
    apply_fields(chapter, payload)
    audit(db, actor, "admin.chapter.update", "chapter", chapter.id, after={"title": chapter.title}, meta=meta)
    db.commit()
    db.refresh(chapter)
    return chapter


def delete_chapter(db: Session, actor: User, chapter_id: str, meta: dict[str, Any]) -> None:
    """删除章节。"""
    chapter = get_or_404(db, Chapter, chapter_id, ErrorCode.CHAPTER_NOT_FOUND, "章节不存在")
    db.delete(chapter)
    audit(db, actor, "admin.chapter.delete", "chapter", chapter_id, meta=meta)
    db.commit()


def create_lesson(db: Session, actor: User, payload: dict[str, Any], meta: dict[str, Any]) -> Lesson:
    """新建课时（含知识点关联）。"""
    topic_slugs = payload.pop("topic_slugs", []) or []
    lesson = Lesson(**payload)
    db.add(lesson)
    db.flush()
    sync_lesson_topics(db, lesson, topic_slugs)
    audit(db, actor, "admin.lesson.create", "lesson", lesson.id, after={"title": lesson.title}, meta=meta)
    db.commit()
    db.refresh(lesson)
    return lesson


def update_lesson(
    db: Session, actor: User, lesson_id: str, payload: dict[str, Any], meta: dict[str, Any]
) -> Lesson:
    """更新课时。"""
    topic_slugs = payload.pop("topic_slugs", None)
    lesson = get_or_404(db, Lesson, lesson_id, ErrorCode.LESSON_NOT_FOUND, "课时不存在")
    apply_fields(lesson, payload)
    if topic_slugs is not None:
        sync_lesson_topics(db, lesson, topic_slugs)
    audit(db, actor, "admin.lesson.update", "lesson", lesson.id, after={"title": lesson.title}, meta=meta)
    db.commit()
    db.refresh(lesson)
    return lesson


def delete_lesson(db: Session, actor: User, lesson_id: str, meta: dict[str, Any]) -> None:
    """删除课时。"""
    lesson = get_or_404(db, Lesson, lesson_id, ErrorCode.LESSON_NOT_FOUND, "课时不存在")
    db.delete(lesson)
    audit(db, actor, "admin.lesson.delete", "lesson", lesson_id, meta=meta)
    db.commit()


def sync_lesson_topics(db: Session, lesson: Lesson, topic_slugs: list[str]) -> None:
    """按 slug 覆盖式重建课时的知识点关联。"""
    db.query(LessonTopic).filter(LessonTopic.lesson_id == lesson.id).delete()
    if not topic_slugs:
        return
    topics = {t.slug: t.id for t in db.scalars(select(Topic).where(Topic.slug.in_(topic_slugs))).all()}
    for index, slug in enumerate(topic_slugs):
        if slug in topics:
            db.add(LessonTopic(lesson_id=lesson.id, topic_id=topics[slug], is_primary=index == 0))
