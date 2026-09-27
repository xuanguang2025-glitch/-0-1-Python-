"""学习进度服务（`docs/API.md` §2.11）。

覆盖：进度总览 / 单课程进度 / 学习看板 / 热力图 / 学习模式，并对外提供两个可复用的写操作：
`award_xp`（经验流水 + 升级判定）与 `sync_enrollment`（按完成课时重算报名进度）。
学习会话（开始 / 心跳 / 结束）见 `session_service`。
"""

from __future__ import annotations

import logging
from datetime import date as DateType
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.constants import level_of_xp, next_level_xp
from app.core.errors import AppError, ErrorCode
from app.models.course import Chapter, Course, CourseEnrollment, Lesson
from app.models.enums import ProgressStatus, SubmissionStatus, UserProjectStatus
from app.models.gamification import XPTransaction
from app.models.learning import LearningProgress, LearningSession
from app.models.project import Project, UserProject
from app.models.submission import Submission
from app.models.user import User
from app.schemas.progress import (
    CourseProgressItem,
    CourseProgressOut,
    HeatmapOut,
    HeatmapPoint,
    LearningDashboardOut,
    ModeOut,
    ProgressOverviewOut,
)
from app.services.session_service import session_seconds
from app.utils.time import last_n_days, now_utc

logger = logging.getLogger("pythonlab.progress")


# ---------------------------------------------------------------------------
# 可复用写操作
# ---------------------------------------------------------------------------


def recompute_level(db: Session, user: User) -> bool:
    """按当前 XP 重算等级，返回是否发生升级。"""
    thresholds = get_settings().level_threshold_list
    before = int(user.level or 1)
    user.level = level_of_xp(int(user.xp or 0), thresholds)
    return user.level > before


def award_xp(
    db: Session,
    user: User,
    amount: int,
    *,
    reason: str,
    ref_type: str | None = None,
    ref_id: str | None = None,
) -> tuple[int, bool]:
    """发放经验值并写入流水，返回 `(实际发放量, 是否升级)`。不提交事务。"""
    amount = max(0, int(amount))
    if amount == 0:
        return 0, False
    user.xp = int(user.xp or 0) + amount
    level_up = recompute_level(db, user)
    db.add(
        XPTransaction(
            user_id=user.id,
            amount=amount,
            reason=reason,
            ref_type=ref_type,
            ref_id=ref_id,
            balance_after=int(user.xp or 0),
        )
    )
    return amount, level_up


def course_lesson_ids(db: Session, course_id: str) -> list[str]:
    """取某课程下「已发布章节的已发布课时」id 列表。"""
    return list(
        db.scalars(
            select(Lesson.id)
            .join(Chapter, Chapter.id == Lesson.chapter_id)
            .where(
                Chapter.course_id == course_id,
                Chapter.is_published.is_(True),
                Lesson.is_published.is_(True),
            )
        ).all()
    )


def sync_enrollment(db: Session, user: User, course_id: str) -> CourseEnrollment | None:
    """按已发布课时的完成情况重算报名进度（存在报名记录时更新并返回）。不提交事务。"""
    enrollment = db.scalars(
        select(CourseEnrollment).where(
            CourseEnrollment.user_id == user.id, CourseEnrollment.course_id == course_id
        )
    ).one_or_none()
    if enrollment is None:
        return None
    lesson_ids = course_lesson_ids(db, course_id)
    total = len(lesson_ids)
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
    enrollment.completed_lessons = completed
    enrollment.progress_percent = int(round(completed / total * 100)) if total else 0
    if completed >= total and total > 0:
        if enrollment.completed_at is None:
            enrollment.completed_at = now_utc()
    return enrollment


# ---------------------------------------------------------------------------
# 读操作
# ---------------------------------------------------------------------------


