"""PYTHON LAB 独立沙箱服务 HTTP 入口。

路由：
- `GET  /health`  服务与安全能力自检（含 `security_level`）
- `GET  /limits`  当前限额与静态规则清单
- `POST /execute` 规范执行入口（ARCHITECTURE.md 协议）
- `POST /run`     `/execute` 的 run 模式别名（`mode` 强制为 run）
- `POST /judge`   `/execute` 的 judge 模式别名（批量跑测试用例）

⚠️ 本服务只提供「受限执行」，**不是安全边界**；生产必须运行在容器中
（见 docs/SANDBOX.md）。
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import __version__, security
from .config import Settings
from .logging import get_logger, setup_logging
from .protocol import ExecutionRequest, ExecutionResponse
from .runner import SandboxRunner

settings = Settings.from_env()
setup_logging(settings.log_level)
LOGGER = get_logger("sandbox.main")

runner: SandboxRunner = SandboxRunner(settings)
STARTED_AT = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """启动/关闭钩子：打印安全等级与平台能力。"""
    snapshot = runner.health_snapshot()
    LOGGER.info(
        "sandbox ready level=%s platform=%s network_isolation=%s port=%s",
        snapshot["security_level"],
        snapshot["capabilities"].get("platform"),
        runner.network_isolation,
        settings.port,
    )
    if snapshot["security_level"] != "hardened":
        LOGGER.warning(
            "security_level=degraded：当前平台无 rlimit/cgroup，"
            "仅超时 kill + 输出截断 + 运行时守卫，禁止用于生产"
        )
    yield
    LOGGER.info("sandbox shutdown")


app = FastAPI(
    title="PYTHON LAB Sandbox",
    description="独立受限代码执行服务（run / judge）",
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_request_id(request: Request, call_next: Any) -> Any:
    """为每个请求附加 `X-Request-Id`，便于跨服务排查。"""
    request_id = request.headers.get("x-request-id", "")
    response = await call_next(request)
    if request_id:
        response.headers["X-Request-Id"] = request_id
    return response


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """把参数类异常收敛为 400 + 统一结构。"""
    return JSONResponse(
        status_code=400,
        content={
            "success": False,
            "data": None,
            "message": str(exc),
            "error": {"code": "BAD_REQUEST", "details": None},
        },
    )


@app.get("/")
def root() -> Dict[str, Any]:
    """服务元信息。"""
    return {
        "service": settings.service_name,
        "version": __version__,
        "docs": "/docs",
        "endpoints": ["/health", "/limits", "/execute", "/run", "/judge"],
    }


@app.get("/health")
def health() -> Dict[str, Any]:
    """健康检查：暴露安全等级、平台能力与限额（backend `runner.ok` 依据）。"""
    snapshot = runner.health_snapshot()
    capabilities = dict(snapshot["capabilities"])
    capabilities["network_isolation"] = runner.network_isolation != "none" or bool(
        capabilities.get("network_isolation")
    )
    return {
        "status": "ok",
        "service": settings.service_name,
        "version": __version__,
        "runner": "sandbox",
        "security_level": snapshot["security_level"],
        "degraded": snapshot["security_level"] != "hardened",
        "platform": capabilities.get("platform"),
        "python": capabilities.get("python"),
        "capabilities": capabilities,
        "limits": snapshot["limits"],
        "uptime_s": round(time.time() - STARTED_AT, 3),
        "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


@app.get("/limits")
def limits() -> Dict[str, Any]:
    """当前生效的限额与静态检查规则。"""
    return {
        "limits": settings.limits_snapshot(),
        "import_mode": settings.import_mode,
        "blocked_imports": list(settings.blocked_imports),
        "static_rules": security.rule_names(),
        "judge": {
            "max_test_cases": settings.max_test_cases,
            "total_budget_ms": settings.judge_total_budget_ms,
        },
    }


@app.post("/execute", response_model=ExecutionResponse)
def execute(payload: ExecutionRequest) -> ExecutionResponse:
    """规范执行入口（run / judge 由 `mode` 决定）。"""
    return runner.execute(payload)


@app.post("/run", response_model=ExecutionResponse)
def run(payload: ExecutionRequest) -> ExecutionResponse:
    """单次运行别名：强制 `mode=run`。"""
    payload.mode = "run"
    return runner.execute(payload)


@app.post("/judge", response_model=ExecutionResponse)
def judge(payload: ExecutionRequest) -> ExecutionResponse:
    """判题别名：强制 `mode=judge`（无测试用例时自动退化为单次运行）。"""
    payload.mode = "judge" if payload.test_cases else "run"
    return runner.execute(payload)


def main() -> None:
    """`python -m app.main` 启动入口。"""
    import uvicorn  # noqa: PLC0415 - 仅 CLI 启动时需要

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        workers=1,
    )


if __name__ == "__main__":
    main()
