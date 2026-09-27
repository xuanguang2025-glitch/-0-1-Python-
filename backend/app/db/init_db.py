"""建表与数据自检工具。

- `create_all()`：直接按模型建表（本机无 Docker 时的快速路径，与 Alembic 二选一）；
- `drop_all()`：清空全部表（`--reset` 与测试使用）；
- `table_report()`：返回各表行数统计，供种子脚本打印。

生产环境请使用 `alembic upgrade head`，本模块主要服务本机开发与测试。
"""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text

from app.db.base import Base
from app.db.session import engine
from app.models import ALL_MODELS  # noqa: F401 - 导入即完成模型注册

logger = logging.getLogger("pythonlab.db")

#: 模型声明的表数量（用于启动期自检，与 DATABASE.md 的 40 张表对齐）
EXPECTED_TABLE_COUNT: int = 41


def create_all() -> list[str]:
    """按模型创建全部表（已存在则跳过），返回创建后的表名列表。"""
    Base.metadata.create_all(bind=engine)
    names = table_names()
    logger.info("建表完成，共 %d 张表", len(names))
    return names


def drop_all() -> None:
    """删除全部表（危险操作，仅开发/测试使用）。"""
    Base.metadata.drop_all(bind=engine)
    logger.warning("已删除全部表")


def table_names() -> list[str]:
    """返回当前库中的表名（升序）。"""
    return sorted(inspect(engine).get_table_names())


def table_report() -> dict[str, int]:
    """统计各表行数，返回 `{表名: 行数}`（按表名升序）。"""
    report: dict[str, int] = {}
    with engine.connect() as connection:
        for name in table_names():
            try:
                count = connection.execute(text(f'SELECT COUNT(*) FROM "{name}"')).scalar()  # noqa: S608 - 表名来自元数据
                report[name] = int(count or 0)
            except Exception:  # noqa: BLE001 - 统计失败不影响主流程
                report[name] = -1
    return report


def has_all_tables() -> bool:
    """判断模型声明的表是否都已存在。"""
    existing = set(table_names())
    expected = {table.name for table in Base.metadata.sorted_tables}
    return expected.issubset(existing)
