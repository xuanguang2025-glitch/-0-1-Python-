"""管理端 API 测试（`tests/test_admin_api.py`）。

覆盖：普通用户访问 admin 返回 403（未登录 401）、管理员 CRUD 成功、
AI 配置写入后读取返回脱敏值（**断言响应不含原始 key 明文**）、写操作产生 audit_logs、
系统设置脱敏。
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.endpoints import admin as admin_endpoint
from app.core.errors import register_exception_handlers
from app.core.security import create_access_token, hash_password
from app.db.init_db import create_all
from app.db.session import SessionLocal
from app.models.ai import AIModelConfig
from app.models.course import Course
from app.models.system import AuditLog
from app.models.user import Profile, User

ADMIN_EMAIL = "admin-test@pythonlab.dev"
USER_EMAIL = "learner-test@pythonlab.dev"
RAW_KEY = "sk-secret-abcdef1234"
RAW_SETTING_KEY = "sk-super-secret-1234"


def _seed() -> dict[str, Any]:
    """建表并写入管理员 + 普通用户（幂等）。"""
    create_all()
    db = SessionLocal()
    try:
        admin = db.scalars(select(User).where(User.email == ADMIN_EMAIL)).one_or_none()
        if admin is None:
            admin = User(
                email=ADMIN_EMAIL,
                username="admin_test",
                hashed_password=hash_password("Admin@12345"),
                role="superadmin",
                is_verified=True,
                xp=10_000,
                level=7,
            )
            db.add(admin)
            db.flush()
            db.add(Profile(user_id=admin.id, display_name="管理员"))

        user = db.scalars(select(User).where(User.email == USER_EMAIL)).one_or_none()
        if user is None:
            user = User(
                email=USER_EMAIL,
                username="learner_test",
                hashed_password=hash_password("Learner@123"),
                role="user",
                is_verified=True,
            )
            db.add(user)
            db.flush()
            db.add(Profile(user_id=user.id, display_name="学习者甲"))

        # 清理历史测试残留，保证唯一约束不冲突
        for row in db.scalars(
            select(Course).where((Course.slug == "test-admin-course") | (Course.stage_no == 96))
        ).all():
            db.delete(row)
        for model in db.scalars(select(AIModelConfig).where(AIModelConfig.name == "测试模型")).all():
            db.delete(model)
        db.commit()
        return {"admin_id": admin.id, "user_id": user.id}
    finally:
        db.close()


def _build_app() -> FastAPI:
    """只挂载 admin 路由。"""
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(admin_endpoint.router, prefix="/api")
    return app


@pytest.fixture(scope="module")
def seeded() -> dict[str, Any]:
    """初始化数据库与种子数据。"""
    return _seed()


@pytest.fixture(scope="module")
def client() -> TestClient:
    """测试客户端。"""
    return TestClient(_build_app())


def _headers(user_id: str, role: str, username: str) -> dict[str, str]:
    """生成 Bearer 认证头。"""
    token, _, _ = create_access_token(user_id, role=role, username=username)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def admin_headers(seeded: dict[str, Any]) -> dict[str, str]:
    """管理员认证头。"""
    return _headers(seeded["admin_id"], "superadmin", "admin_test")


@pytest.fixture(scope="module")
def user_headers(seeded: dict[str, Any]) -> dict[str, str]:
    """普通用户认证头。"""
    return _headers(seeded["user_id"], "user", "learner_test")


# ---------------------------------------------------------------------------
# 权限
# ---------------------------------------------------------------------------


def test_admin_requires_admin(client: TestClient, user_headers: dict[str, str]) -> None:
    """普通用户 403，未登录 401。"""
    forbidden = client.get("/api/admin/dashboard", headers=user_headers)
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "FORBIDDEN"

    unauthorized = client.get("/api/admin/dashboard")
    assert unauthorized.status_code == 401


# ---------------------------------------------------------------------------
# CRUD + 审计
# ---------------------------------------------------------------------------


def test_admin_course_crud_and_audit(client: TestClient, admin_headers: dict[str, str]) -> None:
    """管理员课程 CRUD 成功且产生审计日志。"""
    create = client.post(
        "/api/admin/courses",
        json={"slug": "test-admin-course", "stage_no": 96, "title": "管理员测试课程", "level": "beginner"},
        headers=admin_headers,
    )
    assert create.status_code == 200, create.text
    course = create.json()["data"]
    assert course["slug"] == "test-admin-course"

    update = client.patch(
        f"/api/admin/courses/{course['id']}", json={"title": "管理员测试课程（改）"}, headers=admin_headers
    )
    assert update.status_code == 200
    assert update.json()["data"]["title"] == "管理员测试课程（改）"

    listed = client.get("/api/admin/courses", headers=admin_headers)
    assert listed.status_code == 200
    assert any(item["slug"] == "test-admin-course" for item in listed.json()["data"]["items"])

    delete = client.delete(f"/api/admin/courses/{course['id']}", headers=admin_headers)
    assert delete.status_code == 200

    logs = client.get("/api/admin/logs/audit?page_size=50", headers=admin_headers)
    assert logs.status_code == 200
    actions = [item["action"] for item in logs.json()["data"]["items"]]
    assert "admin.course.create" in actions
    assert "admin.course.update" in actions
    assert "admin.course.delete" in actions

    # 数据库侧确认审计日志确实落库
    db = SessionLocal()
    try:
        assert db.scalars(select(AuditLog).where(AuditLog.action == "admin.course.create")).first() is not None
    finally:
        db.close()


# ---------------------------------------------------------------------------
# AI 配置脱敏
# ---------------------------------------------------------------------------


def test_ai_model_key_masked(client: TestClient, admin_headers: dict[str, str]) -> None:
    """写入 API Key 后读取返回脱敏值，响应绝不包含原始 key。"""
    create = client.post(
        "/api/admin/models",
        json={
            "provider": "deepseek",
            "name": "测试模型",
            "model": "deepseek-chat",
            "api_key": RAW_KEY,
            "is_active": True,
        },
        headers=admin_headers,
    )
    assert create.status_code == 200, create.text
    data = create.json()["data"]
    assert RAW_KEY not in create.text
    assert data["api_key_masked"] is not None
    assert "****" in data["api_key_masked"]
    assert data["api_key_masked"].endswith("1234")

    listing = client.get("/api/admin/models", headers=admin_headers)
    assert listing.status_code == 200
    assert RAW_KEY not in listing.text
    model = next(item for item in listing.json()["data"] if item["name"] == "测试模型")
    assert "****" in model["api_key_masked"]

    test_result = client.post(f"/api/admin/models/{model['id']}/test", headers=admin_headers)
    assert test_result.status_code == 200
    assert RAW_KEY not in test_result.text


# ---------------------------------------------------------------------------
# 系统设置脱敏
# ---------------------------------------------------------------------------


def test_system_settings_masked(client: TestClient, admin_headers: dict[str, str]) -> None:
    """敏感系统设置写入后读取返回脱敏值。"""
    update = client.put(
        "/api/admin/settings/ai.api_key",
        json={"value_json": {"value": RAW_SETTING_KEY}, "description": "测试密钥"},
        headers=admin_headers,
    )
    assert update.status_code == 200, update.text
    assert RAW_SETTING_KEY not in update.text
    body = update.json()["data"]
    assert body["is_sensitive"] is True
    assert "****" in body["value_json"]["value"]

    listing = client.get("/api/admin/settings", headers=admin_headers)
    assert listing.status_code == 200
    assert RAW_SETTING_KEY not in listing.text
    item = next(row for row in listing.json()["data"] if row["key"] == "ai.api_key")
    assert item["is_sensitive"] is True
    assert "****" in item["value_json"]["value"]
