"""课程服务：课程 / 阶段 / 章节树 / 报名（`docs/API.md` §2.3）。

职责边界：只返回 ORM 对象与 Pydantic Schema，不感知 HTTP；业务失败统一 `raise AppError`。
查询一律用 `selectinload` 预加载章节与课时，避免 N+1。
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import AppError, ErrorCode
from app.core.pagination import PageParams, build_page
from app.core.response import PageModel
from app.models.course import Chapter, Course, CourseEnrollment, Lesson
from app.models.enums import ProgressStatus
from app.models.learning import LearningProgress
from app.models.user import User
from app.schemas.course import (
    ChapterOut,
    CourseBrief,
    CourseDetail,
    CourseEnrollmentOut,
    CourseProgressOut,
    LessonBrief,
    StageOut,
)

logger = logging.getLogger("pythonlab.course")

#: 课程列表排序白名单（键 → ORM 列）；未命中时回退 `stage_no` 升序，杜绝字符串拼接注入
COURSE_SORT_COLUMNS: dict[str, str] = {
    "stage_no": "stage_no",
    "-stage_no": "stage_no",
    "order_index": "order_index",
    "-order_index": "order_index",
    "lesson_count": "lesson_count",
    "-lesson_count": "lesson_count",
    "estimated_hours": "estimated_hours",
    "-estimated_hours": "estimated_hours",
}


def _course_loader() -> tuple:
    """课程 → 章节 → 课时的预加载选项（一次查完，避免章节树 N+1）。"""
    return (selectinload(Course.chapters).selectinload(Chapter.lessons),)


def _apply_course_sort(stmt: Select[tuple[Course]], sort: str) -> Select[tuple[Course]]:
    """按白名单给课程查询加排序；未命中回退 `stage_no` 升序。"""
    key = COURSE_SORT_COLUMNS.get(sort)
    if key is None:
        return stmt.order_by(Course.stage_no.asc())
    column = getattr(Course, key)
    return stmt.order_by(column.desc() if sort.startswith("-") else column.asc())


def _progress_map(db: Session, user: User | None, course_ids: Sequence[str]) -> dict[str, int]:
    """批量取「课程 → 进度百分比」映射（未登录或空列表返回空字典）。"""
    if user is None or not course_ids:
        return {}
    rows = db.execute(
        select(CourseEnrollment.course_id, CourseEnrollment.progress_percent).where(
            CourseEnrollment.user_id == user.id,
            CourseEnrollment.course_id.in_(list(course_ids)),
        )
    ).all()
    return {str(course_id): int(percent or 0) for course_id, percent in rows}


def _lesson_progress_map(db: Session, user: User | None, lesson_ids: Sequence[str]) -> dict[str, LearningProgress]:
    """批量取「课时 → 学习进度」映射（用于章节树内课时状态）。"""
    if user is None or not lesson_ids:
        return {}
    rows = db.scalars(
        select(LearningProgress).where(
            LearningProgress.user_id == user.id,
            LearningProgress.lesson_id.in_(list(lesson_ids)),
        )
    ).all()
    return {str(item.lesson_id): item for item in rows}


def course_to_brief(course: Course, progress_percent: int = 0) -> CourseBrief:
    """ORM 课程 → `CourseBrief`（附加我的进度百分比）。"""
    return CourseBrief(
        id=course.id,
        slug=course.slug,
        stage_no=course.stage_no,
        title=course.title,
        subtitle=course.subtitle,
        level=course.level,
        icon=course.icon,
        cover_url=course.cover_url,
        estimated_hours=course.estimated_hours,
        lesson_count=course.lesson_count,
        order_index=course.order_index,
        is_published=course.is_published,
        progress_percent=int(progress_percent or 0),
    )


def lesson_to_brief(lesson: Lesson, progress: LearningProgress | None = None) -> LessonBrief:
    """ORM 课时 → `LessonBrief`（附加我的进度状态）。"""
    return LessonBrief(
        id=lesson.id,
        chapter_id=lesson.chapter_id,
        slug=lesson.slug,
        title=lesson.title,
        summary=lesson.summary,
        lesson_type=lesson.lesson_type,
        difficulty=lesson.difficulty,
        estimated_minutes=lesson.estimated_minutes,
        order_index=lesson.order_index,
        xp_reward=lesson.xp_reward,
        has_playground=lesson.has_playground,
        is_published=lesson.is_published,
        progress_percent=int(progress.progress_percent) if progress else 0,
        status=progress.status if progress else ProgressStatus.NOT_STARTED.value,
    )


def ordered_lessons(course: Course) -> list[Lesson]:
    """课程内「已发布章节 → 已发布课时」的扁平有序列表。"""
    result: list[Lesson] = []
    for chapter in sorted(course.chapters or [], key=lambda item: (item.order_index, item.title)):
        if not chapter.is_published:
            continue
        for lesson in sorted(chapter.lessons or [], key=lambda item: (item.order_index, item.title)):
            if lesson.is_published:
                result.append(lesson)
    return result


def build_chapter_tree(db: Session, course: Course, user: User | None) -> list[ChapterOut]:
    """把已加载的课程组装为章节树（含课时列表与我的进度），只做一次进度查询。"""
    lessons = ordered_lessons(course)
    progress_map = _lesson_progress_map(db, user, [lesson.id for lesson in lessons])
    tree: list[ChapterOut] = []
    for chapter in sorted(course.chapters or [], key=lambda item: (item.order_index, item.title)):
        if not chapter.is_published:
            continue
        chapter_lessons = [
            lesson_to_brief(lesson, progress_map.get(str(lesson.id)))
            for lesson in sorted(chapter.lessons or [], key=lambda item: (item.order_index, item.title))
            if lesson.is_published
        ]
        tree.append(
            ChapterOut(
                id=chapter.id,
                course_id=chapter.course_id,
                slug=chapter.slug,
                title=chapter.title,
                summary_md=chapter.summary_md,
                order_index=chapter.order_index,
                lesson_count=len(chapter_lessons),
                is_published=chapter.is_published,
                lessons=chapter_lessons,
            )
        )
    return tree


def list_courses(
    db: Session,
    params: PageParams,
    *,
    level: str | None = None,
    stage_no: int | None = None,
    keyword: str | None = None,
    user: User | None = None,
) -> PageModel[CourseBrief]:
    """课程列表（分类 / 难度 / 搜索 / 分页 / 排序白名单）。"""
    stmt = select(Course).where(Course.is_published.is_(True))
    if level:
        stmt = stmt.where(Course.level == level)
    if stage_no is not None:
        stmt = stmt.where(Course.stage_no == stage_no)
    if keyword and keyword.strip():
        like = f"%{keyword.strip()}%"
        stmt = stmt.where(
            or_(Course.title.ilike(like), Course.subtitle.ilike(like), Course.slug.ilike(like))
        )
    stmt = _apply_course_sort(stmt, params.sort)

    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    courses = list(db.scalars(stmt.offset(params.offset).limit(params.limit)).all())
    progress = _progress_map(db, user, [course.id for course in courses])
    items = [course_to_brief(course, progress.get(str(course.id), 0)) for course in courses]
    return build_page(items, total, params)


def list_stages(db: Session, user: User | None = None) -> list[StageOut]:
    """18 阶段概览（含我的进度与当前阶段标记）。"""
    courses = db.scalars(
        select(Course).where(Course.is_published.is_(True)).order_by(Course.stage_no.asc())
    ).all()
    progress = _progress_map(db, user, [course.id for course in courses])
    current_stage = current_stage_no(db, user)
    return [
        StageOut(
            stage_no=course.stage_no,
            slug=course.slug,
            title=course.title,
            subtitle=course.subtitle,
            level=course.level,
            icon=course.icon,
            lesson_count=course.lesson_count,
            estimated_hours=course.estimated_hours,
            progress_percent=progress.get(str(course.id), 0),
            is_current=(course.stage_no == current_stage),
        )
        for course in courses
    ]


def current_stage_no(db: Session, user: User | None) -> int | None:
    """用户最近学习的阶段序号（按报名时间倒序取第一条）。"""
    if user is None:
        return None
    row = db.execute(
        select(Course.stage_no)
        .join(CourseEnrollment, CourseEnrollment.course_id == Course.id)
        .where(CourseEnrollment.user_id == user.id)
        .order_by(CourseEnrollment.updated_at.desc())
        .limit(1)
    ).first()
    return int(row[0]) if row else None


def get_course_by_slug(db: Session, slug: str) -> Course:
    """按 slug 取课程（预加载章节树），不存在抛 `COURSE_NOT_FOUND`。"""
    course = db.scalars(
        select(Course).where(Course.slug == slug).options(*_course_loader())
    ).one_or_none()
    if course is None:
        raise AppError(code=ErrorCode.COURSE_NOT_FOUND, message="课程不存在", status_code=404, details=f"slug={slug}")
    return course


def get_course_by_id(db: Session, course_id: str) -> Course:
    """按 id 取课程（预加载章节树），不存在抛 `COURSE_NOT_FOUND`。"""
    course = db.scalars(
        select(Course).where(Course.id == course_id).options(*_course_loader())
    ).one_or_none()
    if course is None:
        raise AppError(code=ErrorCode.COURSE_NOT_FOUND, message="课程不存在", status_code=404, details=f"id={course_id}")
    return course


def build_course_detail(db: Session, course: Course, user: User | None) -> CourseDetail:
    """组装课程详情（课程摘要 + 章节树 + 我的进度）。"""
    progress = _progress_map(db, user, [course.id]).get(str(course.id), 0)
    detail_progress: CourseProgressOut | None = None
    if user is not None:
        detail_progress = _build_course_progress(db, course, user)
    return CourseDetail(
        course=course_to_brief(course, progress),
        chapters=build_chapter_tree(db, course, user),
        progress=detail_progress,
    )


def _build_course_progress(db: Session, course: Course, user: User) -> CourseProgressOut:
    """构造课程进度摘要（完成课时数 / 百分比 / 继续学习课时）。"""
    lesson_ids = [lesson.id for lesson in ordered_lessons(course)]
    completed = 0
    if lesson_ids:
        completed = int(
            db.scalar(
                select(func.count())
                .select_from(LearningProgress)
                .where(
                    LearningProgress.user_id == user.id,
                    LearningProgress.lesson_id.in_(lesson_ids),
                    LearningProgress.status == ProgressStatus.COMPLETED.value,
                )
            )
            or 0
        )
    enrollment = db.scalars(
        select(CourseEnrollment).where(
            CourseEnrollment.user_id == user.id, CourseEnrollment.course_id == course.id
        )
    ).one_or_none()
    total = len(lesson_ids)
    percent = int(round(completed / total * 100)) if total else 0
    return CourseProgressOut(
        course_id=course.id,
        percent=enrollment.progress_percent if enrollment else percent,
        completed_lessons=completed,
        total_lessons=total,
        last_lesson_id=enrollment.last_lesson_id if enrollment else None,
    )


def list_chapters(db: Session, course: Course, user: User | None) -> list[ChapterOut]:
    """课程章节目录（含课时列表）。"""
    return build_chapter_tree(db, course, user)


def list_lessons(db: Session, course: Course, user: User | None) -> list[LessonBrief]:
    """课程全部课时（扁平列表）。"""
    lessons = ordered_lessons(course)
    progress_map = _lesson_progress_map(db, user, [lesson.id for lesson in lessons])
    return [lesson_to_brief(lesson, progress_map.get(str(lesson.id))) for lesson in lessons]


def enroll(db: Session, user: User, course_id: str) -> CourseEnrollmentOut:
    """报名课程；已报名抛 `ALREADY_ENROLLED`（409）。"""
    course = get_course_by_id(db, course_id)
    existing = db.scalars(
        select(CourseEnrollment).where(
            CourseEnrollment.user_id == user.id, CourseEnrollment.course_id == course.id
        )
    ).one_or_none()
    if existing is not None:
        raise AppError(code=ErrorCode.ALREADY_ENROLLED, message="你已报名该课程", status_code=409)
    enrollment = CourseEnrollment(user_id=user.id, course_id=course.id)
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    logger.info("用户报名课程 user_id=%s course_id=%s", user.id, course.id)
    return CourseEnrollmentOut.model_validate(enrollment)


def cancel_enroll(db: Session, user: User, course_id: str) -> None:
    """取消报名；未报名抛 404。"""
    enrollment = db.scalars(
        select(CourseEnrollment).where(
            CourseEnrollment.user_id == user.id, CourseEnrollment.course_id == course_id
        )
    ).one_or_none()
    if enrollment is None:
        raise AppError(code=ErrorCode.NOT_FOUND, message="未报名该课程", status_code=404, details=f"course_id={course_id}")
    db.delete(enrollment)
    db.commit()
    logger.info("用户取消报名 user_id=%s course_id=%s", user.id, course_id)


def my_courses(db: Session, user: User, params: PageParams) -> PageModel[CourseBrief]:
    """我的课程（按报名时间倒序，含进度）。"""
    base = (
        select(Course, CourseEnrollment.progress_percent)
        .join(CourseEnrollment, CourseEnrollment.course_id == Course.id)
        .where(CourseEnrollment.user_id == user.id, Course.is_published.is_(True))
    )
    total = int(db.scalar(select(func.count()).select_from(base.subquery())) or 0)
    rows = db.execute(
        base.order_by(CourseEnrollment.updated_at.desc()).offset(params.offset).limit(params.limit)
    ).all()
    items = [course_to_brief(course, percent) for course, percent in rows]
    return build_page(items, total, params)
