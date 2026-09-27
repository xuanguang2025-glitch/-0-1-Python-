#!/usr/bin/env python
"""PYTHON LAB 种子数据导入命令行入口。

用法：
    python scripts/seed.py                  # 幂等导入全部种子
    python scripts/seed.py --reset          # 先删表重建再导入（危险，仅开发）
    python scripts/seed.py --only courses,problems
    python scripts/seed.py --no-admin       # 不创建默认管理员

说明：
    本脚本会自动把 `backend/` 加入 `sys.path`，因此无论从项目根或 backend 目录
    运行均可正常工作。核心逻辑复用 `app.db.seed.seed_all`。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 保证可以 `import app.*`（scripts/ 的上一级即 backend/）
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def build_parser() -> argparse.ArgumentParser:
    """构建命令行解析器。"""
    parser = argparse.ArgumentParser(
        prog="seed",
        description="PYTHON LAB 种子数据导入工具（幂等，可重复执行）",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="先删除全部表再重建后再导入（危险，仅开发/测试环境）",
    )
    parser.add_argument(
        "--only",
        default="",
        help="仅导入指定分组，逗号分隔：courses,problems,projects,achievements,daily_tasks,challenges,exams",
    )
    parser.add_argument(
        "--no-admin",
        action="store_true",
        help="不创建默认管理员账号",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """脚本入口，返回进程退出码。"""
    args = build_parser().parse_args(argv)

    from app.core.config import get_settings
    from app.core.logging import setup_logging
    from app.db.seed import print_stats, seed_all

    setup_logging("INFO")
    settings = get_settings()
    only = [item.strip() for item in args.only.split(",") if item.strip()]

    database_url = settings.database_url
    print(f"数据库: {database_url}")
    print(f"种子目录: {settings.seeds_dir_path}")
    if args.reset:
        print("[警告] --reset 已启用：将删除全部表并重建")

    stats = seed_all(
        reset=args.reset,
        only=only or None,
        with_admin=not args.no_admin,
    )
    print(print_stats(stats))

    if stats.get("skipped"):
        print(f"[提示] 共 {len(stats['skipped'])} 条跳过/告警，详见上方列表。")
    print("种子导入完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
