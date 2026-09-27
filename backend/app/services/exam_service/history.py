"""考试服务 · 作答历史与成绩单 / 题目简表。"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.pagination import PageParams
from app.models.exam import ExamAttempt
from app.models.problem import Problem
from app.models.user import User
from app.schemas.exam import ExamAttemptBrief, ExamPerQuestionResult, ExamReportOut
from app.schemas.problem import ProblemBrief

from .attempts import get_attempt


def list_attempts(db: Session, user: User, params: PageParams) -> tuple[list[ExamAttemptBrief], int]:
    """`GET /exams/attempts`：作答历史分页。"""
    total = int(
        db.scalar(select(func.count()).select_from(ExamAttempt).where(ExamAttempt.user_id == user.id)) or 0
    )
    rows = list(
        db.scalars(
            select(ExamAttempt)
            .where(ExamAttempt.user_id == user.id)
            .order_by(ExamAttempt.started_at.desc())
            .offset(params.offset)
            .limit(params.limit)
        ).all()
    )
    items: list[ExamAttemptBrief] = []
    for row in rows:
        items.append(
            ExamAttemptBrief(
                id=row.id,
                exam_id=row.exam_id,
                exam_title=row.exam.title if row.exam else None,
                status=row.status,
                score=int(row.score or 0),
                passed=bool(row.passed),
                started_at=row.started_at,
                submitted_at=row.submitted_at,
            )
        )
    return items, total


def get_attempt_report(db: Session, user: User, attempt_id: str) -> ExamReportOut:
    """`GET /exams/attempts/{attempt_id}`：成绩单。"""
    attempt = get_attempt(db, user, attempt_id)
    report = attempt.report_json or {}
    return ExamReportOut(
        attempt_id=attempt.id,
        exam_id=attempt.exam_id,
        score=int(attempt.score or 0),
        total_score=int(report.get("total_score", attempt.exam.total_score if attempt.exam else 100)),
        passed=bool(attempt.passed),
        per_question=[ExamPerQuestionResult(**item) for item in report.get("per_question", [])],
        weak_topics=list(report.get("weak_topics", [])),
        submitted_at=attempt.submitted_at,
    )


def problem_briefs(db: Session, problem_ids: list[str]) -> list[ProblemBrief]:
    """按 id 列表返回题目简表（挑战详情复用）。"""
    if not problem_ids:
        return []
    problems = {p.id: p for p in db.scalars(select(Problem).where(Problem.id.in_(problem_ids))).all()}
    briefs: list[ProblemBrief] = []
    for pid in problem_ids:
        problem = problems.get(pid)
        if problem is not None:
            briefs.append(ProblemBrief.model_validate(problem))
    return briefs
