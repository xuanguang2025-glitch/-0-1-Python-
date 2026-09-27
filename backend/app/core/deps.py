"""FastAPI 依赖注入集合（`docs/ARCHITECTURE.md` §8.5）。

提供：数据库会话、当前用户（可选 / 强制 / 角色断言）、缓存、队列、分页参数。
"""

from __future__ import annotations

from typing import Annotated, Callable, Iterator

from fastapi import Depends, Query, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.cache import get_cache_instance
from app.core.config import Settings, get_settings
from app.core.errors import AppError, ErrorCode
from app.core.pagination import PageParams, normalize_page_params
from app.core.queue import InlineQueue, RQQueue, get_queue_instance
from app.core.security import decode_token
from app.db.session import SessionLocal
from app.models.user import User, UserRole, UserStatus

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

TOKEN_BLACKLIST_PREFIX: str = "jti:blocked:"


def get_db() -> Iterator[Session]:
    """每请求一个数据库会话，请求结束后关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_settings_dep() -> Settings:
    """以依赖形式暴露配置（便于测试覆盖）。"""
    return get_settings()


def get_cache() -> object:
    """获取全局缓存实例。"""
    return get_cache_instance()


def get_queue() -> InlineQueue | RQQueue:
    """获取全局队列实例。"""
    return get_queue_instance()


def get_pagination(
    page: Annotated[int, Query(ge=1, description="页码，从 1 开始")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="每页条数，最大 100")] = 20,
    sort: Annotated[str | None, Query(description="排序键，见白名单")] = None,
) -> PageParams:
    """规范化分页参数（page_size 自动 clamp 到 1..100）。"""
    return normalize_page_params(page=page, page_size=page_size, sort=sort)


def is_token_blocked(jti: str) -> bool:
    """判断 Access Token 的 jti 是否已被登出吊销。"""
    cache = get_cache_instance()
    try:
        return bool(cache.exists(f"{TOKEN_BLACKLIST_PREFIX}{jti}"))
    except Exception:  # noqa: BLE001 - 缓存异常不应导致鉴权直接失败
        return False


def block_token(jti: str, ttl_seconds: int) -> None:
    """把 jti 加入黑名单（TTL = 令牌剩余有效期）。"""
    cache = get_cache_instance()
    try:
        cache.set(f"{TOKEN_BLACKLIST_PREFIX}{jti}", 1, ttl=max(1, ttl_seconds))
    except Exception:  # noqa: BLE001 - 黑名单写入失败仅记录
        pass


def _load_user(db: Session, user_id: str) -> User:
    """按 id 查询用户并校验状态，失败抛业务异常。"""
    user = db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise AppError(code=ErrorCode.USER_NOT_FOUND, message="用户不存在", status_code=404)
    if user.status == UserStatus.SUSPENDED:
        raise AppError(code=ErrorCode.ACCOUNT_SUSPENDED, message="账号已被禁用，请联系管理员", status_code=403)
    return user


def get_current_user(
    request: Request,
    token: Annotated[str | None, Depends(oauth2_scheme)] = None,
    db: Session = Depends(get_db),
) -> User:
    """解析 Bearer Token 并校验类型/黑名单/状态，返回当前用户。"""
    raw_token = token
    if not raw_token:
        # 兼容前端直接放在 Authorization 头但未走 OAuth2 表单的情况
        header = request.headers.get("Authorization", "")
        if header.lower().startswith("bearer "):
            raw_token = header.split(" ", 1)[1].strip()
    if not raw_token:
        raise AppError(code=ErrorCode.UNAUTHORIZED, message="缺少认证令牌", status_code=401)

    payload = decode_token(raw_token, expected_type="access")
    jti = str(payload.get("jti") or "")
    if jti and is_token_blocked(jti):
        raise AppError(code=ErrorCode.TOKEN_REVOKED, message="令牌已失效，请重新登录", status_code=401)

    user = _load_user(db, str(payload.get("sub") or ""))
    # 更新活跃时间（低频写，放在鉴权链路上足够）
    user.touch_active()
    db.commit()
    return user


def get_current_user_optional(
    request: Request,
    token: Annotated[str | None, Depends(oauth2_scheme)] = None,
    db: Session = Depends(get_db),
) -> User | None:
    """可选鉴权：无令牌或令牌无效时返回 None（用于公开接口的进度增强）。"""
    try:
        return get_current_user(request, token, db)
    except AppError:
        return None


def require_role(*roles: str) -> Callable[..., User]:
    """构造角色断言依赖：当前用户角色必须落在 `roles` 内。"""

    def _dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise AppError(code=ErrorCode.FORBIDDEN, message="权限不足", status_code=403)
        return current_user

    return _dependency


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """管理员断言：`role in (admin, superadmin)`。"""
    if current_user.role not in (UserRole.ADMIN, UserRole.SUPERADMIN):
        raise AppError(code=ErrorCode.FORBIDDEN, message="需要管理员权限", status_code=403)
    return current_user


def get_user_by_account(db: Session, account: str) -> User | None:
    """按邮箱或用户名查询用户（登录用）。"""
    value = account.strip().lower()
    stmt = select(User).where(
        (User.email == value) | (User.username == value),
        User.deleted_at.is_(None),
    )
    return db.scalars(stmt).one_or_none()


# 常用依赖类型别名，便于端点签名保持简洁
DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_current_user_optional)]
AdminUser = Annotated[User, Depends(require_admin)]
Pagination = Annotated[PageParams, Depends(get_pagination)]
