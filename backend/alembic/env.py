"""Alembic 运行环境。

- 连接串优先取 `app.core.config.Settings.database_url`（与运行期完全一致），
  未导入成功时才回退到 alembic.ini 中的 `sqlalchemy.url`；
- SQLite 下启用 `render_as_batch=True`，让 ALTER 操作以「建新表-拷数据」方式完成；
- 导入 `app.models` 以确保全部 41 张表注册进 `Base.metadata`。
"""

from __future__ import annotations

import logging
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# 让 `app` 包可被导入（backend/ 加入 sys.path）
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.base import Base  # noqa: E402
from app.models import ALL_MODELS  # noqa: E402,F401 - 导入以注册全部模型

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

logger = logging.getLogger("alembic.env")

target_metadata = Base.metadata


def _resolve_url() -> str:
    """解析数据库连接串：优先运行期配置，其次 alembic.ini。"""
    try:
        from app.core.config import get_settings

        return get_settings().database_url
    except Exception as exc:  # noqa: BLE001 - 配置不可用时回退 ini
        logger.warning("读取应用配置失败，回退 alembic.ini 中的 sqlalchemy.url: %s", exc)
        return config.get_main_option("sqlalchemy.url") or ""


def _ensure_sqlite_dir(url: str) -> None:
    """SQLite 模式下预先创建数据文件所在目录（否则会报 unable to open database file）。"""
    if not url.startswith("sqlite") or "///" not in url:
        return
    path_part = url.split("///", 1)[1]
    if path_part and path_part != ":memory:":
        Path(path_part).parent.mkdir(parents=True, exist_ok=True)


def run_migrations_offline() -> None:
    """离线模式：只生成 SQL，不连接数据库。"""
    url = _resolve_url()
    _ensure_sqlite_dir(url)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        render_as_batch=url.startswith("sqlite"),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：连接数据库并执行迁移。"""
    url = _resolve_url()
    _ensure_sqlite_dir(url)
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = url
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
