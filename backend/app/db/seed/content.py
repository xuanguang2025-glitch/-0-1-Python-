"""内容类种子：知识点树 / 阶段课程 / 标签 / 题目。"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.seed.loader import SeedStats, load_json, load_stage_markdown, upsert
from app.models.course import Chapter, Course, Lesson, LessonTopic, Topic
from app.models.enums import CourseLevel, Difficulty, LessonType, ProblemCategory, ProblemType
from app.models.problem import Problem, ProblemTag, Tag, TestCase
from app.utils.ids import new_uuid

logger = logging.getLogger("pythonlab.seed")


def seed_topics(db: Session, stats: SeedStats) -> dict[str, Topic]:
    """导入知识点树（parent 用 slug 引用），返回 `{slug: Topic}`。"""
    rows: list[dict[str, Any]] = load_json("topics.json", required=False, default=[]) or []
    mapping: dict[str, Topic] = {}

    # 第一轮：创建 / 更新主体（不含父子关系）
    for row in rows:
        topic, _ = upsert(
            db,
            Topic,
            {"slug": str(row["slug"])},
            {
                "name": str(row.get("name") or row["slug"]),
                "description": row.get("description"),
                "order_index": int(row.get("order") or 0),
            },
        )
        if topic is not None:
            mapping[topic.slug] = topic
    db.flush()

    # 第二轮：绑定 parent_id（允许父节点后置定义）
    for row in rows:
        parent_slug = row.get("parent")
        if not parent_slug:
            continue
        topic = mapping.get(str(row["slug"]))
        parent = mapping.get(str(parent_slug))
        if topic is not None and parent is not None and topic.parent_id != parent.id:
            topic.parent_id = parent.id
    db.flush()

    stats.topics = len(mapping)
    logger.info("知识点导入完成：%d 条", stats.topics)
    return mapping


def seed_tags(db: Session, stats: SeedStats) -> dict[str, Tag]:
    """导入标签字典，返回 `{slug: Tag}`。"""
    rows: list[dict[str, Any]] = load_json("tags.json", required=False, default=[]) or []
    mapping: dict[str, Tag] = {}
    for row in rows:
        tag, _ = upsert(
            db,
            Tag,
            {"slug": str(row["slug"])},
            {
                "name": str(row.get("name") or row["slug"]),
                "color": row.get("color"),
                "kind": str(row.get("kind") or "problem"),
                "order_index": int(row.get("order") or 0),
            },
        )
        if tag is not None:
            mapping[tag.slug] = tag
    db.flush()
    stats.tags = len(mapping)
    logger.info("标签导入完成：%d 条", stats.tags)
    return mapping


def seed_courses(db: Session, stats: SeedStats, topics: dict[str, Topic]) -> None:
    """导入 18 个阶段（课程 / 章节 / 课时 / 知识点关联）与课时正文。"""
    courses: list[dict[str, Any]] = load_json("courses.json")
    for course_row in sorted(courses, key=lambda item: int(item.get("stage_no") or 0)):
        stage_no = int(course_row["stage_no"])
        course, _ = upsert(
            db,
            Course,
            {"slug": str(course_row["slug"])},
            {
                "stage_no": stage_no,
                "title": str(course_row["title"]),
                "subtitle": course_row.get("subtitle"),
                "description_md": course_row.get("description_md"),
                "level": str(course_row.get("level") or CourseLevel.BEGINNER.value),
                "icon": course_row.get("icon"),
                "cover_url": course_row.get("cover_url"),
                "estimated_hours": int(course_row.get("estimated_hours") or 0),
                "order_index": int(course_row.get("order_index") or stage_no),
                "is_published": True,
            },
        )
        if course is None:
            continue
        db.flush()
        stats.courses += 1

        try:
            markdown_map = load_stage_markdown(stage_no)
        except FileNotFoundError as exc:
            stats.skipped.append(f"stage-{stage_no:02d} 课时正文缺失：{exc}")
            markdown_map = {}

        chapter_count = 0
        for chapter_index, chapter_row in enumerate(course_row.get("chapters") or [], start=0):
            chapter, _ = upsert(
                db,
                Chapter,
                {"course_id": course.id, "slug": str(chapter_row["slug"])},
                {
                    "title": str(chapter_row["title"]),
                    "summary_md": chapter_row.get("summary_md"),
                    "order_index": int(chapter_row.get("order_index") or chapter_index),
                    "is_published": True,
                },
            )
            if chapter is None:
                continue
            db.flush()
            chapter_count += 1
            stats.chapters += 1

            lesson_count = 0
            for lesson_index, lesson_row in enumerate(chapter_row.get("lessons") or [], start=0):
                lesson_slug = str(lesson_row["slug"])
                content_md = markdown_map.get(lesson_slug, "").strip()
                if not content_md:
                    stats.skipped.append(f"{course.slug}/{chapter.slug}/{lesson_slug} 正文缺失")

                lesson, _ = upsert(
                    db,
                    Lesson,
                    {"chapter_id": chapter.id, "slug": lesson_slug},
                    {
                        "title": str(lesson_row["title"]),
                        "summary": lesson_row.get("summary"),
                        "content_md": content_md or str(lesson_row.get("summary") or lesson_row["title"]),
                        "lesson_type": str(lesson_row.get("lesson_type") or LessonType.CONCEPT.value),
                        "difficulty": str(lesson_row.get("difficulty") or Difficulty.EASY.value),
                        "estimated_minutes": int(lesson_row.get("estimated_minutes") or 15),
                        "order_index": int(lesson_row.get("order_index") or lesson_index),
                        "xp_reward": int(lesson_row.get("xp_reward") or 10),
                        "has_playground": bool(lesson_row.get("has_playground", True)),
                        "starter_code": lesson_row.get("starter_code"),
                        "solution_code": lesson_row.get("solution_code"),
                        "quiz_json": lesson_row.get("quiz"),
                        "is_published": True,
                    },
                )
                if lesson is None:
                    continue
                db.flush()
                lesson_count += 1
                stats.lessons += 1

                _link_lesson_topics(db, lesson, lesson_row, topics)

            chapter.lesson_count = lesson_count

        course.lesson_count = sum(
            int(item.lesson_count or 0) for item in (course.chapters or []) if item is not None
        )
        if course.lesson_count == 0:
            # 关系未加载时按实际查询兜底
            course.lesson_count = int(
                db.scalar(
                    select(Chapter.lesson_count).where(Chapter.course_id == course.id).order_by(Chapter.order_index).limit(1)
                )
                or 0
            )
        logger.info("阶段 %02d 导入完成：章节 %d，课时 %d", stage_no, chapter_count, len(course.chapters or []))

    db.flush()


def _link_lesson_topics(
    db: Session,
    lesson: Lesson,
    lesson_row: dict[str, Any],
    topics: dict[str, Topic],
) -> None:
    """建立课时 ↔ 知识点关联（`primary_topic` 标记主知识点）。"""
    slugs = [str(item) for item in (lesson_row.get("topics") or [])]
    primary = lesson_row.get("primary_topic")
    wanted: dict[str, bool] = {slug: False for slug in slugs}
    if primary:
        wanted[str(primary)] = True

    existing = {
        link.topic_id: link
        for link in db.scalars(select(LessonTopic).where(LessonTopic.lesson_id == lesson.id)).all()
    }
    for slug, is_primary in wanted.items():
        topic = topics.get(slug)
        if topic is None:
            continue
        link = existing.get(topic.id)
        if link is None:
            db.add(LessonTopic(lesson_id=lesson.id, topic_id=topic.id, is_primary=is_primary))
        elif link.is_primary != is_primary:
            link.is_primary = is_primary


def seed_problems(db: Session, stats: SeedStats, tags: dict[str, Tag]) -> dict[str, str]:
    """导入题目、测试用例与标签关联，返回 `{slug: problem_id}`。"""
    rows: list[dict[str, Any]] = load_json("problems.json", required=False, default=[]) or []
    mapping: dict[str, str] = {}

    for row in rows:
        slug = str(row["slug"])
        problem, _ = upsert(
            db,
            Problem,
            {"slug": slug},
            {
                "title": str(row["title"]),
                "statement_md": str(row.get("statement_md") or ""),
                "problem_type": str(row.get("problem_type") or ProblemType.CODING.value),
                "difficulty": str(row.get("difficulty") or Difficulty.EASY.value),
                "category": str(row.get("category") or ProblemCategory.BASICS.value),
                "input_format": row.get("input_format"),
                "output_format": row.get("output_format"),
                "sample_input": row.get("sample_input"),
                "sample_output": row.get("sample_output"),
                "constraints": row.get("constraints"),
                "options_json": row.get("options"),
                "answer_json": row.get("answer"),
                "hint_md": row.get("hint_md"),
                "solution_md": row.get("solution_md"),
                "starter_code": row.get("starter_code"),
                "reference_solution": row.get("reference_solution"),
                "buggy_code": row.get("buggy_code"),
                "time_limit_ms": int(row.get("time_limit_ms") or 5000),
                "memory_limit_mb": int(row.get("memory_limit_mb") or 256),
                "score": int(row.get("score") or 10),
                "xp_reward": int(row.get("xp_reward") or 20),
                "is_published": True,
            },
        )
        if problem is None:
            continue
        problem.clamp_limits()
        db.flush()
        mapping[slug] = problem.id
        stats.problems += 1

        _sync_test_cases(db, problem, row.get("test_cases") or [], stats)
        _sync_problem_tags(db, problem, row.get("tags") or [], tags)

    db.flush()
    logger.info("题目导入完成：%d 道，用例 %d 个", stats.problems, stats.test_cases)
    return mapping


def _sync_test_cases(
    db: Session,
    problem: Problem,
    rows: list[dict[str, Any]],
    stats: SeedStats,
) -> None:
    """按 `order_index` 覆盖式同步测试用例（保证幂等）。"""
    existing = {
        int(item.order_index): item
        for item in db.scalars(select(TestCase).where(TestCase.problem_id == problem.id)).all()
    }
    keep: set[int] = set()
    for index, row in enumerate(rows):
        order = int(row.get("order_index", index))
        keep.add(order)
        payload = {
            "name": row.get("name"),
            "input": str(row.get("input") or ""),
            "expected_output": str(row.get("expected_output") or ""),
            "comparison": str(row.get("comparison") or "trimmed"),
            "float_tolerance": row.get("float_tolerance", 1e-6),
            "is_sample": bool(row.get("is_sample", False)),
            "is_hidden": bool(row.get("is_hidden", not row.get("is_sample", False))),
            "weight": int(row.get("weight") or 1),
            "timeout_ms": row.get("timeout_ms"),
            "order_index": order,
        }
        case = existing.get(order)
        if case is None:
            db.add(TestCase(problem_id=problem.id, **payload))
            stats.test_cases += 1
        else:
            for key, value in payload.items():
                setattr(case, key, value)
    db.flush()

    # 删除种子中已移除的用例（仅限自动生成的顺序位）
    for order, case in existing.items():
        if order not in keep:
            db.delete(case)


def _sync_problem_tags(
    db: Session,
    problem: Problem,
    slugs: list[str],
    tags: dict[str, Tag],
) -> None:
    """同步题目标签关联。"""
    existing = {
        link.tag_id for link in db.scalars(select(ProblemTag).where(ProblemTag.problem_id == problem.id)).all()
    }
    for slug in slugs:
        tag = tags.get(str(slug))
        if tag is None:
            # 先查库中是否已存在（保证重复执行幂等），再决定是否补建
            tag = db.scalars(select(Tag).where(Tag.slug == str(slug))).first()
        if tag is None:
            # 自动补建缺失标签，避免种子直接失败
            tag = Tag(id=new_uuid(), slug=str(slug), name=str(slug), kind="problem")
            db.add(tag)
            db.flush()
        tags[str(slug)] = tag
        if tag.id not in existing:
            db.add(ProblemTag(problem_id=problem.id, tag_id=tag.id))
    db.flush()
