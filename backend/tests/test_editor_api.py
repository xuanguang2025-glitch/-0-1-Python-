"""编辑器与项目链路集成测试（`docs/API.md` §2.8、§2.9、§2.19）。

覆盖：多文件项目 CRUD、路径遍历拒绝、跨文件 import 的运行、代码历史快照 /
恢复 / 版本对比 / 删除。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.models  # noqa: F401 - 触发全部模型注册
from app.api.endpoints import bookmarks, code_history, editor, mistakes, problems, projects, submissions
from app.core.security import create_access_token
from app.models.enums import ProblemCategory
from app.models.project import Project, ProjectFile
from app.models.user import User

MULTI_FILE_MAIN = "from utils import add\nprint(add(1, 2))"
MULTI_FILE_UTILS = "def add(a, b):\n    return a + b"


#: 本域需要挂载的路由（含 /api/python/run 所在的 python_router）。
EDITOR_ROUTERS = (
    problems.router,
    submissions.router,
    editor.router,
    projects.router,
    bookmarks.router,
    mistakes.router,
    code_history.router,
    editor.python_router,
)


@pytest.fixture()
def harness(session_factory, client_factory, seeded_users):
    """复用统一基座：每用例独立内存库 + 会话级缓存 App + 本机执行器。"""
    ids = _seed(session_factory)
    ids["user_id"] = seeded_users.user_id
    client = client_factory(EDITOR_ROUTERS)
    yield {"client": client, "session": session_factory, "ids": ids}


def _seed(TestSession) -> dict:
    """写入多文件项目模板（用户由基座 `seeded_users` 提供）。"""
    db = TestSession()
    try:
        project = Project(
            slug="multi-file-demo",
            title="多文件项目演示",
            summary="跨文件 import",
            description_md="演示多文件项目。",
            level=1,
            category=ProblemCategory.BASICS.value,
            xp_reward=100,
            steps_json=[{"title": "创建工具模块", "detail": "写 utils.py", "done_hint": "可导入"}],
        )
        db.add(project)
        db.flush()
        db.add_all(
            [
                ProjectFile(project_id=project.id, path="main.py", content="# TODO", is_entry=True, order_index=0),
                ProjectFile(project_id=project.id, path="utils.py", content="", order_index=1),
                ProjectFile(
                    project_id=project.id, path="README.md", content="说明", is_readonly=True, order_index=2
                ),
            ]
        )
        db.commit()
        return {"project_id": project.id}
    finally:
        db.close()


def _auth(client: TestClient, session, user_id: str) -> dict[str, str]:
    """生成 Bearer Token。"""
    db = session()
    try:
        user = db.get(User, user_id)
        token, _jti, _exp = create_access_token(user.id, role=user.role, username=user.username)
    finally:
        db.close()
    return {"Authorization": f"Bearer {token}"}


# ------------------------------------------------------------------ 项目
def test_project_list_and_detail(harness) -> None:
    """项目列表与详情（模板文件 / 步骤）。"""
    client, ids = harness["client"], harness["ids"]
    listed = client.get("/api/projects")
    assert listed.json()["data"]["total"] == 1
    detail = client.get(f"/api/projects/{ids['project_id']}")
    data = detail.json()["data"]
    assert len(data["files"]) == 3
    assert data["steps"][0]["title"] == "创建工具模块"


def test_project_start_and_files_crud(harness) -> None:
    """Fork 模板 → 读写文件 → 我的项目反映最新内容。"""
    client, session, ids = harness["client"], harness["session"], harness["ids"]
    headers = _auth(client, session, ids["user_id"])
    pid = ids["project_id"]

    started = client.post(f"/api/projects/{pid}/start", headers=headers)
    assert started.status_code == 200
    assert started.json()["data"]["files_json"]["main.py"] == "# TODO"

    updated = client.put(
        f"/api/projects/{pid}/files",
        json={"files": {"main.py": MULTI_FILE_MAIN, "utils.py": MULTI_FILE_UTILS}},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["files_json"]["utils.py"] == MULTI_FILE_UTILS

    mine = client.get(f"/api/projects/{pid}/my", headers=headers)
    assert mine.json()["data"]["files_json"]["main.py"] == MULTI_FILE_MAIN


def test_project_run_cross_file_import(harness) -> None:
    """多文件项目运行：跨文件 import 生效。"""
    client, session, ids = harness["client"], harness["session"], harness["ids"]
    headers = _auth(client, session, ids["user_id"])
    pid = ids["project_id"]
    client.post(f"/api/projects/{pid}/start", headers=headers)
    client.put(
        f"/api/projects/{pid}/files",
        json={"files": {"main.py": MULTI_FILE_MAIN, "utils.py": MULTI_FILE_UTILS}},
        headers=headers,
    )
    resp = client.post(f"/api/projects/{pid}/run", json={}, headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "success"
    assert data["stdout"].strip() == "3"


def test_project_submit_marks_completed(harness) -> None:
    """提交项目：入口可运行 → 完成并发放 XP。"""
    client, session, ids = harness["client"], harness["session"], harness["ids"]
    headers = _auth(client, session, ids["user_id"])
    pid = ids["project_id"]
    client.post(f"/api/projects/{pid}/start", headers=headers)
    client.put(
        f"/api/projects/{pid}/files",
        json={"files": {"main.py": MULTI_FILE_MAIN, "utils.py": MULTI_FILE_UTILS}},
        headers=headers,
    )
    resp = client.post(f"/api/projects/{pid}/submit", json={"notes_md": "完成"}, headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["user_project"]["status"] == "completed"
    assert data["xp_earned"] == 100


# -------------------------------------------------------------- 路径安全
def test_project_path_traversal_rejected(harness) -> None:
    """写入文件时的路径遍历必须被拒绝。"""
    client, session, ids = harness["client"], harness["session"], harness["ids"]
    headers = _auth(client, session, ids["user_id"])
    pid = ids["project_id"]
    client.post(f"/api/projects/{pid}/start", headers=headers)

    for bad_path in ("../../etc/passwd", "/etc/passwd", "sub/../../secret.py"):
        resp = client.put(
            f"/api/projects/{pid}/files",
            json={"files": {bad_path: "hack"}},
            headers=headers,
        )
        assert resp.status_code == 400, bad_path
        assert resp.json()["error"]["code"] == "INVALID_PATH"


def test_readonly_template_file_protected(harness) -> None:
    """只读模板文件禁止写入。"""
    client, session, ids = harness["client"], harness["session"], harness["ids"]
    headers = _auth(client, session, ids["user_id"])
    resp = client.put(
        f"/api/projects/{ids['project_id']}/files",
        json={"files": {"README.md": "篡改"}},
        headers=headers,
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_PATH"


def test_editor_snapshot_path_traversal_rejected(harness) -> None:
    """代码快照保存时的路径遍历必须被拒绝。"""
    client, session, ids = harness["client"], harness["session"], harness["ids"]
    headers = _auth(client, session, ids["user_id"])
    resp = client.post(
        "/api/editor/save-snapshot",
        json={"context_type": "playground", "file_path": "../../evil.py", "code": "print(1)"},
        headers=headers,
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_PATH"


# -------------------------------------------------------------- 代码历史
def test_code_history_snapshot_restore_compare_delete(harness) -> None:
    """代码历史：快照 → 列表 → 详情 → 对比 → 恢复 → 删除。"""
    client, session, ids = harness["client"], harness["session"], harness["ids"]
    headers = _auth(client, session, ids["user_id"])

    first = client.post(
        "/api/editor/save-snapshot",
        json={"context_type": "playground", "file_path": "main.py", "code": "a = 1", "label": "v1"},
        headers=headers,
    ).json()["data"]
    second = client.post(
        "/api/editor/save-snapshot",
        json={"context_type": "playground", "file_path": "main.py", "code": "a = 2", "label": "v2"},
        headers=headers,
    ).json()["data"]
    assert first["version_no"] == 1
    assert second["version_no"] == 2

    listed = client.get("/api/editor/history", params={"context_type": "playground"}, headers=headers)
    assert listed.json()["data"]["total"] == 2

    detail = client.get(f"/api/editor/history/{first['id']}", headers=headers)
    assert detail.json()["data"]["code"] == "a = 1"

    compared = client.post(
        "/api/editor/compare",
        json={"left_id": first["id"], "right_id": second["id"]},
        headers=headers,
    )
    body = compared.json()["data"]
    assert "-a = 1" in body["diff_text"]
    assert "+a = 2" in body["diff_text"]
    assert body["hunks"]

    restored = client.post(f"/api/editor/history/{first['id']}/restore", headers=headers)
    restored_data = restored.json()["data"]
    assert restored_data["code"] == "a = 1"
    assert restored_data["version_no"] == 3

    deleted = client.delete(f"/api/editor/history/{second['id']}", headers=headers)
    assert deleted.status_code == 200
    gone = client.get(f"/api/editor/history/{second['id']}", headers=headers)
    assert gone.status_code == 404


def test_code_history_isolation(harness) -> None:
    """代码历史在 /code-history 与 /editor 之间共用同一份数据。"""
    client, session, ids = harness["client"], harness["session"], harness["ids"]
    headers = _auth(client, session, ids["user_id"])
    client.post(
        "/api/editor/save-snapshot",
        json={"context_type": "problem", "context_id": "p-1", "file_path": "solution.py", "code": "print(1)\n"},
        headers=headers,
    )
    listed = client.get("/api/code-history", headers=headers)
    assert listed.json()["data"]["total"] == 1
    assert listed.json()["data"]["items"][0]["file_path"] == "solution.py"
