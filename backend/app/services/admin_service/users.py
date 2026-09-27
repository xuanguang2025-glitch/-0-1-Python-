"""管理端服务 · 用户管理。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError, ErrorCode
from app.core.pagination import PageParams
from app.core.security import hash_password, validate_password_strength, validate_username
from app.models.user import Profile, User

from .common import audit, get_or_404, apply_fields, snapshot


def list_users(
    db: Session,
    params: PageParams,
    *,
    q: str | None = None,
    role: str | None = None,
    status: str | None = None,
) -> tuple[list[User], int]:
    """用户列表（搜索 / 筛选 / 分页）。"""
    conditions: list[Any] = [User.deleted_at.is_(None)]
    if q:
        like = f"%{q.strip()}%"
        conditions.append(User.email.ilike(like) | User.username.ilike(like))
    if role:
        conditions.append(User.role == role)
    if status:
        conditions.append(User.status == status)
    total = int(db.scalar(select(func.count()).select_from(User).where(*conditions)) or 0)
    rows = list(
        db.scalars(
            select(User)
            .where(*conditions)
            .order_by(User.created_at.desc())
            .offset(params.offset)
            .limit(params.limit)
        ).all()
    )
    return rows, total


def create_user(db: Session, actor: User, payload: dict[str, Any], meta: dict[str, Any]) -> User:
    """新建用户（含资料）。"""
    email = str(payload["email"]).strip().lower()
    if db.scalars(select(User).where(User.email == email)).one_or_none() is not None:
        raise AppError(code=ErrorCode.EMAIL_EXISTS, message="邮箱已存在", status_code=409)
    validate_username(str(payload["username"]))
    validate_password_strength(str(payload["password"]))
    user = User(
        email=email,
        username=str(payload["username"]),
        hashed_password=hash_password(str(payload["password"])),
        role=str(payload.get("role") or "user"),
        is_verified=True,
    )
    db.add(user)
    db.flush()
    db.add(Profile(user_id=user.id, display_name=str(payload.get("display_name") or user.username)))
    audit(db, actor, "admin.user.create", "user", user.id, after={"email": email}, meta=meta)
    db.commit()
    db.refresh(user)
    return user


def update_user(
    db: Session, actor: User, user_id: str, payload: dict[str, Any], meta: dict[str, Any]
) -> User:
    """更新用户角色 / 状态 / 资料。"""
    user = get_or_404(db, User, user_id, ErrorCode.USER_NOT_FOUND, "用户不存在")
    before = snapshot(user, ["role", "status", "is_verified"])
    apply_fields(user, {k: v for k, v in payload.items() if k in ("role", "status", "is_verified")})
    display_name = payload.get("display_name")
    if display_name is not None:
        profile = db.scalars(select(Profile).where(Profile.user_id == user.id)).one_or_none()
        if profile is None:
            profile = Profile(user_id=user.id)
            db.add(profile)
        profile.display_name = display_name
    audit(
        db, actor, "admin.user.update", "user", user.id,
        before=before, after=snapshot(user, ["role", "status", "is_verified"]), meta=meta,
    )
    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, actor: User, user_id: str, meta: dict[str, Any]) -> None:
    """软删除用户。"""
    user = get_or_404(db, User, user_id, ErrorCode.USER_NOT_FOUND, "用户不存在")
    user.soft_delete()
    user.status = "deleted"
    audit(
        db, actor, "admin.user.delete", "user", user.id,
        before={"status": "active"}, after={"status": "deleted"}, meta=meta,
    )
    db.commit()


def reset_password(
    db: Session, actor: User, user_id: str, new_password: str, meta: dict[str, Any]
) -> None:
    """重置用户密码。"""
    validate_password_strength(new_password)
    user = get_or_404(db, User, user_id, ErrorCode.USER_NOT_FOUND, "用户不存在")
    user.hashed_password = hash_password(new_password)
    audit(db, actor, "admin.user.reset_password", "user", user.id, after={"password": "***"}, meta=meta)
    db.commit()
