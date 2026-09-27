"""题目 / 测试用例 / 标签 Schema（`docs/API.md` §2.5）。"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from app.schemas.common import IdStr, ORMModel, StrictModel


class TagOut(ORMModel):
    """标签响应体。"""

    id: IdStr
    slug: str
    name: str
    color: str | None = None
    kind: str = "problem"
    order_index: int = 0
    count: int | None = Field(default=None, description="关联数量（filters 接口用）")


class TestCaseBrief(ORMModel):
    """样例用例（隐藏用例不返回）。"""

    id: IdStr
    name: str | None = None
    input: str = ""
    expected_output: str = ""
    comparison: str = "trimmed"
    is_sample: bool = False
    order_index: int = 0


class ProblemBrief(ORMModel):
    """题目列表项。"""

    id: IdStr
    slug: str
    title: str
    problem_type: str = "coding"
    difficulty: str = "easy"
    category: str = "basics"
    score: int = 10
    xp_reward: int = 20
    submission_count: int = 0
    accepted_count: int = 0
    acceptance_rate: float = 0.0
    tags: list[str] = Field(default_factory=list)
    my_status: str | None = Field(default=None, description="solved/attempted/unsolved（需登录）")


class ProblemDetail(ORMModel):
    """题目详情。"""

    id: IdStr
    slug: str
    title: str
    statement_md: str = ""
    problem_type: str = "coding"
    difficulty: str = "easy"
    category: str = "basics"
    input_format: str | None = None
    output_format: str | None = None
    sample_input: str | None = None
    sample_output: str | None = None
    constraints: str | None = None
    options_json: Any | None = None
    hint_md: str | None = None
    solution_md: str | None = None
    starter_code: str | None = None
    buggy_code: str | None = None
    time_limit_ms: int = 5000
    memory_limit_mb: int = 256
    score: int = 10
    xp_reward: int = 20
    submission_count: int = 0
    accepted_count: int = 0
    acceptance_rate: float = 0.0
    tags: list[TagOut] = Field(default_factory=list)
    sample_cases: list[TestCaseBrief] = Field(default_factory=list)
    my_status: str | None = None
    my_last_submission_id: str | None = None


class ProblemTagOut(ORMModel):
    """`GET /problems/filters` 的筛选字典。"""

    types: list[dict[str, Any]] = Field(default_factory=list)
    difficulties: list[dict[str, Any]] = Field(default_factory=list)
    categories: list[dict[str, Any]] = Field(default_factory=list)
    tags: list[TagOut] = Field(default_factory=list)


class DiscussionAIOut(ORMModel):
    """题目讨论区 AI 摘要。"""

    summary_md: str
    degraded: bool = False


class AdminTestCaseIn(StrictModel):
    """管理端测试用例写入体。"""

    name: str | None = Field(default=None, max_length=100)
    input: str = ""
    expected_output: str = ""
    comparison: str = "trimmed"
    float_tolerance: float | None = 1e-6
    is_sample: bool = False
    is_hidden: bool = True
    weight: int = Field(default=1, ge=0, le=100)
    timeout_ms: int | None = Field(default=None, ge=100, le=30_000)
    order_index: int = 0


class AdminProblemIn(StrictModel):
    """管理端题目写入体。"""

    slug: str = Field(..., min_length=1, max_length=150)
    title: str = Field(..., min_length=1, max_length=200)
    statement_md: str = ""
    problem_type: str = "coding"
    difficulty: str = "easy"
    category: str = "basics"
    input_format: str | None = None
    output_format: str | None = None
    sample_input: str | None = None
    sample_output: str | None = None
    constraints: str | None = None
    options_json: Any | None = None
    answer_json: Any | None = None
    hint_md: str | None = None
    solution_md: str | None = None
    starter_code: str | None = None
    reference_solution: str | None = None
    buggy_code: str | None = None
    time_limit_ms: int = Field(default=5000, ge=1000, le=10_000)
    memory_limit_mb: int = Field(default=256, ge=32, le=512)
    score: int = Field(default=10, ge=0, le=100)
    xp_reward: int = Field(default=20, ge=0, le=1000)
    is_published: bool = True
    tags: list[str] = Field(default_factory=list)
    test_cases: list[AdminTestCaseIn] = Field(default_factory=list)


class ProblemImportResult(ORMModel):
    """批量导入结果。"""

    created: int = 0
    updated: int = 0
    failed: list[dict[str, Any]] = Field(default_factory=list)


class AdminTagIn(StrictModel):
    """管理端标签写入体。"""

    slug: str = Field(..., min_length=1, max_length=120)
    name: str = Field(..., min_length=1, max_length=120)
    color: str | None = Field(default=None, max_length=20)
    kind: str = "problem"
    order_index: int = 0


# 便于端点直接引用时间类型
__all__ = [
    "AdminProblemIn",
    "AdminTagIn",
    "AdminTestCaseIn",
    "DiscussionAIOut",
    "ProblemBrief",
    "ProblemDetail",
    "ProblemImportResult",
    "ProblemTagOut",
    "TagOut",
    "TestCaseBrief",
]
