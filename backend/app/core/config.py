"""应用配置中心（pydantic-settings）。

职责：
1. 集中声明全部环境变量（清单见 docs/ARCHITECTURE.md §8.3）；
2. 提供 `db_flavor()` 等降级判定入口，供 DB / Cache / Queue / Runner / AI 选择实现；
3. 对路径类配置（SQLite 文件、上传目录、种子目录）统一按项目根目录解析为绝对路径。

约定：本模块不导入 `app.models` / `app.services`，保持核心层最底层依赖。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> backend/
BACKEND_DIR: Path = Path(__file__).resolve().parents[2]
# backend/ -> 仓库根
PROJECT_ROOT: Path = BACKEND_DIR.parent

DbFlavor = Literal["sqlite", "postgres"]


class Settings(BaseSettings):
    """全局配置对象。所有字段均可通过同名环境变量覆盖。"""

    model_config = SettingsConfigDict(
        env_file=(str(BACKEND_DIR / ".env"), str(PROJECT_ROOT / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---------------- 应用 ----------------
    app_env: str = Field(default="development", description="development|testing|production")
    app_name: str = Field(default="PYTHON LAB")
    app_version: str = Field(default="1.0.0")
    debug: bool = Field(default=True)
    log_level: str = Field(default="INFO")
    secret_key: str = Field(default="change-me-in-production")
    api_prefix: str = Field(default="/api")
    backend_host: str = Field(default="127.0.0.1")
    backend_port: int = Field(default=8000)
    cors_origins: str = Field(default="http://localhost:3000,http://127.0.0.1:3000")
    request_timeout_ms: int = Field(default=30_000)
    upload_dir: str = Field(default="./data/uploads")
    max_upload_mb: int = Field(default=10)

    # ---------------- 数据库 ----------------
    database_url: str = Field(default="sqlite:///./data/pythonlab.db")
    db_echo: bool = Field(default=False)
    db_pool_size: int = Field(default=10)
    sqlite_wal: bool = Field(default=True)

    # ---------------- 缓存 ----------------
    cache_backend: str = Field(default="auto", description="auto|redis|memory")
    redis_url: str = Field(default="redis://localhost:6379/0")
    cache_probe_timeout_ms: int = Field(default=800)
    cache_default_ttl: int = Field(default=300)

    # ---------------- 队列 ----------------
    queue_backend: str = Field(default="auto", description="auto|rq|inline")
    rq_queue_name: str = Field(default="pythonlab")

    # ---------------- 认证 ----------------
    jwt_algorithm: str = Field(default="HS256")
    jwt_secret_key: str = Field(default="change-me")
    access_token_ttl_min: int = Field(default=15)
    refresh_token_ttl_days: int = Field(default=30)
    pwd_hash_scheme: str = Field(default="bcrypt", description="bcrypt|argon2")
    pwd_min_length: int = Field(default=8)
    register_enabled: bool = Field(default=True)
    default_user_role: str = Field(default="user")

    # ---------------- 沙箱 ----------------
    sandbox_mode: str = Field(default="auto", description="auto|remote|local|stub")
    sandbox_url: str = Field(default="http://localhost:8081")
    sandbox_probe_timeout_ms: int = Field(default=1500)
    sandbox_timeout_ms: int = Field(default=5000)
    sandbox_memory_mb: int = Field(default=256)
    sandbox_cpu_limit_ms: int = Field(default=4000)
    sandbox_max_output_bytes: int = Field(default=65536)
    sandbox_allow_network: bool = Field(default=False)
    local_runner_enabled: bool = Field(default=True)
    sandbox_allowed_imports: str = Field(
        default="math,json,itertools,collections,re,string,sys,random,datetime,"
        "functools,heapq,bisect,typing"
    )
    allow_anon_run: bool = Field(default=False, description="是否允许匿名调用 /api/python/run")

    # ---------------- AI ----------------
    ai_provider: str = Field(default="deepseek")
    ai_model: str = Field(default="deepseek-chat")
    ai_base_url: str = Field(default="https://api.deepseek.com/v1")
    ai_api_key: str = Field(default="")
    ai_temperature: float = Field(default=0.3)
    ai_max_tokens: int = Field(default=2048)
    ai_timeout_ms: int = Field(default=30_000)
    ai_offline: bool = Field(default=False)
    ai_rate_limit_per_hour: int = Field(default=60)
    ai_cache_ttl: int = Field(default=600)
    ai_default_mode: str = Field(default="standard", description="beginner|standard|advanced")
    ai_allow_full_answer_in_drill: bool = Field(default=False)

    # ---------------- 游戏化 ----------------
    xp_per_lesson: int = Field(default=10)
    xp_per_ac: int = Field(default=20)
    xp_per_project: int = Field(default=100)
    level_thresholds: str = Field(default="0,100,300,700,1500,3000,6000")
    daily_task_count: int = Field(default=3)

    # ---------------- 种子 / 管理员 ----------------
    seed_on_startup: bool = Field(default=True)
    admin_email: str = Field(default="admin@pythonlab.dev")
    admin_password: str = Field(default="Admin@12345")
    admin_username: str = Field(default="admin")
    seeds_dir: str = Field(default="../database/seeds")

    # ---------------- 分页 ----------------
    default_page_size: int = Field(default=20)
    max_page_size: int = Field(default=100)

    # ---------------- 校验与派生 ----------------
    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        """把相对路径的 SQLite URL 解析为相对 backend/ 的绝对路径，避免工作目录差异。"""
        url = str(value).strip()
        if url.startswith("sqlite") and "///" in url:
            path_part = url.split("///", 1)[1]
            if path_part and not path_part.startswith("/") and ":" not in path_part[:2]:
                abs_path = (BACKEND_DIR / path_part).resolve()
                return f"{url.split('///', 1)[0]}///{abs_path.as_posix()}"
        return url

    def _resolve_dir(self, raw: str) -> Path:
        """把可能是相对路径的目录配置解析为绝对路径（相对 backend/ 目录）。"""
        path = Path(raw)
        if not path.is_absolute():
            path = (BACKEND_DIR / path).resolve()
        return path

    @property
    def upload_dir_path(self) -> Path:
        """上传目录绝对路径（不存在时惰性创建）。"""
        path = self._resolve_dir(self.upload_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def seeds_dir_path(self) -> Path:
        """种子数据目录绝对路径。"""
        return self._resolve_dir(self.seeds_dir)

    # ---------------- 降级判定 ----------------
    @property
    def db_flavor(self) -> DbFlavor:
        """按 DATABASE_URL 前缀判定数据库种类（sqlite / postgres）。"""
        url = self.database_url.lower()
        if url.startswith("sqlite"):
            return "sqlite"
        if url.startswith("postgresql") or url.startswith("postgres"):
            return "postgres"
        raise ValueError(f"不支持的 DATABASE_URL（必须以 sqlite 或 postgresql 开头）: {self.database_url}")

    @property
    def is_sqlite(self) -> bool:
        """当前是否为 SQLite 模式。"""
        return self.db_flavor == "sqlite"

    @property
    def is_production(self) -> bool:
        """是否为生产环境。"""
        return self.app_env.lower() == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        """CORS 允许的来源列表。"""
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def allowed_imports(self) -> list[str]:
        """本地执行器允许的 import 白名单。"""
        return [item.strip() for item in self.sandbox_allowed_imports.split(",") if item.strip()]

    @property
    def level_threshold_list(self) -> list[int]:
        """等级经验阈值列表（升序）。"""
        items: list[int] = []
        for chunk in self.level_thresholds.split(","):
            chunk = chunk.strip()
            if chunk:
                items.append(int(chunk))
        return sorted(items) or [0]

    @property
    def ai_enabled(self) -> bool:
        """AI 远程模型是否可用（有 key 且未强制离线）。"""
        if self.ai_offline:
            return False
        key = (self.ai_api_key or "").strip()
        if not key or key.startswith("sk-your-"):
            return False
        return True

    @property
    def database_host_hint(self) -> str:
        """数据库主机摘要（用于健康检查展示，不含凭据）。"""
        parsed = urlparse(self.database_url)
        if self.is_sqlite:
            return Path(parsed.path or "pythonlab.db").name
        return f"{parsed.hostname or 'localhost'}:{parsed.port or 5432}"

    def clamp_timeout_ms(self, timeout_ms: int | None) -> int:
        """把执行超时限制在 [1000, 10000] 毫秒区间内。"""
        if not timeout_ms or timeout_ms <= 0:
            return self.sandbox_timeout_ms
        return max(1000, min(10_000, int(timeout_ms)))

    def clamp_memory_mb(self, memory_mb: int | None) -> int:
        """把内存限制限制在 [32, 512] MB 区间内。"""
        if not memory_mb or memory_mb <= 0:
            return self.sandbox_memory_mb
        return max(32, min(512, int(memory_mb)))

    def as_public_dict(self) -> dict[str, Any]:
        """返回可安全展示给前端的配置摘要（不含任何密钥）。"""
        return {
            "app_name": self.app_name,
            "app_version": self.app_version,
            "env": self.app_env,
            "db_flavor": self.db_flavor,
            "cache_backend": self.cache_backend,
            "queue_backend": self.queue_backend,
            "sandbox_mode": self.sandbox_mode,
            "ai_provider": self.ai_provider if self.ai_enabled else "rule",
            "register_enabled": self.register_enabled,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """获取全局单例配置（进程内缓存，测试可 `get_settings.cache_clear()`）。"""
    return Settings()


settings: Settings = get_settings()
