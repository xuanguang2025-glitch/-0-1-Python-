"""编辑器 / 代码历史 Schema（`docs/API.md` §2.9 与 §2.19）。"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.common import IdStr, ORMModel, StrictModel


class SnapshotCreateRequest(StrictModel):
    """`POST /editor/save-snapshot` 请求体。"""

    context_type: str = Field(default="playground", description="lesson/problem/project/playground")
    context_id: IdStr | None = None
    file_path: str = Field(default="main.py", min_length=1, max_length=255)
    code: str = Field(default="", max_length=200_000)
    label: str | None = Field(default=None, max_length=120)
    source: str = Field(default="manual", description="manual/auto/submit")


class CodeHistoryOut(ORMModel):
    """代码历史详情。"""

    id: IdStr
    user_id: IdStr | None = None
    context_type: str = "playground"
    context_id: str | None = None
    file_path: str = "main.py"
    code: str = ""
    label: str | None = None
    version_no: int = 1
    parent_id: str | None = None
    source: str = "manual"
    size_bytes: int = 0
    line_count: int = 0
    created_at: datetime | None = None


class CodeHistoryBrief(ORMModel):
    """代码历史列表项（不含完整代码）。"""

    id: IdStr
    context_type: str = "playground"
    context_id: str | None = None
    file_path: str = "main.py"
    label: str | None = None
    version_no: int = 1
    source: str = "manual"
    size_bytes: int = 0
    line_count: int = 0
    created_at: datetime | None = None


class CompareRequest(StrictModel):
    """`POST /editor/compare` 请求体。"""

    left_id: IdStr
    right_id: IdStr


class CompareHunk(ORMModel):
    """差异块。"""

    old_start: int = 0
    old_lines: int = 0
    new_start: int = 0
    new_lines: int = 0
    lines: list[dict[str, str]] = Field(default_factory=list)


class CompareOut(ORMModel):
    """差异对比结果。"""

    diff_text: str = ""
    hunks: list[CompareHunk] = Field(default_factory=list)
