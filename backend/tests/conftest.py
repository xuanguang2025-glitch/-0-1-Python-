"""统一测试基座（`backend/tests/conftest.py`）。

解决的问题
----------
1. **建库慢**：磁盘 SQLite 每个用例 `create_all` 建 41 张表约 18 秒，导致全量
   套件被磁盘 DDL 拖垮；改用**内存 SQLite + StaticPool**后建库约 0.10 秒。
2. **重复搭 App**：每个用例都重新 `FastAPI()` + `include_router()`（约 0.95 秒/次）。
   这里把 App 与 `TestClient` 按「路由集合」做**会话级缓存**，`get_db` 覆盖改为
   每次请求动态解析当前用例的 session 工厂，从而同时拿到「App 只建一次」与
   「每用例独立数据库」。
3. **全局状态串味**：限流计数走全局缓存（`cache_container`），跨用例会累积导致
   偶发 429。这里每个用例注入全新 `MemoryCache` 并在结束后复位。

对外夹具
--------
- `db_engine` / `session_factory` / `db`：内存库与会话；
- `app_factory` / `client_factory` / `make_client`：会话级缓存的临时应用与客户端；
- `seeded_users` / `auth_tokens` / `user_headers` / `admin_headers`：普通用户与管理员；
- `upload_dir`：每用例独立的上传目录（指向 `tmp_path`）。

注意：本文件只提供**测试期**基础设施，不修改任何业务代码。
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Iterator, Sequence

# 必须在导入 app 之前固定测试环境
# pytest.ini 的 [pytest] env 会设置这些变量；此处 setdefault 作为兜底，保证单独运行也一致。
os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("AI_OFFLINE", "true")
os.environ.setdefault("AI_API_KEY", "")
os.environ.setdefault("CACHE_BACKEND", "memory")
os.environ.setdefault("QUEUE_BACKEND", "inline")
os.environ.setdefault("SANDBOX_MODE", "stub")
os.environ.setdefault("DATABASE_URL", "sqlite:///./data/pythonlab_test.db")

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import Engine, create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.models  # noqa: E402,F401 - 触发全部模型注册
from app.core.cache import MemoryCache, cache_container  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.deps import get_db  # noqa: E402
from app.core.errors import register_exception_handlers  # noqa: E402
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.models.user import Profile, User  # noqa: E402
from app.services.sandbox_client import (  # noqa: E402
    SandboxClient,
    reset_sandbox_client,
    set_sandbox_client,
)

#: 真实种子库（内容域测试需要真实课程数据）。
REAL_DB: Path = Path(__file__).resolve().parents[1] / "data" / "pythonlab.db"

#: 内存库建表耗时（本机实测：磁盘 ~18s / 内存 ~0.1s），表数量由守护用例校验。

#: 当前用例的 session 工厂。App 为会话级缓存，其 `get_db` 覆盖在请求时读取此槽位，
#: 从而做到「App 只建一次」+「每用例独立数据库」。
_ACTIVE: dict[str, Any] = {"session_factory": None}

#: 按路由集合缓存 App / TestClient，避免每用例重复搭应用。
_APP_CACHE: dict[tuple[int, ...], FastAPI] = {}
_CLIENT_CACHE: dict[tuple[int, ...], TestClient] = {}


# --------------------------------------------------------------------- 环境隔离
@pytest.fixture(scope="session")
def upload_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """把上传目录指向 pytest 管理的临时目录，避免用例写脏仓库内的 `data/uploads`。

    刻意做成**会话级**：早期版本用函数级 `tmp_path`，结果每个用例都新建一个临时目录
    （全量 100+ 个），既拖慢运行又会把宿主的临时目录清理守卫顶到批量阈值。
    上传目录本身与用例无关，会话级足够。
    """
    target = tmp_path_factory.mktemp("uploads") / "data"
    target.mkdir(parents=True, exist_ok=True)
    settings = get_settings()
    original = settings.upload_dir
    settings.upload_dir = str(target)
    try:
        yield target
    finally:
        settings.upload_dir = original


@pytest.fixture(autouse=True)
def isolated_globals(upload_dir: Path) -> Iterator[None]:
    """每用例重置全局状态：缓存（限流计数）、沙箱客户端。

    - 全新 `MemoryCache` → `rate:*` 计数不跨用例累积，杜绝偶发 429；
    - 执行器固定为 `local`（本机降级模式）→ 判题类用例可真实执行代码。
    """
    cache_container.override(MemoryCache())
    set_sandbox_client(SandboxClient(mode="local"))
    try:
        yield
    finally:
        reset_sandbox_client()
        cache_container.reset()


# ----------------------------------------------------------------------- 数据库
@pytest.fixture()
def db_engine() -> Iterator[Engine]:
    """每用例独立的内存 SQLite（单连接，保证建表与请求共享同一库）。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture()
