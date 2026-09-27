"""全库枚举字典（DATABASE.md §11，值与前端 `types/enums.ts` 严格一致）。

约定：值一律小写 snake_case；数据库中以 `String` 存储枚举值（不用 SQL ENUM，
保证 SQLite/PostgreSQL 一致且可平滑扩展）。
"""

from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    """字符串枚举基类：`str(x)` 返回其值，方便直接入库与序列化。"""

    def __str__(self) -> str:
        return str(self.value)

    @classmethod
    def values(cls) -> list[str]:
        """返回全部枚举值列表（用于校验与前端字典接口）。"""
        return [member.value for member in cls]

    @classmethod
    def has(cls, value: str) -> bool:
        """判断给定字符串是否为合法枚举值。"""
        return value in cls._value2member_map_


class UserRole(StrEnum):
    """用户角色。"""

    USER = "user"
    ADMIN = "admin"
    SUPERADMIN = "superadmin"


class UserStatus(StrEnum):
    """用户状态。"""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class Difficulty(StrEnum):
    """难度（四档）。"""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"


class CourseLevel(StrEnum):
    """课程/项目难度级别。"""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class LessonType(StrEnum):
    """课时类型。"""

    CONCEPT = "concept"
    PRACTICE = "practice"
    QUIZ = "quiz"
    PROJECT = "project"


class ProblemType(StrEnum):
    """题型（7 种）。"""

    CHOICE = "choice"
    JUDGE = "judge"
    BLANK = "blank"
    COMPLETION = "completion"
    CODING = "coding"
    DEBUG = "debug"
    ALGORITHM = "algorithm"


class ProblemCategory(StrEnum):
    """题目分类（≥10 类）。"""

    BASICS = "basics"
    STRINGS = "strings"
    LISTS = "lists"
    DICTS = "dicts"
    SETS_TUPLES = "sets_tuples"
    FUNCTIONS = "functions"
    OOP = "oop"
    FILES = "files"
    EXCEPTIONS = "exceptions"
    REGEX = "regex"
    ALGORITHMS = "algorithms"
    DATA_STRUCTURES = "data_structures"
    STDLIB = "stdlib"
    DEBUG = "debug"
    CONCURRENCY = "concurrency"


class SubmissionStatus(StrEnum):
    """判题状态。"""

    PENDING = "pending"
    JUDGING = "judging"
    ACCEPTED = "accepted"
    WRONG_ANSWER = "wrong_answer"
    RUNTIME_ERROR = "runtime_error"
    TIME_LIMIT_EXCEEDED = "time_limit_exceeded"
    MEMORY_LIMIT_EXCEEDED = "memory_limit_exceeded"
    COMPILE_ERROR = "compile_error"
    SECURITY_ERROR = "security_error"
    INTERNAL_ERROR = "internal_error"


class ComparisonMode(StrEnum):
    """判题输出对比模式。"""

    EXACT = "exact"
    TRIMMED = "trimmed"
    FLOAT = "float"
    CUSTOM = "custom"


class RunnerType(StrEnum):
    """执行器类型。"""

    SANDBOX = "sandbox"
    LOCAL = "local"


class ProgressStatus(StrEnum):
    """学习进度状态。"""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class MasteryLevel(StrEnum):
    """知识点掌握级别。"""

    NONE = "none"
    WEAK = "weak"
    MEDIUM = "medium"
    STRONG = "strong"
    MASTERED = "mastered"


class MistakeErrorType(StrEnum):
    """错题错误类型。"""

    CONCEPT = "concept"
    SYNTAX = "syntax"
    LOGIC = "logic"
    RUNTIME = "runtime"
    TIMEOUT = "timeout"
    STYLE = "style"
    OUTPUT = "output"


class BookmarkKind(StrEnum):
    """收藏类型。"""

    PROBLEM = "problem"
    LESSON = "lesson"
    PROJECT = "project"
    SNIPPET = "snippet"
    CHALLENGE = "challenge"


class CodeContextType(StrEnum):
    """代码历史上下文类型。"""

    LESSON = "lesson"
    PROBLEM = "problem"
    PROJECT = "project"
    PLAYGROUND = "playground"


class CodeSource(StrEnum):
    """代码历史来源。"""

    MANUAL = "manual"
    AUTO = "auto"
    SUBMIT = "submit"


class LearningMode(StrEnum):
    """学习模式（跨模块统一切换）。"""

    FREE = "free"
    SYSTEM = "system"
    EXAM = "exam"
    DRILL = "drill"
    PROJECT = "project"
    CHALLENGE = "challenge"
    AI = "ai"


