"""Code Review 测试：九维度静态审查命中已知缺陷 + 结构化评审服务（全离线）。"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.services.ai.base import ChatMessage
from app.services.ai.review import CodeReviewService, analyze_error_report, extract_json_object
from app.services.ai.rule_based import RuleBasedProvider
from app.services.ai.static_analysis import review_code

# 含三类已知缺陷：可变默认参数 + 裸 except + 未使用导入
BAD_CODE = """
import os
import json


def summarize(items=[]):
    try:
        total = 0
        for i in range(len(items)):
            total += items[i]
    except:
        pass
    if items == None:
        return 0
    return total
""".strip("\n")


def _titles(result: dict) -> str:
    """把问题标题拼成字符串，便于包含断言。"""
    return " | ".join(issue["title"] for issue in result["issues"])


def test_static_review_detects_known_defects() -> None:
    """离线静态审查命中：可变默认参数 / 裸 except / == None / 未使用导入。"""
    result = review_code(BAD_CODE)
    text = " | ".join(issue.title for issue in result.issues)
    assert "可变默认参数" in text
    assert "裸 except" in text
    assert "与 None 用等值比较" in text
    assert "未使用的导入" in text
    assert "range(len(...))" in text
    assert result.score < 100
    assert result.improved_code  # 生成了改进后代码


def test_static_review_clean_code_scores_high() -> None:
    """规范代码评分高、问题少。"""
    result = review_code("def add(a, b):\n    return a + b\n")
    assert result.score >= 90


def test_review_service_offline_structured_output() -> None:
    """CodeReviewService（离线 Provider）返回结构化 ReviewOut，degraded=True。"""
    service = CodeReviewService(provider=RuleBasedProvider())
    request = SimpleNamespace(code=BAD_CODE, focus=None, language="python")
    result = asyncio.run(service.review(request))
    assert result["degraded"] is True
    assert isinstance(result["score"], int)
    assert isinstance(result["issues"], list) and result["issues"]
    assert "可变默认参数" in _titles(result)
    for issue in result["issues"]:
        assert issue["severity"] in {"error", "warning", "info"}
        assert issue["title"]


def test_review_service_rejects_empty_code() -> None:
    """空代码 → BAD_REQUEST。"""
    from app.core.errors import AppError, ErrorCode

    service = CodeReviewService(provider=RuleBasedProvider())
    request = SimpleNamespace(code="   ", focus=None, language="python")
    try:
        asyncio.run(service.review(request))
    except AppError as exc:
        assert exc.code == ErrorCode.BAD_REQUEST
    else:  # pragma: no cover
        raise AssertionError("空代码应抛 BAD_REQUEST")


def test_extract_json_object_with_fence() -> None:
    """从 Markdown 围栏中提取 JSON。"""
    text = '```json\n{"score": 80, "issues": []}\n```'
    data = extract_json_object(text)
    assert data == {"score": 80, "issues": []}


def test_bad_json_falls_back_to_offline() -> None:
    """模型返回非 JSON 时回落本地静态审查（永不 5xx）。"""

    class BadProvider(RuleBasedProvider):
        """返回不可解析文本的假 Provider。"""

        async def chat(self, messages: list[ChatMessage], **opts):  # type: ignore[override]
            response = await super().chat(messages, **opts)
            response.content = "这不是 JSON"
            return response

    service = CodeReviewService(provider=BadProvider())
    request = SimpleNamespace(code=BAD_CODE, focus=None, language="python")
    result = asyncio.run(service.review(request))
    assert result["degraded"] is True
    assert result["issues"]


def test_analyze_error_report_offline() -> None:
    """报错分析（离线）返回结构化结果。"""
    result = asyncio.run(
        analyze_error_report(
            RuleBasedProvider(),
            code="nums = [1, 2]\nprint(nums[5])",
            error_message="IndexError: list index out of range",
            traceback_text='Traceback (most recent call last):\n  File "main.py", line 5, in <module>\n    print(nums[5])\nIndexError: list index out of range',
        )
    )
    assert result["error_type"] == "IndexError"
    assert result["related_topics"]
    assert result["degraded"] is True
