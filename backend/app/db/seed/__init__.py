"""种子数据导入入口（幂等，可重复执行）。

用法：
    python -m app.db.seed            # 或在脚本中 `from app.db.seed import seed_all`
    python scripts/seed.py           # 推荐：带 --reset / --only 参数
    python scripts/seed.py --reset   # 清空全部表后重建（危险，仅开发环境）
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.db.seed.content import seed_courses, seed_problems, seed_tags, seed_topics
from app.db.seed.extras import (
    seed_achievements,
    seed_admin_user,
    seed_challenges,
    seed_daily_tasks,
    seed_exams,
    seed_projects,
    seed_system_settings,
)
from app.db.seed.loader import SeedStats, seeds_root

logger = logging.getLogger("pythonlab.seed")

__all__ = ["SeedStats", "seed_all", "seeds_root", "print_stats"]


def seed_all(
    *,
    reset: bool = False,
    only: list[str] | None = None,
    session: Session | None = None,
    with_admin: bool = True,
) -> dict[str, Any]:
    """执行种子导入。

    Args:
        reset: 是否先删除全部表并重建（危险，仅开发/测试）。
        only: 仅导入指定分组，可选 `courses` / `problems` / `projects` /
            `achievements` / `daily_tasks` / `challenges` / `exams`。
        session: 复用的会话（为空时自行创建并关闭）。
        with_admin: 是否创建默认管理员。

    Returns:
        统计字典（含 courses / chapters / lessons / problems 等计数）。
    """
    from app.db.init_db import create_all, drop_all
    from app.db.session import SessionLocal

    if reset:
        logger.warning("--reset 已启用：将删除全部表并重建")
        drop_all()
    create_all()

    own_session = session is None
    db = session or SessionLocal()
    stats = SeedStats()
    groups = set(only) if only else {"topics", "courses", "problems", "projects", "achievements", "daily_tasks", "challenges", "exams"}

    try:
        topics = seed_topics(db, stats) if {"topics", "courses"} & groups else {}
        tags = seed_tags(db, stats) if {"tags", "problems"} & groups else {}

        if "courses" in groups:
            seed_courses(db, stats, topics)
        if "problems" in groups:
            problem_ids = seed_problems(db, stats, tags)
        else:
            problem_ids = _existing_problem_ids(db)
        if "projects" in groups:
            seed_projects(db, stats)
        if "achievements" in groups:
            seed_achievements(db, stats)
        if "daily_tasks" in groups:
            seed_daily_tasks(db, stats)
        if "challenges" in groups:
            seed_challenges(db, stats, problem_ids)
        if "exams" in groups:
            seed_exams(db, stats, problem_ids)

        seed_system_settings(db)
        if with_admin:
            seed_admin_user(db)

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        if own_session:
            db.close()

    return stats.as_dict()


def _existing_problem_ids(db: Session) -> dict[str, str]:
    """读取库中已有题目 id（用于已存在题目时的挑战/试卷关联）。"""
    from sqlalchemy import select

    from app.models.problem import Problem

    rows = db.execute(select(Problem.slug, Problem.id)).all()
    return {str(slug): str(pid) for slug, pid in rows}


def print_stats(stats: dict[str, Any]) -> str:
    """把统计字典格式化为多行中文文本（供 CLI 打印）。"""
    lines = [
        "种子导入统计",
        f"  阶段(courses)   : {stats.get('courses', 0)}",
        f"  章节(chapters)  : {stats.get('chapters', 0)}",
        f"  课时(lessons)   : {stats.get('lessons', 0)}",
        f"  知识点(topics)  : {stats.get('topics', 0)}",
        f"  标签(tags)      : {stats.get('tags', 0)}",
        f"  题目(problems)  : {stats.get('problems', 0)}",
        f"  测试用例(cases) : {stats.get('test_cases', 0)}",
        f"  项目(projects)  : {stats.get('projects', 0)}",
        f"  项目文件(files) : {stats.get('project_files', 0)}",
        f"  成就(achv)      : {stats.get('achievements', 0)}",
        f"  每日任务(daily) : {stats.get('daily_tasks', 0)}",
        f"  挑战(challenges): {stats.get('challenges', 0)}",
        f"  试卷(exams)     : {stats.get('exams', 0)}",
    ]
    skipped = stats.get("skipped") or []
    if skipped:
        lines.append(f"  跳过/告警        : {len(skipped)} 条")
        for item in skipped[:10]:
            lines.append(f"    - {item}")
        if len(skipped) > 10:
            lines.append(f"    ... 其余 {len(skipped) - 10} 条略")
    return "\n".join(lines)


def main() -> None:
    """模块直跑入口：`python -m app.db.seed`。"""
    import argparse

    from app.core.logging import setup_logging

    parser = argparse.ArgumentParser(description="PYTHON LAB 种子数据导入")
    parser.add_argument("--reset", action="store_true", help="先删除全部表再重建（危险）")
    parser.add_argument("--only", default="", help="仅导入指定分组，逗号分隔")
    parser.add_argument("--no-admin", action="store_true", help="不创建默认管理员")
    args = parser.parse_args()

    setup_logging("INFO")
    only = [item.strip() for item in args.only.split(",") if item.strip()]
    stats = seed_all(reset=args.reset, only=only or None, with_admin=not args.no_admin)
    print(print_stats(stats))


if __name__ == "__main__":
    main()
