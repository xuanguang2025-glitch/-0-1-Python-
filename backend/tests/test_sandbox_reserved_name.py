"""保留文件名绕过回归测试（P0）+ 目录逃逸拦截（P1）。

背景：AST 白名单修复**引入了一个新 P0** —— `scan_source` 的 `skip_paths` 曾把整个
`RESERVED_FILENAMES` 按 basename 跳过，于是把载荷写进 `_plab_guard.py` 并以其为
入口即可完全跳过 AST 校验。同一载荷放在 `main.py` 会被拦，只改文件名就能越权执行
系统命令、读写任意文件、`os.chdir('..')` 逃逸工作目录（QA 已由 team-lead 复现，
证据脚本见 `scripts/security/qa_reserved_name.py` / `scripts/security/qa_ast_confirm.py`）。

本文件锁定的防线（从外到内）：

1. **schema 层**：`RunRequest` 拒绝保留名 → HTTP 400 `INVALID_PATH`；
2. **路径校验层**：`validate_relative_path` 拒绝保留名 → 400（覆盖判题 / 项目运行
   等所有触达执行器的入口，单点 choke）；
3. **执行器层**：`scan_source` 只跳过引导文件 `__plab_boot__.py`，`_plab_guard.py`
   照常 AST 校验 → `security_error` 且无输出；
4. **AST 层**：`check_files` 对保留名内容照常判定（含 `from os import chdir` 别名形态）。

同时锁定 P1 目录逃逸：`os.chdir('..')`、`os.makedirs` / `os.mkdir`、
`Path('../x').write_text()`、`Path('C:/...')`，并保证正常教学代码不误杀
（`Path('out.txt')`、`os.getcwd()`、`Path('sub').mkdir()`）。
"""

from __future__ import annotations

import sys
from typing import Any

from fastapi.testclient import TestClient
import pytest

from app.api.endpoints import editor
from app.core.errors import AppError, ErrorCode
from app.sandbox.ast_guard import check_files, check_source
from app.sandbox.protocol import (
    LOCAL_BOOTSTRAP_NAME,
    RESERVED_FILENAMES,
    SandboxFile,
    SandboxRequest,
)
from app.sandbox.runner import LocalRunner, scan_source
from app.services.sandbox_client import SandboxClient
from app.utils.validators import validate_relative_path

#: 仅挂载 /api/python/run 所在 router
RUN_ROUTERS = (editor.python_router,)

#: 平台相关的敏感绝对路径（Windows 用 win.ini，POSIX 用 /etc/passwd）
SENSITIVE_ABS: str = "C:/Windows/win.ini" if sys.platform == "win32" else "/etc/passwd"

#: QA 实测的保留名载荷：系统命令 + 逃逸 + 任意文件读写的组合
RESERVED_PAYLOAD = (
    "import os\n"
    "print('PWNED_VIA_RESERVED_NAME')\n"
    "os.chdir('..')\n"
    f"print(open({SENSITIVE_ABS!r}).read()[:20])\n"
)

#: 需要「照常 AST 校验」的保留名（引导文件由系统生成且每次覆盖，不在此列）
SCANNED_RESERVED_NAMES: tuple[str, ...] = tuple(
    sorted(name for name in RESERVED_FILENAMES if name != LOCAL_BOOTSTRAP_NAME)
)


# --------------------------------------------------------------------- 夹具
@pytest.fixture()
def api(client_factory, db, user_headers) -> tuple[TestClient, dict[str, str]]:
    """`/api/python/run` 客户端 + 普通用户鉴权头。"""
    return client_factory(RUN_ROUTERS), user_headers


def _post_run(client: TestClient, headers: dict[str, str], payload: dict[str, Any]) -> Any:
    """POST /api/python/run 并返回原始响应（调用方断言状态码）。"""
    return client.post("/api/python/run", json=payload, headers=headers)