class SessionType(StrEnum):
    """学习会话类型。"""

    LESSON = "lesson"
    PROBLEM = "problem"
    PROJECT = "project"
    EXAM = "exam"
    PLAYGROUND = "playground"
    CHALLENGE = "challenge"
    AI = "ai"


class AIMode(StrEnum):
    """AI 讲解模式（按学习者水平）。"""

    BEGINNER = "beginner"
    STANDARD = "standard"
    ADVANCED = "advanced"


class AIScene(StrEnum):
    """AI 使用场景。"""

    TUTOR = "tutor"
    REVIEW = "review"
    ERROR = "error"
    EXAM = "exam"
    FREE = "free"


class AIMessageRole(StrEnum):
    """AI 消息角色。"""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class AIMessageKind(StrEnum):
    """AI 回答类型（渐进式提示层级）。"""

    HINT = "hint"
    APPROACH = "approach"
    PARTIAL = "partial"
    FULL = "full"
    EXPLAIN = "explain"
    REVIEW = "review"
    ERROR_ANALYSIS = "error_analysis"
    ANSWER = "answer"


class AchievementCategory(StrEnum):
    """成就分类。"""

    LEARNING = "learning"
    PRACTICE = "practice"
    STREAK = "streak"
    PROJECT = "project"
    SOCIAL = "social"
    SPECIAL = "special"


class ChallengeType(StrEnum):
    """挑战周期类型。"""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    SPECIAL = "special"


class ChallengeStatus(StrEnum):
    """用户挑战参与状态。"""

    JOINED = "joined"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class UserProjectStatus(StrEnum):
    """用户项目状态。"""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class ExamLevel(StrEnum):
    """考试级别。"""

    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class ExamAttemptStatus(StrEnum):
    """考试作答状态。"""

    IN_PROGRESS = "in_progress"
    GRADED = "graded"
    ABANDONED = "abandoned"


class NotificationType(StrEnum):
    """通知类型。"""

    SYSTEM = "system"
    ACHIEVEMENT = "achievement"
    DAILY = "daily"
    CHALLENGE = "challenge"
    AI = "ai"
    ADMIN = "admin"


class AnnouncementLevel(StrEnum):
    """公告重要程度。"""

    INFO = "info"
    WARNING = "warning"
    IMPORTANT = "important"


class TagKind(StrEnum):
    """标签适用范围。"""

    PROBLEM = "problem"
    COURSE = "course"
    PROJECT = "project"
    LESSON = "lesson"
    SNIPPET = "snippet"


class ThemePreference(StrEnum):
    """主题偏好。"""

    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"


class AIProviderName(StrEnum):
    """AI 服务商。"""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    DEEPSEEK = "deepseek"
    QWEN = "qwen"
    ZHIPU = "zhipu"
    MOONSHOT = "moonshot"
    CUSTOM = "custom"


def enum_dict() -> dict[str, list[str]]:
    """返回全部枚举字典（供 `GET /api/health` 或前端字典接口使用）。"""
    return {
        "role": UserRole.values(),
        "user_status": UserStatus.values(),
        "difficulty": Difficulty.values(),
        "course_level": CourseLevel.values(),
        "lesson_type": LessonType.values(),
        "problem_type": ProblemType.values(),
        "problem_category": ProblemCategory.values(),
        "submission_status": SubmissionStatus.values(),
        "comparison": ComparisonMode.values(),
        "runner": RunnerType.values(),
        "progress_status": ProgressStatus.values(),
        "mastery_level": MasteryLevel.values(),
        "mistake_error_type": MistakeErrorType.values(),
        "bookmark_kind": BookmarkKind.values(),
        "code_context_type": CodeContextType.values(),
        "code_source": CodeSource.values(),
        "learning_mode": LearningMode.values(),
        "session_type": SessionType.values(),
        "ai_mode": AIMode.values(),
        "ai_scene": AIScene.values(),
        "ai_message_role": AIMessageRole.values(),
        "ai_message_kind": AIMessageKind.values(),
        "achievement_category": AchievementCategory.values(),
        "challenge_type": ChallengeType.values(),
        "challenge_status": ChallengeStatus.values(),
        "user_project_status": UserProjectStatus.values(),
        "exam_level": ExamLevel.values(),
        "exam_attempt_status": ExamAttemptStatus.values(),
        "notification_type": NotificationType.values(),
        "announcement_level": AnnouncementLevel.values(),
        "tag_kind": TagKind.values(),
        "theme_preference": ThemePreference.values(),
        "ai_provider": AIProviderName.values(),
    }
