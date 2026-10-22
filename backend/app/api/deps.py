"""API 层依赖：请求元信息与限流。

限流按 `docs/API.md` §1.4 的窗口计数实现，基于缓存（Redis / 内存均可）；
超限抛 `RATE_LIMITED`（HTTP 429）。

**客户端 IP 的可信度**（安全修复）：`X-Forwarded-For` 由客户端可任意伪造，
若无条件采信，攻击者轮换该头即可绕过所有按 IP 的限流（QA 实测：固定伪造 XFF
15 次触发 5 次 429，轮换 XFF 15 次 0 次 429）。因此现在**只有当对端本身是
配置的可信反向代理时**才读 XFF，并取**最右侧**的那一跳（最左侧是客户端可写的）；
默认 `TRUSTED_PROXIES` 为空 = 不信任任何代理，直接用 TCP 对端地址。
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC
import ipaddress

from fastapi import Depends, Request

from app.core import config as app_config
from app.core.cache import get_cache_instance
from app.core.constants import RATE_LIMITS
from app.core.deps import get_current_user
from app.core.errors import AppError, ErrorCode
from app.core.security import decode_token
from app.models.user import User
from app.services.auth_service import RequestMeta

RATE_LIMIT_PREFIX = "rate:"


def _parse_ip(value: str | None):
    """把字符串解析为 IP 对象；非法返回 None。"""
    text = (value or "").strip()
    if not text:
        return None
    # XFF 里可能是 "host:port" 或 "[v6]:port"
    if text.startswith("["):
        text = text[1 : text.find("]")] if "]" in text else text
    elif text.count(":") == 1 and "." in text:
        text = text.split(":", 1)[0]
    try:
        return ipaddress.ip_address(text)
    except ValueError:
        return None


def _is_trusted_proxy(peer: str | None) -> bool:
    """判断 TCP 对端是否属于 `TRUSTED_PROXIES`。"""
    if not peer:
        return False
    entries = app_config.get_settings().trusted_proxy_list
    if not entries:
        return False
    address = _parse_ip(peer)
    if address is None:
        # TestClient 等非 IP 对端（如 "testclient"）按字符串精确匹配
        return peer in entries
    for entry in entries:
        if "/" in entry:
            try:
                if address in ipaddress.ip_network(entry, strict=False):
                    return True
            except ValueError:
                continue
        elif _parse_ip(entry) == address:
            return True
    return False


def client_ip(request: Request) -> str | None:
    """取客户端 IP。

    - 对端**不是**可信代理（默认情形）→ 只用 `request.client.host`，忽略 XFF；
    - 对端是可信代理 → 解析 XFF，取最右侧一跳（可信代理自己追加的那一跳）。
    """
    peer = request.client.host if request.client else None
    if not _is_trusted_proxy(peer):
        return peer

    forwarded = request.headers.get("x-forwarded-for")
    if not forwarded:
        return peer
    # 最右侧优先；若最右侧仍是可信代理（多级反代），继续向左找到第一个非可信地址
    trusted = app_config.get_settings().trusted_proxy_list
    for candidate in reversed([item.strip() for item in forwarded.split(",") if item.strip()]):
        if not trusted or candidate not in trusted:
            return candidate[:45]
    return forwarded.split(",")[-1].strip()[:45]


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
            from datetime import datetime

            meta.access_expires_at = datetime.fromtimestamp(float(expires), tz=UTC)
    return meta


def enforce_rate_limit(key: str, limit: int, window_seconds: int) -> None:
    """窗口计数限流：超过 `limit` 抛 `RATE_LIMITED`。"""
    cache = get_cache_instance()
    cache_key = f"{RATE_LIMIT_PREFIX}{key}"
    try:
        count = cache.incr(cache_key, 1, ttl=window_seconds)
    except Exception:
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
