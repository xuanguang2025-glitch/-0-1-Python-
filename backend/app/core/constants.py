"""数值型常量与规则表（等级阈值、XP 规则、限流、掌握度算法参数）。

枚举定义集中在 `app/models/enums.py`（与前端 `types/enums.ts` 对齐），本模块只放
数值与映射表，避免两处重复定义枚举。
"""

from __future__ import annotations

# ---------------- 分页 ----------------
DEFAULT_PAGE_SIZE: int = 20
MAX_PAGE_SIZE: int = 100

# ---------------- 掌握度（SM-2 简化版，见 docs/DATABASE.md §6.2）----------------
MASTERY_CORRECT_GAIN: float = 0.2      # 正确：score += (100 - score) * 0.2
MASTERY_WRONG_DECAY: float = 0.25      # 错误：score -= score * 0.25
MASTERY_UPGRADE_STREAK: int = 3        # 连续正确 3 次升级别
MASTERY_LEVEL_THRESHOLDS: list[tuple[float, str]] = [
    (0.0, "none"),
    (20.0, "weak"),
    (50.0, "medium"),
    (75.0, "strong"),
    (90.0, "mastered"),
]
# 间隔复习天数（按掌握度级别）
MASTERY_REVIEW_INTERVAL_DAYS: dict[str, int] = {
    "none": 1,
    "weak": 2,
    "medium": 4,
    "strong": 7,
    "mastered": 15,
}

# ---------------- XP 原因 ----------------
XP_REASON_LESSON: str = "lesson_complete"
XP_REASON_AC: str = "ac"
XP_REASON_DAILY_TASK: str = "daily_task"
XP_REASON_ACHIEVEMENT: str = "achievement"
XP_REASON_PROJECT: str = "project"
XP_REASON_CHALLENGE: str = "challenge"

# ---------------- 限流（`docs/API.md` §1.4）----------------
RATE_LIMITS: dict[str, tuple[int, int]] = {
    # 名称: (次数上限, 时间窗口秒数)
    "auth": (10, 60),
    "run": (30, 60),
    "submit": (20, 60),
    "export": (5, 60),
}

# ---------------- 代码历史 ----------------
CODE_HISTORY_KEEP: int = 30          # 同一上下文保留的最近版本数
MAX_CODE_BYTES: int = 200_000        # 单次保存代码大小上限
MAX_SNIPPET_BYTES: int = 100_000     # 收藏代码片段上限

# ---------------- 输出与截断 ----------------
MAX_STDOUT_CHARS: int = 8000         # 入库的输出截断长度
MAX_ERROR_MESSAGE_CHARS: int = 2000  # 错误信息截断长度
DEFAULT_TIMEOUT_MS: int = 5000
DEFAULT_MEMORY_MB: int = 256

# ---------------- 文件与上传 ----------------
AVATAR_MAX_BYTES: int = 2 * 1024 * 1024
AVATAR_MIME_TYPES: tuple[str, ...] = ("image/jpeg", "image/png", "image/webp")
IMPORT_MAX_BYTES: int = 10 * 1024 * 1024
ALLOWED_FILE_EXTENSIONS: tuple[str, ...] = (".py", ".md", ".json", ".txt", ".csv")

# ---------------- 难度权重（排序 / 推荐用）----------------
DIFFICULTY_ORDER: dict[str, int] = {"easy": 1, "medium": 2, "hard": 3, "expert": 4}

# ---------------- AI ----------------
AI_MAX_HISTORY_MESSAGES: int = 10    # 组装提示时携带的最近对话轮数
AI_MODES: tuple[str, ...] = ("beginner", "standard", "advanced")
AI_HINT_LEVELS: tuple[str, ...] = ("hint", "approach", "partial", "full", "explain")

# ---------------- 挑战 / 考试 ----------------
CHALLENGE_LEADERBOARD_LIMIT: int = 100
EXAM_DEFAULT_DURATION_MIN: int = 60


def mastery_level_of(score: float) -> str:
    """把 0-100 的掌握度分数映射为级别字符串。"""
    level = "none"
    for threshold, name in MASTERY_LEVEL_THRESHOLDS:
        if score >= threshold:
            level = name
    return level


def level_of_xp(xp: int, thresholds: list[int]) -> int:
    """按经验阈值列表计算等级（1 起，最大 7）。"""
    level = 1
    for index, threshold in enumerate(thresholds, start=1):
        if xp >= threshold:
            level = index
    return level


def next_level_xp(xp: int, thresholds: list[int]) -> int:
    """返回下一等级所需经验值；已满级时返回当前阈值（即不再增长）。"""
    for threshold in thresholds:
        if xp < threshold:
            return threshold
    return thresholds[-1] if thresholds else 0
