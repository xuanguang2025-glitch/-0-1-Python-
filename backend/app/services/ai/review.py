"""Code Review 服务（九维度结构化评审 + 报错分析）。

九维度：正确性 / 可读性 / 复杂度 / 命名 / 重复代码 / 潜在 Bug / 安全问题 /
Python 风格(PEP 8) / 优化建议。

输出结构化 JSON：总体分析 + 问题列表（含行号、严重级别、说明、修复建议）
+ 改进后的代码 + 评分。远程模型返回的 JSON 解析失败会**重试一次**，仍失败则
回落本地静态审查（`static_analysis.review_code`）以纯结构化结果兜底。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import AppError, ErrorCode
from app.services.ai import repository
from app.services.ai.base import AIProvider, AIResponse, ChatMessage
from app.services.ai.error_analysis import analyze_error
from app.services.ai.prompts import (
    ERROR_ANALYSIS_SYSTEM,
    REVIEW_DIMENSIONS,
    REVIEW_SYSTEM,
    build_error_user_prompt,
    build_review_user_prompt,
)
from app.services.ai.registry import get_provider
from app.services.ai.static_analysis import review_code

logger = logging.getLogger("pythonlab.ai.review")

_JSON_FENCE_RE: re.Pattern[str] = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_VALID_SEVERITY = {"error", "warning", "info"}


def extract_json_object(text: str) -> dict[str, Any] | None:
    """从模型输出中提取首个 JSON 对象（容忍 Markdown 围栏与前后噪声）。"""
    raw = (text or "").strip()
    if not raw:
        return None
    fenced = _JSON_FENCE_RE.search(raw)
    candidates = [fenced.group(1)] if fenced else []
    candidates.append(raw)
    # 退一步：截取第一个 { 到最后一个 }
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end > start:
        candidates.append(raw[start : end + 1])
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict):
            return data
    return None


def _coerce_issues(raw_issues: Any) -> list[dict[str, Any]]:
    """把模型返回的 issues 归一化为 `ReviewIssue` 结构。"""
    issues: list[dict[str, Any]] = []
    if not isinstance(raw_issues, list):
        return issues
    for item in raw_issues:
        if not isinstance(item, dict):
            continue
        severity = str(item.get("severity") or "warning").lower()
        line = item.get("line")
        try:
            line = int(line) if line is not None else None
        except (TypeError, ValueError):
            line = None
        issues.append(
            {
                "severity": severity if severity in _VALID_SEVERITY else "warning",
                "line": line,
                "title": str(item.get("title") or item.get("name") or "问题").strip(),
                "suggestion": str(item.get("suggestion") or item.get("advice") or "").strip(),
            }
        )
    return issues


def _normalize_review(data: dict[str, Any], *, degraded: bool) -> dict[str, Any]:
    """把评审 JSON 归一化为 `ReviewOut` 结构。"""
    try:
        score = int(data.get("score", 0))
    except (TypeError, ValueError):
        score = 0
    score = max(0, min(100, score))
    return {
        "score": score,
        "summary_md": str(data.get("summary_md") or data.get("summary") or "").strip(),
        "issues": _coerce_issues(data.get("issues")),
        "improved_code": (str(data.get("improved_code")).strip() if data.get("improved_code") else None),
        "degraded": bool(degraded),
    }


def _offline_review(code: str) -> dict[str, Any]:
    """本地静态审查兜底。"""
    return review_code(code).as_dict()


class CodeReviewService:
    """代码评审服务。"""

    def __init__(self, provider: AIProvider | None = None) -> None:
        """初始化。

        Args:
            provider: 可选注入的 Provider（测试用）。
        """
        self._provider = provider

    @property
    def provider(self) -> AIProvider:
        """当前 Provider。"""
        return self._provider or get_provider()

    @property
    def dimensions(self) -> list[str]:
        """九维度清单。"""
        return list(REVIEW_DIMENSIONS)

    async def review(
        self,
        request: Any,
        *,
        db: Session | None = None,
        user: Any = None,
    ) -> dict[str, Any]:
        """执行代码评审。

        Args:
            request: `schemas.ai.ReviewRequest`。
            db: 可选数据库会话（写用量日志）。
            user: 可选当前用户。

        Returns:
            与 `schemas.ai.ReviewOut` 对齐的字典。

        Raises:
            AppError: 代码为空（`BAD_REQUEST`）。
        """
        code = (getattr(request, "code", "") or "").strip()
        if not code:
            raise AppError(code=ErrorCode.BAD_REQUEST, message="代码不能为空", status_code=400)
        focus = getattr(request, "focus", None)
        language = getattr(request, "language", "python") or "python"

        messages = [
            ChatMessage(role="system", content=REVIEW_SYSTEM),
            ChatMessage(role="user", content=build_review_user_prompt(code, focus=focus, language=language)),
        ]

        result: dict[str, Any] | None = None
        last_response: AIResponse | None = None
        for _ in range(2):  # 首次 + 解析失败重试一次
            try:
                response = await self.provider.chat(messages, task="review", json_mode=True)
            except AppError:
                raise
            except Exception as exc:  # noqa: BLE001 - 远程异常一律兜底，避免 5xx
                logger.warning("代码评审调用失败，使用本地兜底: %s", exc)
                break
            last_response = response
            data = extract_json_object(response.content)
            if data is not None:
                result = _normalize_review(data, degraded=bool(response.degraded))
                break

        if result is None:
            # 模型返回无法解析 → 本地静态审查兜底
            result = _offline_review(code)
            if last_response is not None:
                result["degraded"] = True

        if db is not None and last_response is not None:
            self._log_usage(db, user, last_response, scene="review")
        return result

    @staticmethod
    def _log_usage(db: Session, user: Any, response: AIResponse, *, scene: str) -> None:
        """写用量日志（失败仅告警）。"""
        try:
            repository.write_usage_log(
                db,
                user_id=str(user.id) if user is not None else None,
                conversation_id=None,
                provider=response.provider,
                model=response.model,
                scene=scene,
                usage=response.usage,
                latency_ms=response.latency_ms,
                success=True,
                degraded=response.degraded,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("写评审用量日志失败: %s", exc)


async def analyze_error_report(
    provider: AIProvider | None,
    *,
    code: str,
    error_message: str,
    traceback_text: str | None = None,
    db: Session | None = None,
    user: Any = None,
) -> dict[str, Any]:
    """分析报错并返回结构化结果（远程 JSON → 本地规则兜底）。

    Args:
        provider: Provider（为空取全局单例）。
        code: 出错的代码。
        error_message: 报错信息。
        traceback_text: 完整 traceback。
        db: 可选数据库会话（写用量日志）。
        user: 可选当前用户。

    Returns:
        与 `schemas.ai.ErrorAnalysisOut` 对齐的字典。
    """
    active = provider or get_provider()
    messages = [
        ChatMessage(role="system", content=ERROR_ANALYSIS_SYSTEM),
        ChatMessage(role="user", content=build_error_user_prompt(code, error_message, traceback_text)),
    ]
    response: AIResponse | None = None
    try:
        response = await active.chat(
            messages,
            task="error",
            json_mode=True,
            code=code,
            error_message=error_message,
            traceback=traceback_text or "",
        )
        data = extract_json_object(response.content)
        if data is not None:
            result = _normalize_error(data, degraded=bool(response.degraded))
            if db is not None:
                CodeReviewService._log_usage(db, user, response, scene="error")
            return result
    except Exception as exc:  # noqa: BLE001 - 兜底，避免 5xx
        logger.warning("报错分析调用失败，使用本地规则: %s", exc)

    result = analyze_error(code, error_message, traceback_text).as_dict()
    if db is not None and response is not None:
        CodeReviewService._log_usage(db, user, response, scene="error")
    return result


def _normalize_error(data: dict[str, Any], *, degraded: bool) -> dict[str, Any]:
    """把报错分析 JSON 归一化为 `ErrorAnalysisOut` 结构。"""
    fix_steps = data.get("fix_steps")
    if isinstance(fix_steps, str):
        fix_steps = [fix_steps]
    if not isinstance(fix_steps, list):
        fix_steps = []
    topics = data.get("related_topics")
    if isinstance(topics, str):
        topics = [topics]
    if not isinstance(topics, list):
        topics = []
    return {
        "error_type": str(data.get("error_type") or "runtime"),
        "cause": str(data.get("cause") or "").strip(),
        "location": (str(data.get("location")).strip() if data.get("location") else None),
        "fix_steps": [str(step) for step in fix_steps],
        "minimal_example": (str(data.get("minimal_example")).strip() if data.get("minimal_example") else None),
        "related_topics": [str(topic) for topic in topics],
        "degraded": bool(degraded),
    }


__all__ = [
    "CodeReviewService",
    "analyze_error_report",
    "extract_json_object",
]
