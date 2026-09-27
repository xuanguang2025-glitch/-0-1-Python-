"""管理端端点 · 公共辅助。"""

from __future__ import annotations

from typing import Any

from fastapi import Request

from app.api.deps import client_ip, client_user_agent


def meta(request: Request) -> dict[str, Any]:
    """构造审计所需的请求元信息（IP / User-Agent）。"""
    return {"ip": client_ip(request), "user_agent": client_user_agent(request)}
