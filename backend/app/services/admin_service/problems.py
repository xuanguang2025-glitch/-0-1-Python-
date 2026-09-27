"""管理端服务 · 题目 / 测试用例。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ErrorCode
from app.core.pagination import PageParams
from app.models.problem import Problem, ProblemTag, Tag, TestCase
from app.models.user import User

from .common import apply_fields, audit, get_or_404


def list_problems(
    db: Session,
    params: PageParams,
    *,
    q: str | None = None,
    difficulty: str | None = None,
    category: str | None = None,
) -> tuple[list[Problem], int]:
    """题目列表。"""
    conditions: list[Any] = []
    if q:
        conditions.append(Problem.title.ilike(f"%{q.strip()}%"))
    if difficulty:
        conditions.append(Problem.difficulty == difficulty)
    if category:
        conditions.append(Problem.category == category)
    total = int(db.scalar(select(func.count()).select_from(Problem).where(*conditions)) or 0)
    rows = list(
        db.scalars(
            select(Problem)
            .where(*conditions)
            .order_by(Problem.created_at.desc())
            .offset(params.offset)
            .limit(params.limit)
        ).all()
    )
    return rows, total


def create_problem(db: Session, actor: User, payload: dict[str, Any], meta: dict[str, Any]) -> Problem:
    """新建题目（含测试用例）。"""
    test_cases = payload.pop("test_cases", []) or []
    tags = payload.pop("tags", []) or []
    problem = Problem(**payload, created_by=actor.id)
    problem.clamp_limits()
    db.add(problem)
    db.flush()
    replace_test_cases(db, problem, test_cases)
    sync_problem_tags(db, problem, tags)
    audit(db, actor, "admin.problem.create", "problem", problem.id, after={"slug": problem.slug}, meta=meta)
    db.commit()
    db.refresh(problem)
    return problem


def update_problem(
    db: Session, actor: User, problem_id: str, payload: dict[str, Any], meta: dict[str, Any]
) -> Problem:
    """更新题目。"""
    test_cases = payload.pop("test_cases", None)
    tags = payload.pop("tags", None)
    problem = get_or_404(db, Problem, problem_id, ErrorCode.PROBLEM_NOT_FOUND, "题目不存在")
    apply_fields(problem, payload)
    problem.clamp_limits()
    if test_cases is not None:
        replace_test_cases(db, problem, test_cases)
    if tags is not None:
        sync_problem_tags(db, problem, tags)
    audit(db, actor, "admin.problem.update", "problem", problem.id, after={"title": problem.title}, meta=meta)
    db.commit()
    db.refresh(problem)
    return problem


def delete_problem(db: Session, actor: User, problem_id: str, meta: dict[str, Any]) -> None:
    """删除题目。"""
    problem = get_or_404(db, Problem, problem_id, ErrorCode.PROBLEM_NOT_FOUND, "题目不存在")
    db.delete(problem)
    audit(db, actor, "admin.problem.delete", "problem", problem_id, meta=meta)
    db.commit()


def replace_test_cases(db: Session, problem: Problem, cases: list[dict[str, Any]]) -> None:
    """覆盖式重建题目测试用例。"""
    for case in list(problem.test_cases or []):
        db.delete(case)
    db.flush()
    for index, case in enumerate(cases):
        data = dict(case)
        data.setdefault("order_index", index)
        db.add(TestCase(problem_id=problem.id, **data))


def sync_problem_tags(db: Session, problem: Problem, tag_slugs: list[str]) -> None:
    """按 slug 覆盖式重建题目标签关联。"""
    db.query(ProblemTag).filter(ProblemTag.problem_id == problem.id).delete()
    if not tag_slugs:
        return
    tags = {t.slug: t.id for t in db.scalars(select(Tag).where(Tag.slug.in_(tag_slugs))).all()}
    for slug in tag_slugs:
        if slug in tags:
            db.add(ProblemTag(problem_id=problem.id, tag_id=tags[slug]))


def import_problems(
    db: Session, actor: User, items: list[dict[str, Any]], meta: dict[str, Any]
) -> dict[str, Any]:
    """批量导入题目，返回 `{created, updated, failed}`。"""
    created = updated = 0
    failed: list[dict[str, Any]] = []
    for index, raw in enumerate(items):
        try:
            slug = str(raw.get("slug") or "").strip()
            if not slug:
                raise ValueError("缺少 slug")
            existing = db.scalars(select(Problem).where(Problem.slug == slug)).one_or_none()
            payload = {
                k: v
                for k, v in raw.items()
                if k in ("title", "statement_md", "problem_type", "difficulty",
                         "category", "answer_json", "options_json", "score", "xp_reward")
            }
            if existing is None:
                problem = Problem(slug=slug, title=str(raw.get("title") or slug), created_by=actor.id, **payload)
                db.add(problem)
                db.flush()
                created += 1
            else:
                apply_fields(existing, payload)
                problem = existing
                updated += 1
            if raw.get("test_cases"):
                replace_test_cases(db, problem, raw["test_cases"])
        except Exception as exc:  # noqa: BLE001 - 单条失败不影响整体
            failed.append({"index": index, "error": str(exc)})
    audit(
        db, actor, "admin.problem.import", "problem", None,
        after={"created": created, "updated": updated}, meta=meta,
    )
    db.commit()
    return {"created": created, "updated": updated, "failed": failed}


def create_test_case(db: Session, actor: User, payload: dict[str, Any], meta: dict[str, Any]) -> TestCase:
    """新建测试用例。"""
    case = TestCase(**payload)
    db.add(case)
    db.flush()
    audit(db, actor, "admin.test_case.create", "test_case", case.id, meta=meta)
    db.commit()
    db.refresh(case)
    return case


def update_test_case(
    db: Session, actor: User, case_id: str, payload: dict[str, Any], meta: dict[str, Any]
) -> TestCase:
    """更新测试用例。"""
    case = get_or_404(db, TestCase, case_id, ErrorCode.NOT_FOUND, "测试用例不存在")
    apply_fields(case, payload)
    audit(db, actor, "admin.test_case.update", "test_case", case.id, meta=meta)
    db.commit()
    db.refresh(case)
    return case


def delete_test_case(db: Session, actor: User, case_id: str, meta: dict[str, Any]) -> None:
    """删除测试用例。"""
    case = get_or_404(db, TestCase, case_id, ErrorCode.NOT_FOUND, "测试用例不存在")
    db.delete(case)
    audit(db, actor, "admin.test_case.delete", "test_case", case_id, meta=meta)
    db.commit()
