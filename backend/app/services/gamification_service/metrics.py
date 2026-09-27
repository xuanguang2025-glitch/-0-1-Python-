"""游戏化服务 · 指标快照（全部使用 SQL 聚合，避免全表遍历）。"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.challenge import UserChallenge
from app.models.course import Course, CourseEnrollment
from app.models.enums import ChallengeStatus, ProgressStatus
from app.models.exam import ExamAttempt
from app.models.learning import Bookmark, KnowledgeMastery, LearningProgress, LearningSession, Mistake
from app.models.problem import Problem
from app.models.project import Project, UserProject
from app.models.submission import Submission
from app.models.user import User
from app.utils.time import day_range, now_utc, today_utc

from .common import ACCEPTED, count


def build_metrics(db: Session, user: User, event: dict[str, Any] | None = None) -> dict[str, Any]:
    """构建成就 / 每日任务评估所需的指标快照。"""
    uid = user.id
    day_start, _day_end = day_range(today_utc())

    lessons_completed = count(
        db,
        select(func.count())
        .select_from(LearningProgress)
        .where(LearningProgress.user_id == uid, LearningProgress.status == ProgressStatus.COMPLETED.value),
    )
    completed_courses = list(
        db.scalars(
            select(Course.slug)
            .join(CourseEnrollment, CourseEnrollment.course_id == Course.id)
            .where(CourseEnrollment.user_id == uid, CourseEnrollment.progress_percent >= 100)
        ).all()
    )
    problems_accepted = count(
        db,
        select(func.count(func.distinct(Submission.problem_id))).where(
            Submission.user_id == uid, Submission.status == ACCEPTED, Submission.problem_id.is_not(None)
        ),
    )
    by_type = db.execute(
        select(Problem.problem_type, func.count(func.distinct(Submission.problem_id)))
        .join(Submission, Submission.problem_id == Problem.id)
        .where(Submission.user_id == uid, Submission.status == ACCEPTED)
        .group_by(Problem.problem_type)
    ).all()
    by_difficulty = db.execute(
        select(Problem.difficulty, func.count(func.distinct(Submission.problem_id)))
        .join(Submission, Submission.problem_id == Problem.id)
        .where(Submission.user_id == uid, Submission.status == ACCEPTED)
        .group_by(Problem.difficulty)
    ).all()
    projects_completed = count(
        db,
        select(func.count())
        .select_from(UserProject)
        .where(UserProject.user_id == uid, UserProject.status == "completed"),
    )
    capstones_completed = count(
        db,
        select(func.count())
        .select_from(UserProject)
        .join(Project, Project.id == UserProject.project_id)
        .where(UserProject.user_id == uid, UserProject.status == "completed", Project.level >= 8),
    )
    exams_passed = count(
        db,
        select(func.count()).select_from(ExamAttempt).where(ExamAttempt.user_id == uid, ExamAttempt.passed.is_(True)),
    )
    exam_best = int(
        db.scalar(select(func.coalesce(func.max(ExamAttempt.score), 0)).where(ExamAttempt.user_id == uid)) or 0
    )
    challenges_completed = count(
        db,
        select(func.count())
        .select_from(UserChallenge)
        .where(UserChallenge.user_id == uid, UserChallenge.status == ChallengeStatus.COMPLETED.value),
    )
    bookmarks = count(db, select(func.count()).select_from(Bookmark).where(Bookmark.user_id == uid))
    mistakes_reviewed = count(
        db,
        select(func.count()).select_from(Mistake).where(Mistake.user_id == uid, Mistake.review_count > 0),
    )
    mastery_count = count(db, select(func.count()).select_from(KnowledgeMastery).where(KnowledgeMastery.user_id == uid))

    # 今日指标（每日任务用）
    lessons_today = count(
        db,
        select(func.count())
        .select_from(LearningProgress)
        .where(
            LearningProgress.user_id == uid,
            LearningProgress.status == ProgressStatus.COMPLETED.value,
            LearningProgress.completed_at >= day_start,
        ),
    )
    submissions_today = count(
        db,
        select(func.count())
        .select_from(Submission)
        .where(Submission.user_id == uid, Submission.created_at >= day_start),
    )
    accepted_today = count(
        db,
        select(func.count())
        .select_from(Submission)
        .where(Submission.user_id == uid, Submission.status == ACCEPTED, Submission.created_at >= day_start),
    )
    study_seconds_today = int(
        db.scalar(
            select(func.coalesce(func.sum(LearningSession.duration_seconds), 0)).where(
                LearningSession.user_id == uid, LearningSession.started_at >= day_start
            )
        )
        or 0
    )
    ai_messages_today = count(
        db,
        select(func.count())
        .select_from(LearningSession)
        .where(
            LearningSession.user_id == uid,
            LearningSession.session_type == "ai",
            LearningSession.started_at >= day_start,
        ),
    )
    mistake_reviews_today = count(
        db,
        select(func.count())
        .select_from(Mistake)
        .where(Mistake.user_id == uid, Mistake.review_count > 0, Mistake.updated_at >= day_start),
    )

    since = now_utc() - timedelta(days=30)
    hours = {
        moment.hour
        for moment in db.scalars(
            select(LearningSession.started_at).where(
                LearningSession.user_id == uid, LearningSession.started_at >= since
            ).limit(1000)
        ).all()
        if moment is not None
    }
    if event and isinstance(event.get("hour"), int):
        hours.add(int(event["hour"]))

    return {
        "lessons_completed": lessons_completed,
        "courses_completed": len(completed_courses),
        "completed_course_slugs": set(completed_courses),
        "problems_accepted": problems_accepted,
        "accepted_by_type": {str(r[0]): int(r[1] or 0) for r in by_type},
        "accepted_by_difficulty": {str(r[0]): int(r[1] or 0) for r in by_difficulty},
        "streak_days": int(user.streak_days or 0),
        "projects_completed": projects_completed,
        "capstones_completed": capstones_completed,
        "exams_passed": exams_passed,
        "exam_best_score": exam_best,
        "challenges_completed": challenges_completed,
        "bookmarks": bookmarks,
        "mistakes_reviewed": mistakes_reviewed,
        "mastery_count": mastery_count,
        "level": int(user.level or 1),
        "study_hours": hours,
        "login": 1,
        "lessons_today": lessons_today,
        "submissions_today": submissions_today,
        "accepted_today": accepted_today,
        "study_minutes": study_seconds_today // 60,
        "ai_messages": ai_messages_today,
        "mistake_reviews": mistake_reviews_today,
    }


def satisfied(condition: dict[str, Any], metrics: dict[str, Any]) -> bool:
    """评估单条成就条件（兼容 `{type, value}` 与 `{metric, op, value}` 两种格式）。"""
    if not condition:
        return False
    ctype = condition.get("type")
    value = condition.get("value")

    if ctype is None:
        # 兼容模型内置格式 {metric, op, value}
        metric = condition.get("metric")
        if metric not in metrics:
            return False
        actual, target = metrics[metric], condition.get("value", 0)
        try:
            return int(actual) >= int(target)
        except (TypeError, ValueError):
            return False

    if ctype == "lessons_completed":
        return metrics["lessons_completed"] >= int(value or 0)
    if ctype == "course_completed":
        return str(value) in metrics["completed_course_slugs"]
    if ctype == "stages_completed":
        return metrics["courses_completed"] >= int(value or 0)
    if ctype == "problems_accepted":
        return metrics["problems_accepted"] >= int(value or 0)
    if ctype == "problems_accepted_type":
        return metrics["accepted_by_type"].get(str((value or {}).get("problem_type")), 0) >= int(
            (value or {}).get("count", 1)
        )
    if ctype == "problems_accepted_difficulty":
        return metrics["accepted_by_difficulty"].get(str((value or {}).get("difficulty")), 0) >= int(
            (value or {}).get("count", 1)
        )
    if ctype == "streak_days":
        return metrics["streak_days"] >= int(value or 0)
    if ctype == "projects_completed":
        return metrics["projects_completed"] >= int(value or 0)
    if ctype == "capstones_completed":
        return metrics["capstones_completed"] >= int(value or 0)
    if ctype == "exams_passed":
        return metrics["exams_passed"] >= int(value or 0)
    if ctype == "exam_score":
        return metrics["exam_best_score"] >= int(value or 0)
    if ctype == "challenges_completed":
        return metrics["challenges_completed"] >= int(value or 0)
    if ctype == "bookmarks":
        return metrics["bookmarks"] >= int(value or 0)
    if ctype == "mistakes_reviewed":
        return metrics["mistakes_reviewed"] >= int(value or 0)
    if ctype == "level_reached":
        return metrics["level"] >= int(value or 0)
    if ctype == "study_time_range":
        start, end = int((value or {}).get("start", 0)), int((value or {}).get("end", 24))
        return any(start <= hour < end for hour in metrics["study_hours"])
    return False
