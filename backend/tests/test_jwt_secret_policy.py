"""JWT 密钥策略回归测试（P0：默认密钥可伪造管理员身份）。

`jwt_secret_key` 默认 `change-me`，而 HS256 是**对称签名** —— 拿到密钥就能离线
签出 `role=superadmin` 的合法 token（QA 已实测 `GET /api/admin/users` 返回全部用户）。

锁定两条规则：
- 生产环境（`app_env=production`）且密钥为默认值 / 占位符 / 长度 < 32 → **拒绝启动**；
- 开发与测试环境不静默使用弱默认值 → 自动换成随机强密钥并告警。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import (
    MIN_SECRET_LENGTH,
    Settings,
    enforce_secret_policy,
    generate_strong_secret,
    is_weak_secret,
)
from app.main import _startup_self_check
from app.sandbox.runner import reset_runner


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        "change-me",
        "change-me-please",
        "change-me-in-production",
        "secret",
        "short-key-123",
        "your-jwt-secret",
    ],
)
def test_is_weak_secret_detects_placeholders(value: str) -> None:
    """默认值 / 占位符 / 过短都算弱密钥。"""
    assert is_weak_secret(value) is True


def test_is_weak_secret_accepts_strong_value() -> None:
    """随机强密钥不应被误判为弱密钥。"""
    strong = generate_strong_secret()
    assert is_weak_secret(strong) is False
    assert len(strong) >= MIN_SECRET_LENGTH


def test_production_rejects_default_jwt_secret() -> None:
    """生产环境 + 默认 JWT 密钥 → 抛异常，且报错含修复指引。"""
    settings = Settings(
        app_env="production",
        jwt_secret_key="change-me",
        secret_key="change-me-in-production",
        database_url="sqlite:///:memory:",
    )
    assert settings.is_production is True
    with pytest.raises(RuntimeError) as excinfo:
        enforce_secret_policy(settings)
    message = str(excinfo.value)
    assert "jwt_secret_key" in message
    assert "JWT_SECRET_KEY" in message  # 必须告诉运维去设哪个变量


def test_production_rejects_short_secret() -> None:
    """长度不足 32 字符的密钥在生产同样被拒（哪怕不是默认值）。"""
    settings = Settings(
        app_env="production",
        jwt_secret_key="a" * 31,
        secret_key=generate_strong_secret(),
        database_url="sqlite:///:memory:",
    )
    with pytest.raises(RuntimeError):
        enforce_secret_policy(settings)


def test_production_accepts_strong_secrets() -> None:
    """生产环境配置了强密钥 → 放行。"""
    strong = generate_strong_secret()
    settings = Settings(
        app_env="production",
        jwt_secret_key=strong,
        secret_key=strong,
        database_url="sqlite:///:memory:",
    )
    assert enforce_secret_policy(settings) == []


@pytest.mark.parametrize("app_env", ["development", "testing"])
def test_non_production_replaces_weak_secret_with_random(app_env: str) -> None:
    """开发/测试环境不静默使用弱默认值：自动换成随机强密钥。"""
    settings = Settings(
        app_env=app_env,
        jwt_secret_key="change-me",
        secret_key="change-me-in-production",
        database_url="sqlite:///:memory:",
    )
    replaced = enforce_secret_policy(settings)
    assert set(replaced) == {"jwt_secret_key", "secret_key"}
    assert settings.jwt_secret_key != "change-me"
    assert is_weak_secret(settings.jwt_secret_key) is False
    assert is_weak_secret(settings.secret_key) is False


def test_generated_secret_differs_between_calls() -> None:
    """两次生成的密钥必须不同（不能是固定弱值）。"""
    assert generate_strong_secret() != generate_strong_secret()


def test_startup_self_check_blocks_production_with_default_secret() -> None:
    """真实启动自检入口：生产 + 默认密钥必须抛异常（QA 复现路径）。

    抛异常发生在任何数据库访问之前，因此无需隔离数据库。
    """
    settings = Settings(
        app_env="production",
        jwt_secret_key="change-me",
        secret_key="change-me-in-production",
        database_url="sqlite:///:memory:",
        seed_on_startup=False,
        sandbox_mode="stub",
    )
    with pytest.raises(RuntimeError) as excinfo:
        _startup_self_check(settings)
    assert "JWT_SECRET_KEY" in str(excinfo.value)


def test_startup_self_check_passes_production_with_strong_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """配置了强密钥时自检不阻断。

    必须隔离数据库：`_startup_self_check` 内部的 `db_ping()` 走全局
    `get_settings()` 构造的引擎（即 `data/pythonlab.db`），而 SQLite 连接会执行
    `PRAGMA journal_mode=WAL` —— 那是一次**真实写库头**操作，会污染真实种子库。
    这里把 db 探测桩掉，保证测试绝不触碰真实库。
    """
    monkeypatch.setattr("app.db.session.ping", lambda: True)
    monkeypatch.setattr("app.db.session.table_names", lambda: ["users"])
    strong = generate_strong_secret()
    settings = Settings(
        app_env="production",
        jwt_secret_key=strong,
        secret_key=strong,
        database_url="sqlite:///:memory:",
        seed_on_startup=False,
        sandbox_mode="stub",
    )
    try:
        _startup_self_check(settings)
    finally:
        reset_runner()
    assert settings.jwt_secret_key == strong


def test_security_doc_mentions_jwt_secret_requirement() -> None:
    """`docs/SECURITY.md`（安全文档正本）必须写明生产必须设置 JWT_SECRET_KEY。"""
    doc = Path(__file__).resolve().parents[2] / "docs" / "SECURITY.md"
    text = doc.read_text(encoding="utf-8")
    assert "JWT_SECRET_KEY" in text
