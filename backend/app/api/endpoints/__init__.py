"""端点实现包（按 `docs/API.md` 的路由分组拆分）。"""

from app.api.endpoints import ai, auth, health, users

__all__ = ["ai", "auth", "health", "users"]
