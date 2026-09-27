"""挑战赛 Schema（`docs/API.md` §2.14）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.common import IdStr, ORMModel, StrictModel
from app.schemas.problem import ProblemBrief


class ChallengeBrief(ORMModel):
    """挑战列表项。"""

    id: IdStr
    slug: str
    title: str
    challenge_type: str = "daily"
    difficulty: str = "easy"
    start_at: datetime | None = None
    end_at: datetime | None = None
    duration_minutes: int = 60
    xp_reward: int = 50
    participant_count: int = 0
    problem_count: int = 0
    is_open: bool = True
    my_status: str | None = None


class UserChallengeOut(ORMModel):
    """我的挑战成绩。"""

    id: IdStr
    challenge_id: IdStr
    status: str = "joined"
    score: int = 0
    passed_cases: int = 0
    total_time_ms: int = 0
    rank: int | None = None
    submitted_at: datetime | None = None


class ChallengeDetail(ORMModel):
    """挑战详情。"""

    challenge: ChallengeBrief
    description_md: str | None = None
    rules_md: str | None = None
    problems: list[ProblemBrief] = Field(default_factory=list)
    my: UserChallengeOut | None = None


class ChallengeSubmitRequest(StrictModel):
    """`POST /challenges/{id}/submit` 请求体。"""

    solutions: dict[str, str] = Field(default_factory=dict, description="{problem_id: code}")


class LeaderboardEntry(ORMModel):
    """排行榜条目：**仅昵称与成绩**。"""

    rank: int = 0
    display_name: str = ""
    score: int = 0
    total_time_ms: int = 0


class LeaderboardOut(ORMModel):
    """排行榜响应体。"""

    entries: list[LeaderboardEntry] = Field(default_factory=list)
    total: int = 0
    updated_at: datetime | None = None


class ChallengeSubmitOut(ORMModel):
    """挑战提交结果。"""

    user_challenge: UserChallengeOut
    passed_cases: int = 0
    details: list[dict[str, Any]] = Field(default_factory=list)
