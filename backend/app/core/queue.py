"""任务队列抽象：RQ（有 Redis）↔ Inline（进程内线程池）自动降级。

调用方只依赖 `enqueue(fn, *args, **kwargs)`，不感知底层实现；
`auto` 模式下 Redis 不可用则直接同步执行，保证功能不中断。
"""

from __future__ import annotations

import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Protocol

logger = logging.getLogger("pythonlab.queue")


class Queue(Protocol):
    """队列协议。"""

    @property
    def backend(self) -> str:
        """后端名称（`rq` / `inline`）。"""

    def enqueue(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> str:
        """入队任务，返回任务 ID。"""


class InlineQueue:
    """进程内同步队列：提交到线程池立即执行（无 Redis 时的降级实现）。"""

    def __init__(self, max_workers: int = 4) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="plab-inline")

    @property
    def backend(self) -> str:
        return "inline"

    def enqueue(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> str:
        job_id = f"inline-{uuid.uuid4().hex[:12]}"

        def _runner() -> None:
            try:
                func(*args, **kwargs)
            except Exception:  # noqa: BLE001 - 后台任务异常不得影响主流程
                logger.exception("inline 任务执行失败 job_id=%s func=%s", job_id, getattr(func, "__name__", func))

        self._executor.submit(_runner)
        return job_id


class RQQueue:
    """RQ 队列实现（依赖 Redis）。"""

    def __init__(self, queue: Any) -> None:
        self._queue = queue

    @property
    def backend(self) -> str:
        return "rq"

    def enqueue(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> str:
        job = self._queue.enqueue(func, *args, **kwargs)
        return str(getattr(job, "id", ""))


def build_queue() -> InlineQueue | RQQueue:
    """按配置构建队列实例（`auto` 模式探测 Redis，失败降级 inline）。"""
    from app.core.config import get_settings

    settings = get_settings()
    mode = (settings.queue_backend or "auto").lower()

    if mode == "inline":
        logger.info("queue=inline（显式配置）")
        return InlineQueue()

    try:
        import redis
        from rq import Queue as _RQ

        if mode == "auto":
            timeout_seconds = max(0.05, settings.cache_probe_timeout_ms / 1000.0)
            client = redis.from_url(
                settings.redis_url,
                socket_connect_timeout=timeout_seconds,
                socket_timeout=timeout_seconds,
            )
            client.ping()
        else:
            client = redis.from_url(settings.redis_url)

        queue = _RQ(settings.rq_queue_name, connection=client)
        logger.info("queue=rq（队列名: %s）", settings.rq_queue_name)
        return RQQueue(queue)
    except Exception as exc:  # noqa: BLE001 - 任何异常都应降级
        if mode == "rq":
            raise
        logger.warning("Redis/RQ 不可用，降级为进程内 inline 队列: %s", exc)
        return InlineQueue()


class QueueContainer:
    """队列单例容器。"""

    def __init__(self) -> None:
        self._queue: InlineQueue | RQQueue | None = None

    def get(self) -> InlineQueue | RQQueue:
        """获取全局队列实例（首次调用时构建）。"""
        if self._queue is None:
            self._queue = build_queue()
        return self._queue

    def override(self, queue: InlineQueue | RQQueue) -> None:
        """替换队列实现（测试用）。"""
        self._queue = queue

    def reset(self) -> None:
        """清空实例。"""
        self._queue = None


queue_container = QueueContainer()


def get_queue_instance() -> InlineQueue | RQQueue:
    """获取全局队列实例。"""
    return queue_container.get()