def session_factory(db_engine: Engine) -> Iterator[sessionmaker[Session]]:
    """绑定到当前用例内存库的会话工厂，并登记为当前活跃工厂。"""
    factory = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False, class_=Session)
    _ACTIVE["session_factory"] = factory
    try:
        yield factory
    finally:
        _ACTIVE["session_factory"] = None


@pytest.fixture()
def db(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    """供造数与直接断言使用的会话。"""
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


# ------------------------------------------------------------------- 应用与客户端
def _override_get_db() -> Iterator[Session]:
    """`get_db` 覆盖：每次请求都从当前用例的活跃工厂取会话。"""
    factory = _ACTIVE["session_factory"]
    if factory is None:
        raise RuntimeError("未启用 session_factory 夹具，无法解析数据库会话")
    session = factory()
    try:
        yield session
    finally:
        session.close()


def _router_key(routers: Sequence[Any], prefix: str) -> tuple[int, ...]:
    """用路由对象身份 + 前缀作为缓存键。"""
    return tuple(id(router) for router in routers) + (hash(prefix),)


@pytest.fixture(scope="session")
def app_factory() -> Iterator[Callable[..., FastAPI]]:
    """返回按「路由集合」缓存的应用构建器。"""

    def build(
        routers: Sequence[Any],
        *,
        prefix: str = "/api",
        dependencies: dict[Any, Any] | None = None,
    ) -> FastAPI:
        """构建（或复用）一个临时 FastAPI 应用。"""
        key = _router_key(routers, prefix)
        cached = _APP_CACHE.get(key)
        if cached is not None:
            return cached
        app = FastAPI()
        register_exception_handlers(app)
        for router in routers:
            app.include_router(router, prefix=prefix)
        app.dependency_overrides[get_db] = _override_get_db
        if dependencies:
            app.dependency_overrides.update(dependencies)
        _APP_CACHE[key] = app
        return app

    yield build
    _APP_CACHE.clear()
    _CLIENT_CACHE.clear()


@pytest.fixture(scope="session")
def client_factory(app_factory: Callable[..., FastAPI]) -> Iterator[Callable[..., TestClient]]:
    """返回按「路由集合」缓存的 TestClient 构建器。"""

    def make(
        routers: Sequence[Any],
        *,
        prefix: str = "/api",
        dependencies: dict[Any, Any] | None = None,
    ) -> TestClient:
        """构建（或复用）一个 TestClient。"""
        key = _router_key(routers, prefix)
        cached = _CLIENT_CACHE.get(key)
        if cached is None:
            cached = TestClient(app_factory(routers, prefix=prefix, dependencies=dependencies))
            _CLIENT_CACHE[key] = cached
        return cached

    yield make
    for client in _CLIENT_CACHE.values():
        client.close()


@pytest.fixture()
def make_client(client_factory: Callable[..., TestClient]) -> Callable[..., TestClient]:
    """用例内直接拿到客户端构建器（函数级别名，便于注入）。"""
    return client_factory


@pytest.fixture(scope="session")
def install_session_factory() -> Callable[[sessionmaker[Session] | None], None]:
    """把指定 session 工厂登记为当前活跃工厂（传 `None` 表示取消登记）。

    供「使用真实种子库（而非每用例内存库）」的域使用：这类域自己持有模块级引擎，
    只需把它登记为活跃工厂，会话级缓存的 App 的 `get_db` 覆盖即可解析到它。
    设为会话级是为了能被模块级夹具使用。
    """

    def _install(factory: sessionmaker[Session] | None) -> None:
        _ACTIVE["session_factory"] = factory

    return _install


# ------------------------------------------------------------------- 用户与令牌
#: 测试统一口令。bcrypt cost=12 单次约 0.24s，若每个用例都现算会白白多花十几秒，
#: 因此整个会话只算一次，所有测试用户复用同一个哈希串。
TEST_PASSWORD = "Test@12345"


@pytest.fixture(scope="session")
def password_hash() -> str:
    """全会话复用的 bcrypt 哈希（避免每个用例重复付出 bcrypt 成本）。"""
    return hash_password(TEST_PASSWORD)


@pytest.fixture()
def seeded_users(db: Session, password_hash: str) -> SimpleNamespace:
    """写入一个普通用户与一个超级管理员（含 Profile）。"""
    user = User(
        email="tester@pythonlab.dev",
        username="tester",
        hashed_password=password_hash,
        role="user",
        is_verified=True,
    )
    admin = User(
        email="tester_admin@pythonlab.dev",
        username="tester_admin",
        hashed_password=password_hash,
        role="superadmin",
        is_verified=True,
    )
    db.add_all([user, admin])
    db.flush()
    db.add_all(
        [
            Profile(user_id=user.id, display_name="测试用户"),
            Profile(user_id=admin.id, display_name="测试管理员"),
        ]
    )
    db.commit()
    return SimpleNamespace(
        user_id=user.id,
        admin_id=admin.id,
        username=user.username,
        admin_username=admin.username,
    )


@pytest.fixture()
def auth_tokens(seeded_users: SimpleNamespace) -> SimpleNamespace:
    """为普通用户与管理员各生成一个 Access Token。"""
    user_token, _jti, _exp = create_access_token(
        seeded_users.user_id, role="user", username=seeded_users.username
    )
    admin_token, _jti, _exp = create_access_token(
        seeded_users.admin_id, role="superadmin", username=seeded_users.admin_username
    )
    return SimpleNamespace(user=user_token, admin=admin_token)


@pytest.fixture()
def user_headers(auth_tokens: SimpleNamespace) -> dict[str, str]:
    """普通用户鉴权头。"""
    return {"Authorization": f"Bearer {auth_tokens.user}"}


@pytest.fixture()
def admin_headers(auth_tokens: SimpleNamespace) -> dict[str, str]:
    """管理员鉴权头。"""
    return {"Authorization": f"Bearer {auth_tokens.admin}"}


# ------------------------------------------------------------------ 真实种子库
def copy_real_db(target: Path) -> None:
    """把真实种子库在线备份到 `target`（含 WAL 中已提交的数据）。"""
    source = sqlite3.connect(str(REAL_DB))
    dest = sqlite3.connect(str(target))
    try:
        source.backup(dest)
    finally:
        dest.close()
        source.close()


@pytest.fixture(scope="session")
def seeded_real_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """真实种子库的一致副本（内容域校验真实课程数据时使用）。"""
    if not REAL_DB.exists():
        pytest.skip(f"真实数据库不存在：{REAL_DB}")
    target = tmp_path_factory.mktemp("realseed") / "seed.db"
    copy_real_db(target)
    return target


__all__ = [
    "REAL_DB",
    "admin_headers",
    "app_factory",
    "auth_tokens",
    "client_factory",
    "copy_real_db",
    "db",
    "db_engine",
    "install_session_factory",
    "isolated_globals",
    "make_client",
    "password_hash",
    "seeded_real_db",
    "seeded_users",
    "session_factory",
    "upload_dir",
    "user_headers",
]
