"""认证服务：注册 / 登录 / 刷新 / 登出 / 改密（`docs/API.md` §2.1）。

安全要点：
1. 密码只以 bcrypt 哈希入库，任何响应都不含 `hashed_password`；
2. Refresh Token 仅保存 sha256 摘要，刷新时「轮换 + 吊销旧令牌」；
3. 登出同时吊销 Refresh 记录与当前 Access 的 `jti`（缓存黑名单，TTL=剩余有效期）。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import block_token, get_user_by_account
from app.core.errors import AppError, ErrorCode
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    token_hash,
    validate_password_strength,
    verify_password,
)
from app.models.enums import UserStatus
from app.models.user import Profile, RefreshToken, User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    TokenPair,
    UserBrief,
    UserMe,
    ProfileBrief,
)
from app.utils.time import is_expired

logger = logging.getLogger("pythonlab.auth")


@dataclass(slots=True)
class RequestMeta:
    """登录/刷新时记录的请求元信息。"""

    ip: str | None = None
    user_agent: str | None = None
    jti: str | None = None
    access_expires_at: datetime | None = None


def _issue_token_pair(db: Session, user: User, meta: RequestMeta) -> TokenPair:
    """签发令牌对并把 Refresh Token 摘要落库。"""
    settings = get_settings()
    display_name = user.display_name
    access_token, _access_jti, _access_exp = create_access_token(
        user.id,
        role=user.role,
        username=user.username,
        display_name=display_name,
    )
    refresh_token, refresh_jti, refresh_exp = create_refresh_token(user.id)

    record = RefreshToken(
        user_id=user.id,
        jti=refresh_jti,
        token_hash=token_hash(refresh_token),
        user_agent=(meta.user_agent or "")[:255] or None,
        ip=(meta.ip or "")[:45] or None,
        expires_at=refresh_exp,
    )
    db.add(record)
    db.commit()

    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.access_token_ttl_min * 60,
        user=UserBrief.from_user(user),
    )


def register(db: Session, payload: RegisterRequest, meta: RequestMeta | None = None) -> TokenPair:
    """注册新用户并直接返回令牌对。

    Raises:
        AppError: 注册被关闭 / 邮箱或用户名已存在。
    """
    settings = get_settings()
    if not settings.register_enabled:
        raise AppError(code=ErrorCode.REGISTER_DISABLED, message="当前已关闭注册", status_code=403)

    validate_password_strength(payload.password)
    email = payload.email.strip().lower()
    username = payload.username.strip()

    existing_email = db.scalars(select(User).where(User.email == email)).one_or_none()
    if existing_email is not None:
        raise AppError(code=ErrorCode.EMAIL_EXISTS, message="该邮箱已被注册", status_code=409)
    existing_name = db.scalars(select(User).where(User.username == username)).one_or_none()
    if existing_name is not None:
        raise AppError(code=ErrorCode.USERNAME_EXISTS, message="该用户名已被占用", status_code=409)

    user = User(
        email=email,
        username=username,
        hashed_password=hash_password(payload.password),
        role=settings.default_user_role,
        status=UserStatus.ACTIVE.value,
        is_verified=True,
        xp=0,
        level=1,
    )
    user.record_login()
    db.add(user)
    db.flush()

    # 1:1 建立资料（display_name 默认取用户名，排行榜唯一展示名）
    db.add(
        Profile(
            user_id=user.id,
            display_name=username,
            timezone="UTC",
            ai_mode=settings.ai_default_mode,
        )
    )
    db.commit()
    db.refresh(user)

    logger.info("新用户注册成功 user_id=%s username=%s", user.id, user.username)
    return _issue_token_pair(db, user, meta or RequestMeta())


def login(db: Session, payload: LoginRequest, meta: RequestMeta | None = None) -> TokenPair:
    """账号密码登录（失败统一返回 `INVALID_CREDENTIALS`，避免账号枚举）。"""
    user = get_user_by_account(db, payload.account)
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise AppError(code=ErrorCode.INVALID_CREDENTIALS, message="账号或密码错误", status_code=401)
    if user.status == UserStatus.SUSPENDED:
        raise AppError(code=ErrorCode.ACCOUNT_SUSPENDED, message="账号已被禁用，请联系管理员", status_code=403)

    user.record_login()
    db.commit()
    db.refresh(user)
    return _issue_token_pair(db, user, meta or RequestMeta())


def refresh(db: Session, raw_refresh_token: str, meta: RequestMeta | None = None) -> TokenPair:
    """刷新令牌（轮换：旧 refresh 立即吊销，签发新的一对）。"""
    payload = decode_token(raw_refresh_token, expected_type="refresh")
    record = db.scalars(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash(raw_refresh_token))
    ).one_or_none()
    if record is None:
        raise AppError(code=ErrorCode.UNAUTHORIZED, message="刷新令牌无效", status_code=401)
    if record.revoked:
        raise AppError(code=ErrorCode.TOKEN_REVOKED, message="刷新令牌已被吊销，请重新登录", status_code=401)
    if is_expired(record.expires_at):
        raise AppError(code=ErrorCode.TOKEN_EXPIRED, message="登录已过期，请重新登录", status_code=401)

    user = db.get(User, str(payload.get("sub") or record.user_id))
    if user is None or user.deleted_at is not None:
        raise AppError(code=ErrorCode.USER_NOT_FOUND, message="用户不存在", status_code=404)
    if user.status == UserStatus.SUSPENDED:
        raise AppError(code=ErrorCode.ACCOUNT_SUSPENDED, message="账号已被禁用", status_code=403)

    record.revoke()
    db.commit()
    return _issue_token_pair(db, user, meta or RequestMeta())


def logout(db: Session, user: User, meta: RequestMeta, refresh_token: str | None = None) -> None:
    """登出：吊销 Refresh 记录 + 把当前 Access 的 jti 加入黑名单。"""
    if refresh_token:
        record = db.scalars(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash(refresh_token),
                RefreshToken.user_id == user.id,
            )
        ).one_or_none()
        if record is not None:
            record.revoke()
    else:
        # 未传 refresh_token 时吊销该用户全部未吊销记录（安全兜底）
        records = db.scalars(
            select(RefreshToken).where(RefreshToken.user_id == user.id, RefreshToken.revoked.is_(False))
        ).all()
        for item in records:
            item.revoke()
    db.commit()

    if meta.jti:
        # 直接按 Access Token 的最大有效期缓存黑名单，避免边界误差
        block_token(meta.jti, get_settings().access_token_ttl_min * 60)


def change_password(db: Session, user: User, payload: ChangePasswordRequest) -> None:
    """修改自己的密码，并吊销全部 Refresh Token 强制其它设备重新登录。"""
    if not verify_password(payload.old_password, user.hashed_password):
        raise AppError(code=ErrorCode.INVALID_CREDENTIALS, message="原密码不正确", status_code=401)
    validate_password_strength(payload.new_password)
    user.hashed_password = hash_password(payload.new_password)
    for record in db.scalars(
        select(RefreshToken).where(RefreshToken.user_id == user.id, RefreshToken.revoked.is_(False))
    ).all():
        record.revoke()
    db.commit()


def reset_password(db: Session, user_id: str, new_password: str) -> None:
    """管理员重置指定用户密码（同时吊销其全部 Refresh Token）。"""
    user = db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise AppError(code=ErrorCode.USER_NOT_FOUND, message="用户不存在", status_code=404)
    validate_password_strength(new_password)
    user.hashed_password = hash_password(new_password)
    for record in db.scalars(
        select(RefreshToken).where(RefreshToken.user_id == user.id, RefreshToken.revoked.is_(False))
    ).all():
        record.revoke()
    db.commit()


def build_user_me(user: User) -> UserMe:
    """组装 `GET /auth/me` 响应体（严格不含密码哈希）。"""
    profile = user.profile
    return UserMe(
        id=user.id,
        email=user.email,
        username=user.username,
        role=user.role,
        status=user.status,
        is_verified=bool(user.is_verified),
        xp=int(user.xp or 0),
        level=int(user.level or 1),
        streak_days=int(user.streak_days or 0),
        max_streak_days=int(user.max_streak_days or 0),
        login_count=int(user.login_count or 0),
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        profile=(
            ProfileBrief(
                display_name=profile.display_name,
                avatar_url=profile.avatar_url,
                bio=profile.bio,
                theme_preference=profile.theme_preference,
                ai_mode=profile.ai_mode,
                learning_mode=profile.learning_mode,
            )
            if profile is not None
            else None
        ),
    )
