"""PYTHON LAB 后端应用包。

分层：`core`（基础设施）→ `db` / `models`（数据）→ `schemas` / `services`（业务）
→ `api`（HTTP 接口），依赖只允许自外向内单向流动。
"""

__all__ = ["__version__"]

__version__ = "1.0.0"
