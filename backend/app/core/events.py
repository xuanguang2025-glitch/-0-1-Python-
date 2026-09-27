"""进程内领域事件总线。

用于解耦「完成课时 / 提交通过 / 项目完成」等业务动作与「XP / 成就 / 通知 / 统计」
等副作用：发布方不感知订阅方，订阅方异常不会影响主流程。
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Callable

logger = logging.getLogger("pythonlab.events")

# 事件名常量
LESSON_COMPLETED: str = "lesson.completed"
SUBMISSION_ACCEPTED: str = "submission.accepted"
SUBMISSION_FAILED: str = "submission.failed"
PROJECT_COMPLETED: str = "project.completed"
CHALLENGE_SUBMITTED: str = "challenge.submitted"
USER_REGISTERED: str = "user.registered"
XP_GAINED: str = "xp.gained"
ACHIEVEMENT_UNLOCKED: str = "achievement.unlocked"

Handler = Callable[[dict[str, Any]], None]


class EventBus:
    """同步事件总线（进程内发布订阅，线程安全由 GIL + dict 原子操作保证）。"""

    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, event: str, handler: Handler) -> None:
        """订阅事件。同一事件可有多个订阅者，按订阅顺序调用。"""
        self._handlers[event].append(handler)

    def unsubscribe(self, event: str, handler: Handler) -> None:
        """取消订阅（测试用）。"""
        handlers = self._handlers.get(event)
        if handlers and handler in handlers:
            handlers.remove(handler)

    def publish(self, event: str, payload: dict[str, Any] | None = None) -> None:
        """发布事件：逐个调用订阅者，任一订阅者异常仅记录日志。"""
        data = payload or {}
        for handler in list(self._handlers.get(event, [])):
            try:
                handler(data)
            except Exception:  # noqa: BLE001 - 订阅方失败不得影响主流程
                logger.exception("事件处理失败 event=%s handler=%s", event, getattr(handler, "__name__", handler))

    def clear(self) -> None:
        """清空全部订阅（测试用）。"""
        self._handlers.clear()


event_bus = EventBus()


def publish(event: str, payload: dict[str, Any] | None = None) -> None:
    """向全局事件总线发布事件。"""
    event_bus.publish(event, payload)


def subscribe(event: str, handler: Handler) -> None:
    """向全局事件总线订阅事件。"""
    event_bus.subscribe(event, handler)
