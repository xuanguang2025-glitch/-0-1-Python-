"""健康检查服务：返回 DB / Cache / Queue / Runner / AI 的**真实**降级状态。

`/api/health/deps` 是排查「本机无 Docker」问题的第一入口，必须反映实际生效的实现，
而不是配置声明值（例如配置 `auto` 但 Redis 不通时应显示 `memory`）。
"""

from __future__ import annotations

import logging

from app.core.cache import get_cache_instance
from app.core.config import get_settings
from app.core.queue import get_queue_instance
from app.db.session import ping as db_ping
from app.sandbox.runner import get_runner
from app.schemas.health import (
    AIStatus,
    CacheStatus,
    DbStatus,
    DepsHealthOut,
    HealthOut,
    QueueStatus,
    RunnerStatus,
)

logger = logging.getLogger("pythonlab.health")


def get_health() -> HealthOut:
    """基础健康检查（进程存活即 ok）。"""
    settings = get_settings()
    return HealthOut(status="ok", version=settings.app_version, env=settings.app_env)


def get_deps_health() -> DepsHealthOut:
    """依赖健康检查：逐项探测并汇总降级标志。"""
    settings = get_settings()
    degraded = False

    # 数据库
    db_ok = db_ping()
    db_status = DbStatus(
        ok=db_ok,
        flavor=settings.db_flavor,
        target=settings.database_host_hint,
        detail=None if db_ok else "数据库连接失败",
    )
    if not db_ok:
        degraded = True

    # 缓存
    cache_backend = "unknown"
    cache_ok = False
    cache_detail: str | None = None
    try:
        cache = get_cache_instance()
        cache_backend = cache.backend
        cache_ok = cache.ping()
    except Exception as exc:  # noqa: BLE001 - 健康检查不得抛错
        cache_detail = str(exc)
    if cache_backend != "redis":
        degraded = True
    cache_status = CacheStatus(ok=cache_ok, backend=cache_backend, detail=cache_detail)

    # 队列
    queue_backend = "unknown"
    try:
        queue_backend = get_queue_instance().backend
    except Exception as exc:  # noqa: BLE001
        logger.warning("队列状态探测失败: %s", exc)
    if queue_backend != "rq":
        degraded = True
    queue_status = QueueStatus(ok=queue_backend != "unknown", backend=queue_backend)

    # 执行器
    runner = get_runner()
    runner_status = RunnerStatus(
        ok=runner.is_ok(),
        mode=runner.mode,
        detail=None if runner.mode == "remote" else "本机执行器（无远程沙箱，能力受限）",
    )
    if runner.mode != "remote":
        degraded = True

    # AI：探测真实生效的 Provider（无 Key / 离线时降级为本地规则助手）
    ai_enabled = settings.ai_enabled
    ai_provider = settings.ai_provider if ai_enabled else "rule_based"
    ai_model = settings.ai_model if ai_enabled else "rule-based"
    ai_detail: str | None = None if ai_enabled else "未配置 AI Key，使用本地规则助手"
    try:
        from app.services.ai.tutor import TutorService

        info = TutorService().status()
        if ai_enabled:
            # 仅在已启用时采用真实 Provider/模型；降级态保持 rule_based / rule-based 语义
            ai_provider = str(info.get("provider") or ai_provider)
            ai_model = str(info.get("model") or ai_model)
        elif bool(info.get("degraded")):
            ai_detail = ai_detail or "AI 子系统已降级"
    except Exception as exc:  # noqa: BLE001 - 健康检查不得抛错
        logger.warning("AI 状态探测失败，回退配置值: %s", exc)

    ai_status = AIStatus(
        ok=ai_enabled,
        provider=ai_provider,
        model=ai_model,
        available=ai_enabled,
        degraded=not ai_enabled,
        detail=ai_detail,
    )
    if not ai_enabled:
        degraded = True

    return DepsHealthOut(
        status="ok" if not degraded else "degraded",
        db=db_status,
        cache=cache_status,
        queue=queue_status,
        runner=runner_status,
        ai=ai_status,
        degraded=degraded,
        version=settings.app_version,
    )
