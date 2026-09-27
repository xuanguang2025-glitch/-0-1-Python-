"""管理端服务 · 公共工具与常量。

集中放置跨子模块复用的常量、脱敏工具、审计写入与通用 CRUD 辅助函数，
避免各子模块重复实现。
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.enums import SubmissionStatus
from app.models.system import AuditLog, SystemSetting
from app.models.user import User

logger = logging.getLogger("pythonlab.admin")

# 敏感键提示词：命中即视为需要脱敏的配置项
SENSITIVE_HINTS: tuple[str, ...] = ("key", "secret", "password", "token")
# 提交状态：通过
ACCEPTED: str = SubmissionStatus.ACCEPTED.value
# 模型密钥在 system_settings 中的存储键模板
AI_KEY_TEMPLATE: str = "ai.model.{model_id}.api_key"
# 全局 AI 密钥在 system_settings 中的存储键
GLOBAL_AI_KEY: str = "ai.api_key"


def mask_secret(value: str | None) -> str | None:
    """把密钥脱敏为 `sk-****last4` 形式（明文永不回传）。"""
    if not value:
        return None
    text = str(value)
    if len(text) <= 4:
        return "****"
    prefix = text[:3] if text.startswith("sk-") else text[:2]
    return f"{prefix}****{text[-4:]}"


def is_sensitive(key: str) -> bool:
    """判断配置键是否为敏感项。"""
    lowered = key.lower()
    return any(hint in lowered for hint in SENSITIVE_HINTS)


def audit(
    db: Session,
    actor: User | None,
    action: str,
    target_type: str,
    target_id: str | None,
    *,
    before: Any = None,
    after: Any = None,
    meta: dict[str, Any] | None = None,
) -> None:
    """写入审计日志（不含 commit，由调用方统一提交）。"""
    db.add(
        AuditLog(
            actor_id=actor.id if actor else None,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail_json={"before": before, "after": after},
            ip=(meta or {}).get("ip"),
            user_agent=(meta or {}).get("user_agent"),
        )
    )


def get_or_404(db: Session, model: Any, obj_id: str, code: str, message: str) -> Any:
    """按 id 获取实体，不存在抛 404。"""
    obj = db.get(model, obj_id)
    if obj is None:
        raise AppError(code=code, message=message, status_code=404)
    return obj


def snapshot(obj: Any, fields: list[str]) -> dict[str, Any]:
    """提取实体部分字段快照（用于审计 before/after）。"""
    return {name: getattr(obj, name, None) for name in fields}


def apply_fields(obj: Any, data: dict[str, Any]) -> None:
    """把非 None 的字段写入实体（白名单由调用方通过 data 控制）。"""
    for key, value in data.items():
        if value is not None and hasattr(obj, key):
            setattr(obj, key, value)


def read_setting(db: Session, key: str) -> Any:
    """读取系统配置值（缺失返回 None）。"""
    row = db.scalars(select(SystemSetting).where(SystemSetting.key == key)).one_or_none()
    return row.value_json if row is not None else None


def write_setting(
    db: Session,
    key: str,
    value: Any,
    *,
    actor: User | None,
    description: str | None = None,
) -> SystemSetting:
    """写入系统配置（不存在则创建，不 commit）。"""
    row = db.scalars(select(SystemSetting).where(SystemSetting.key == key)).one_or_none()
    if row is None:
        row = SystemSetting(key=key, value_json=value, description=description)
        db.add(row)
    else:
        row.value_json = value
        if description:
            row.description = description
    row.updated_by = actor.id if actor else None
    db.flush()
    return row
