"""FastAPI 应用工厂与生命周期。

启动顺序：
1. 初始化日志 → 2. 装配中间件（请求上下文 / CORS）→ 3. 注册全局异常处理器
→ 4. 挂载路由 → 5. 启动期自检（数据库连通 + 表存在，必要时可选执行种子）。

所有依赖都具备降级路径，因此本机无 Docker（无 Postgres / Redis / 沙箱 / AI Key）时
服务依然能正常启动（见 `GET /api/health/deps`）。
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import RequestContextMiddleware, setup_logging

logger = logging.getLogger("pythonlab")


def _startup_self_check(settings: Settings) -> None:
    """启动期自检：打印实际生效的降级实现，并在缺表时给出明确指引。"""
    from app.core.cache import get_cache_instance
    from app.core.queue import get_queue_instance
    from app.db.session import ping as db_ping
    from app.db.session import table_names
    from app.sandbox.runner import get_runner

    logger.info("=" * 68)
    logger.info("%s v%s 启动中（env=%s, debug=%s）", settings.app_name, settings.app_version, settings.app_env, settings.debug)

    db_ok = db_ping()
    tables = table_names() if db_ok else []
    logger.info("数据库: flavor=%s target=%s ok=%s 表数=%d", settings.db_flavor, settings.database_host_hint, db_ok, len(tables))

    try:
        logger.info("缓存: backend=%s", get_cache_instance().backend)
        logger.info("队列: backend=%s", get_queue_instance().backend)
        logger.info("执行器: mode=%s", get_runner().mode)
        logger.info("AI: provider=%s degraded=%s", settings.ai_provider if settings.ai_enabled else "rule", not settings.ai_enabled)
    except Exception as exc:  # noqa: BLE001 - 自检不得阻断启动
        logger.warning("依赖自检出现异常（不影响启动）: %s", exc)

    if db_ok and not tables:
        logger.warning("数据库为空，请先执行：alembic upgrade head  或  python scripts/seed.py --reset")
    logger.info("=" * 68)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期：启动自检 + （可选）自动种子。"""
    settings = get_settings()
    _startup_self_check(settings)

    if settings.seed_on_startup:
        try:
            from app.db.init_db import has_all_tables
            from app.db.seed import seed_all

            if has_all_tables():
                stats = seed_all(reset=False)
                logger.info(
                    "种子校验完成：课程 %s / 章节 %s / 课时 %s / 题目 %s",
                    stats.get("courses", 0),
                    stats.get("chapters", 0),
                    stats.get("lessons", 0),
                    stats.get("problems", 0),
                )
        except Exception as exc:  # noqa: BLE001 - 种子失败不阻断服务启动
            logger.warning("自动种子跳过：%s", exc)

    yield
    logger.info("%s 已停止", settings.app_name)


def create_app(settings: Settings | None = None) -> FastAPI:
    """应用工厂：构造并返回配置完毕的 FastAPI 实例。"""
    config = settings or get_settings()
    setup_logging(config.log_level, json_format=config.is_production)

    app = FastAPI(
        title=config.app_name,
        version=config.app_version,
        description="PYTHON LAB 后端 API（统一响应结构，详见 docs/API.md）",
        docs_url="/docs" if not config.is_production else None,
        redoc_url="/redoc" if not config.is_production else None,
        openapi_url="/openapi.json" if not config.is_production else None,
        lifespan=lifespan,
    )

    # ---- 中间件 ----
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Response-Time", "Content-Disposition"],
    )

    # ---- 全局异常 ----
    register_exception_handlers(app)

    # ---- 静态文件（上传的头像等）----
    try:
        from fastapi.staticfiles import StaticFiles

        app.mount("/uploads", StaticFiles(directory=str(config.upload_dir_path)), name="uploads")
    except Exception as exc:  # noqa: BLE001 - 上传目录异常不应阻断启动
        logger.warning("静态目录挂载失败: %s", exc)

    # ---- 路由 ----
    app.include_router(api_router, prefix=config.api_prefix)

    # ---- 根路径：避免 404 迷惑排查 ----
    @app.get("/", include_in_schema=False)
    def _root() -> JSONResponse:
        """根路径返回服务基本信息与文档入口。"""
        return JSONResponse(
            {
                "success": True,
                "data": {
                    "name": config.app_name,
                    "version": config.app_version,
                    "env": config.app_env,
                    "api_prefix": config.api_prefix,
                    "docs": "/docs",
                    "health": f"{config.api_prefix}/health/deps",
                },
                "message": "",
                "error": None,
            }
        )

    # ---- 兜底 404 由 `register_exception_handlers` 统一处理（保持统一响应结构）----

    logger.info("FastAPI 应用已创建，路由数=%d", len(app.routes))
    return app


app = create_app()