# ------------------------------------------------------- 防线 1：schema 层 400
@pytest.mark.parametrize("name", sorted(RESERVED_FILENAMES))
def test_schema_rejects_reserved_filenames(name: str) -> None:
    """`RunRequest` 必须拒绝保留名（payload 本身无害，拒绝理由是「名字被占用」）。"""
    from app.schemas.sandbox import RunRequest

    with pytest.raises(AppError) as exc_info:
        RunRequest(files=[{"path": name, "content": "print(1)"}], entry=name)
    assert exc_info.value.code == ErrorCode.INVALID_PATH
    assert exc_info.value.status_code == 400
    assert name in str(exc_info.value.details or "")


def test_schema_allows_ordinary_filenames() -> None:
    """普通文件名不受影响（防止修复过度，把正常提交也拒了）。"""
    from app.schemas.sandbox import RunRequest

    request = RunRequest(
        files=[{"path": "utils/helper.py", "content": "def add(a, b):\n    return a + b\n"}],
        entry="main.py",
    )
    assert [item.path for item in request.files] == ["utils/helper.py"]


# ------------------------------------------------------- 防线 2：API 层 400
@pytest.mark.parametrize("name", sorted(RESERVED_FILENAMES))
def test_api_rejects_reserved_filename_with_400(api, name: str) -> None:
    """走真实 HTTP 链路：保留名必须在入口处被 400 拒绝，且载荷绝不执行。"""
    client, headers = api
    response = _post_run(
        client,
        headers,
        {"files": [{"path": name, "content": RESERVED_PAYLOAD}], "entry": name},
    )
    assert response.status_code == 400, response.text
    body = response.json()
    assert body["error"]["code"] == ErrorCode.INVALID_PATH
    assert body["success"] is False
    # 拒绝发生在执行之前：没有任何执行结果字段
    assert body["data"] is None
    assert "PWNED_VIA_RESERVED_NAME" not in response.text


def test_api_reserved_name_in_multifile_project_rejected(api) -> None:
    """保留名混在多文件项目里同样被拒（不能靠加一个正常 main.py 夹带）。"""
    client, headers = api
    response = _post_run(
        client,
        headers,
        {
            "files": [
                {"path": "main.py", "content": "print('hello')\n"},
                {"path": "_plab_guard.py", "content": RESERVED_PAYLOAD},
            ]
        },
    )
    assert response.status_code == 400, response.text
    assert response.json()["error"]["code"] == ErrorCode.INVALID_PATH


# ------------------------------------------------- 防线 2b：路径校验层 400
@pytest.mark.parametrize("name", sorted(RESERVED_FILENAMES))
def test_validate_relative_path_rejects_reserved_names(name: str) -> None:
    """`validate_relative_path` 是判题 / 项目运行 / 代码快照的共同入口，也必须拒绝。"""
    with pytest.raises(AppError) as exc_info:
        validate_relative_path(name)
    assert exc_info.value.code == ErrorCode.INVALID_PATH
    assert exc_info.value.status_code == 400


@pytest.mark.parametrize("name", sorted(RESERVED_FILENAMES))
def test_sandbox_client_rejects_reserved_names(name: str) -> None:
    """`SandboxClient`（所有上层服务的执行入口）对保留名抛 400 语义的 AppError。"""
    client = SandboxClient(mode="local")
    with pytest.raises(AppError) as exc_info:
        client.run({name: RESERVED_PAYLOAD}, entry=name)
    assert exc_info.value.code == ErrorCode.INVALID_PATH
    assert exc_info.value.status_code == 400


