"""结构化日志与请求上下文中间件。

- 开发环境用可读文本格式，生产环境输出单行 JSON（便于采集）；
- 中间件为每个请求注入 `request_id`（响应头 `X-Request-ID`）并统计耗时。
"""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from typing import Any, Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER: str = "X-Request-ID"
logger = logging.getLogger("pythonlab")


class JsonFormatter(logging.Formatter):
    """单行 JSON 日志格式（生产环境）。"""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        for key in ("request_id", "user_id", "path", "status", "duration_ms"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """可读文本格式（开发/测试环境）。"""

    def __init__(self) -> None:
        super().__init__(fmt="%(asctime)s %(levelname)-7s [%(name)s] %(message)s", datefmt="%H:%M:%S")


def setup_logging(level: str = "INFO", json_format: bool = False) -> None:
    """初始化根日志器（幂等，重复调用只更新等级与格式）。"""
    root = logging.getLogger()
    root.setLevel(level.upper())
    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if json_format else TextFormatter())
    root.addHandler(handler)

    # 抑制第三方库的噪音日志
    for name in ("sqlalchemy.engine", "uvicorn.access", "watchfiles"):
        logging.getLogger(name).setLevel(logging.WARNING)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """注入 `request_id`、记录访问日志并回传响应头。"""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        request.state.request_id = request_id
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.exception(
                "请求异常 %s %s request_id=%s duration_ms=%.1f",
                request.method,
                request.url.path,
                request_id,
                duration_ms,
            )
            raise

        duration_ms = (time.perf_counter() - start) * 1000
        response.headers[REQUEST_ID_HEADER] = request_id
        response.headers["X-Response-Time"] = f"{duration_ms:.1f}ms"
        logger.info(
            "%s %s -> %s (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response
