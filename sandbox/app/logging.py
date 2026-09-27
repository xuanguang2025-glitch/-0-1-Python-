"""沙箱日志：单行结构化输出，带耗时与 request_id。"""

from __future__ import annotations

import json
import logging
import sys
import time
from contextlib import contextmanager
from typing import Iterator, Optional

_CONFIGURED = False


class JsonFormatter(logging.Formatter):
    """把日志记录格式化为单行 JSON，便于容器日志采集。"""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in ("request_id", "mode", "status", "duration_ms"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """人类可读格式（本机开发默认）。"""

    def format(self, record: logging.LogRecord) -> str:
        extra = " ".join(
            f"{key}={getattr(record, key)}"
            for key in ("request_id", "mode", "status", "duration_ms")
            if hasattr(record, key)
        )
        base = f"{time.strftime('%H:%M:%S')} {record.levelname:<5} {record.name}: {record.getMessage()}"
        return f"{base} [{extra}]" if extra else base


def setup_logging(level: str = "INFO", json_format: bool = False) -> None:
    """初始化根 logger（幂等）。"""
    global _CONFIGURED
    if _CONFIGURED:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if json_format else TextFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    for noisy in ("uvicorn.access", "uvicorn.error"):
        logging.getLogger(noisy).handlers = [handler]
    _CONFIGURED = True


def get_logger(name: str = "sandbox") -> logging.Logger:
    """获取指定名称的 logger（未初始化则先按默认初始化）。"""
    setup_logging()
    return logging.getLogger(name)


@contextmanager
def log_scope(logger: logging.Logger, message: str, **fields: object) -> Iterator[None]:
    """记录一段执行的耗时（异常时以 WARNING 输出）。"""
    started = time.perf_counter()
    try:
        yield
    except Exception as exc:  # noqa: BLE001 - 只用于日志包装，异常继续上抛
        logger.warning("%s failed: %s", message, exc, extra=fields)
        raise
    else:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        extra = dict(fields)
        extra["duration_ms"] = elapsed_ms
        logger.info("%s done", message, extra=extra)


def mask(text: Optional[str], keep: int = 4) -> str:
    """对密钥类字符串做脱敏（日志中避免泄漏）。"""
    if not text:
        return ""
    if len(text) <= keep:
        return "*" * len(text)
    return f"{text[:keep]}{'*' * (len(text) - keep)}"
