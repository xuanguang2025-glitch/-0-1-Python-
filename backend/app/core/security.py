"""密码哈希与 JWT 签发 / 校验。

要点：
1. 密码绝不明文：bcrypt（可切换 argon2）加盐哈希，永不出库到任何 Schema；
2. Access Token 15 分钟、Refresh Token 30 天，载荷结构见 docs/ARCHITECTURE.md §8.4；
3. 令牌密钥一律从环境变量读取（`JWT_SECRET_KEY`），代码内无硬编码；
4. Refresh Token 在库中只保存 sha256 摘要，登出时按 `jti` 吊销。
"""

from __future__ import annotations

import hashlib
import logging
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings
from app.core.errors import AppError, ErrorCode

logger = logging.getLogger("pythonlab.security")

# bcrypt 会对超过 72 字节的密码做截断，因此注册时限制最大长度
MAX_PASSWORD_BYTES: int = 72

_USERNAME_RE: re.Pattern[str] = re.compile(r"^[A-Za-z0-9_]{3,20}$")
_EMAIL_RE: re.Pattern[str] = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _build_context() -> CryptContext | None:
    """按配置构建 passlib 密码哈希上下文；不可用时返回 None（回退原生 bcrypt）。"""
    scheme = get_settings().pwd_hash_scheme.lower()
    schemes = ["argon2", "bcrypt"] if scheme == "argon2" else ["bcrypt"]
    try:
        context = CryptContext(schemes=schemes, deprecated="auto")
        # 自检一次：passlib 1.7.4 与 bcrypt>=4.1 不兼容时会在此抛错
        probe = context.hash("pythonlab-probe")
        if not context.verify("pythonlab-probe", probe):
            return None
        return context
    except Exception as exc:  # noqa: BLE001 - 任何后端异常都降级到原生实现
        logger.warning("passlib 哈希后端不可用，回退到 bcrypt 原生实现: %s", exc)
        return None


def _hash_with_bcrypt(plain_password: str, rounds: int = 12) -> str:
    """使用 `bcrypt` 原生 API 生成哈希（passlib 不可用时的兜底实现）。"""
    import bcrypt

    salt = bcrypt.gensalt(rounds=rounds)
    return bcrypt.hashpw(_safe_password(plain_password).encode("utf-8"), salt).decode("utf-8")


