"""管理端服务 · AI 配置 / 模型。

约定：API Key 只写不读，读取一律脱敏为 `sk-****last4`。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ErrorCode
from app.models.ai import AIModelConfig
from app.models.system import SystemSetting
from app.models.user import User

from .common import (
    AI_KEY_TEMPLATE,
    GLOBAL_AI_KEY,
    audit,
    apply_fields,
    get_or_404,
    mask_secret,
    read_setting,
    write_setting,
)


def _model_key(model_id: str) -> str:
    """模型密钥在 system_settings 中的存储键。"""
    return AI_KEY_TEMPLATE.format(model_id=model_id)


def get_ai_config(db: Session) -> dict[str, Any]:
    """`GET /admin/ai-config`：全局 AI 配置（密钥脱敏）。"""
    from app.core.config import get_settings

    settings = get_settings()
    raw_key = read_setting(db, GLOBAL_AI_KEY)
    stored = raw_key.get("value") if isinstance(raw_key, dict) else raw_key
    return {
        "provider": settings.ai_provider,
        "model": settings.ai_model,
        "base_url": settings.ai_base_url,
        "temperature": settings.ai_temperature,
        "max_tokens": settings.ai_max_tokens,
        "offline": settings.ai_offline,
        "rate_limit_per_hour": settings.ai_rate_limit_per_hour,
        "degraded": not settings.ai_enabled,
        "api_key_configured": bool(stored) or settings.ai_enabled,
        "api_key_masked": mask_secret(stored) if stored else None,
        "prompt_overrides": read_setting(db, "ai.prompt.overrides") or {},
    }


def update_ai_config(
    db: Session, actor: User, payload: dict[str, Any], meta: dict[str, Any]
) -> dict[str, Any]:
    """`PUT /admin/ai-config`：更新全局 AI 配置（`api_key` 只写）。"""
    api_key = payload.pop("api_key", None)
    if api_key:
        write_setting(db, GLOBAL_AI_KEY, {"value": api_key}, actor=actor, description="全局 AI 密钥（只写）")
    if payload.get("prompt_overrides") is not None:
        write_setting(db, "ai.prompt.overrides", payload["prompt_overrides"], actor=actor)
    changed = {k: v for k, v in payload.items() if v is not None and k != "prompt_overrides"}
    if changed:
        write_setting(db, "ai.config", changed, actor=actor, description="AI 运行参数覆盖")
    audit(
        db, actor, "admin.ai_config.update", "system_setting", GLOBAL_AI_KEY,
        after={"changed": list(changed.keys()), "api_key": "***" if api_key else None}, meta=meta,
    )
    db.commit()
    return get_ai_config(db)


def list_models(db: Session) -> list[AIModelConfig]:
    """模型配置列表。"""
    return list(db.scalars(select(AIModelConfig).order_by(AIModelConfig.created_at.desc())).all())


def model_out(db: Session, model: AIModelConfig) -> dict[str, Any]:
    """构造模型配置输出（密钥脱敏）。"""
    raw = read_setting(db, _model_key(model.id))
    stored = raw.get("value") if isinstance(raw, dict) else raw
    data = {c.key: getattr(model, c.key) for c in model.__table__.columns}
    data["api_key_masked"] = mask_secret(stored) if stored else None
    return data


def list_models_out(db: Session) -> list[dict[str, Any]]:
    """模型配置列表输出（密钥脱敏）。"""
    return [model_out(db, model) for model in list_models(db)]


def serialize_model(db: Session, model: AIModelConfig) -> dict[str, Any]:
    """单个模型配置输出（密钥脱敏）。"""
    return model_out(db, model)


def create_model(db: Session, actor: User, payload: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    """新建模型配置（`api_key` 只写）。"""
    api_key = payload.pop("api_key", None)
    model = AIModelConfig(**payload)
    if model.is_default:
        _clear_default_models(db, exclude_id=None)
    db.add(model)
    db.flush()
    if api_key:
        write_setting(db, _model_key(model.id), {"value": api_key}, actor=actor, description=f"模型 {model.name} 密钥")
    audit(db, actor, "admin.model.create", "ai_model_config", model.id, after={"name": model.name}, meta=meta)
    db.commit()
    db.refresh(model)
    return model_out(db, model)


def update_model(
    db: Session, actor: User, model_id: str, payload: dict[str, Any], meta: dict[str, Any]
) -> dict[str, Any]:
    """更新模型配置。"""
    api_key = payload.pop("api_key", None)
    model = get_or_404(db, AIModelConfig, model_id, ErrorCode.NOT_FOUND, "模型配置不存在")
    if payload.get("is_default"):
        _clear_default_models(db, exclude_id=model.id)
    apply_fields(model, payload)
    if api_key:
        write_setting(db, _model_key(model.id), {"value": api_key}, actor=actor)
    audit(db, actor, "admin.model.update", "ai_model_config", model.id, after={"name": model.name}, meta=meta)
    db.commit()
    db.refresh(model)
    return model_out(db, model)


def delete_model(db: Session, actor: User, model_id: str, meta: dict[str, Any]) -> None:
    """删除模型配置（连同密钥）。"""
    model = get_or_404(db, AIModelConfig, model_id, ErrorCode.NOT_FOUND, "模型配置不存在")
    row = db.scalars(select(SystemSetting).where(SystemSetting.key == _model_key(model_id))).one_or_none()
    if row is not None:
        db.delete(row)
    db.delete(model)
    audit(db, actor, "admin.model.delete", "ai_model_config", model_id, meta=meta)
    db.commit()


def _clear_default_models(db: Session, *, exclude_id: str | None) -> None:
    """把其它模型的默认标记清除（保证全局唯一默认）。"""
    for item in db.scalars(select(AIModelConfig).where(AIModelConfig.is_default.is_(True))).all():
        if item.id != exclude_id:
            item.is_default = False


def test_model(db: Session, actor: User, model_id: str, meta: dict[str, Any]) -> dict[str, Any]:
    """`POST /admin/models/{id}/test`：连通性测试（**不回显 key**）。"""
    from app.core.config import get_settings

    model = get_or_404(db, AIModelConfig, model_id, ErrorCode.NOT_FOUND, "模型配置不存在")
    raw = read_setting(db, _model_key(model.id))
    stored = raw.get("value") if isinstance(raw, dict) else raw
    settings = get_settings()
    key_ready = bool(stored) or settings.ai_enabled
    audit(db, actor, "admin.model.test", "ai_model_config", model.id, after={"ok": key_ready}, meta=meta)
    db.commit()
    if not key_ready:
        return {"ok": False, "latency_ms": 0, "error": "未配置密钥，使用本地规则助手"}
    # 无外网 / 无 SDK 时，仅做配置校验，不真正发起请求
    return {"ok": True, "latency_ms": 0, "error": None}
