"""提交与判题 Schema（`docs/API.md` §2.6 与 §3.3）。"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.common import IdStr, ORMModel, StrictModel


class SubmissionCreateRequest(StrictModel):
    """`POST /submissions` 请求体。"""

    problem_id: IdStr | None = Field(default=None, description="客观题可为空，随堂练习用 lesson_id")
    lesson_id: IdStr | None = None
    code: str = Field(default="", max_length=200_000)
    language: str = Field(default="python", max_length=20, description="当前仅支持 python")
    answer: str | int | bool | None = Field(default=None, description="客观题答案（选择/判断/填空）")

    @property
    def effective_answer(self) -> str:
        """统一为字符串形式的客观题答案。"""
        if self.answer is None:
            return self.code
        if isinstance(self.answer, bool):
            return "true" if self.answer else "false"
        return str(self.answer)


class SubmissionResultOut(ORMModel):
    """单个用例的判题结果（隐藏用例输出脱敏）。"""

    id: IdStr | None = None
    test_case_id: str | None = None
    passed: bool = False
    time_ms: int = 0
    memory_kb: int = 0
    actual_output: str | None = None
    expected_output: str | None = None
    diff: str | None = None
    stderr: str | None = None
    message: str | None = None


class SubmissionOut(ORMModel):
    """提交详情（`docs/API.md` §3.3）。"""

    id: IdStr
    user_id: IdStr | None = None
    problem_id: str | None = None
    lesson_id: str | None = None
    challenge_id: str | None = None
    language: str = "python"
    code: str = ""
    status: str = "pending"
    score: int = 0
    passed_cases: int = 0
    total_cases: int = 0
    time_ms: int = 0
    memory_kb: int = 0
    error_type: str | None = None
    error_message: str | None = None
    runner: str = "local"
    judged_by: str = "local"
    created_at: datetime | None = None
    finished_at: datetime | None = None
    results: list[SubmissionResultOut] = Field(default_factory=list)


class SubmissionBrief(ORMModel):
    """提交列表项。"""

    id: IdStr
    problem_id: str | None = None
    problem_title: str | None = None
    lesson_id: str | None = None
    status: str = "pending"
    score: int = 0
    passed_cases: int = 0
    total_cases: int = 0
    time_ms: int = 0
    memory_kb: int = 0
    language: str = "python"
    created_at: datetime | None = None


class SubmissionStatusOut(ORMModel):
    """轮询判题状态响应体。"""

    status: str = "pending"
    passed_cases: int = 0
    total_cases: int = 0
    finished: bool = False


class RejudgeRequest(StrictModel):
    """批量重判请求体（管理端）。"""

    problem_id: IdStr | None = None
    limit: int = Field(default=20, ge=1, le=200)
