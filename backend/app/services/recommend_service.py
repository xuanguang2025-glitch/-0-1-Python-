"""推荐服务（`docs/API.md` 推荐能力）：下一节课程 / 适合题目 / 复习内容 / 学习建议。

策略（数据量小，无需复杂模型）：
- 下一节：取最近报名课程中第一个未完成课时，无报名则回退到阶段 1 首课；
- 题目：排除已通过，按分类薄弱度与通过率综合排序；
- 复习：优先「到期复习」与「薄弱」知识点；
- 建议：基于连续天数、掌握度、错题与课程完成度给出可执行文案。
"""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.course import Course, CourseEnrollment
from app.models.enums import ProgressStatus, SubmissionStatus
from app.models.learning import KnowledgeMastery, LearningProgress, Mistake
from app.models.problem import Problem, ProblemTag, Tag
from app.models.submission import Submission
from app.models.user import User
from app.schemas.course import LessonBrief
from app.schemas.problem import ProblemBrief
from app.schemas.statistics import RecommendationItem
from app.services import course_service, mastery_service
from app.utils.time import now_utc

logger = logging.getLogger("pythonlab.recommend")


def recommend_next_lesson(db: Session, user: User) -> LessonBrief | None:
    """推荐下一节课时：最近报名课程的第一个未完成课时。"""
    course = _active_course(db, user) or _first_course(db)
    if course is None:
        return None
    course = course_service.get_course_by_id(db, course.id)
    completed_ids = set(
        db.scalars(
            select(LearningProgress.lesson_id).where(
                LearningProgress.user_id == user.id,
                LearningProgress.status == ProgressStatus.COMPLETED.value,
            )
        ).all()
    )
    lessons = course_service.ordered_lessons(course)
    for lesson in lessons:
        if str(lesson.id) not in completed_ids:
            return course_service.lesson_to_brief(lesson)
    return course_service.lesson_to_brief(lessons[0]) if lessons else None


def recommend_problems(db: Session, user: User, limit: int = 10) -> list[ProblemBrief]:
    """推荐适合题目：排除已通过，按通过率与难度综合排序。"""
    limit = max(1, min(50, int(limit)))
    solved = select(Submission.problem_id).where(
        Submission.user_id == user.id,
        Submission.status == SubmissionStatus.ACCEPTED.value,
        Submission.problem_id.is_not(None),
    )
    problems = db.scalars(
        select(Problem)
        .where(Problem.is_published.is_(True), Problem.id.not_in(solved))
        .order_by(Problem.acceptance_rate.desc(), Problem.difficulty.asc())
        .limit(limit)
    ).all()
    return [_problem_brief(db, problem) for problem in problems]


def recommend_review(db: Session, user: User, limit: int = 10) -> list[RecommendationItem]:
    """复习内容推荐：到期复习 / 薄弱知识点 + 未解决错题。"""
    limit = max(1, min(50, int(limit)))
    items: list[RecommendationItem] = []
    now = now_utc()

    due_rows = db.execute(
        select(KnowledgeMastery, None)
        .where(KnowledgeMastery.user_id == user.id, KnowledgeMastery.next_review_at <= now)
        .order_by(KnowledgeMastery.next_review_at.asc())
        .limit(limit)
    ).all()
    topic_ids = [record.topic_id for record, _ in due_rows]
    from app.models.course import Topic

    name_map: dict[str, str] = {}
    if topic_ids:
        name_map = {
            str(topic_id): name
            for topic_id, name in db.execute(
                select(Topic.id, Topic.name).where(Topic.id.in_(topic_ids))
            ).all()
        }
    for record, _ in due_rows:
        items.append(
            RecommendationItem(
                type="topic",
                id=record.topic_id,
                title=name_map.get(str(record.topic_id), "知识点"),
                reason="已到复习时间，建议巩固",
            )
        )

    if len(items) < limit:
        for weak in mastery_service.weak_topics(db, user, limit - len(items)):
            items.append(
                RecommendationItem(
                    type="topic",
                    id=weak.topic_id,
                    title=weak.name or "知识点",
                    reason=f"掌握度较低（{weak.mastery_score:.0f} 分）",
                )
            )

    if len(items) < limit:
        mistakes = db.scalars(
            select(Mistake)
            .where(Mistake.user_id == user.id, Mistake.resolved.is_(False))
            .order_by(Mistake.created_at.desc())
            .limit(limit - len(items))
        ).all()
        for mistake in mistakes:
            items.append(
                RecommendationItem(
                    type="mistake",
                    id=mistake.id,
                    title=mistake.title or "错题重做",
                    reason="错题待攻克，建议重做",
                )
            )
    return items[:limit]


def recommend_advice(db: Session, user: User) -> list[RecommendationItem]:
    """学习建议：基于连续天数 / 掌握度 / 课程完成度 / 错题生成可执行文案。"""
    advice: list[RecommendationItem] = []

    next_lesson = recommend_next_lesson(db, user)
    if next_lesson is not None:
        advice.append(
            RecommendationItem(
                type="lesson",
                id=next_lesson.id,
                title=f"继续学习：{next_lesson.title}",
                reason="按既定路线推进，保持节奏",
            )
        )

    if int(user.streak_days or 0) == 0:
        advice.append(
            RecommendationItem(type="habit", id=None, title="今天还没有学习记录", reason="先完成任意一节课程即可续上连续天数")
        )

    weak = mastery_service.weak_topics(db, user, 3)
    for item in weak:
        advice.append(
            RecommendationItem(
                type="review",
                id=item.topic_id,
                title=f"复习「{item.name or '知识点'}」",
                reason="该知识点较薄弱，建议针对性练习",
            )
        )

    pending_mistakes = int(
        db.scalar(
            select(func.count())
            .select_from(Mistake)
            .where(Mistake.user_id == user.id, Mistake.resolved.is_(False))
        )
        or 0
    )
    if pending_mistakes:
        advice.append(
            RecommendationItem(
                type="mistake",
                id=None,
                title=f"有 {pending_mistakes} 道错题待复习",
                reason="错题重做能快速补齐短板",
            )
        )
    return advice


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------


def _active_course(db: Session, user: User) -> Course | None:
    """最近报名的课程。"""
    return db.scalars(
        select(Course)
        .join(CourseEnrollment, CourseEnrollment.course_id == Course.id)
        .where(CourseEnrollment.user_id == user.id)
        .order_by(CourseEnrollment.updated_at.desc())
        .limit(1)
    ).one_or_none()


def _first_course(db: Session) -> Course | None:
    """阶段 1 课程（回退用）。"""
    return db.scalars(
        select(Course).where(Course.is_published.is_(True)).order_by(Course.stage_no.asc()).limit(1)
    ).one_or_none()


def _problem_brief(db: Session, problem: Problem) -> ProblemBrief:
    """ORM 题目 → `ProblemBrief`（附带标签名）。"""
    tag_names = list(
        db.scalars(
            select(Tag.name)
            .join(ProblemTag, ProblemTag.tag_id == Tag.id)
            .where(ProblemTag.problem_id == problem.id)
        ).all()
    )
    return ProblemBrief(
        id=problem.id,
        slug=problem.slug,
        title=problem.title,
        problem_type=problem.problem_type,
        difficulty=problem.difficulty,
        category=problem.category,
        score=problem.score,
        xp_reward=problem.xp_reward,
        submission_count=problem.submission_count,
        accepted_count=problem.accepted_count,
        acceptance_rate=float(problem.acceptance_rate or 0.0),
        tags=[str(name) for name in tag_names],
    )
