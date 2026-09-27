"""种子数据加载器：JSON 读取、Markdown 课时切分与通用 upsert 工具。

数据源目录：`database/seeds/`（可通过 `SEEDS_DIR` 覆盖）
- `courses.json`     18 个阶段（含章节与知识点挂载）
- `topics.json`      知识点树（≥120 条）
- `tags.json`        标签字典
- `problems.json`    题目（含 test_cases / tags）
- `projects.json`    项目（含 project_files）
- `achievements.json` 成就定义
- `daily_tasks.json` 每日任务定义
- `challenges.json`  挑战赛
- `exams.json`       试卷
- `lessons/stage-XX.md` 课时正文（按 `## <lesson-slug>` 锚点切分）
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings

logger = logging.getLogger("pythonlab.seed")

#: 课时锚点：二级标题 `## lesson-slug`
LESSON_ANCHOR_RE: re.Pattern[str] = re.compile(r"^##\s+([a-z0-9][a-z0-9-]*)\s*$", re.MULTILINE)

T = TypeVar("T")


@dataclass(slots=True)
class SeedStats:
    """种子执行统计。"""

    courses: int = 0
    chapters: int = 0
    lessons: int = 0
    topics: int = 0
    tags: int = 0
    problems: int = 0
    test_cases: int = 0
    projects: int = 0
    project_files: int = 0
    achievements: int = 0
    daily_tasks: int = 0
    challenges: int = 0
    exams: int = 0
    skipped: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        """转换为字典（便于打印与返回）。"""
        return {
            "courses": self.courses,
            "chapters": self.chapters,
            "lessons": self.lessons,
            "topics": self.topics,
            "tags": self.tags,
            "problems": self.problems,
            "test_cases": self.test_cases,
            "projects": self.projects,
            "project_files": self.project_files,
            "achievements": self.achievements,
            "daily_tasks": self.daily_tasks,
            "challenges": self.challenges,
            "exams": self.exams,
            "skipped": self.skipped,
        }


def seeds_root() -> Path:
    """种子数据根目录（不存在时抛出明确错误）。"""
    path = get_settings().seeds_dir_path
    if not path.exists():
        raise FileNotFoundError(f"种子目录不存在：{path}（可通过 SEEDS_DIR 环境变量指定）")
    return path


def load_json(name: str, *, required: bool = True, default: Any = None) -> Any:
    """读取 `database/seeds/<name>`，不存在时按 `required` 决定抛错或返回默认值。"""
    path = seeds_root() / name
    if not path.exists():
        if required:
            raise FileNotFoundError(f"种子文件缺失：{path}")
        logger.warning("种子文件缺失，跳过：%s", path)
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def split_lessons(markdown: str) -> dict[str, str]:
    """按 `## <lesson-slug>` 锚点切分课时正文。

    Args:
        markdown: 单个阶段 Markdown 全文。

    Returns:
        `{lesson_slug: 正文 Markdown}`（不含锚点行本身）。

    Raises:
        ValueError: 文件缺少一级标题或没有任何课时锚点。
    """
    matches = list(LESSON_ANCHOR_RE.finditer(markdown or ""))
    if not matches:
        raise ValueError("课时文件未找到任何 `## <slug>` 锚点")

    result: dict[str, str] = {}
    for index, match in enumerate(matches):
        slug = match.group(1)
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        body = markdown[start:end].strip("\n")
        if not body.strip():
            raise ValueError(f"课时 `{slug}` 正文为空")
        result[slug] = body
    return result


def load_stage_markdown(stage_no: int) -> dict[str, str]:
    """读取某阶段的课时 Markdown 并切分。"""
    filename = f"lessons/stage-{stage_no:02d}.md"
    path = seeds_root() / filename
    if not path.exists():
        raise FileNotFoundError(f"课时文件缺失：{path}")
    return split_lessons(path.read_text(encoding="utf-8"))


def upsert(
    db: Session,
    model: type[T],
    lookup: dict[str, Any],
    values: dict[str, Any],
    *,
    create: bool = True,
) -> tuple[T | None, bool]:
    """按 `lookup` 条件查询并更新/创建记录。

    Args:
        db: 会话。
        model: ORM 模型类。
        lookup: 唯一键条件（如 `{"slug": "stage-01"}`）。
        values: 需要写入的字段。
        create: 未命中时是否创建。

    Returns:
        `(实例, 是否新建)`；未创建且未命中时返回 `(None, False)`。
    """
    stmt = select(model)
    for key, value in lookup.items():
        stmt = stmt.where(getattr(model, key) == value)
    instance = db.scalars(stmt).first()

    if instance is None:
        if not create:
            return None, False
        instance = model(**lookup, **values)
        db.add(instance)
        return instance, True

    for key, value in values.items():
        if getattr(instance, key) != value:
            setattr(instance, key, value)
    return instance, False


def flush(db: Session) -> None:
    """统一 flush（保持 id 可用）并吞掉无意义异常。"""
    db.flush()


def chunked(items: Iterable[T], size: int) -> Iterable[list[T]]:
    """把可迭代对象按 `size` 分批（大表批量写入用）。"""
    batch: list[T] = []
    for item in items:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch
