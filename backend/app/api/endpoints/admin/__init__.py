"""管理端端点（`docs/API.md` §2.21）。

所有路由均要求管理员权限（`AdminUser`，越权 403，未登录 401）；所有写操作写入 audit_logs。

本包按领域拆分，`__init__` 汇总为单一 `router`（前缀 `/admin`），对外仍以
`from app.api.endpoints import admin` + `admin.router` 的方式挂载。
"""

from __future__ import annotations

from fastapi import APIRouter

from . import ai, catalog, courses, overview, problems, projects, system, users

router = APIRouter(prefix="/admin", tags=["admin"])

for _sub_router in (
    overview.router,
    users.router,
    courses.router,
    problems.router,
    projects.router,
    catalog.router,
    ai.router,
    system.router,
):
    router.include_router(_sub_router)

__all__ = ["router"]
