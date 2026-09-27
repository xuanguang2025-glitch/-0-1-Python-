"""题库服务：列表 / 筛选字典 / 随机 / 推荐 / 详情 / 相似题 / 讨论区摘要（`docs/API.md` §2.5）。

安全红线：**非样例测试点（`is_sample=false`）的 `expected_output` 绝不进入任何返回前端的数据**，
详情仅暴露 `is_sample=true` 的用例，且用例片段只回传 input / expected（样例本身就是公开信息）。
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError, ErrorCode
from app.core.pagination import PageParams
from app.models.enums import MasteryLevel, ProblemType, SubmissionStatus
from app.models.learning import KnowledgeMastery
from app.models.problem import Problem, ProblemTag, Tag, TestCase
from app.models.course import Topic
from app.models.submission import Submission
from app.models.user import User
from app.schemas.problem import (
    DiscussionAIOut,
    ProblemBrief,
    ProblemDetail,
    ProblemTagOut,
    TagOut,
    TestCaseBrief,
)

logger = logging.getLogger("pythonlab.problem")

#: 列表排序字段白名单 → ORM 列
_SORT_COLUMNS = {
    "created_at": lambda: Problem.created_at,
    "updated_at": lambda: Problem.updated_at,
    "difficulty": lambda: Problem.difficulty,
    "acceptance_rate": lambda: Problem.acceptance_rate,
    "score": lambda: Problem.score,
    "order_index": lambda: Problem.order_index,
}

_PROBLEM_TYPE_LABELS = {
    "choice": "选择题",
    "judge": "判断题",
    "blank": "填空题",
    "completion": "代码补全",
    "coding": "编程题",
    "debug": "Debug",
    "algorithm": "算法题",
}


def list_problems(
    db: Session,
    user: User | None,
    *,
    problem_type: str | None = None,
    difficulty: str | None = None,
    category: str | None = None,
    tag: str | None = None,
    status: str | None = None,
    keyword: str | None = None,
    params: PageParams,
) -> tuple[list[Problem], int]:
    """按多条件筛选题目并分页，返回 `(题目列表, 总数)`。"""
    stmt = select(Problem).where(Problem.is_published.is_(True))
    if problem_type:
        stmt = stmt.where(Problem.problem_type == problem_type)
    if difficulty:
        stmt = stmt.where(Problem.difficulty == difficulty)
    if category:
        stmt = stmt.where(Problem.category == category)
    if keyword:
        like = f"%{keyword.strip()}%"
        stmt = stmt.where(or_(Problem.title.ilike(like), Problem.statement_md.ilike(like)))
    if tag:
        stmt = stmt.where(
            Problem.id.in_(
                select(ProblemTag.problem_id).join(Tag, Tag.id == ProblemTag.tag_id).where(Tag.slug == tag)
            )
        )
    if status in ("solved", "unsolved") and user is not None:
        solved = select(Submission.problem_id).where(
            Submission.user_id == user.id,
            Submission.status == SubmissionStatus.ACCEPTED.value,
            Submission.problem_id.is_not(None),
        )
        stmt = stmt.where(Problem.id.in_(solved) if status == "solved" else Problem.id.notin_(solved))

    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    stmt = _apply_sort(stmt, params.sort)
    items = list(db.scalars(stmt.offset(params.offset).limit(params.limit)).all())
    return items, total


def build_briefs(db: Session, problems: list[Problem], user: User | None) -> list[ProblemBrief]:
    """批量构造题目列表项（含标签与「我的状态」）。"""
    if not problems:
        return []
    ids = [item.id for item in problems]
    tags_map = _tags_by_problem(db, ids)
    status_map = _my_status_map(db, user, ids)
    briefs: list[ProblemBrief] = []
    for problem in problems:
        my_status = status_map.get(problem.id, "unsolved")
        briefs.append(
            ProblemBrief(
                id=problem.id,
                slug=problem.slug,
                title=problem.title,
                problem_type=problem.problem_type,
                difficulty=problem.difficulty,
                category=problem.category,
                score=int(problem.score or 0),
                xp_reward=int(problem.xp_reward or 0),
                submission_count=int(problem.submission_count or 0),
                accepted_count=int(problem.accepted_count or 0),
                acceptance_rate=float(problem.acceptance_rate or 0.0),
                tags=tags_map.get(problem.id, []),
                my_status=my_status if user is not None else None,
            )
        )
    return briefs


def get_problem_or_404(db: Session, problem_id: str) -> Problem:
    """按 id 获取已发布题目，不存在则 404。"""
    problem = db.get(Problem, problem_id)
    if problem is None or not problem.is_published:
        raise AppError(code=ErrorCode.PROBLEM_NOT_FOUND, message="题目不存在", status_code=404)
    return problem


def build_detail(db: Session, problem: Problem, user: User | None) -> ProblemDetail:
    """构造题目详情（仅含样例用例，隐藏用例绝不外泄）。"""
    tags = list(
        db.scalars(
            select(Tag).join(ProblemTag, ProblemTag.tag_id == Tag.id).where(ProblemTag.problem_id == problem.id)
        ).all()
    )
    sample_cases = [
        TestCaseBrief.model_validate(case)
        for case in sorted(problem.test_cases or [], key=lambda item: item.order_index)
        if case.is_sample
    ]
    my_status, last_submission_id = _my_status_for(db, user, problem.id)
    return ProblemDetail(
        id=problem.id,
        slug=problem.slug,
        title=problem.title,
        statement_md=problem.statement_md or "",
        problem_type=problem.problem_type,
        difficulty=problem.difficulty,
        category=problem.category,
        input_format=problem.input_format,
        output_format=problem.output_format,
        sample_input=problem.sample_input,
        sample_output=problem.sample_output,
        constraints=problem.constraints,
        options_json=problem.options_json,
        hint_md=problem.hint_md,
        solution_md=problem.solution_md,
        starter_code=problem.starter_code,
        buggy_code=problem.buggy_code,
        time_limit_ms=int(problem.time_limit_ms or 5000),
        memory_limit_mb=int(problem.memory_limit_mb or 256),
        score=int(problem.score or 0),
        xp_reward=int(problem.xp_reward or 0),
        submission_count=int(problem.submission_count or 0),
        accepted_count=int(problem.accepted_count or 0),
        acceptance_rate=float(problem.acceptance_rate or 0.0),
        tags=[TagOut.model_validate(item) for item in tags],
        sample_cases=sample_cases,
        my_status=my_status if user is not None else None,
        my_last_submission_id=last_submission_id,
    )


def get_filters(db: Session) -> ProblemTagOut:
    """返回题目筛选字典（题型 / 难度 / 分类的计数 + 标签列表）。"""
    base = select(Problem).where(Problem.is_published.is_(True)).subquery()

    def _group(column: Any) -> list[dict[str, Any]]:
        rows = db.execute(select(column, func.count()).select_from(base).group_by(column)).all()
        return [{"value": str(value), "count": int(count)} for value, count in rows]

    types = _group(base.c.problem_type)
    for item in types:
        item["label"] = _PROBLEM_TYPE_LABELS.get(item["value"], item["value"])
    tags = db.execute(
        select(Tag, func.count(ProblemTag.problem_id))
        .outerjoin(ProblemTag, ProblemTag.tag_id == Tag.id)
        .group_by(Tag.id)
        .order_by(Tag.order_index.asc(), Tag.name.asc())
    ).all()
    return ProblemTagOut(
        types=types,
        difficulties=_group(base.c.difficulty),
        categories=_group(base.c.category),
        tags=[TagOut.model_validate(tag).model_copy(update={"count": int(count)}) for tag, count in tags],
    )


def get_random_problem(
    db: Session,
    user: User | None,
    *,
    difficulty: str | None = None,
    category: str | None = None,
    exclude_solved: bool = True,
) -> Problem:
    """随机取一题（可排除已解决题目）。"""
    stmt = select(Problem).where(Problem.is_published.is_(True))
    if difficulty:
        stmt = stmt.where(Problem.difficulty == difficulty)
    if category:
        stmt = stmt.where(Problem.category == category)
    if exclude_solved and user is not None:
        solved = select(Submission.problem_id).where(
            Submission.user_id == user.id,
            Submission.status == SubmissionStatus.ACCEPTED.value,
            Submission.problem_id.is_not(None),
        )
        stmt = stmt.where(Problem.id.notin_(solved))
    problem = db.scalars(stmt.order_by(func.random()).limit(1)).first()
    if problem is None:
        # 兜底：排除已解决后为空时返回任意一题
        problem = db.scalars(
            select(Problem).where(Problem.is_published.is_(True)).order_by(func.random()).limit(1)
        ).first()
    if problem is None:
        raise AppError(code=ErrorCode.PROBLEM_NOT_FOUND, message="题库为空", status_code=404)
    return problem


def recommend_problems(db: Session, user: User, *, limit: int = 10) -> list[Problem]:
    """基于薄弱知识点 + 未解决题目推荐题目。"""
    weak_levels = (MasteryLevel.NONE.value, MasteryLevel.WEAK.value, MasteryLevel.MEDIUM.value)
    weak_slugs = list(
        db.scalars(
            select(Topic.slug)
            .join(KnowledgeMastery, KnowledgeMastery.topic_id == Topic.id)
            .where(KnowledgeMastery.user_id == user.id, KnowledgeMastery.mastery_level.in_(weak_levels))
            .order_by(KnowledgeMastery.mastery_score.asc())
            .limit(10)
        ).all()
    )
    solved = select(Submission.problem_id).where(
        Submission.user_id == user.id,
        Submission.status == SubmissionStatus.ACCEPTED.value,
        Submission.problem_id.is_not(None),
    )
    conditions = [Problem.is_published.is_(True), Problem.id.notin_(solved)]
    stmt = select(Problem).where(*conditions)
    if weak_slugs:
        stmt = stmt.where(
            Problem.id.in_(
                select(ProblemTag.problem_id).join(Tag, Tag.id == ProblemTag.tag_id).where(Tag.slug.in_(weak_slugs))
            )
        )
    picked = list(db.scalars(stmt.order_by(Problem.difficulty.asc(), func.random()).limit(limit)).all())
    if len(picked) < limit:
        # 补充：未解决题目随机补齐，保证数量充足
        exclude_ids = [item.id for item in picked]
        filler_stmt = select(Problem).where(*conditions)
        if exclude_ids:
            filler_stmt = filler_stmt.where(Problem.id.notin_(exclude_ids))
        picked.extend(
            db.scalars(filler_stmt.order_by(func.random()).limit(limit - len(picked))).all()
        )
    return picked


def similar_problems(db: Session, problem: Problem, *, limit: int = 5) -> list[Problem]:
    """相似题推荐：同分类/同题型优先，其次难度接近。"""
    stmt = (
        select(Problem)
        .where(
            Problem.is_published.is_(True),
            Problem.id != problem.id,
            or_(Problem.category == problem.category, Problem.problem_type == problem.problem_type),
        )
        .order_by(Problem.category == problem.category, Problem.difficulty.asc())
        .limit(limit)
    )
    items = list(db.scalars(stmt).all())
    if len(items) < limit:
        exclude_ids = [item.id for item in items] + [problem.id]
        filler = db.scalars(
            select(Problem)
            .where(Problem.is_published.is_(True), Problem.id.notin_(exclude_ids))
            .order_by(func.random())
            .limit(limit - len(items))
        ).all()
        items.extend(filler)
    return items


def discussion_ai(problem: Problem) -> DiscussionAIOut:
    """生成题解要点（本地模板，无外部 Key 时亦可用）。"""
    points: list[str] = []
    if problem.problem_type in (ProblemType.CHOICE.value, ProblemType.JUDGE.value, ProblemType.BLANK.value):
        points.append("先明确本题考查的核心概念，再逐项排除明显错误的选项/答案。")
    else:
        points.append("先读输入 / 输出格式，明确需要读取哪些数据、输出什么。")
        points.append("把大问题拆成小步骤：解析输入 → 处理逻辑 → 格式化输出。")
    if problem.hint_md:
        points.append(f"题目提示：{problem.hint_md.strip().splitlines()[0][:120]}")
    if problem.solution_md:
        points.append("题解要点（节选）：" + problem.solution_md.strip().splitlines()[0][:120])
    if problem.input_format:
        points.append("注意输入格式细节，避免因空格 / 换行导致格式错误。")
    summary = "### 解题思路要点\n" + "\n".join(f"{index}. {text}" for index, text in enumerate(points, start=1))
    return DiscussionAIOut(summary_md=summary, degraded=True)


# ------------------------------------------------------------------ 内部工具
def _apply_sort(stmt: Any, sort: str) -> Any:
    """按白名单给查询加排序（未知字段回落到创建时间倒序）。"""
    key = sort if sort in _SORT_COLUMNS or sort.lstrip("-") in _SORT_COLUMNS else "-created_at"
    descending = key.startswith("-")
    column = _SORT_COLUMNS[key.lstrip("-")]()
    return stmt.order_by(column.desc() if descending else column.asc(), Problem.id.asc())


def _tags_by_problem(db: Session, problem_ids: list[str]) -> dict[str, list[str]]:
    """批量查询每题标签（返回标签 slug 列表）。"""
    rows = db.execute(
        select(ProblemTag.problem_id, Tag.slug)
        .join(Tag, Tag.id == ProblemTag.tag_id)
        .where(ProblemTag.problem_id.in_(problem_ids))
    ).all()
    mapping: dict[str, list[str]] = defaultdict(list)
    for problem_id, slug in rows:
        mapping[problem_id].append(str(slug))
    return mapping


def _my_status_map(db: Session, user: User | None, problem_ids: list[str]) -> dict[str, str]:
    """批量查询用户对题目的状态（solved/attempted/unsolved）。"""
    if user is None or not problem_ids:
        return {}
    rows = db.execute(
        select(Submission.problem_id, Submission.status).where(
            Submission.user_id == user.id, Submission.problem_id.in_(problem_ids)
        )
    ).all()
    mapping: dict[str, str] = {}
    for problem_id, submission_status in rows:
        if problem_id is None:
            continue
        if submission_status == SubmissionStatus.ACCEPTED.value:
            mapping[problem_id] = "solved"
        elif mapping.get(problem_id) != "solved":
            mapping[problem_id] = "attempted"
    return mapping


def _my_status_for(db: Session, user: User | None, problem_id: str) -> tuple[str | None, str | None]:
    """单题状态与最近一次提交 id。"""
    if user is None:
        return None, None
    mapping = _my_status_map(db, user, [problem_id])
    last_id = db.scalar(
        select(Submission.id)
        .where(Submission.user_id == user.id, Submission.problem_id == problem_id)
        .order_by(Submission.created_at.desc())
        .limit(1)
    )
    status = mapping.get(problem_id, "unsolved")
    return status, (str(last_id) if last_id else None)


__all__ = [
    "build_briefs",
    "build_detail",
    "discussion_ai",
    "get_filters",
    "get_problem_or_404",
    "get_random_problem",
    "list_problems",
    "recommend_problems",
    "similar_problems",
]
