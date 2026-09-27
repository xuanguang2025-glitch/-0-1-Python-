"""时间工具：统一 UTC、日期区间与时长格式化。

约定：数据库所有 `DateTime(timezone=True)` 字段一律存 UTC，展示层再按用户时区转换。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Iterable


def now_utc() -> datetime:
    """当前 UTC 时间（带时区）。"""
    return datetime.now(timezone.utc)


def to_utc(value: datetime) -> datetime:
    """把时间统一转换为带时区的 UTC 时间（无时区输入按 UTC 处理）。"""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def date_to_str(value: date) -> str:
    """日期转 `YYYY-MM-DD` 字符串。"""
    return value.strftime("%Y-%m-%d")


def today_utc() -> date:
    """当前 UTC 日期。"""
    return now_utc().date()


def day_range(target: date) -> tuple[datetime, datetime]:
    """返回某天的起止时间区间 `[00:00, 次日00:00)`（UTC）。"""
    start = datetime(target.year, target.month, target.day, tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


def last_n_days(n: int, *, end: date | None = None) -> list[date]:
    """返回最近 `n` 天的日期列表（升序，含今天）。"""
    end_date = end or today_utc()
    return [end_date - timedelta(days=offset) for offset in range(n - 1, -1, -1)]


def add_days(value: datetime, days: int) -> datetime:
    """在指定时间上加天数。"""
    return value + timedelta(days=days)


def seconds_between(start: datetime, end: datetime) -> int:
    """两个时间点之间的秒数（非负）。"""
    return max(0, int((end - start).total_seconds()))


def format_duration(seconds: int) -> str:
    """把秒数格式化为「1 小时 23 分」/「4 分 05 秒」这类中文可读串。"""
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours} 小时 {minutes:02d} 分"
    if minutes:
        return f"{minutes} 分 {secs:02d} 秒"
    return f"{secs} 秒"


def format_minutes(minutes: int) -> str:
    """把分钟数格式化为「2 小时 10 分」。"""
    return format_duration(int(minutes) * 60)


def iso_utc(value: datetime | None) -> str | None:
    """序列化为 ISO-8601 UTC 字符串（末尾 `Z`）。"""
    if value is None:
        return None
    return to_utc(value).strftime("%Y-%m-%dT%H:%M:%SZ")


def is_expired(value: datetime | None, *, now: datetime | None = None) -> bool:
    """判断某时间是否已过期（空值视为未设置，不过期）。"""
    if value is None:
        return False
    return to_utc(value) <= (now or now_utc())


def group_by_date(items: Iterable[tuple[datetime, int]]) -> dict[str, int]:
    """把 `(时间, 数值)` 序列按日期聚合，返回 `{"2026-09-26": 12, ...}`。"""
    result: dict[str, int] = {}
    for moment, value in items:
        key = date_to_str(to_utc(moment).date())
        result[key] = result.get(key, 0) + int(value)
    return result
