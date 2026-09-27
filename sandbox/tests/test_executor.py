"""沙箱服务自测（pytest）。

覆盖：正常执行、超时、系统命令拦截、敏感路径拦截、输出截断、judge 模式。
运行：`sandbox/.venv/Scripts/python -m pytest sandbox/tests -q`
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import protocol as plab_protocol  # noqa: E402
from app.config import Settings  # noqa: E402
from app.protocol import ExecutionRequest  # noqa: E402
from app.runner import SandboxRunner  # noqa: E402


@pytest.fixture(scope="module")
def runner() -> SandboxRunner:
    """构造使用较小内存限额的执行器。"""
    settings = Settings.from_env()
    settings.default_memory_mb = 256
    settings.max_memory_mb = 512
    settings.static_scan = True
    return SandboxRunner(settings)


def execute(runner: SandboxRunner, code: str, **kwargs) -> object:
    """同步执行一段代码。"""
    return runner.execute(ExecutionRequest(code=code, **kwargs))


def test_hello_world(runner: SandboxRunner) -> None:
    """print 正常输出。"""
    result = execute(runner, 'print("hello world")')
    assert result.status == "success", result.stderr
    assert result.stdout.strip() == "hello world"
    assert result.exit_code == 0


def test_timeout_kills_process(runner: SandboxRunner) -> None:
    """死循环被超时 kill。"""
    result = execute(runner, "while True:\n    pass", timeout_ms=2000)
    assert result.status == "timeout"
    assert result.timed_out is True
    assert result.time_ms < 8000


def test_os_system_blocked(runner: SandboxRunner) -> None:
    """os.system 被拦截（静态检查或运行时守卫）。"""
    result = execute(runner, 'import os\nos.system("echo hacked")')
    assert result.status == "security_error"
    assert "hacked" not in result.stdout


def test_sensitive_path_blocked(runner: SandboxRunner) -> None:
    """敏感路径读取被拦截。"""
    target = "C:/Windows/win.ini" if sys.platform == "win32" else "/etc/passwd"
    result = execute(runner, f'print(open(r"{target}").read())')
    assert result.status == "security_error"


def test_output_truncated(runner: SandboxRunner) -> None:
    """超大输出被截断到上限以内。"""
    result = execute(runner, 'print("A" * 10 ** 7)')
    assert result.truncated is True
    assert len(result.stdout.encode("utf-8")) <= 65536 + 64


def test_judge_mode(runner: SandboxRunner) -> None:
    """judge 模式逐用例比对。"""
    request = ExecutionRequest(
        code="a, b = map(int, input().split())\nprint(a + b)",
        mode="judge",
        test_cases=[
            plab_protocol.TestCaseSpec(id="tc1", input="1 2\n", expected="3"),
            plab_protocol.TestCaseSpec(id="tc2", input="10 20\n", expected="30"),
        ],
    )
    result = runner.execute(request)
    assert result.total_cases == 2
    assert result.passed_cases == 2
    assert result.status == "success"


def test_static_scan_blocks_sensitive_path() -> None:
    """静态检查层：明文绝对路径也应被拦截（不依赖运行时守卫）。"""
    settings = Settings.from_env()
    settings.static_scan = True
    local = SandboxRunner(settings)
    target = "C:/Windows/win.ini" if sys.platform == "win32" else "/etc/passwd"
    result = local.execute(ExecutionRequest(code=f'print(open(r"{target}").read())'))
    assert result.status == "security_error"


def test_runtime_guard_blocks_when_static_scan_off() -> None:
    """运行时守卫层：关掉静态检查后，敏感路径与 shell 调用仍被拦。"""
    settings = Settings.from_env()
    settings.static_scan = False
    local = SandboxRunner(settings)
    sensitive = "C:/Windows/win.ini" if sys.platform == "win32" else "/etc/passwd"

    path_result = local.execute(ExecutionRequest(code=f'print(open(r"{sensitive}").read())'))
    assert path_result.status == "security_error", path_result.stderr

    shell_result = local.execute(
        ExecutionRequest(code='import os\nos.system("echo hacked")')
    )
    assert shell_result.status == "security_error", shell_result.stderr
    assert "hacked" not in shell_result.stdout


def test_import_blacklist_and_reload_blocked(runner: SandboxRunner) -> None:
    """导入黑名单与 importlib 重载均被守卫拦截。"""
    blocked_import = runner.execute(ExecutionRequest(code="import subprocess\nprint('x')"))
    assert blocked_import.status == "security_error"

    reload_attempt = runner.execute(
        ExecutionRequest(code="import importlib, os\nimportlib.reload(os)\nos.system('echo hi')")
    )
    assert reload_attempt.status == "security_error"
    assert "hi" not in reload_attempt.stdout


def test_multifile_project_run(runner: SandboxRunner) -> None:
    """多文件项目：子目录模块可被入口文件导入。"""
    request = ExecutionRequest(
        mode="run",
        entry="main.py",
        files=[
            plab_protocol.FileSpec(path="main.py", content="from utils.helper import add\nprint(add(2, 3))"),
            plab_protocol.FileSpec(path="utils/__init__.py", content=""),
            plab_protocol.FileSpec(path="utils/helper.py", content="def add(a, b):\n    return a + b"),
        ],
    )
    result = runner.execute(request)
    assert result.status == "success", result.stderr
    assert result.stdout.strip() == "5"


def test_path_traversal_rejected(runner: SandboxRunner) -> None:
    """路径遍历与非 python 语言被拒绝。"""
    traversal = runner.execute(
        ExecutionRequest(files=[plab_protocol.FileSpec(path="../escape.py", content="print(1)")])
    )
    assert traversal.status == "internal_error"

    language = runner.execute(ExecutionRequest(code="print(1)", language="javascript"))
    assert language.status == "runtime_error"
    assert language.error is not None and language.error.type == "BAD_REQUEST"


def test_health_async_smoke() -> None:
    """HTTP 层冒烟：/health 返回 security_level。"""
    httpx = pytest.importorskip("httpx")
    from app.main import app  # noqa: PLC0415

    async def call() -> dict:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")
            assert response.status_code == 200
            return response.json()

    payload = asyncio.run(call())
    assert payload["status"] == "ok"
    assert payload["security_level"] in ("hardened", "degraded")
