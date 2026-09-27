"""统计报表服务 · 分类正确率。"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.problem import Problem
from app.models.submission import Submission
from app.models.user import User
from app.schemas.statistics import CategoryStat, CategoryStatsOut

from .common import ACCEPTED


def categories(db: Session, user: User) -> CategoryStatsOut:
    """`GET /statistics/categories`：各分类已解决 / 总数 / 得分。"""
    total_rows = db.execute(
        select(Problem.category, func.count()).where(Problem.is_published.is_(True)).group_by(Problem.category)
    ).all()
    solved_rows = db.execute(
        select(Problem.category, func.count(func.distinct(Submission.problem_id)))
        .join(Submission, Submission.problem_id == Problem.id)
        .where(Submission.user_id == user.id, Submission.status == ACCEPTED)
        .group_by(Problem.category)
    ).all()
    solved_map = {str(row[0]): int(row[1] or 0) for row in solved_rows}
    items: list[CategoryStat] = []
    for category, total in sorted(total_rows, key=lambda r: str(r[0])):
        total_int = int(total or 0)
        solved = solved_map.get(str(category), 0)
        items.append(
            CategoryStat(
                category=str(category),
                solved=solved,
                total=total_int,
                score=round(solved / total_int * 100, 1) if total_int else 0.0,
            )
        )
    return CategoryStatsOut(categories=items)
