"""业务异常体系、错误码表与全局异常处理器。

约定：Service 层一律 `raise AppError(code=..., message=...)`，由本模块的处理器
统一转换为 `docs/API.md` §1.1 的响应结构；未捕获异常一律映射为 `INTERNAL_ERROR`。
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.response import error_response

logger = logging.getLogger("pythonlab")


class ErrorCode:
    """错误码常量（`docs/API.md` §4）。"""

    BAD_REQUEST = "BAD_REQUEST"
    UNAUTHORIZED = "UNAUTHORIZED"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    TOKEN_REVOKED = "TOKEN_REVOKED"
    FORBIDDEN = "FORBIDDEN"
    ACCOUNT_SUSPENDED = "ACCOUNT_SUSPENDED"
    AI_FULL_ANSWER_DISABLED = "AI_FULL_ANSWER_DISABLED"
    NOT_FOUND = "NOT_FOUND"
    USER_NOT_FOUND = "USER_NOT_FOUND"
    PROBLEM_NOT_FOUND = "PROBLEM_NOT_FOUND"
    LESSON_NOT_FOUND = "LESSON_NOT_FOUND"
    COURSE_NOT_FOUND = "COURSE_NOT_FOUND"
    CHAPTER_NOT_FOUND = "CHAPTER_NOT_FOUND"
    PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
    SUBMISSION_NOT_FOUND = "SUBMISSION_NOT_FOUND"
    CONVERSATION_NOT_FOUND = "CONVERSATION_NOT_FOUND"
    MISTAKE_NOT_FOUND = "MISTAKE_NOT_FOUND"
    BOOKMARK_NOT_FOUND = "BOOKMARK_NOT_FOUND"
    HISTORY_NOT_FOUND = "HISTORY_NOT_FOUND"
    EXAM_NOT_FOUND = "EXAM_NOT_FOUND"
    CHALLENGE_NOT_FOUND = "CHALLENGE_NOT_FOUND"
    NOTIFICATION_NOT_FOUND = "NOTIFICATION_NOT_FOUND"
    EMAIL_EXISTS = "EMAIL_EXISTS"
    USERNAME_EXISTS = "USERNAME_EXISTS"
    ALREADY_ENROLLED = "ALREADY_ENROLLED"
    ALREADY_JOINED = "ALREADY_JOINED"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    WEAK_PASSWORD = "WEAK_PASSWORD"
    RATE_LIMITED = "RATE_LIMITED"
    AI_RATE_LIMITED = "AI_RATE_LIMITED"
    SANDBOX_TIMEOUT = "SANDBOX_TIMEOUT"
    SANDBOX_UNAVAILABLE = "SANDBOX_UNAVAILABLE"
    SANDBOX_REJECTED = "SANDBOX_REJECTED"
    OUTPUT_TOO_LARGE = "OUTPUT_TOO_LARGE"
    AI_PROVIDER_UNAVAILABLE = "AI_PROVIDER_UNAVAILABLE"
    AI_BAD_RESPONSE = "AI_BAD_RESPONSE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    INVALID_FILE_TYPE = "INVALID_FILE_TYPE"
    INVALID_PATH = "INVALID_PATH"
    CHALLENGE_CLOSED = "CHALLENGE_CLOSED"
    EXAM_EXPIRED = "EXAM_EXPIRED"
    REGISTER_DISABLED = "REGISTER_DISABLED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    DB_ERROR = "DB_ERROR"


class AppError(Exception):
    """业务异常：携带错误码、HTTP 状态码与可选详情。"""

    def __init__(
        self,
        code: str = ErrorCode.BAD_REQUEST,
        message: str = "请求失败",
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details

    def __repr__(self) -> str:
        return f"AppError(code={self.code!r}, status={self.status_code}, message={self.message!r})"


def not_found(code: str, message: str) -> AppError:
    """构造 404 业务异常的快捷方式。"""
    return AppError(code=code, message=message, status_code=status.HTTP_404_NOT_FOUND)


def forbidden(message: str = "权限不足") -> AppError:
    """构造 403 业务异常的快捷方式。"""
    return AppError(code=ErrorCode.FORBIDDEN, message=message, status_code=status.HTTP_403_FORBIDDEN)


def _write_error(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: Any | None = None,
) -> JSONResponse:
    """按统一结构输出错误响应，并在响应头回传 request_id 便于排查。"""
    body = error_response(code=code, message=message, details=details)
    response = JSONResponse(status_code=status_code, content=body)
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        response.headers["X-Request-ID"] = str(request_id)
    return response


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器（顺序：业务异常 → 校验异常 → HTTP 异常 → 兜底）。"""

    @app.exception_handler(AppError)
    async def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:  # noqa: ANN001
        return _write_error(request, exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # error.details 结构：[{"loc": [...], "msg": "...", "type": "..."}]
        details: list[dict[str, Any]] = [
            {"loc": list(map(str, err.get("loc", []))), "msg": err.get("msg", ""), "type": err.get("type", "")}
            for err in exc.errors()
        ]
        return _write_error(
            request,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            ErrorCode.VALIDATION_ERROR,
            "请求参数校验失败",
            details,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {
            401: ErrorCode.UNAUTHORIZED,
            403: ErrorCode.FORBIDDEN,
            404: ErrorCode.NOT_FOUND,
            405: ErrorCode.BAD_REQUEST,
            429: ErrorCode.RATE_LIMITED,
        }.get(exc.status_code, ErrorCode.BAD_REQUEST)
        return _write_error(request, exc.status_code, code, str(exc.detail))

    @app.exception_handler(HTTPException)
    async def _handle_fastapi_http(request: Request, exc: HTTPException) -> JSONResponse:
        return _write_error(request, exc.status_code, ErrorCode.BAD_REQUEST, str(exc.detail))

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "-")
        logger.exception("未捕获异常 request_id=%s: %s", request_id, exc)
        return _write_error(
            request,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            ErrorCode.INTERNAL_ERROR,
            f"服务器内部错误（request_id={request_id}）",
        )
