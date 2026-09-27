"""考试服务 · 作答流程（开始 / 保存 / 交卷）。"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError, ErrorCode
from app.models.enums import ExamAttemptStatus
from app.models.exam import Exam, ExamAttempt
from app.models.problem import Problem
from app.models.user import User
from app.schemas.exam import (
    ExamAttemptOut,
    ExamBrief,
    ExamDetail,
    ExamPerQuestionResult,
    ExamReportOut,
    ExamSaveOut,
)
from app.services import gamification_service
from app.utils.time import now_utc

from .common import PAPER_KEY, is_expired, remaining_seconds
from .grading import grade_problem
from .papers import assemble_specs, load_questions, paper_specs


def list_exams(db: Session, user: User, level: str | None = None) -> list[ExamBrief]:
    """`GET /exams`：试卷列表（含我的最好成绩）。"""
    stmt = select(Exam).where(Exam.is_published.is_(True))
    if level:
        stmt = stmt.where(Exam.level == level)
    exams = list(db.scalars(stmt.order_by(Exam.level.asc(), Exam.code.asc())).all())

    result: list[ExamBrief] = []
    for exam in exams:
        attempts = list(
            db.scalars(
                select(ExamAttempt).where(ExamAttempt.user_id == user.id, ExamAttempt.exam_id == exam.id)
            ).all()
        )
        best = max((int(a.score or 0) for a in attempts), default=None)
        passed = any(bool(a.passed) for a in attempts)
        result.append(
            ExamBrief(
                id=exam.id,
                code=exam.code,
                title=exam.title,
                level=exam.level,
                duration_minutes=exam.duration_minutes,
                total_score=exam.total_score,
                pass_score=exam.pass_score,
                question_count=len(exam.problem_ids),
                my_best_score=best,
                my_passed=passed,
            )
        )
    return result


def get_exam_detail(db: Session, user: User, exam_id: str) -> ExamDetail:
    """`GET /exams/{id}`：试卷详情（不含答案）。"""
    exam = get_exam(db, exam_id)
    brief = next((item for item in list_exams(db, user) if item.id == exam.id), None)
    if brief is None:
        brief = ExamBrief(id=exam.id, code=exam.code, title=exam.title, level=exam.level)
    questions = load_questions(db, paper_specs(exam))
    return ExamDetail(exam=brief, questions=questions)


def get_exam(db: Session, exam_id: str) -> Exam:
    """按 id 获取试卷（不存在抛 404）。"""
    exam = db.get(Exam, exam_id)
    if exam is None:
        raise AppError(code=ErrorCode.EXAM_NOT_FOUND, message="试卷不存在", status_code=404)
    return exam


def paper_from_attempt(attempt: ExamAttempt) -> list[dict[str, Any]]:
    """从作答记录中还原试卷定义。"""
    data = attempt.answers_json or {}
    specs = data.get(PAPER_KEY) or []
    return [dict(item) for item in specs if isinstance(item, dict)]


def _minutes(minutes: int) -> timedelta:
    """分钟 → timedelta。"""
    return timedelta(minutes=max(1, int(minutes or 60)))


def get_attempt(db: Session, user: User, attempt_id: str) -> ExamAttempt:
    """获取属于当前用户的作答记录（不存在抛 404）。"""
    attempt = db.get(ExamAttempt, attempt_id)
    if attempt is None or attempt.user_id != user.id:
        raise AppError(code=ErrorCode.NOT_FOUND, message="作答记录不存在", status_code=404)
    return attempt


def start_exam(db: Session, user: User, exam_id: str) -> ExamAttemptOut:
    """`POST /exams/{id}/start`：生成试卷并开始计时（已有未超时作答则续答）。"""
    exam = get_exam(db, exam_id)
    existing = db.scalars(
        select(ExamAttempt)
        .where(
            ExamAttempt.user_id == user.id,
            ExamAttempt.exam_id == exam.id,
            ExamAttempt.status == ExamAttemptStatus.IN_PROGRESS.value,
        )
        .order_by(ExamAttempt.started_at.desc())
    ).first()

    if existing is not None and not is_expired(existing):
        attempt = existing
        specs = paper_from_attempt(existing) or assemble_specs(db, exam)
    else:
        specs = assemble_specs(db, exam)
        attempt = ExamAttempt(
            user_id=user.id,
            exam_id=exam.id,
            status=ExamAttemptStatus.IN_PROGRESS.value,
            answers_json={PAPER_KEY: specs},
            deadline_at=now_utc() + _minutes(exam.duration_minutes),
        )
        db.add(attempt)
        db.commit()
        db.refresh(attempt)

    return ExamAttemptOut(
        attempt_id=attempt.id,
        exam_id=exam.id,
        deadline_at=attempt.deadline_at,
        remaining_seconds=remaining_seconds(attempt),
        questions=load_questions(db, specs),
    )


def save_answers(db: Session, user: User, attempt_id: str, answers: dict[str, Any]) -> ExamSaveOut:
    """中途保存作答（保留试卷定义）。"""
    attempt = get_attempt(db, user, attempt_id)
    if attempt.status != ExamAttemptStatus.IN_PROGRESS.value:
        raise AppError(code=ErrorCode.BAD_REQUEST, message="该作答已提交，无法保存", status_code=400)
    merged = dict(attempt.answers_json or {})
    for key, value in answers.items():
        if key != PAPER_KEY:
            merged[key] = value
    attempt.answers_json = merged
    db.commit()
    return ExamSaveOut(attempt_id=attempt.id, saved=len(answers), remaining_seconds=remaining_seconds(attempt))


def submit_exam(db: Session, user: User, exam_id: str, payload: dict[str, Any]) -> ExamReportOut:
    """`POST /exams/{id}/submit`：自动判分并写回报告。"""
    exam = get_exam(db, exam_id)
    attempt_id = str(payload.get("attempt_id") or "")
    attempt = get_attempt(db, user, attempt_id)
    answers = dict(payload.get("answers") or {})
    specs = paper_from_attempt(attempt) or assemble_specs(db, exam)

    ids = [str(s["id"]) for s in specs if s.get("id")]
    problems = {p.id: p for p in db.scalars(select(Problem).where(Problem.id.in_(ids))).all()}
    per_question: list[ExamPerQuestionResult] = []
    total_score = 0
    earned = 0
    wrong_categories: dict[str, int] = {}
    for spec in specs:
        problem = problems.get(str(spec.get("id")))
        if problem is None:
            continue
        point = int(spec.get("score", problem.score or 10))
        total_score += point
        result = grade_problem(db, problem, answers.get(problem.id))
        earned += int(result["score"])
        per_question.append(
            ExamPerQuestionResult(
                problem_id=problem.id,
                correct=bool(result["correct"]),
                score=int(result["score"]),
                expected=result.get("expected"),
            )
        )
        if not result["correct"]:
            wrong_categories[problem.category] = wrong_categories.get(problem.category, 0) + 1

    passed = earned >= int(exam.pass_score or 60)
    weak_topics = [
        {"category": key, "wrong": value}
        for key, value in sorted(wrong_categories.items(), key=lambda kv: -kv[1])
    ]
    report = {
        "score": earned,
        "total_score": total_score,
        "passed": passed,
        "per_question": [item.model_dump() for item in per_question],
        "weak_topics": weak_topics,
    }
    attempt.grade(earned, passed, report)
    gamification_service.award_xp(db, user, max(0, earned // 2), "exam", "exam", exam.id)
    db.commit()
    gamification_service.check_and_unlock(db, user, {"metric": "exam_score"})

    return ExamReportOut(
        attempt_id=attempt.id,
        exam_id=exam.id,
        score=earned,
        total_score=total_score,
        passed=passed,
        per_question=per_question,
        weak_topics=weak_topics,
        submitted_at=attempt.submitted_at,
    )
