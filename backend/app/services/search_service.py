"""全局搜索服务（`docs/API.md` §2.16）。

不引入全文索引表：SQLite 走 `LIKE`（SQLAlchemy `ilike` 自动 `lower(...) LIKE`），
按类型分组返回课程 / 课时 / 题目 / 项目 / 代码示例，并给出搜索联想。
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.course import Chapter, Course, Lesson
from app.models.problem import Problem
from app.models.project import Project
from app.schemas.search import SearchGroup, SearchItem, SearchOut, SuggestItem, SuggestOut

logger = logging.getLogger("pythonlab.search")

ALL_TYPES: tuple[str, ...] = ("course", "lesson", "problem", "project", "snippet")
GROUP_LABELS: dict[str, str] = {
    "course": "课程",
    "lesson": "课时",
    "problem": "题目",
    "project": "项目",
    "snippet": "代码示例",
}


def global_search(
    db: Session,
    q: str,
    types: Sequence[str] | None = None,
    limit: int = 5,
) -> SearchOut:
    """跨类型全局搜索，返回分组结果。"""
    keyword = (q or "").strip()
    if not keyword:
        return SearchOut(groups=[], total=0, keyword="")
    limit = max(1, min(20, int(limit)))
    wanted = [item for item in (types or ALL_TYPES) if item in ALL_TYPES] or list(ALL_TYPES)
    like = f"%{keyword}%"

    groups: list[SearchGroup] = []
    for type_name in wanted:
        items = _search_type(db, type_name, keyword, like, limit)
        if items:
            groups.append(
                SearchGroup(type=type_name, label=GROUP_LABELS.get(type_name, type_name), items=items)
            )
    total = sum(len(group.items) for group in groups)
    return SearchOut(groups=groups, total=total, keyword=keyword)


def suggest(db: Session, q: str, limit: int = 8) -> SuggestOut:
    """搜索联想：按课程 / 题目 / 课时标题前缀与包含匹配。"""
    keyword = (q or "").strip()
    if not keyword:
        return SuggestOut(suggestions=[])
    like = f"%{keyword}%"
    suggestions: list[SuggestItem] = []

    courses = db.scalars(
        select(Course)
        .where(Course.is_published.is_(True), Course.title.ilike(like))
        .order_by(Course.stage_no.asc())
        .limit(limit)
    ).all()
    for course in courses:
        suggestions.append(SuggestItem(text=course.title, type="course", url=f"/courses/{course.slug}"))

    problems = db.scalars(
        select(Problem)
        .where(Problem.is_published.is_(True), Problem.title.ilike(like))
        .order_by(Problem.id.asc())
        .limit(limit)
    ).all()
    for problem in problems:
        suggestions.append(SuggestItem(text=problem.title, type="problem", url=f"/problems/{problem.id}"))

    if len(suggestions) < limit:
        lessons = db.execute(
            select(Lesson, Course.slug)
            .join(Chapter, Chapter.id == Lesson.chapter_id)
            .join(Course, Course.id == Chapter.course_id)
            .where(Lesson.is_published.is_(True), Lesson.title.ilike(like))
            .limit(limit)
        ).all()
        for lesson, course_slug in lessons:
            suggestions.append(
                SuggestItem(text=lesson.title, type="lesson", url=f"/courses/{course_slug}/{lesson.id}")
            )

    return SuggestOut(suggestions=suggestions[:limit])


# ---------------------------------------------------------------------------
# 内部：按类型检索
# ---------------------------------------------------------------------------


def _search_type(db: Session, type_name: str, keyword: str, like: str, limit: int) -> list[SearchItem]:
    """按类型分发检索。"""
    if type_name == "course":
        return _search_courses(db, keyword, like, limit)
    if type_name == "lesson":
        return _search_lessons(db, keyword, like, limit, code_only=False)
    if type_name == "problem":
        return _search_problems(db, keyword, like, limit)
    if type_name == "project":
        return _search_projects(db, keyword, like, limit)
    if type_name == "snippet":
        return _search_lessons(db, keyword, like, limit, code_only=True)
    return []


def _search_courses(db: Session, keyword: str, like: str, limit: int) -> list[SearchItem]:
    """检索课程（标题 / 副标题 / 描述）。"""
    rows = db.scalars(
        select(Course)
        .where(
            Course.is_published.is_(True),
            or_(
                Course.title.ilike(like),
                Course.subtitle.ilike(like),
                Course.description_md.ilike(like),
            ),
        )
        .order_by(Course.stage_no.asc())
        .limit(limit)
    ).all()
    return [
        SearchItem(
            id=course.id,
            title=course.title,
            subtitle=course.subtitle or f"阶段 {course.stage_no}",
            url=f"/courses/{course.slug}",
            highlight=_highlight(course.title or course.subtitle or "", keyword),
        )
        for course in rows
    ]


def _search_lessons(db: Session, keyword: str, like: str, limit: int, *, code_only: bool) -> list[SearchItem]:
    """检索课时；`code_only=True` 时改为检索课时内代码示例（starter/solution）。"""
    conditions = (
        or_(Lesson.starter_code.ilike(like), Lesson.solution_code.ilike(like))
        if code_only
        else or_(Lesson.title.ilike(like), Lesson.summary.ilike(like))
    )
    rows = db.execute(
        select(Lesson, Course.slug, Course.title)
        .join(Chapter, Chapter.id == Lesson.chapter_id)
        .join(Course, Course.id == Chapter.course_id)
        .where(Lesson.is_published.is_(True), conditions)
        .limit(limit)
    ).all()
    items: list[SearchItem] = []
    for lesson, course_slug, course_title in rows:
        subtitle = f"{course_title} · {lesson.lesson_type}" if not code_only else "代码示例"
        items.append(
            SearchItem(
                id=lesson.id,
                title=lesson.title if not code_only else f"{lesson.title} 代码示例",
                subtitle=subtitle,
                url=f"/courses/{course_slug}/{lesson.id}",
                highlight=_highlight(lesson.summary or lesson.title or "", keyword),
            )
        )
    return items


def _search_problems(db: Session, keyword: str, like: str, limit: int) -> list[SearchItem]:
    """检索题目（标题 / slug / 题干）。"""
    rows = db.scalars(
        select(Problem)
        .where(
            Problem.is_published.is_(True),
            or_(Problem.title.ilike(like), Problem.slug.ilike(like), Problem.statement_md.ilike(like)),
        )
        .order_by(Problem.acceptance_rate.desc())
        .limit(limit)
    ).all()
    return [
        SearchItem(
            id=problem.id,
            title=problem.title,
            subtitle=f"{problem.category} · {problem.difficulty}",
            url=f"/problems/{problem.id}",
            highlight=_highlight(problem.statement_md or problem.title or "", keyword),
        )
        for problem in rows
    ]


def _search_projects(db: Session, keyword: str, like: str, limit: int) -> list[SearchItem]:
    """检索项目（标题 / 概要 / 需求文档）。"""
    rows = db.scalars(
        select(Project)
        .where(
            Project.is_published.is_(True),
            or_(Project.title.ilike(like), Project.summary.ilike(like), Project.description_md.ilike(like)),
        )
        .order_by(Project.level.asc())
        .limit(limit)
    ).all()
    return [
        SearchItem(
            id=project.id,
            title=project.title,
            subtitle=project.summary or f"Level {project.level}",
            url=f"/projects/{project.id}",
            highlight=_highlight(project.summary or project.title or "", keyword),
        )
        for project in rows
    ]


def _highlight(text: str, keyword: str, radius: int = 30) -> str:
    """从文本中截取关键词附近的片段作为高亮摘要（大小写不敏感）。"""
    if not text or not keyword:
        return ""
    lowered = text.lower()
    position = lowered.find(keyword.lower())
    if position < 0:
        return text[: radius * 2].strip()
    start = max(0, position - radius)
    end = min(len(text), position + len(keyword) + radius)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{text[start:end].strip()}{suffix}"
