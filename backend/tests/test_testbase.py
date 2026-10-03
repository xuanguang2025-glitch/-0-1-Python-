"""统一测试基座（`tests/conftest.py`）的守护用例。

这些用例本身不测业务，只测**基座没有被改坏**，防止后续有人把内存库、令牌夹具、
限流隔离或 App 复用改掉而不自知。
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import inspect, select, text

from app.api.endpoints import auth as auth_endpoint
from app.core.cache import get_cache_instance
from app.db.base import Base
from app.models.user import Profile, User

GUARD_ROUTERS = (auth_endpoint.router,)


def test_db_engine_creates_every_metadata_table(db_engine) -> None:
    """内存库必须建出 metadata 里的全部表（本机实测 41 张），一张都不能少。"""
    expected = set(Base.metadata.tables)
    assert len(expected) >= 41, f"metadata 表数量异常：{len(expected)}"

    actual = set(inspect(db_engine).get_table_names())
    missing = expected - actual
    assert not missing, f"内存库缺少表：{sorted(missing)}"


def test_db_engine_is_memory_and_writable(db_engine, db) -> None:
    """内存库可读可写，且确实不是磁盘文件（`sqlite://` + StaticPool）。"""
    assert db_engine.url.database in (None, "", ":memory:"), f"期望内存库，实际：{db_engine.url}"
    assert db.execute(text("SELECT 1")).scalar_one() == 1


def test_token_fixture_authenticates_against_auth_me(client_factory, user_headers) -> None:
    """`user_headers` 令牌必须能通过真实鉴权链路（GET /api/auth/me → 200）。"""
    client: TestClient = client_factory(GUARD_ROUTERS)
    resp = client.get("/api/auth/me", headers=user_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["email"] == "tester@pythonlab.dev"


def test_rate_limit_cache_is_reset_between_tests() -> None:
    """每个用例开始时缓存必须是空的——否则 `rate:*` 计数会跨用例串味导致偶发 429。"""
    assert len(get_cache_instance()) == 0, "用例开始时缓存非空，限流/缓存隔离已失效"


def test_client_factory_reuses_app_within_session(client_factory) -> None:
    """同一组路由必须复用同一个 TestClient（会话级缓存，这是提速的关键）。"""
    first = client_factory(GUARD_ROUTERS)
    second = client_factory(GUARD_ROUTERS)
    assert first is second


def test_seeded_users_have_expected_roles(seeded_users, db) -> None:
    """基座必须同时产出普通用户与超级管理员，且角色 / Profile 正确。"""
    assert seeded_users.user_id != seeded_users.admin_id
    roles = {
        user.id: user.role
        for user in (db.get(User, seeded_users.user_id), db.get(User, seeded_users.admin_id))
    }
    assert roles[seeded_users.user_id] == "user"
    assert roles[seeded_users.admin_id] == "superadmin"
    profiles = db.scalars(
        select(Profile).where(Profile.user_id.in_([seeded_users.user_id, seeded_users.admin_id]))
    ).all()
    assert len(profiles) == 2, "两个用户都应有 Profile"
