"""考试服务 · 试卷装配与题目展示。"""

from __future__ import annotations

import random
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.exam import Exam
from app.models.problem import Problem
from app.schemas.exam import ExamQuestionOut

from .common import DIFFICULTY_BY_LEVEL


def paper_specs(exam: Exam) -> list[dict[str, Any]]:
    """返回试卷题目与分值定义（`{id, score, order}`）。"""
    specs = exam.question_specs
    if specs:
        return specs
    return []


def assemble_specs(db: Session, exam: Exam) -> list[dict[str, Any]]:
    """组装试卷：优先用试卷定义，缺失时按难度从题库抽取（选择 + 代码 + Debug + 编程）。"""
    specs = paper_specs(exam)
    if not specs:
        difficulties = DIFFICULTY_BY_LEVEL.get(exam.level, ("easy", "medium"))
        problems = list(
            db.scalars(
                select(Problem)
                .where(Problem.is_published.is_(True), Problem.difficulty.in_(difficulties))
                .order_by(Problem.difficulty.asc(), Problem.id.asc())
                .limit(8)
            ).all()
        )
        specs = [{"id": p.id, "score": int(p.score or 10), "order": i} for i, p in enumerate(problems)]
    if exam.shuffle:
        shuffled = list(specs)
        random.shuffle(shuffled)
        for order, spec in enumerate(shuffled):
            spec["order"] = order
        return shuffled
    return specs


def question_out(problem: Problem, score: int) -> ExamQuestionOut:
    """构造不含答案的题目响应体。"""
    return ExamQuestionOut(
        problem_id=problem.id,
        title=problem.title,
        problem_type=problem.problem_type,
        difficulty=problem.difficulty,
        score=int(score),
        statement_md=problem.statement_md or "",
        options_json=problem.options_json,
        starter_code=problem.starter_code,
        sample_input=problem.sample_input,
        sample_output=problem.sample_output,
    )


def load_questions(db: Session, specs: list[dict[str, Any]]) -> list[ExamQuestionOut]:
    """按 spec 批量加载题目，构造题目响应列表。"""
    ids = [str(spec.get("id")) for spec in specs if spec.get("id")]
    if not ids:
        return []
    problems = {p.id: p for p in db.scalars(select(Problem).where(Problem.id.in_(ids))).all()}
    result: list[ExamQuestionOut] = []
    for spec in specs:
        problem = problems.get(str(spec.get("id")))
        if problem is not None:
            result.append(question_out(problem, int(spec.get("score", problem.score or 10))))
    return result
