"""考试服务 · 公共常量与时区安全辅助。"""

from __future__ import annotations

from app.models.exam import ExamAttempt
from app.utils.time import now_utc, to_utc

#: 客观题类型（直接判分，不走判题器）
OBJECTIVE_TYPES: frozenset[str] = frozenset({"choice", "judge", "blank", "completion"})
#: 试卷定义在 `answers_json` 中的保留键
PAPER_KEY = "__paper__"
#: 试卷等级 → 可选难度
DIFFICULTY_BY_LEVEL: dict[str, tuple[str, ...]] = {
    "basic": ("easy", "medium"),
    "intermediate": ("medium", "hard"),
    "advanced": ("hard", "expert"),
}


def is_expired(attempt: ExamAttempt) -> bool:
    """安全判断作答是否超时（归一化时区）。"""
    if attempt.deadline_at is None:
        return False
    return to_utc(attempt.deadline_at) <= now_utc()


def remaining_seconds(attempt: ExamAttempt) -> int:
    """剩余作答秒数（归一化时区，非负）。"""
    if attempt.deadline_at is None:
        return 0
    return max(0, int((to_utc(attempt.deadline_at) - now_utc()).total_seconds()))