# --------------------------------------------- 防线 3：执行器层照常 AST 校验
@pytest.mark.parametrize("name", SCANNED_RESERVED_NAMES)
def test_local_runner_scans_reserved_names(name: str) -> None:
    """即使绕过 schema / 客户端层，执行器也必须拦下保留名里的载荷。"""
    request = SandboxRequest(
        request_id="test-reserved",
        files=[SandboxFile(path=name, content=RESERVED_PAYLOAD)],
        entry=name,
    )
    response = LocalRunner().run(request)
    assert response.status == "security_error", f"{name}: {response.stdout!r}"
    assert response.stdout == ""
    assert "PWNED_VIA_RESERVED_NAME" not in (response.stdout or "")
    # 载荷故意含多种违规（chdir / 绝对路径读），命中任意一条即算拦截成功
    assert response.error and any(
        rule in response.error for rule in ("dangerous_attribute", "dangerous_module_attribute", "open_absolute_path")
    ), response.error


def test_runner_only_skips_bootstrap_file() -> None:
    """`scan_source` 的免检集合只剩引导文件；保留名出现在 files 里即被拦。"""
    violation = scan_source(
        {"_plab_guard.py": "import os\nos.system('echo PWNED_VIA_RESERVED_NAME')\n", "main.py": "print('ok')\n"},
        skip_paths={LOCAL_BOOTSTRAP_NAME},
    )
    assert violation is not None
    assert violation.rule == "dangerous_attribute"
    assert violation.filename == "_plab_guard.py"


def test_bootstrap_file_still_skipped() -> None:
    """引导文件仍免检：它含 `runpy.run_path` 等非白名单 import，是系统生成代码。"""
    from app.services.sandbox_local import bootstrap_code

    files = {"main.py": "print('ok')\n", LOCAL_BOOTSTRAP_NAME: bootstrap_code("main.py")}
    assert scan_source(files, skip_paths={LOCAL_BOOTSTRAP_NAME}) is None


# ------------------------------------------------------- 防线 4：AST 单元层
def test_ast_guard_validates_reserved_name_content() -> None:
    """`check_files` 对保留名内容照常判定（QA 的决定性载荷）。"""
    violation = check_files(
        {"_plab_guard.py": "import os\nos.system('echo PWNED_VIA_RESERVED_NAME')\n"},
        skip_paths={LOCAL_BOOTSTRAP_NAME},
    )
    assert violation is not None
    assert violation.rule == "dangerous_attribute"


def test_ast_guard_validates_absolute_read_in_reserved_name() -> None:
    """保留名里的任意文件读同样被拦（`open('C:/Windows/win.ini')`）。"""
    violation = check_files(
        {"_plab_guard.py": f"print(open({SENSITIVE_ABS!r}).read())\n"},
        skip_paths={LOCAL_BOOTSTRAP_NAME},
    )
    assert violation is not None
    assert violation.rule == "open_absolute_path"


# --------------------------------------------------------- P1：目录逃逸拦截
ESCAPE_CASES: list[tuple[str, str, str]] = [
    ("chdir_parent", "import os\nos.chdir('..')\nprint('escaped')\n", "dangerous_module_attribute"),
    ("chdir_abs", "import os\nos.chdir('C:/')\n", "dangerous_module_attribute"),
    ("makedirs_parent", "import os\nos.makedirs('../qa_escape_dir', exist_ok=True)\n", "dangerous_module_attribute"),
    ("mkdir_parent", "import os\nos.mkdir('../qa_escape_dir')\n", "dangerous_module_attribute"),
    ("from_os_import_chdir", "from os import chdir\nchdir('..')\n", "import_dangerous_name"),
    ("from_os_import_makedirs", "from os import makedirs\nmakedirs('../d')\n", "import_dangerous_name"),
    (
        "pathlib_parent_write",
        "from pathlib import Path\nPath('../qa_escape_proof2.txt').write_text('x')\n",
        "path_constructor_escape",
    ),
    (
        "pathlib_abs_read",
        f"from pathlib import Path\nPath({SENSITIVE_ABS!r}).read_text()\n",
        "path_literal",
    ),
    (
        "pathlib_alias_parent",
        "import pathlib as pl\npl.Path('../x').write_text('y')\n",
        "path_constructor_escape",
    ),
]


