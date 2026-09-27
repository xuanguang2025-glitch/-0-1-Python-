"""健康检查 Schema（`docs/API.md` §2.22）。"""

from __future__ import annotations

from pydantic import Field

from app.schemas.common import ORMModel


class HealthOut(ORMModel):
    """基础健康检查。"""

    status: str = "ok"
    version: str = "1.0.0"
    env: str = "development"


class DepStatus(ORMModel):
    """单个依赖的状态。"""

    ok: bool = True
    detail: str | None = None


class DbStatus(DepStatus):
    """数据库状态。"""

    flavor: str = "sqlite"
    target: str = ""


class CacheStatus(DepStatus):
    """缓存状态。"""

    backend: str = "memory"


class QueueStatus(DepStatus):
    """队列状态。"""

    backend: str = "inline"


class RunnerStatus(DepStatus):
    """代码执行器状态。"""

    mode: str = "local"


class AIStatus(DepStatus):
    """AI 提供方状态（provider / model / available / degraded）。"""

    provider: str = "rule"
    model: str = "rule-based"
    available: bool = False
    degraded: bool = True


class DepsHealthOut(ORMModel):
    """依赖健康检查（`GET /api/health/deps`）。"""

    status: str = "ok"
    db: DbStatus = Field(default_factory=DbStatus)
    cache: CacheStatus = Field(default_factory=CacheStatus)
    queue: QueueStatus = Field(default_factory=QueueStatus)
    runner: RunnerStatus = Field(default_factory=RunnerStatus)
    ai: AIStatus = Field(default_factory=AIStatus)
    degraded: bool = False
    version: str = "1.0.0"
