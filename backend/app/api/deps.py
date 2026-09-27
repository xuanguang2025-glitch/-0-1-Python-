"""API 层依赖：请求元信息与限流。

限流按 `docs/API.md` §1.4 的窗口计数实现，基于缓存（Redis / 内存均可）；
超限抛 `RATE_LIMITED`（HTTP 429）。
"""

from __future__ import annotations

from typing import Callable

from fastapi import Depends, Request

from app.core.cache import get_cache_instance
from app.core.constants import RATE_LIMITS
from app.core.deps import get_current_user
from app.core.errors import AppError, ErrorCode
from app.core.security import decode_token
from app.models.user import User
from app.services.auth_service import RequestMeta

RATE_LIMIT_PREFIX = "rate:"


def client_ip(request: Request) -> str | None:
    """取客户端 IP（优先 X-Forwarded-For，便于反向代理场景）。"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:45]
    return request.client.host if request.client else None


def client_user_agent(request: Request) -> str | None:
    """取客户端 User-Agent（截断到列长度）。"""
    raw = request.headers.get("user-agent")
    return raw[:255] if raw else None


def build_request_meta(request: Request, *, with_token_context: bool = False) -> RequestMeta:
    """构造请求元信息；`with_token_context=True` 时解析当前 Access 的 jti 与过期时间。"""
    meta = RequestMeta(ip=client_ip(request), user_agent=client_user_agent(request))
    if not with_token_context:
        return meta

    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        token = header.split(" ", 1)[1].strip()
        try:
            payload = decode_token(token, expected_type="access")
        except AppError:
            return meta
        meta.jti = payload.get("jti")
        expires = payload.get("exp")
        if isinstance(expires, (int, float)):
            from datetime import datetime, timezone

            meta.access_expires_at = datetime.fromtimestamp(float(expires), tz=timezone.utc)
    return meta


def enforce_rate_limit(key: str, limit: int, window_seconds: int) -> None:
    """窗口计数限流：超过 `limit` 抛 `RATE_LIMITED`。"""
    cache = get_cache_instance()
    cache_key = f"{RATE_LIMIT_PREFIX}{key}"
    try:
        count = cache.incr(cache_key, 1, ttl=window_seconds)
    except Exception:  # noqa: BLE001 - 缓存异常时放行，避免误伤用户
        return
    if count > limit:
        raise AppError(
            code=ErrorCode.RATE_LIMITED,
            message=f"操作过于频繁，请 {window_seconds} 秒后重试",
            status_code=429,
            details={"limit": limit, "window_seconds": window_seconds},
        )


def rate_limit(name: str) -> Callable[[Request], None]:
    """构造按 IP 限流的依赖。

    Args:
        name: `RATE_LIMITS` 中的键（auth / run / submit / export）。

    Returns:
        FastAPI 依赖函数。
    """
    limit, window = RATE_LIMITS.get(name, (60, 60))

    def _dependency(request: Request) -> None:
        enforce_rate_limit(f"{name}:{client_ip(request) or 'unknown'}", limit, window)

    return _dependency


def rate_limit_user(name: str) -> Callable[..., None]:
    """构造按登录用户限流的依赖（用于 /api/submissions 等）。

    Args:
        name: `RATE_LIMITS` 中的键。

    Returns:
        FastAPI 依赖函数（内部依赖 `get_current_user`）。
    """

    limit, window = RATE_LIMITS.get(name, (60, 60))

    def _dependency(request: Request, user: User = Depends(get_current_user)) -> None:
        enforce_rate_limit(f"{name}:{user.id}", limit, window)

    return _dependency
