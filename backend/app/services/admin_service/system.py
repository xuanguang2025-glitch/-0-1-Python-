"""管理端服务 · 日志 / 设置 / 维护。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.pagination import PageParams
from app.models.ai import AIUsageLog
from app.models.learning import LearningSession
from app.models.submission import Submission
from app.models.system import AuditLog, SystemSetting
from app.models.user import User

from .common import ACCEPTED, audit, is_sensitive, mask_secret, write_setting


def list_audit_logs(
    db: Session,
    params: PageParams,
    *,
    action: str | None = None,
    actor_id: str | None = None,
) -> tuple[list[AuditLog], int]:
    """审计日志分页。"""
    conditions: list[Any] = []
    if action:
        conditions.append(AuditLog.action == action)
    if actor_id:
        conditions.append(AuditLog.actor_id == actor_id)
    total = int(db.scalar(select(func.count()).select_from(AuditLog).where(*conditions)) or 0)
    rows = list(
        db.scalars(
            select(AuditLog)
            .where(*conditions)
            .order_by(AuditLog.created_at.desc())
            .offset(params.offset)
            .limit(params.limit)
        ).all()
    )
    return rows, total


def list_ai_usage(db: Session, params: PageParams) -> tuple[list[AIUsageLog], int]:
    """AI 用量日志分页。"""
    total = int(db.scalar(select(func.count()).select_from(AIUsageLog)) or 0)
    rows = list(
        db.scalars(
            select(AIUsageLog).order_by(AIUsageLog.created_at.desc()).offset(params.offset).limit(params.limit)
        ).all()
    )
    return rows, total


def list_error_logs(db: Session, limit: int = 50) -> list[dict[str, Any]]:
    """错误日志（按状态聚合）。"""
    rows = db.execute(
        select(Submission.status, func.count(), func.max(Submission.created_at))
        .where(Submission.status != ACCEPTED)
        .group_by(Submission.status)
        .order_by(func.count().desc())
        .limit(limit)
    ).all()
    return [
        {"code": str(row[0]), "count": int(row[1] or 0), "last_at": row[2], "sample_message": None}
        for row in rows
    ]


def session_overview(db: Session) -> dict[str, Any]:
    """学习会话概览（总量 / 活跃人数 / 按类型聚合）。"""
    total_sessions = int(db.scalar(select(func.count()).select_from(LearningSession)) or 0)
    total_seconds = int(db.scalar(select(func.coalesce(func.sum(LearningSession.duration_seconds), 0))) or 0)
    active_users = int(db.scalar(select(func.count(func.distinct(LearningSession.user_id)))) or 0)
    rows = db.execute(
        select(
            LearningSession.session_type,
            func.count(),
            func.coalesce(func.sum(LearningSession.duration_seconds), 0),
        ).group_by(LearningSession.session_type)
    ).all()
    return {
        "total_sessions": total_sessions,
        "total_minutes": total_seconds // 60,
        "active_users": active_users,
        "by_type": [
            {"session_type": str(r[0]), "sessions": int(r[1] or 0), "minutes": int(r[2] or 0) // 60}
            for r in rows
        ],
    }


def mask_setting_value(key: str, value: Any) -> Any:
    """对敏感系统配置值脱敏（递归处理字典中的字符串）。"""
    if isinstance(value, dict):
        return {k: (mask_secret(v) if isinstance(v, str) and v else v) for k, v in value.items()}
    if isinstance(value, str):
        return mask_secret(value)
    return value


def list_settings(db: Session) -> list[dict[str, Any]]:
    """系统设置列表（敏感项脱敏）。"""
    rows = list(db.scalars(select(SystemSetting).order_by(SystemSetting.key.asc())).all())
    result: list[dict[str, Any]] = []
    for row in rows:
        sensitive = is_sensitive(row.key)
        value = mask_setting_value(row.key, row.value_json) if sensitive else row.value_json
        result.append(
            {
                "id": row.id,
                "key": row.key,
                "value_json": value,
                "description": row.description,
                "updated_at": row.updated_at,
                "is_sensitive": sensitive,
            }
        )
    return result


def update_setting(
    db: Session, actor: User, key: str, payload: dict[str, Any], meta: dict[str, Any]
) -> dict[str, Any]:
    """读写系统设置（敏感项写入后读取仍脱敏）。"""
    row = write_setting(db, key, payload.get("value_json"), actor=actor, description=payload.get("description"))
    sensitive = is_sensitive(key)
    audit(
        db, actor, "admin.setting.update", "system_setting", key,
        after={"key": key, "value": "***" if sensitive else row.value_json}, meta=meta,
    )
    db.commit()
    return {
        "id": row.id,
        "key": row.key,
        "value_json": mask_setting_value(key, row.value_json) if sensitive else row.value_json,
        "description": row.description,
        "updated_at": row.updated_at,
        "is_sensitive": sensitive,
    }


def enqueue_rejudge(
    db: Session, actor: User, problem_id: str | None, limit: int, meta: dict[str, Any]
) -> dict[str, Any]:
    """批量重判（入队）。本机无队列时记录审计并返回待处理数量。"""
    stmt = select(func.count()).select_from(Submission)
    if problem_id:
        stmt = stmt.where(Submission.problem_id == problem_id)
    count = int(db.scalar(stmt) or 0)
    queued = min(count, max(1, int(limit or 20)))
    audit(db, actor, "admin.maintenance.rejudge", "submission", problem_id, after={"queued": queued}, meta=meta)
    db.commit()
    return {"queued": queued, "problem_id": problem_id}
