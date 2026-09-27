"""PYTHON LAB 独立代码沙箱服务（FastAPI）。

本包对外只暴露 `app.main:app`，内部按职责拆分为：
- `config.py`   ：环境变量与限额配置
- `logging.py`  ：结构化日志
- `protocol.py` ：与 backend 共享的 HTTP + JSON 执行协议
- `security.py` ：执行前的源码静态检查
- `guard.py`    ：注入到子进程内的运行时守卫（禁网/禁危险调用/输出截断）
- `limits.py`   ：资源限额（Linux rlimit / Windows psutil 轮询）与进程树 kill
- `runner.py`   ：落盘 → 执行 → 收集输出 → 组装响应
- `main.py`     ：HTTP 路由
"""

__version__ = "1.0.0"
__all__ = ["__version__"]