def _verify_with_bcrypt(plain_password: str, hashed_password: str) -> bool:
    """使用 `bcrypt` 原生 API 校验哈希。"""
    import bcrypt

    try:
        return bcrypt.checkpw(_safe_password(plain_password).encode("utf-8"), hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        return False


_PWD_CONTEXT: CryptContext | None = _build_context()


def hash_password(plain_password: str) -> str:
    """对明文密码做加盐哈希，返回可安全入库的字符串。"""
    if _PWD_CONTEXT is None:
        return _hash_with_bcrypt(plain_password)
    return _PWD_CONTEXT.hash(_safe_password(plain_password))


def verify_password(plain_password: str, hashed_password: str | None) -> bool:
    """校验明文密码与库中哈希是否匹配（哈希为空一律失败）。"""
    if not hashed_password:
        return False
    if _PWD_CONTEXT is None:
        return _verify_with_bcrypt(plain_password, hashed_password)
    try:
        return _PWD_CONTEXT.verify(_safe_password(plain_password), hashed_password)
    except ValueError:
        # 历史脏数据或算法不匹配，退回原生校验再试一次
        return _verify_with_bcrypt(plain_password, hashed_password)


def needs_rehash(hashed_password: str) -> bool:
    """判断已有哈希是否需要按当前策略重新计算（算法升级时用）。"""
    if _PWD_CONTEXT is None:
        return not hashed_password.startswith("$2b$12$")
    try:
        return _PWD_CONTEXT.needs_update(hashed_password)
    except ValueError:
        return True


def _safe_password(plain_password: str) -> str:
    """把密码截断到 bcrypt 的安全长度，避免静默截断导致的不可预期行为。"""
    raw = plain_password.encode("utf-8")
    if len(raw) <= MAX_PASSWORD_BYTES:
        return plain_password
    return raw[:MAX_PASSWORD_BYTES].decode("utf-8", errors="ignore")


def validate_password_strength(password: str) -> None:
    """校验密码强度：长度 + 字母 + 数字，不满足抛 `WEAK_PASSWORD`。"""
    settings = get_settings()
    if len(password) < settings.pwd_min_length:
        raise AppError(
            code=ErrorCode.WEAK_PASSWORD,
            message=f"密码长度至少需要 {settings.pwd_min_length} 位",
            status_code=422,
        )
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise AppError(
            code=ErrorCode.WEAK_PASSWORD,
            message=f"密码长度不能超过 {MAX_PASSWORD_BYTES} 个字节",
            status_code=422,
        )
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise AppError(
            code=ErrorCode.WEAK_PASSWORD,
            message="密码需同时包含字母和数字",
            status_code=422,
        )


def validate_username(username: str) -> None:
    """校验用户名格式（3-20 位字母数字下划线）。"""
    if not _USERNAME_RE.match(username or ""):
        raise AppError(
            code=ErrorCode.VALIDATION_ERROR,
            message="用户名需为 3-20 位字母、数字或下划线",
            status_code=422,
            details=[{"loc": ["body", "username"], "msg": "invalid username", "type": "value_error"}],
        )


def validate_email(email: str) -> str:
    """校验邮箱格式并返回小写形式。"""
    value = (email or "").strip().lower()
    if not _EMAIL_RE.match(value):
        raise AppError(
            code=ErrorCode.VALIDATION_ERROR,
            message="邮箱格式不正确",
            status_code=422,
            details=[{"loc": ["body", "email"], "msg": "invalid email", "type": "value_error"}],
        )
    return value


def token_hash(raw_token: str) -> str:
    """计算令牌的 sha256 摘要（Refresh Token 入库只存摘要）。"""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def now_utc() -> datetime:
    """当前 UTC 时间（带时区）。"""
    return datetime.now(timezone.utc)


def _sign(payload: dict[str, Any]) -> str:
    """使用配置中的密钥与算法签发 JWT。"""
    settings = get_settings()
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(
    user_id: str,
    *,
    role: str,
    username: str,
    display_name: str = "",
) -> tuple[str, str, datetime]:
    """签发 Access Token，返回 `(token, jti, expires_at)`。"""
    settings = get_settings()
    now = now_utc()
    expires_at = now + timedelta(minutes=settings.access_token_ttl_min)
    jti = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "sub": user_id,
        "typ": "access",
        "role": role,
        "usr": username,
        "nick": display_name,
        "ver": 1,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": jti,
    }
    return _sign(payload), jti, expires_at


def create_refresh_token(user_id: str) -> tuple[str, str, datetime]:
    """签发 Refresh Token，返回 `(token, jti, expires_at)`。"""
    settings = get_settings()
    now = now_utc()
    expires_at = now + timedelta(days=settings.refresh_token_ttl_days)
    jti = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "sub": user_id,
        "typ": "refresh",
        "ver": 1,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": jti,
    }
    return _sign(payload), jti, expires_at


def decode_token(token: str, *, expected_type: str | None = None) -> dict[str, Any]:
    """解析并校验 JWT；失败时抛出带明确错误码的 `AppError`。

    Args:
        token: 原始 JWT 字符串。
        expected_type: 期望的令牌类型（`access` / `refresh`），为空则不校验类型。

    Returns:
        解码后的载荷字典。

    Raises:
        AppError: 令牌过期 / 无效 / 类型不符。
    """
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:  # type: ignore[attr-defined]
        raise AppError(code=ErrorCode.TOKEN_EXPIRED, message="令牌已过期，请刷新后重试", status_code=401) from exc
    except JWTError as exc:
        raise AppError(code=ErrorCode.UNAUTHORIZED, message="无效的令牌", status_code=401) from exc

    if expected_type and payload.get("typ") != expected_type:
        raise AppError(code=ErrorCode.UNAUTHORIZED, message="令牌类型不匹配", status_code=401)
    return payload


def random_token(length: int = 32) -> str:
    """生成密码学安全的随机串（用于导出令牌、邀请码等）。"""
    return secrets.token_urlsafe(length)