@pytest.mark.parametrize("name,code,rule", ESCAPE_CASES)
def test_ast_guard_blocks_directory_escape(name: str, code: str, rule: str) -> None:
    """每种目录逃逸手法都必须命中预期规则。"""
    violation = check_source(code, filename="main.py")
    assert violation is not None, f"{name} 未被拦截"
    assert violation.rule == rule, f"{name} 规则不符: {violation.describe()}"


@pytest.mark.parametrize("name,code,rule", ESCAPE_CASES)
def test_local_runner_blocks_directory_escape(name: str, code: str, rule: str) -> None:
    """执行器直连路径同样拒绝逃逸（不经 HTTP 也不能绕过）。"""
    request = SandboxRequest(
        request_id="test-escape",
        files=[SandboxFile(path="main.py", content=code)],
        entry="main.py",
    )
    response = LocalRunner().run(request)
    assert response.status == "security_error", f"{name}: {response.stdout!r}"
    assert response.stdout == ""
    assert response.error and rule in response.error


@pytest.mark.parametrize("name,code,rule", ESCAPE_CASES)
def test_api_blocks_directory_escape(api, name: str, code: str, rule: str) -> None:
    """真实 HTTP 链路同样拒绝逃逸。"""
    client, headers = api
    response = _post_run(client, headers, {"files": [{"path": "main.py", "content": code}]})
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "security_error", f"{name}: {data}"
    assert data["stdout"] == ""


# ------------------------------------------------- 正常教学代码不得被误杀
def test_api_relative_path_constructor_runs(api) -> None:
    """`Path('out.txt')` 相对路径构造 + write_text/read_text 必须照常执行。"""
    client, headers = api
    code = (
        "from pathlib import Path\n"
        "p = Path('out.txt')\n"
        "p.write_text('hello-path')\n"
        "print(p.read_text())\n"
        "print(p.exists())\n"
    )
    response = _post_run(client, headers, {"files": [{"path": "main.py", "content": code}]})
    data = response.json()["data"]
    assert data["status"] == "success", data
    assert data["stdout"].splitlines()[:2] == ["hello-path", "True"]


def test_api_path_mkdir_runs(api) -> None:
    """`os.mkdir` 被拦后的正当出口：`Path('sub').mkdir()`（工作目录内）必须可用。"""
    client, headers = api
    code = (
        "from pathlib import Path\n"
        "Path('sub').mkdir()\n"
        "print(Path('sub').is_dir())\n"
        "print(sorted(p.name for p in Path('.').iterdir()))\n"
    )
    response = _post_run(client, headers, {"files": [{"path": "main.py", "content": code}]})
    data = response.json()["data"]
    assert data["status"] == "success", data
    assert data["stdout"].splitlines()[0] == "True"


def test_api_os_getcwd_runs(api) -> None:
    """`os.getcwd()` 是合法教学内容（`os.chdir` 被拦不能顺带误杀它）。"""
    client, headers = api
    response = _post_run(
        client, headers, {"files": [{"path": "main.py", "content": "import os\nprint(os.getcwd() != '')\n"}]}
    )
    data = response.json()["data"]
    assert data["status"] == "success", data
    assert data["stdout"].strip() == "True"


def test_ast_guard_allows_learner_pathlib_code() -> None:
    """常见 pathlib 写法（相对路径 / iterdir / joinpath）不得被误杀。"""
    for code in [
        "from pathlib import Path\nprint(Path('a') / 'b')\n",
        "from pathlib import Path\nprint(Path('data.txt').exists())\n",
        "from pathlib import Path\nprint(sorted(p.name for p in Path('.').iterdir()))\n",
        "from pathlib import Path\nprint(Path('.').joinpath('x.py').suffix)\n",
        "from pathlib import Path\nPath('sub').mkdir(exist_ok=True)\n",
    ]:
        violation = check_source(code, filename="main.py")
        assert violation is None, f"误杀: {violation.describe() if violation else ''} <- {code!r}"
