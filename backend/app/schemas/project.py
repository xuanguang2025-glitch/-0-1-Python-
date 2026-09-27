"""项目中心 Schema（`docs/API.md` §2.8）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.common import IdStr, ORMModel, StrictModel


class ProjectFileOut(ORMModel):
    """项目模板文件。"""

    id: IdStr
    path: str
    content: str = ""
    language: str = "python"
    is_entry: bool = False
    is_readonly: bool = False
    description: str | None = None
    order_index: int = 0


class ProjectBrief(ORMModel):
    """项目列表项。"""

    id: IdStr
    slug: str
    title: str
    summary: str | None = None
    level: int = 1
    difficulty: str = "easy"
    category: str = "basics"
    cover_url: str | None = None
    estimated_hours: int = 4
    xp_reward: int = 100
    order_index: int = 0
    my_status: str | None = None
    progress_percent: int = 0


class ProjectStepOut(ORMModel):
    """项目步骤。"""

    title: str = ""
    detail: str = ""
    done_hint: str = ""


class UserProjectOut(ORMModel):
    """用户项目进度。"""

    id: IdStr | None = None
    user_id: IdStr | None = None
    project_id: IdStr
    status: str = "not_started"
    progress_percent: int = 0
    current_step: int = 0
    files_json: dict[str, str] = Field(default_factory=dict)
    notes_md: str | None = None
    last_run_status: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime | None = None


class ProjectDetail(ORMModel):
    """项目详情。"""

    project: ProjectBrief
    files: list[ProjectFileOut] = Field(default_factory=list)
    steps: list[ProjectStepOut] = Field(default_factory=list)
    rubric: Any | None = None
    description_md: str = ""
    my: UserProjectOut | None = None


class ProjectFilesUpdateRequest(StrictModel):
    """`PUT /projects/{id}/files` 请求体。"""

    files: dict[str, str] = Field(default_factory=dict, description="{path: content}")

    def normalized(self) -> dict[str, str]:
        """返回浅拷贝，避免调用方持有的字典被后续修改。"""
        return dict(self.files)


class ProjectRunRequest(StrictModel):
    """`POST /projects/{id}/run` 请求体。"""

    entry: str | None = Field(default=None, max_length=255)
    stdin: str = Field(default="", max_length=100_000)


class ProjectSubmitRequest(StrictModel):
    """`POST /projects/{id}/submit` 请求体。"""

    notes_md: str | None = Field(default=None, max_length=5000)


class ProjectSubmitOut(ORMModel):
    """项目提交结果。"""

    user_project: UserProjectOut
    xp_earned: int = 0
    level_up: bool = False
    unlocked_achievements: list[str] = Field(default_factory=list)
    checks: list[dict[str, Any]] = Field(default_factory=list, description="步骤校验明细")
