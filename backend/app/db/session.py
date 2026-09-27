"""数据库引擎与会话工厂。

按 `DATABASE_URL` 前缀自动选择后端：
- `sqlite`：`connect_args={"check_same_thread": False}`，并注册 `PRAGMA foreign_keys=ON`
  与 WAL 模式（SQLite 必须显式开启外键，见 DATABASE.md §13）；
- `postgresql`：启用连接池（pool_pre_ping + pool_size），不传 check_same_thread。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

logger = logging.getLogger("pythonlab.db")

settings = get_settings()


def _build_engine() -> Engine:
    """按配置构建 Engine（首次导入时调用一次）。"""
    url = settings.database_url
    kwargs: dict[str, Any] = {
        "echo": settings.db_echo,
        "future": True,
    }

    if settings.is_sqlite:
        # SQLite 需要允许跨线程使用（FastAPI 线程池执行同步端点）
        kwargs["connect_args"] = {"check_same_thread": False, "timeout": 15}
        # 确保父目录存在，否则 sqlite 会直接报 unable to open database file
        db_path = url.split("///", 1)[-1]
        if db_path and db_path not in (":memory:", ""):
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        kwargs.pop("pool_size", None)
    else:
        kwargs.update(
            pool_pre_ping=True,
            pool_size=settings.db_pool_size,
            max_overflow=max(5, settings.db_pool_size // 2),
            pool_recycle=1800,
        )

    engine = create_engine(url, **kwargs)

    if settings.is_sqlite:
        _register_sqlite_listeners(engine)

    logger.info(
        "数据库引擎已创建 flavor=%s target=%s",
        settings.db_flavor,
        settings.database_host_hint,
    )
    return engine


def _register_sqlite_listeners(engine: Engine) -> None:
    """注册 SQLite 连接事件：开启外键约束与 WAL 日志模式。"""

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_connection: Any, _record: Any) -> None:  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            if settings.sqlite_wal:
                cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
        finally:
            cursor.close()


engine: Engine = _build_engine()

SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)


def get_engine() -> Engine:
    """返回全局 Engine（供健康检查与迁移脚本使用）。"""
    return engine


def create_session() -> Session:
    """创建一个独立会话（脚本 / 后台任务使用，需自行关闭）。"""
    return SessionLocal()


def ping(timeout_seconds: float = 2.0) -> bool:
    """探测数据库连通性（健康检查用），任何异常返回 False。"""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # noqa: BLE001 - 健康检查不应抛出
        logger.warning("数据库探活失败: %s", exc)
        return False


def table_names() -> list[str]:
    """返回当前库中的全部表名（升序）。"""
    from sqlalchemy import inspect

    return sorted(inspect(engine).get_table_names())