def get_overview(db: Session, user: User) -> ProgressOverviewOut:
    """进度总览：全部阶段的完成度 + 汇总统计 + 当前阶段。"""
    courses = db.scalars(
        select(Course).where(Course.is_published.is_(True)).order_by(Course.stage_no.asc())
    ).all()
    enrollment_rows = db.execute(
        select(CourseEnrollment.course_id, CourseEnrollment.progress_percent, CourseEnrollment.last_lesson_id).where(
            CourseEnrollment.user_id == user.id
        )
    ).all()
    enroll_map = {str(row[0]): (int(row[1] or 0), row[2]) for row in enrollment_rows}

    completed_lesson_ids = set(
        db.scalars(
            select(LearningProgress.lesson_id).where(
                LearningProgress.user_id == user.id,
                LearningProgress.status == ProgressStatus.COMPLETED.value,
            )
        ).all()
    )

    items: list[CourseProgressItem] = []
    for course in courses:
        percent, last_lesson_id = enroll_map.get(str(course.id), (0, None))
        items.append(
            CourseProgressItem(
                course_id=course.id,
                slug=course.slug,
                stage_no=course.stage_no,
                title=course.title,
                percent=percent,
                completed_lessons=0,
                total_lessons=int(course.lesson_count or 0),
                last_lesson_id=last_lesson_id,
            )
        )

    total_lessons = sum(int(course.lesson_count or 0) for course in courses)
    total_lessons = max(total_lessons, len(completed_lesson_ids))
    completed = len(completed_lesson_ids)
    overall = int(round(completed / total_lessons * 100)) if total_lessons else 0

    current_stage: int | None = None
    if enrollment_rows:
        latest = db.execute(
            select(Course.stage_no)
            .join(CourseEnrollment, CourseEnrollment.course_id == Course.id)
            .where(CourseEnrollment.user_id == user.id)
            .order_by(CourseEnrollment.updated_at.desc())
            .limit(1)
        ).first()
        current_stage = int(latest[0]) if latest else None

    return ProgressOverviewOut(
        courses=items,
        completed_lessons=completed,
        total_lessons=total_lessons,
        overall_percent=overall,
        current_stage=current_stage,
    )


def get_course_progress(db: Session, user: User, course_id: str) -> CourseProgressOut:
    """单课程进度明细（完成课时 id 列表 + 百分比 + 继续学习课时）。"""
    course = db.get(Course, course_id)
    if course is None:
        raise AppError(code=ErrorCode.COURSE_NOT_FOUND, message="课程不存在", status_code=404, details=f"id={course_id}")
    lesson_ids = course_lesson_ids(db, course_id)
    completed: list[str] = []
    if lesson_ids:
        completed = list(
            db.scalars(
                select(LearningProgress.lesson_id).where(
                    LearningProgress.user_id == user.id,
                    LearningProgress.lesson_id.in_(lesson_ids),
                    LearningProgress.status == ProgressStatus.COMPLETED.value,
                )
            ).all()
        )
    enrollment = db.scalars(
        select(CourseEnrollment).where(
            CourseEnrollment.user_id == user.id, CourseEnrollment.course_id == course_id
        )
    ).one_or_none()
    percent = enrollment.progress_percent if enrollment else int(round(len(completed) / len(lesson_ids) * 100)) if lesson_ids else 0
    return CourseProgressOut(
        course_id=course_id,
        percent=int(percent or 0),
        completed_lessons=[str(item) for item in completed],
        last_lesson_id=enrollment.last_lesson_id if enrollment else None,
    )


