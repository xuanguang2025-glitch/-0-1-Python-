"""AI 测试夹具：在导入应用前固定离线环境，保证测试完全不依赖外网与真实 Key。"""

from __future__ import annotations

import os

# pytest.ini 的 [pytest] env 会设置这些变量；此处 setdefault 作为兜底，保证单独运行也一致。
os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("AI_OFFLINE", "true")
os.environ.setdefault("AI_API_KEY", "")
os.environ.setdefault("CACHE_BACKEND", "memory")
os.environ.setdefault("QUEUE_BACKEND", "inline")
os.environ.setdefault("SANDBOX_MODE", "stub")
os.environ.setdefault("DATABASE_URL", "sqlite:///./data/pythonlab_test.db")
