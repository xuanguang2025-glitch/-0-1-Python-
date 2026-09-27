"""业务服务层：编排数据库与外部依赖，向 API 层暴露纯业务函数。

约定：
- 只接收/返回 ORM 对象或 Schema，不感知 HTTP；
- 业务失败一律 `raise AppError`；
- 服务之间可互相调用，但不得反向依赖 `app.api`。
"""

from app.services import auth_service, health_service, user_service

__all__ = ["auth_service", "health_service", "user_service"]