def get_dashboard(db: Session, user: User) -> LearningDashboardOut:
    """学习看板概览（今日/本周时长、连续天数、等级 XP、完成度、题目与项目数）。"""
    settings = get_settings()
    now = now_utc()
    day_start = datetime(now.year, now.month, now.day, tzinfo=now.tzinfo)
    week_start = day_start - timedelta(days=6)

    today_sessions = db.scalars(
        select(LearningSession).where(
            LearningSession.user_id == user.id, LearningSession.started_at >= day_start
        )
    ).all()
    week_sessions = db.scalars(
        select(LearningSession).where(
            LearningSession.user_id == user.id, LearningSession.started_at >= week_start
        )
    ).all()
    today_seconds = sum(session_seconds(item) for item in today_sessions)
    week_seconds = sum(session_seconds(item) for item in week_sessions)

    completed_lessons = int(
        db.scalar(
            select(func.count())
            .select_from(LearningProgress)
            .where(
                LearningProgress.user_id == user.id,
                LearningProgress.status == ProgressStatus.COMPLETED.value,
            )
        )
        or 0
    )
    total_lessons = int(
        db.scalar(select(func.coalesce(func.sum(Course.lesson_count), 0)).where(Course.is_published.is_(True))) or 0
    )
    total_courses = int(db.scalar(select(func.count()).select_from(Course).where(Course.is_published.is_(True))) or 0)
    completed_courses = int(
        db.scalar(
            select(func.count()).select_from(CourseEnrollment).where(
                CourseEnrollment.user_id == user.id, CourseEnrollment.progress_percent >= 100
            )
        )
        or 0
    )
    solved = int(
        db.scalar(
            select(func.count(func.distinct(Submission.problem_id))).where(
                Submission.user_id == user.id,
                Submission.status == SubmissionStatus.ACCEPTED.value,
                Submission.problem_id.is_not(None),
            )
        )
        or 0
    )
    submissions = int(db.scalar(select(func.count()).select_from(Submission).where(Submission.user_id == user.id)) or 0)
    projects_total = int(db.scalar(select(func.count()).select_from(Project).where(Project.is_published.is_(True))) or 0)
    projects_completed = int(
        db.scalar(
            select(func.count()).select_from(UserProject).where(
                UserProject.user_id == user.id,
                UserProject.status == UserProjectStatus.COMPLETED.value,
            )
        )
        or 0
    )

    overall = int(round(completed_lessons / total_lessons * 100)) if total_lessons else 0
    return LearningDashboardOut(
        today_minutes=int(today_seconds // 60),
        week_minutes=int(week_seconds // 60),
        streak_days=int(user.streak_days or 0),
        max_streak_days=int(user.max_streak_days or 0),
        level=int(user.level or 1),
        xp=int(user.xp or 0),
        next_level_xp=next_level_xp(int(user.xp or 0), settings.level_threshold_list),
        completed_lessons=completed_lessons,
        total_lessons=total_lessons,
        completed_courses=completed_courses,
        total_courses=total_courses,
        overall_percent=overall,
        solved_problems=solved,
        submissions=submissions,
        projects_completed=projects_completed,
        projects_total=projects_total,
        current_stage=_latest_stage(db, user),
    )


def get_heatmap(db: Session, user: User, days: int = 180) -> HeatmapOut:
    """学习热力图（按天聚合会话次数与分钟数，缺失日期补零）。"""
    days = max(1, min(366, int(days)))
    window = last_n_days(days)
    start = datetime(window[0].year, window[0].month, window[0].day, tzinfo=now_utc().tzinfo)
    sessions = db.scalars(
        select(LearningSession).where(
            LearningSession.user_id == user.id, LearningSession.started_at >= start
        )
    ).all()
    count_map: dict[DateType, int] = {}
    minutes_map: dict[DateType, int] = {}
    for item in sessions:
        key = item.started_at.date()
        count_map[key] = count_map.get(key, 0) + 1
        minutes_map[key] = minutes_map.get(key, 0) + int(session_seconds(item) // 60)

    points = [
        HeatmapPoint(date=day, count=count_map.get(day, 0), minutes=minutes_map.get(day, 0)) for day in window
    ]
    active_days = sum(1 for point in points if point.count > 0)
    return HeatmapOut(
        points=points,
        total_count=sum(point.count for point in points),
        active_days=active_days,
        max_count=max((point.count for point in points), default=0),
    )


def set_mode(db: Session, user: User, learning_mode: str) -> ModeOut:
    """切换学习模式（写入 profile.learning_mode）。"""
    from app.services import user_service

    profile = user_service.get_profile(db, user)
    profile.learning_mode = learning_mode
    db.commit()
    db.refresh(profile)
    return ModeOut(learning_mode=profile.learning_mode)


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------


def _latest_stage(db: Session, user: User) -> int | None:
    """最近学习的阶段序号。"""
    row = db.execute(
        select(Course.stage_no)
        .join(CourseEnrollment, CourseEnrollment.course_id == Course.id)
        .where(CourseEnrollment.user_id == user.id)
        .order_by(CourseEnrollment.updated_at.desc())
        .limit(1)
    ).first()
    return int(row[0]) if row else None
