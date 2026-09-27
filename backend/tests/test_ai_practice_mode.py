"""练习模式约束测试：后端必须真正禁止完整答案（提示词 + 后置裁剪）。"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.core.errors import AppError, ErrorCode
from app.services.ai import repository
from app.services.ai.base import ChatMessage
from app.services.ai.rule_based import RuleBasedProvider
from app.services.ai.tutor import TutorService, enforce_practice_constraint


# ---------------------------------------------------------------------------
# 纯函数：后置约束
# ---------------------------------------------------------------------------


def test_practice_mode_blocks_full_level() -> None:
    """练习模式请求 full/explain → 抛 AI_FULL_ANSWER_DISABLED。"""
    with pytest.raises(AppError) as exc:
        enforce_practice_constraint("完整实现……", practice_mode=True, level="full")
    assert exc.value.code == ErrorCode.AI_FULL_ANSWER_DISABLED
    assert exc.value.status_code == 403


def test_practice_mode_allows_when_configured() -> None:
    """显式放开完整答案时不拦截。"""
    content = "完整实现……"
    assert enforce_practice_constraint(content, practice_mode=True, level="full", allow_full_answer=True) == content


def test_non_practice_never_blocks() -> None:
    """非练习模式：任何层级原样返回。"""
    content = "```python\nprint(1)\n```"
    assert enforce_practice_constraint(content, practice_mode=False, level="full") == content


def test_practice_mode_strips_solution_sections() -> None:
    """练习模式删除被「完整答案」标题引导的代码块。"""
    content = "先想想思路。\n\n#### 完整答案\n```python\nprint(42)\n```\n再试试看。"
    result = enforce_practice_constraint(content, practice_mode=True, level="hint")
    assert "print(42)" not in result
    assert "先想想思路" in result


def test_practice_mode_empty_after_strip_gets_notice() -> None:
    """整段都是完整答案时给出提示文案，绝不留空。"""
    content = "完整答案\n```python\nprint(42)\n```"
    result = enforce_practice_constraint(content, practice_mode=True, level="hint")
    assert "print(42)" not in result
    assert result.strip() != ""


# ---------------------------------------------------------------------------
# Provider：hint 层级不产生完整代码块
# ---------------------------------------------------------------------------


def test_rule_based_hint_has_no_code_block() -> None:
    """离线 hint 输出不含围栏代码块（杜绝完整答案）。"""
    provider = RuleBasedProvider()
    response = asyncio.run(
        provider.chat([ChatMessage(role="user", content="怎么写循环打印 1 到 10")], task="tutor", level="hint")
    )
    assert "```" not in response.content
    enforced = enforce_practice_constraint(response.content, practice_mode=True, level="hint")
    assert "```" not in enforced


def test_rule_based_partial_uses_todo_placeholder() -> None:
    """离线 partial 输出仅给带 TODO 的骨架，不是完整答案。"""
    provider = RuleBasedProvider()
    response = asyncio.run(
        provider.chat([ChatMessage(role="user", content="帮我读入两个整数求和")], task="tutor", level="partial")
    )
    assert "TODO" in response.content


# ---------------------------------------------------------------------------
# 编排层：TutorService 端到端（隔离 DB）
# ---------------------------------------------------------------------------


def _stub_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    """把会话持久化替换为无副作用存根。"""
    fake_conversation = SimpleNamespace(
        id="conv-1",
        rename_from_first_message=lambda *_: None,
        count_message=lambda **_: None,
    )
    monkeypatch.setattr(repository, "create_conversation", lambda *a, **k: fake_conversation)
    monkeypatch.setattr(repository, "append_message", lambda *a, **k: SimpleNamespace(id="msg-1"))
    monkeypatch.setattr(repository, "recent_history", lambda *a, **k: [])
    monkeypatch.setattr(repository, "write_usage_log", lambda *a, **k: None)


def _request(**over) -> SimpleNamespace:
    base = dict(
        conversation_id=None,
        message="怎么写循环打印 1 到 10",
        mode="standard",
        scene="tutor",
        level="hint",
        practice_mode=True,
        context=None,
    )
    base.update(over)
    return SimpleNamespace(**base)


def test_tutor_chat_practice_full_answer_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    """编排层：练习模式 + level=full → 403 AI_FULL_ANSWER_DISABLED。"""
    _stub_repository(monkeypatch)
    service = TutorService(provider=RuleBasedProvider())
    with pytest.raises(AppError) as exc:
        asyncio.run(service.chat(db=None, user=SimpleNamespace(id="u1"), request=_request(level="full"), cache=None))
    assert exc.value.code == ErrorCode.AI_FULL_ANSWER_DISABLED


def test_tutor_chat_practice_hint_returns_no_full_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    """编排层：练习模式 + hint → 返回内容不含围栏代码块。"""
    _stub_repository(monkeypatch)
    service = TutorService(provider=RuleBasedProvider())
    result = asyncio.run(
        service.chat(db=None, user=SimpleNamespace(id="u1"), request=_request(level="hint"), cache=None)
    )
    assert result["degraded"] is True
    assert "```" not in result["content_md"]
    assert result["kind"] == "hint"
    assert result["suggestions"]
