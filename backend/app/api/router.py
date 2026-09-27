"""API 路由汇总（全部域已挂载）。

分组与来源：
- 基座：`/auth` / `/users` / `/health`
- 内容与学习域：`/courses` / `/lessons` / `/progress` / `/search` / `/recommendations`
- 游戏化 / 统计 / 挑战 / 考试 / 通知 / 后台：`/statistics` / `/achievements` /
  `/challenges` / `/exams` / `/notifications` / `/admin`
- 判题与编辑器域：`/problems` / `/submissions` / `/editor` / `/python`（代码运行）
- AI 域：`/ai`
- 个人数据域：`/bookmarks` / `/mistakes` / `/code-history`

说明：
1. `admin` 实现为**包**（`app/api/endpoints/admin/`），对外统一暴露 `admin.router`。
2. `/python/run`（代码运行）定义于 `app/api/endpoints/editor.py` 的 `python_router`
   （`editor.py` 同时导出 `router` 与 `python_router`），**不存在**独立的
   `python_runner.py`；此处按实际模块 `editor.python_router` 挂载。
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.endpoints import (
    achievements,
    admin,
    ai,
    auth,
    bookmarks,
    challenges,
    code_history,
    courses,
    editor,
    exams,
    health,
    lessons,
    mistakes,
    notifications,
    problems,
    progress,
    projects,
    recommendations,
    search,
    statistics,
    submissions,
    users,
)

api_router = APIRouter()

# ---- 基座 ----
api_router.include_router(auth.router)            # /api/auth（7）
api_router.include_router(users.router)           # /api/users（8）
api_router.include_router(health.router)          # /api/health（3）

# ---- 内容与学习域 ----
api_router.include_router(courses.router)          # /api/courses（9）
api_router.include_router(lessons.router)          # /api/lessons（6）
api_router.include_router(progress.router)         # /api/progress（11）
api_router.include_router(search.router)           # /api/search（2）
api_router.include_router(recommendations.router)  # /api/recommendations（4）

# ---- 游戏化 / 统计 / 挑战 / 考试 / 通知 / 后台域 ----
api_router.include_router(statistics.router)     # /api/statistics（7）
api_router.include_router(achievements.router)   # /api/achievements（7）
api_router.include_router(challenges.router)     # /api/challenges（7）
api_router.include_router(exams.router)          # /api/exams（7）
api_router.include_router(notifications.router)  # /api/notifications（7）
api_router.include_router(admin.router)          # /api/admin（53）

# ---- 判题与编辑器域 ----
api_router.include_router(problems.router)       # /api/problems
api_router.include_router(submissions.router)    # /api/submissions
api_router.include_router(projects.router)       # /api/projects
api_router.include_router(editor.router)         # /api/editor
api_router.include_router(editor.python_router)  # /api/python（代码运行）

# ---- AI 域 ----
api_router.include_router(ai.router)             # /api/ai

# ---- 个人数据域 ----
api_router.include_router(bookmarks.router)      # /api/bookmarks
api_router.include_router(mistakes.router)       # /api/mistakes
api_router.include_router(code_history.router)   # /api/code-history

__all__ = ["api_router"]
