"""扩展类种子：项目 / 成就 / 每日任务 / 挑战 / 试卷 / 系统配置。"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import CHALLENGE_LEADERBOARD_LIMIT  # noqa: F401 - 契约常量在此集中引用
from app.db.seed.loader import SeedStats, load_json, upsert
from app.models.challenge import Challenge
from app.models.enums import ChallengeType, Difficulty, ExamLevel, ProblemCategory
from app.models.exam import Exam
from app.models.gamification import Achievement, DailyTask
from app.models.project import Project, ProjectFile
from app.models.system import SystemSetting
from app.utils.time import now_utc

logger = logging.getLogger("pythonlab.seed")


def seed_projects(db: Session, stats: SeedStats) -> None:
    """导入实战项目与项目文件。"""
    rows: list[dict[str, Any]] = load_json("projects.json", required=False, default=[]) or []
    for row in rows:
        project, _ = upsert(
            db,
            Project,
            {"slug": str(row["slug"])},
            {
                "title": str(row["title"]),
                "summary": row.get("summary"),
                "description_md": str(row.get("description_md") or ""),
                "level": int(row.get("level") or 1),
                "difficulty": str(row.get("difficulty") or Difficulty.EASY.value),
                "category": str(row.get("category") or ProblemCategory.BASICS.value),
                "cover_url": row.get("cover_url"),
                "estimated_hours": int(row.get("estimated_hours") or 4),
                "xp_reward": int(row.get("xp_reward") or 100),
                "steps_json": row.get("steps") or [],
                "rubric_json": row.get("rubric") or {},
                "is_published": True,
                "order_index": int(row.get("order_index") or 0),
            },
        )
        if project is None:
            continue
        db.flush()
        stats.projects += 1

        for index, file_row in enumerate(row.get("files") or []):
            payload = {
                "content": str(file_row.get("content") or ""),
                "language": str(file_row.get("language") or "python"),
                "is_entry": bool(file_row.get("is_entry", False)),
                "is_readonly": bool(file_row.get("is_readonly", False)),
                "description": file_row.get("description"),
                "order_index": int(file_row.get("order_index", index)),
            }
            _file, created = upsert(
                db,
                ProjectFile,
                {"project_id": project.id, "path": str(file_row["path"])},
                payload,
            )
            if created:
                stats.project_files += 1
        db.flush()

    logger.info("项目导入完成：%d 个（文件 %d 个）", stats.projects, stats.project_files)


def seed_achievements(db: Session, stats: SeedStats) -> None:
    """导入成就定义。"""
    rows: list[dict[str, Any]] = load_json("achievements.json", required=False, default=[]) or []
    for index, row in enumerate(rows):
        _, _created = upsert(
            db,
            Achievement,
            {"code": str(row["code"])},
            {
                "name": str(row.get("name") or row["code"]),
                "description": row.get("description"),
                "icon": row.get("icon"),
                "category": str(row.get("category") or "learning"),
                "condition_json": row.get("condition") or {},
                "xp_reward": int(row.get("xp_reward") or 10),
                "badge_color": str(row.get("badge_color") or "blue"),
                "is_secret": bool(row.get("is_secret", False)),
                "is_active": True,
                "order_index": int(row.get("order_index", index)),
            },
        )
        stats.achievements += 1
    db.flush()
    logger.info("成就导入完成：%d 条", stats.achievements)


def seed_daily_tasks(db: Session, stats: SeedStats) -> None:
    """导入每日任务定义。"""
    rows: list[dict[str, Any]] = load_json("daily_tasks.json", required=False, default=[]) or []
    for index, row in enumerate(rows):
        upsert(
            db,
            DailyTask,
            {"code": str(row["code"])},
            {
                "title": str(row.get("title") or row["code"]),
                "description": row.get("description"),
                "metric": str(row.get("metric") or "submissions"),
                "target_count": int(row.get("target_count") or 1),
                "xp_reward": int(row.get("xp_reward") or 10),
                "is_active": True,
                "order_index": int(row.get("order_index", index)),
            },
        )
        stats.daily_tasks += 1
    db.flush()
    logger.info("每日任务导入完成：%d 条", stats.daily_tasks)


def seed_challenges(db: Session, stats: SeedStats, problem_ids: dict[str, str]) -> None:
    """导入挑战赛（题目按 slug 引用，滚动生成时间窗保证「进行中」状态可用）。"""
    rows: list[dict[str, Any]] = load_json("challenges.json", required=False, default=[]) or []
    now = now_utc()
    for row in rows:
        duration = int(row.get("duration_minutes") or 60)
        start_offset = int(row.get("start_offset_minutes") or 0)
        end_offset = int(row.get("end_offset_minutes") or duration)
        resolved = [problem_ids[slug] for slug in (row.get("problem_slugs") or []) if slug in problem_ids]
        upsert(
            db,
            Challenge,
            {"slug": str(row["slug"])},
            {
                "title": str(row["title"]),
                "description_md": row.get("description_md"),
                "challenge_type": str(row.get("challenge_type") or ChallengeType.DAILY.value),
                "difficulty": str(row.get("difficulty") or Difficulty.EASY.value),
                "problem_ids_json": resolved,
                "rules_md": row.get("rules_md"),
                "start_at": now + timedelta(minutes=start_offset),
                "end_at": now + timedelta(minutes=end_offset),
                "duration_minutes": duration,
                "xp_reward": int(row.get("xp_reward") or 50),
                "is_published": True,
            },
        )
        stats.challenges += 1
    db.flush()
    logger.info("挑战导入完成：%d 个（题目解析 %d 个）", stats.challenges, len(problem_ids))


def seed_exams(db: Session, stats: SeedStats, problem_ids: dict[str, str]) -> None:
    """导入试卷（题目 + 分值）。"""
    rows: list[dict[str, Any]] = load_json("exams.json", required=False, default=[]) or []
    for row in rows:
        questions: list[dict[str, Any]] = []
        for index, item in enumerate(row.get("questions") or []):
            slug = str(item.get("slug") or "")
            problem_id = problem_ids.get(slug)
            if problem_id:
                questions.append({"id": problem_id, "score": int(item.get("score") or 10), "order": index})
        upsert(
            db,
            Exam,
            {"code": str(row["code"])},
            {
                "title": str(row["title"]),
                "level": str(row.get("level") or ExamLevel.BASIC.value),
                "duration_minutes": int(row.get("duration_minutes") or 60),
                "total_score": int(row.get("total_score") or 100),
                "pass_score": int(row.get("pass_score") or 60),
                "question_ids_json": questions,
                "shuffle": bool(row.get("shuffle", True)),
                "is_published": True,
            },
        )
        stats.exams += 1
    db.flush()
    logger.info("试卷导入完成：%d 套", stats.exams)


def seed_system_settings(db: Session) -> None:
    """写入默认系统配置（幂等，仅缺失时创建）。"""
    defaults: list[dict[str, Any]] = [
        {
            "key": "site.announcement",
            "value_json": {"enabled": True, "text": "欢迎来到 PYTHON LAB，从阶段 1 开始你的 Python 之旅"},
            "description": "首页顶部公告文案",
        },
        {
            "key": "ai.prompt.overrides",
            "value_json": {},
            "description": "AI 提示词覆盖（按 scene 覆盖，留空使用内置模板）",
        },
        {
            "key": "learning.streak.rule",
            "value_json": {"min_minutes_per_day": 10, "reset_after_days": 1},
            "description": "连续学习天数判定规则",
        },
    ]
    created = 0
    for item in defaults:
        existing = db.scalars(select(SystemSetting).where(SystemSetting.key == item["key"])).one_or_none()
        if existing is None:
            db.add(SystemSetting(**item))
            created += 1
    db.flush()
    logger.info("系统配置初始化完成：新增 %d 条", created)


def seed_admin_user(db: Session) -> str:
    """创建默认管理员（若不存在），返回管理员邮箱。"""
    from app.core.config import get_settings
    from app.core.security import hash_password
    from app.models.enums import UserRole
    from app.models.user import Profile, User

    settings = get_settings()
    email = settings.admin_email.strip().lower()
    existing = db.scalars(select(User).where(User.email == email)).one_or_none()
    if existing is not None:
        if existing.role != UserRole.ADMIN.value:
            existing.role = UserRole.SUPERADMIN.value
            db.flush()
        return email

    admin = User(
        email=email,
        username=settings.admin_username,
        hashed_password=hash_password(settings.admin_password),
        role=UserRole.SUPERADMIN.value,
        is_verified=True,
        level=7,
        xp=10_000,
    )
    db.add(admin)
    db.flush()
    db.add(Profile(user_id=admin.id, display_name=settings.admin_username, bio="系统管理员"))
    db.flush()
    logger.info("默认管理员已创建：%s", email)
    return email
