"""缓存抽象：Redis ↔ 进程内内存缓存自动降级（`docs/ARCHITECTURE.md` §1.3 ②）。

- `CACHE_BACKEND=redis` 强制使用 Redis，构造失败直接抛错（不静默降级）；
- `CACHE_BACKEND=memory` 强制使用内存缓存；
- `CACHE_BACKEND=auto` 启动期探测 `PING`，失败则打印 WARN 并降级为 `MemoryCache`。

统一接口：`get / set / delete / exists / incr / expire / clear / get_or_set`。
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import OrderedDict
from typing import Any, Callable, Protocol

logger = logging.getLogger("pythonlab.cache")


class Cache(Protocol):
    """缓存后端协议。所有实现必须线程安全。"""

    @property
    def backend(self) -> str:
        """后端名称（`redis` / `memory`）。"""

    def get(self, key: str) -> Any | None:
        """读取缓存值；不存在或已过期返回 None。"""

    def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """写入缓存。"""

    def delete(self, key: str) -> bool:
        """删除键。"""

    def exists(self, key: str) -> bool:
        """判断键是否存在。"""

    def incr(self, key: str, amount: int = 1, ttl: int | None = None) -> int:
        """自增计数器，返回自增后的值。"""

    def expire(self, key: str, ttl: int) -> bool:
        """设置过期时间。"""

    def clear(self) -> None:
        """清空全部缓存（仅测试/维护使用）。"""

    def get_or_set(self, key: str, ttl: int, factory: Callable[[], Any]) -> Any:
        """缓存穿透保护：命中直接返回，未命中则调用 `factory` 并写入。"""

    def ping(self) -> bool:
        """健康检查。"""


class MemoryCache:
    """进程内 TTL + LRU 缓存（Redis 不可用时的降级实现）。

    使用 `OrderedDict` 维护插入顺序，惰性过期 + 容量上限淘汰最旧键。
    """

    def __init__(self, max_size: int = 5000, default_ttl: int = 300) -> None:
        self._max_size = max(1, int(max_size))
        self._default_ttl = int(default_ttl)
        self._store: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._lock = threading.RLock()

    @property
    def backend(self) -> str:
        return "memory"

    def _purge_expired(self, key: str | None = None) -> None:
        """惰性删除过期键；`key` 为空时全量扫描（低频调用）。"""
        now = time.monotonic()
        if key is not None:
            entry = self._store.get(key)
            if entry is not None and entry[1] <= now:
                self._store.pop(key, None)
            return
        expired = [k for k, (_, deadline) in self._store.items() if deadline <= now]
        for k in expired:
            self._store.pop(k, None)

    def _evict_if_needed(self) -> None:
        """超出容量上限时淘汰最旧的键。"""
        while len(self._store) > self._max_size:
            self._store.popitem(last=False)

    def get(self, key: str) -> Any | None:
        with self._lock:
            self._purge_expired(key)
            entry = self._store.get(key)
            if entry is None:
                return None
            # 命中后移到末尾，维持 LRU 顺序
            self._store.move_to_end(key)
            return entry[0]

    def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        ttl_seconds = self._default_ttl if ttl is None else int(ttl)
        if ttl_seconds <= 0:
            return self.delete(key)
        with self._lock:
            self._store[key] = (value, time.monotonic() + ttl_seconds)
            self._store.move_to_end(key)
            self._evict_if_needed()
        return True

    def delete(self, key: str) -> bool:
        with self._lock:
            return self._store.pop(key, None) is not None

    def exists(self, key: str) -> bool:
        with self._lock:
            self._purge_expired(key)
            return key in self._store

    def incr(self, key: str, amount: int = 1, ttl: int | None = None) -> int:
        with self._lock:
            current = self.get(key)
            base = int(current) if isinstance(current, (int, float)) else 0
            value = base + int(amount)
            self.set(key, value, ttl)
            return value

    def expire(self, key: str, ttl: int) -> bool:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return False
            self._store[key] = (entry[0], time.monotonic() + int(ttl))
            return True

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def get_or_set(self, key: str, ttl: int, factory: Callable[[], Any]) -> Any:
        cached = self.get(key)
        if cached is not None:
            return cached
        value = factory()
        self.set(key, value, ttl)
        return value

    def ping(self) -> bool:
        return True

    def __len__(self) -> int:
        """当前缓存键数量（便于测试与运维观察）。"""
        with self._lock:
            self._purge_expired()
            return len(self._store)


class RedisCache:
    """Redis 缓存实现。值统一以 JSON 序列化，保证跨语言可读。"""

    def __init__(self, client: Any, default_ttl: int = 300) -> None:
        self._client = client
        self._default_ttl = int(default_ttl)

    @property
    def backend(self) -> str:
        return "redis"

    @staticmethod
    def _encode(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, default=str)

    @staticmethod
    def _decode(raw: Any) -> Any | None:
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return raw

    def get(self, key: str) -> Any | None:
        return self._decode(self._client.get(key))

    def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        ttl_seconds = self._default_ttl if ttl is None else int(ttl)
        if ttl_seconds <= 0:
            return bool(self._client.delete(key))
        return bool(self._client.setex(key, ttl_seconds, self._encode(value)))

    def delete(self, key: str) -> bool:
        return bool(self._client.delete(key))

    def exists(self, key: str) -> bool:
        return bool(self._client.exists(key))

    def incr(self, key: str, amount: int = 1, ttl: int | None = None) -> int:
        value = int(self._client.incrby(key, int(amount)))
        if ttl and value == int(amount):
            # 首次自增时设置过期时间，避免计数器永不过期
            self._client.expire(key, int(ttl))
        return value

    def expire(self, key: str, ttl: int) -> bool:
        return bool(self._client.expire(key, int(ttl)))

    def clear(self) -> None:
        self._client.flushdb()

    def get_or_set(self, key: str, ttl: int, factory: Callable[[], Any]) -> Any:
        cached = self.get(key)
        if cached is not None:
            return cached
        value = factory()
        self.set(key, value, ttl)
        return value

    def ping(self) -> bool:
        try:
            return bool(self._client.ping())
        except Exception:  # noqa: BLE001 - 健康检查不应抛出
            return False


def build_cache() -> MemoryCache | RedisCache:
    """按配置构建缓存实例（`auto` 模式探测 Redis，失败降级内存缓存）。"""
    from app.core.config import get_settings

    settings = get_settings()
    mode = (settings.cache_backend or "auto").lower()

    if mode == "memory":
        logger.info("cache=memory（显式配置）")
        return MemoryCache(default_ttl=settings.cache_default_ttl)

    if mode == "redis":
        import redis  # 延迟导入：无 Redis 时也能启动

        client = redis.from_url(settings.redis_url, decode_responses=True)
        client.ping()
        logger.info("cache=redis（显式配置）")
        return RedisCache(client, default_ttl=settings.cache_default_ttl)

    # auto：探测后决定
    try:
        import redis

        timeout_seconds = max(0.05, settings.cache_probe_timeout_ms / 1000.0)
        client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=timeout_seconds,
            socket_timeout=timeout_seconds,
        )
        client.ping()
        logger.info("cache=redis（auto 探测成功: %s）", settings.redis_url)
        return RedisCache(client, default_ttl=settings.cache_default_ttl)
    except Exception as exc:  # noqa: BLE001 - 任何异常都应降级而非中断启动
        logger.warning("Redis 不可用，降级为进程内内存缓存: %s", exc)
        return MemoryCache(max_size=5000, default_ttl=settings.cache_default_ttl)


class CacheContainer:
    """缓存单例容器，支持测试期替换实现。"""

    def __init__(self) -> None:
        self._cache: MemoryCache | RedisCache | None = None

    def get(self) -> MemoryCache | RedisCache:
        """获取全局缓存实例（首次调用时构建）。"""
        if self._cache is None:
            self._cache = build_cache()
        return self._cache

    def override(self, cache: MemoryCache | RedisCache) -> None:
        """替换缓存实现（测试用）。"""
        self._cache = cache

    def reset(self) -> None:
        """清空实例（下次调用重新探测）。"""
        self._cache = None


cache_container = CacheContainer()


def get_cache_instance() -> MemoryCache | RedisCache:
    """获取全局缓存实例。"""
    return cache_container.get()
