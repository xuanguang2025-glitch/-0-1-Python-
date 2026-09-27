"""课时服务：详情（含定位与目录）/ 进度上报 / 完成打卡 / 随堂练习（`docs/API.md` §2.4）。

前端 `/lesson/[id]` 页面需要左侧完整章节目录，因此 `build_lesson_detail` 会一次性返回
所属课程 / 章节定位信息、上一节 / 下一节导航与完整 `course_outline`。
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.constants import XP_REASON_LESSON
from app.core.errors import AppError, ErrorCode
from app.models.course import Chapter, Course, Lesson, LessonTopic
from app.models.enums import ProgressStatus
from app.models.learning import KnowledgeMastery, LearningProgress
from app.models.user import User
from app.schemas.course import (
    LessonBrief,
    LessonCompleteOut,
    LessonDetail,
    LessonNav,
    LessonProgressRequest,
    LearningProgressOut,
    QuizResultDetail,
    QuizResultOut,
    QuizSubmitRequest,
    TopicOut,
)
from app.services import course_service, mastery_service, progress_service

logger = logging.getLogger("pythonlab.lesson")


def get_lesson(db: Session, lesson_id: str) -> Lesson:
    """按 id 取课时（预加载章节 / 课程 / 全课程章节树 / 知识点），不存在抛 404。"""
    lesson = db.scalars(
        select(Lesson)
        .where(Lesson.id == lesson_id)
        .options(
            selectinload(Lesson.chapter)
            .selectinload(Chapter.course)
            .selectinload(Course.chapters)
            .selectinload(Chapter.lessons),
            selectinload(Lesson.lesson_topics).selectinload(LessonTopic.topic),
        )
    ).one_or_none()
    if lesson is None:
        raise AppError(code=ErrorCode.LESSON_NOT_FOUND, message="课时不存在", status_code=404, details=f"id={lesson_id}")
    return lesson


def build_lesson_detail(db: Session, lesson: Lesson, user: User | None) -> LessonDetail:
    """组装课时详情（正文 + 定位 + 导航 + 目录 + 知识点 + 我的进度）。"""
    chapter: Chapter = lesson.chapter
    course: Course = chapter.course
    ordered = course_service.ordered_lessons(course)
    index_map = {str(item.id): idx for idx, item in enumerate(ordered)}
    lesson_index = index_map.get(str(lesson.id), 0)
    prev_lesson = ordered[lesson_index - 1] if lesson_index > 0 else None
    next_lesson = ordered[lesson_index + 1] if lesson_index + 1 < len(ordered) else None

    published_chapters = [item for item in (course.chapters or []) if item.is_published]
    chapter_index = next(
        (idx for idx, item in enumerate(published_chapters) if item.id == chapter.id), 0
    )

    nav_ids = [item.id for item in (prev_lesson, next_lesson) if item is not None]
    nav_progress = course_service._lesson_progress_map(db, user, nav_ids)  # noqa: SLF001 - 复用同包进度映射
    progress = None
    if user is not None:
        progress = db.scalars(
            select(LearningProgress).where(
                LearningProgress.user_id == user.id, LearningProgress.lesson_id == lesson.id
            )
        ).one_or_none()

    return LessonDetail(
        id=lesson.id,
        chapter_id=lesson.chapter_id,
        slug=lesson.slug,
        title=lesson.title,
        summary=lesson.summary,
        content_md=lesson.content_md or "",
        lesson_type=lesson.lesson_type,
        difficulty=lesson.difficulty,
        estimated_minutes=lesson.estimated_minutes,
        order_index=lesson.order_index,
        xp_reward=lesson.xp_reward,
        has_playground=lesson.has_playground,
        starter_code=lesson.starter_code,
        solution_code=lesson.solution_code,
        quiz_json=lesson.quiz_json,
        topics=_lesson_topics(db, lesson, user),
        prev=course_service.lesson_to_brief(prev_lesson, nav_progress.get(str(prev_lesson.id))) if prev_lesson else None,
        next=course_service.lesson_to_brief(next_lesson, nav_progress.get(str(next_lesson.id))) if next_lesson else None,
        progress=_progress_out(progress) if progress else None,
        course_id=course.id,
        course_title=course.title,
        course_slug=course.slug,
        chapter_title=chapter.title,
        chapter_index=chapter_index,
        lesson_index=lesson_index,
        total_lessons=len(ordered),
        prev_lesson=LessonNav(id=prev_lesson.id, title=prev_lesson.title, slug=prev_lesson.slug) if prev_lesson else None,
        next_lesson=LessonNav(id=next_lesson.id, title=next_lesson.title, slug=next_lesson.slug) if next_lesson else None,
        course_outline=course_service.build_chapter_tree(db, course, user),
    )


def list_lesson_topics(db: Session, lesson: Lesson, user: User | None) -> list[TopicOut]:
    """课时关联知识点（含我的掌握度）。"""
    return _lesson_topics(db, lesson, user)


def get_next_lesson(db: Session, lesson: Lesson, user: User | None = None) -> LessonBrief | None:
    """课程内「下一节课时」（无后继返回 None）。"""
    course = lesson.chapter.course if lesson.chapter is not None else None
    if course is None:
        return None
    ordered = course_service.ordered_lessons(course)
    index = next((idx for idx, item in enumerate(ordered) if item.id == lesson.id), None)
    if index is None or index + 1 >= len(ordered):
        return None
    nxt = ordered[index + 1]
    progress_map = course_service._lesson_progress_map(db, user, [nxt.id])  # noqa: SLF001
    return course_service.lesson_to_brief(nxt, progress_map.get(str(nxt.id)))


def update_progress(db: Session, user: User, lesson: Lesson, payload: LessonProgressRequest) -> LearningProgressOut:
    """上报学习进度（写 learning_progress，并同步报名进度）。"""
    record = _get_or_create_progress(db, user, lesson)
    record.touch(payload.progress_percent, payload.time_spent_seconds or 0)
    if payload.code_snapshot is not None:
        record.code_snapshot = payload.code_snapshot
    course_id = _course_id_of_lesson(db, lesson)
    enrollment = progress_service.sync_enrollment(db, user, course_id) if course_id else None
    if enrollment is not None:
        enrollment.last_lesson_id = lesson.id
    db.commit()
    db.refresh(record)
    return _progress_out(record)


def complete_lesson(
    db: Session,
    user: User,
    lesson: Lesson,
    time_spent_seconds: int | None = None,
) -> LessonCompleteOut:
    """标记课时完成：写进度 + 发放 XP + 触发掌握度 + 同步报名进度。"""
    record = _get_or_create_progress(db, user, lesson)
    record.touch(100, time_spent_seconds or 0)

    xp_amount = int(lesson.xp_reward or get_settings().xp_per_lesson)
    xp_earned, level_up = progress_service.award_xp(
        db, user, xp_amount, reason=XP_REASON_LESSON, ref_type="lesson", ref_id=lesson.id
    )

    # 触发主知识点掌握度（完成即视为正向练习）
    primary_topic_ids = [
        link.topic_id for link in (lesson.lesson_topics or []) if link.is_primary
    ]
    if primary_topic_ids:
        mastery_service.touch_topics(db, user, primary_topic_ids, correct=True)

    course_id = _course_id_of_lesson(db, lesson)
    enrollment = progress_service.sync_enrollment(db, user, course_id) if course_id else None
    if enrollment is not None:
        enrollment.last_lesson_id = lesson.id

    unlocked = _unlock_achievements(db, user)
    db.commit()
    db.refresh(record)
    logger.info("课时完成 user_id=%s lesson_id=%s xp=%s", user.id, lesson.id, xp_earned)
    return LessonCompleteOut(
        progress=_progress_out(record),
        xp_earned=xp_earned,
        level_up=level_up,
        unlocked_achievements=unlocked,
    )


def submit_quiz(db: Session, lesson: Lesson, payload: QuizSubmitRequest) -> QuizResultOut:
    """随堂练习判分（按 qid 或题序匹配，返回逐题结果）。"""
    quiz: list[dict[str, Any]] = list(lesson.quiz_json or [])
    if not quiz:
        return QuizResultOut(correct_count=0, total=0, passed=False, details=[])

    lookup = _quiz_lookup(quiz)
    details: list[QuizResultDetail] = []
    correct_count = 0
    for answer in payload.answers:
        item = lookup.get(answer.qid)
        if item is None:
            details.append(QuizResultDetail(qid=answer.qid, correct=False, expected=None, explain=None))
            continue
        expected = item.get("answer")
        is_correct = _normalize(answer.value) == _normalize(expected)
        if is_correct:
            correct_count += 1
        details.append(
            QuizResultDetail(
                qid=answer.qid,
                correct=is_correct,
                expected=expected,
                explain=item.get("explain"),
            )
        )
    total = len(quiz)
    passed = correct_count >= max(1, int(total * 0.6 + 0.999))
    return QuizResultOut(correct_count=correct_count, total=total, passed=passed, details=details)


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------


def _lesson_topics(db: Session, lesson: Lesson, user: User | None) -> list[TopicOut]:
    """课时知识点列表（附带我的掌握度）。"""
    links = list(lesson.lesson_topics or [])
    if not links:
        return []
    topic_ids = [link.topic_id for link in links]
    mastery_map: dict[str, KnowledgeMastery] = {}
    if user is not None and topic_ids:
        rows = db.scalars(
            select(KnowledgeMastery).where(
                KnowledgeMastery.user_id == user.id, KnowledgeMastery.topic_id.in_(topic_ids)
            )
        ).all()
        mastery_map = {str(item.topic_id): item for item in rows}
    return [
        TopicOut(
            id=link.topic.id,
            slug=link.topic.slug,
            name=link.topic.name,
            parent_id=link.topic.parent_id,
            description=link.topic.description,
            order_index=link.topic.order_index,
            is_primary=bool(link.is_primary),
            mastery_score=float(mastery_map[str(link.topic_id)].mastery_score) if str(link.topic_id) in mastery_map else None,
            mastery_level=mastery_map[str(link.topic_id)].mastery_level if str(link.topic_id) in mastery_map else None,
        )
        for link in links
        if link.topic is not None
    ]


def _get_or_create_progress(db: Session, user: User, lesson: Lesson) -> LearningProgress:
    """取用户对某课时的进度记录，缺失时创建并 flush。"""
    record = db.scalars(
        select(LearningProgress).where(
            LearningProgress.user_id == user.id, LearningProgress.lesson_id == lesson.id
        )
    ).one_or_none()
    if record is None:
        record = LearningProgress(
            user_id=user.id,
            lesson_id=lesson.id,
            status=ProgressStatus.NOT_STARTED.value,
        )
        db.add(record)
        db.flush()
    return record


def _course_id_of_lesson(db: Session, lesson: Lesson) -> str | None:
    """取课时所属课程 id（章节关系未加载时回查一次）。"""
    if lesson.chapter is not None:
        return lesson.chapter.course_id
    return db.scalar(select(Chapter.course_id).where(Chapter.id == lesson.chapter_id))


def _progress_out(record: LearningProgress) -> LearningProgressOut:
    """ORM 进度 → Schema。"""
    return LearningProgressOut(
        id=record.id,
        lesson_id=record.lesson_id,
        status=record.status,
        progress_percent=int(record.progress_percent or 0),
        time_spent_seconds=int(record.time_spent_seconds or 0),
        attempt_count=int(record.attempt_count or 0),
        started_at=record.started_at,
        completed_at=record.completed_at,
        updated_at=record.updated_at,
    )


def _quiz_lookup(quiz: Sequence[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """构造 qid → 题目映射，兼容题序（0/1 基）与题干文本作为 qid。"""
    lookup: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(quiz):
        question = str(item.get("q", ""))
        for key in {str(index), f"q{index}", f"q{index + 1}", question}:
            if key:
                lookup[key] = item
    return lookup


def _normalize(value: Any) -> Any:
    """把作答与标准答案归一化后比较（字符串去空白；列表/布尔原样）。"""
    if isinstance(value, str):
        return value.strip()
    return value


def _unlock_achievements(db: Session, user: User) -> list[str]:
    """尝试调用游戏化服务解锁成就；该模块不可用时不阻断主流程。"""
    try:
        from app.services import gamification_service  # noqa: PLC0415 - 惰性导入避免跨域强耦合

        checker = getattr(gamification_service, "check_achievements", None)
        if callable(checker):
            result = checker(db, user)
            return [str(item) for item in (result or [])]
    except Exception as exc:  # noqa: BLE001 - 成就解锁失败不应影响完成打卡
        logger.debug("成就解锁跳过：%s", exc)
    return []
