"""管理端服务（`docs/API.md` §2.21）。

约定：
- 所有写操作**必须写审计日志**（谁 / 何时 / 对什么 / 做了什么 / 变更前后摘要）；
- 密钥 / 密码等敏感字段**永不回传明文**，写库前加密由调用方决定，读取一律脱敏。

本包按领域拆分为若干子模块，`__init__` 统一重导出公共 API，对外仍以
`from app.services import admin_service` 的方式使用（保持既有调用不变）。
"""

from __future__ import annotations

# --- 公共工具 ---
from .common import (
    ACCEPTED,
    AI_KEY_TEMPLATE,
    GLOBAL_AI_KEY,
    SENSITIVE_HINTS,
    apply_fields as _apply,
    audit as _audit,
    get_or_404 as _get,
    is_sensitive as _is_sensitive,
    mask_secret,
    read_setting as _read_setting,
    snapshot as _snapshot,
    write_setting as _write_setting,
)

# --- 仪表盘 ---
from .dashboard import dashboard, day_bounds as _day_bounds

# --- 用户管理 ---
from .users import (
    create_user,
    delete_user,
    list_users,
    reset_password,
    update_user,
)

# --- 课程 / 章节 / 课时 ---
from .courses import (
    create_chapter,
    create_course,
    create_lesson,
    delete_chapter,
    delete_course,
    delete_lesson,
    list_courses,
    sync_lesson_topics as _sync_lesson_topics,
    update_chapter,
    update_course,
    update_lesson,
)

# --- 题目 / 测试用例 ---
from .problems import (
    create_problem,
    create_test_case,
    delete_problem,
    delete_test_case,
    import_problems,
    list_problems,
    replace_test_cases as _replace_test_cases,
    sync_problem_tags as _sync_problem_tags,
    update_problem,
    update_test_case,
)

# --- 项目 / 项目文件 ---
from .projects import (
    create_project,
    create_project_file,
    delete_project,
    delete_project_file,
    list_projects,
    update_project,
    update_project_file,
)

# --- 标签 / 公告 ---
from .content import (
    create_announcement,
    create_tag,
    delete_announcement,
    delete_tag,
    list_announcements,
    list_tags,
    update_announcement,
    update_tag,
)

# --- AI 配置 / 模型 ---
from .ai_config import (
    create_model,
    delete_model,
    get_ai_config,
    list_models,
    list_models_out,
    model_out as _model_out,
    serialize_model,
    test_model,
    update_ai_config,
    update_model,
)

# --- 日志 / 设置 / 维护 ---
from .system import (
    enqueue_rejudge,
    list_ai_usage,
    list_audit_logs,
    list_error_logs,
    list_settings,
    mask_setting_value,
    session_overview,
    update_setting,
)

__all__ = [
    # 工具
    "mask_secret", "mask_setting_value", "SENSITIVE_HINTS", "ACCEPTED",
    "AI_KEY_TEMPLATE", "GLOBAL_AI_KEY",
    # 仪表盘
    "dashboard",
    # 用户
    "list_users", "create_user", "update_user", "delete_user", "reset_password",
    # 课程
    "list_courses", "create_course", "update_course", "delete_course",
    "create_chapter", "update_chapter", "delete_chapter",
    "create_lesson", "update_lesson", "delete_lesson",
    # 题目
    "list_problems", "create_problem", "update_problem", "delete_problem", "import_problems",
    "create_test_case", "update_test_case", "delete_test_case",
    # 项目
    "list_projects", "create_project", "update_project", "delete_project",
    "create_project_file", "update_project_file", "delete_project_file",
    # 标签 / 公告
    "list_tags", "create_tag", "update_tag", "delete_tag",
    "list_announcements", "create_announcement", "update_announcement", "delete_announcement",
    # AI
    "get_ai_config", "update_ai_config", "list_models", "list_models_out", "serialize_model",
    "create_model", "update_model", "delete_model", "test_model",
    # 日志 / 设置 / 维护
    "list_audit_logs", "list_ai_usage", "list_error_logs", "session_overview",
    "list_settings", "update_setting", "enqueue_rejudge",
]
