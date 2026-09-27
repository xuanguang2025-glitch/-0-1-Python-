"""核心层：配置、安全、响应、异常、缓存、队列、日志、事件、依赖、分页。

依赖方向：`core` 不依赖 `services` / `api`，可被任意层安全导入。
"""

from app.core.config import Settings, get_settings, settings
from app.core.errors import AppError, ErrorCode, register_exception_handlers
from app.core.events import event_bus, publish, subscribe
from app.core.pagination import PageParams, build_page, normalize_page_params, paginate
from app.core.response import ErrorDetail, PageModel, ResponseModel, error_response, success_response
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    validate_password_strength,
    verify_password,
)

__all__ = [
    "AppError",
    "ErrorCode",
    "ErrorDetail",
    "PageModel",
    "PageParams",
    "ResponseModel",
    "Settings",
    "build_page",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "error_response",
    "event_bus",
    "get_settings",
    "hash_password",
    "normalize_page_params",
    "paginate",
    "publish",
    "register_exception_handlers",
    "settings",
    "subscribe",
    "success_response",
    "validate_password_strength",
    "verify_password",
]
