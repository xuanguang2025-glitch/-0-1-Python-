"""管理端 API 测试（`tests/test_admin_api.py`）。

覆盖 `docs/API.md` §2.22 全部 53 个 operation，重点是 admin 域的高风险面：

- **越权重灾区**：53 个 operation 逐一验证「普通用户 403 / 未登录 401」；
- **密钥不回显**：AI 全局配置与模型配置的 `api_key` 写入后读取必须脱敏（`sk-****last4`）；
- **软删除语义**：`DELETE /admin/users/{id}` 后无法登录，且数据库行仍在（软删非物理删）；
- **审计留痕**：写操作在 `audit_logs` 留痕并可按 action / actor 检索；
- **批量导入边界**：空数组、缺 slug、非法 JSON 三类输入的 `failed[]` 语义。

已知业务缺陷（详见交付报告，测试中以 `BUG-x` 标注并钉住当前状态，修复时会立即失败提醒）：

- `BUG-1`：`POST /admin/test-cases` 恒 500（`AdminTestCaseIn` 缺 `problem_id`，而
  `TestCase.problem_id` 为 NOT NULL，且 `StrictModel` 禁止额外字段）。
- `BUG-2`：`POST /admin/problems/import` 传非法 JSON 恒 500（应为 4xx）。
- `BUG-3`：`import_problems` 对含 `title` 的条目 100% 失败
  （`Problem() got multiple values for keyword argument 'title'`）。
- `BUG-4`：`PUT /admin/ai-config` 的 `provider/model/temperature` 等写入
  `system_settings` 但读回走 app settings，改动不生效（`api_key`/`prompt_overrides` 正常）。
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.endpoints import admin as admin_endpoint
from app.api.endpoints import auth as auth_endpoint
from app.core.security import verify_password
from app.models.ai import AIModelConfig
from app.models.course import Course
from app.models.problem import TestCase
from app.models.submission import Submission
from app.models.system import AuditLog
from app.models.user import User

RAW_KEY = "sk-secret-abcdef1234"
RAW_SETTING_KEY = "sk-super-secret-1234"
RAW_AI_CONFIG_KEY = "sk-global-config-9876"
RAW_MODEL_KEY = "sk-model-key-4321"
NEW_PASSWORD = "Brand@12345"

#: admin 域全部 operation（方法, 路径模板），共 53 条，用于越权矩阵。
ADMIN_OPS: tuple[tuple[str, str], ...] = (
    ("GET", "/api/admin/ai-config"),
    ("PUT", "/api/admin/ai-config"),
    ("GET", "/api/admin/announcements"),
    ("POST", "/api/admin/announcements"),
    ("PATCH", "/api/admin/announcements/{announcement_id}"),
    ("DELETE", "/api/admin/announcements/{announcement_id}"),
    ("POST", "/api/admin/chapters"),
    ("PATCH", "/api/admin/chapters/{chapter_id}"),
    ("DELETE", "/api/admin/chapters/{chapter_id}"),
    ("GET", "/api/admin/courses"),
    ("POST", "/api/admin/courses"),
    ("PATCH", "/api/admin/courses/{course_id}"),
    ("DELETE", "/api/admin/courses/{course_id}"),
    ("GET", "/api/admin/dashboard"),
    ("POST", "/api/admin/lessons"),
    ("PATCH", "/api/admin/lessons/{lesson_id}"),
    ("DELETE", "/api/admin/lessons/{lesson_id}"),
    ("GET", "/api/admin/logs/ai-usage"),
    ("GET", "/api/admin/logs/audit"),
    ("GET", "/api/admin/logs/errors"),
    ("GET", "/api/admin/logs/sessions"),
    ("POST", "/api/admin/maintenance/rejudge"),
    ("GET", "/api/admin/models"),
    ("POST", "/api/admin/models"),
    ("PATCH", "/api/admin/models/{model_id}"),
    ("DELETE", "/api/admin/models/{model_id}"),
    ("POST", "/api/admin/models/{model_id}/test"),
    ("GET", "/api/admin/problems"),
    ("POST", "/api/admin/problems"),
    ("POST", "/api/admin/problems/import"),
    ("PATCH", "/api/admin/problems/{problem_id}"),
    ("DELETE", "/api/admin/problems/{problem_id}"),
    ("POST", "/api/admin/project-files"),
    ("PATCH", "/api/admin/project-files/{file_id}"),
    ("DELETE", "/api/admin/project-files/{file_id}"),
    ("GET", "/api/admin/projects"),
    ("POST", "/api/admin/projects"),
    ("PATCH", "/api/admin/projects/{project_id}"),
    ("DELETE", "/api/admin/projects/{project_id}"),
    ("GET", "/api/admin/settings"),
    ("PUT", "/api/admin/settings/{key}"),
    ("GET", "/api/admin/tags"),
    ("POST", "/api/admin/tags"),
    ("PATCH", "/api/admin/tags/{tag_id}"),
    ("DELETE", "/api/admin/tags/{tag_id}"),
    ("POST", "/api/admin/test-cases"),
    ("PATCH", "/api/admin/test-cases/{case_id}"),
    ("DELETE", "/api/admin/test-cases/{case_id}"),
    ("GET", "/api/admin/users"),
    ("POST", "/api/admin/users"),
    ("PATCH", "/api/admin/users/{user_id}"),
    ("DELETE", "/api/admin/users/{user_id}"),
    ("POST", "/api/admin/users/{user_id}/reset-password"),
)

#: 越权矩阵里各路径的「合法最小请求体」，确保命中 403 而不是先被 422 拦下。
_OP_BODIES: dict[str, Any] = {
    "/api/admin/announcements": {"title": "矩阵公告"},
    "/api/admin/chapters": {"course_id": "matrix-course", "slug": "matrix-ch", "title": "矩阵章节"},
    "/api/admin/courses": {"slug": "matrix-course", "stage_no": 95, "title": "矩阵课程"},
    "/api/admin/lessons": {"chapter_id": "matrix-chapter", "slug": "matrix-ls", "title": "矩阵课时"},
    "/api/admin/maintenance/rejudge": {},
    "/api/admin/models": {"name": "矩阵模型", "model": "matrix-model"},
    "/api/admin/problems": {"slug": "matrix-problem", "title": "矩阵题目"},
    "/api/admin/project-files": {"project_id": "matrix-project", "path": "main.py"},
    "/api/admin/projects": {"slug": "matrix-project", "title": "矩阵项目"},
    "/api/admin/tags": {"slug": "matrix-tag", "name": "矩阵标签"},
    "/api/admin/test-cases": {"input": "1", "expected_output": "1"},
    "/api/admin/users": {"email": "matrix@pythonlab.dev", "username": "matrixuser", "password": NEW_PASSWORD},
    "/api/admin/users/dummy-user/reset-password": {"new_password": NEW_PASSWORD},
}


def _kwargs_for(url: str) -> dict[str, Any]:
    """按路径给出最小合法请求体（multipart 导入单独处理）。"""
    if url == "/api/admin/problems/import":
        return {"files": {"file": ("m.json", b"[]", "application/json")}}
    if url in _OP_BODIES:
        return {"json": _OP_BODIES[url]}
    return {"json": {}}


def _concrete(url: str) -> str:
    """把路径模板里的占位符替换为哑 id（鉴权依赖先于业务查库，故哑 id 即可）。"""
    if "{" not in url:
        return url
    parts = []
    for segment in url.strip("/").split("/"):
        parts.append("dummy-id" if segment.startswith("{") else segment)
    return "/" + "/".join(parts)


# ---------------------------------------------------------------------------
# 测试夹具（复用 conftest 统一基座：内存 SQLite + 会话级缓存 App）
# ---------------------------------------------------------------------------


@pytest.fixture()
def seeded(db, seeded_users) -> dict[str, Any]:
    """用户由基座 `seeded_users` 提供，这里只需清理本用例域内的历史残留。"""
    for row in db.scalars(
        select(Course).where((Course.slug == "test-admin-course") | (Course.stage_no == 96))
    ).all():
        db.delete(row)
    for model in db.scalars(select(AIModelConfig).where(AIModelConfig.name == "测试模型")).all():
        db.delete(model)
    db.commit()
    return {"admin_id": seeded_users.admin_id, "user_id": seeded_users.user_id}


@pytest.fixture()
def client(client_factory) -> TestClient:
    """测试客户端（只挂载 admin 路由）。"""
    return client_factory([admin_endpoint.router])


@pytest.fixture()
def auth_client(client_factory) -> TestClient:
    """额外挂载 auth 路由的客户端（软删除后无法登录等端到端场景用）。"""
    return client_factory([admin_endpoint.router, auth_endpoint.router])


@pytest.fixture()
def admin_headers(auth_tokens) -> dict[str, str]:
    """管理员认证头。"""
    return {"Authorization": f"Bearer {auth_tokens.admin}"}


@pytest.fixture()
def user_headers(auth_tokens) -> dict[str, str]:
    """普通用户认证头。"""
    return {"Authorization": f"Bearer {auth_tokens.user}"}


# ---------------------------------------------------------------------------
# 造数辅助
# ---------------------------------------------------------------------------


def _new_course(client: TestClient, ah: dict[str, str], slug: str = "adm-course", stage: int = 96) -> str:
    r = client.post(
        "/api/admin/courses",
        json={"slug": slug, "stage_no": stage, "title": "管理端课程", "level": "beginner"},
        headers=ah,
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["id"]


def _new_chapter(client: TestClient, ah: dict[str, str], course_id: str, slug: str = "adm-chapter") -> str:
    r = client.post(
        "/api/admin/chapters",
        json={"course_id": course_id, "slug": slug, "title": "管理端章节"},
        headers=ah,
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["id"]


def _new_lesson(client: TestClient, ah: dict[str, str], chapter_id: str, slug: str = "adm-lesson") -> str:
    r = client.post(
        "/api/admin/lessons",
        json={"chapter_id": chapter_id, "slug": slug, "title": "管理端课时"},
        headers=ah,
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["id"]


def _new_problem(client: TestClient, ah: dict[str, str], slug: str = "adm-problem") -> str:
    r = client.post(
        "/api/admin/problems",
        json={"slug": slug, "title": "管理端题目", "problem_type": "coding", "difficulty": "easy"},
        headers=ah,
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["id"]


# ---------------------------------------------------------------------------
# 权限
# ---------------------------------------------------------------------------


def test_admin_requires_admin(client: TestClient, user_headers: dict[str, str]) -> None:
    """普通用户 403，未登录 401。"""
    forbidden = client.get("/api/admin/dashboard", headers=user_headers)
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "FORBIDDEN"

    unauthorized = client.get("/api/admin/dashboard")
    assert unauthorized.status_code == 401


def test_every_admin_endpoint_forbids_normal_user(client: TestClient, user_headers: dict[str, str]) -> None:
    """越权重灾区：53 个 operation 对普通用户**全部**返回 403（无一例外）。"""
    assert len(ADMIN_OPS) == 53, "admin operation 清单应与路由表一致（53 条）"
    leaked: list[str] = []
    for method, template in ADMIN_OPS:
        url = _concrete(template)
        response = client.request(method, url, headers=user_headers, **_kwargs_for(url))
        if response.status_code != 403:
            leaked.append(f"{method} {template} -> {response.status_code}")
            continue
        if response.json()["error"]["code"] != "FORBIDDEN":
            leaked.append(f"{method} {template} -> 非 FORBIDDEN 错误码")
    assert not leaked, f"以下 admin 端点未正确拒绝普通用户：{leaked}"


def test_every_admin_endpoint_requires_authentication(client: TestClient, db) -> None:
    """未登录访问 53 个 operation 全部 401。"""
    leaked: list[str] = []
    for method, template in ADMIN_OPS:
        url = _concrete(template)
        response = client.request(method, url, **_kwargs_for(url))
        if response.status_code != 401:
            leaked.append(f"{method} {template} -> {response.status_code}")
            continue
        if response.json()["error"]["code"] != "UNAUTHORIZED":
            leaked.append(f"{method} {template} -> 非 UNAUTHORIZED 错误码")
    assert not leaked, f"以下 admin 端点未正确拒绝未登录请求：{leaked}"


def test_dashboard_overview(client: TestClient, admin_headers: dict[str, str]) -> None:
    """仪表盘返回用户 / 提交 / 依赖健康等总览字段。"""
    r = client.get("/api/admin/dashboard", headers=admin_headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    for field in ("users_total", "active_today", "submissions_today", "acceptance_rate",
                  "error_rate", "ai_calls_today", "runner", "db_flavor", "cache_backend"):
        assert field in data, f"仪表盘缺少字段 {field}"
    assert data["users_total"] >= 1


# ---------------------------------------------------------------------------
# 用户管理
# ---------------------------------------------------------------------------


def test_user_create_and_list_with_filters(client: TestClient, admin_headers: dict[str, str], seeded_users) -> None:
    """新建用户后可按关键字 / 角色检索，并支持分页。"""
    created = client.post(
        "/api/admin/users",
        json={"email": "alice@pythonlab.dev", "username": "alice", "password": NEW_PASSWORD,
              "display_name": "爱丽丝"},
        headers=admin_headers,
    )
    assert created.status_code == 200, created.text
    assert created.json()["data"]["email"] == "alice@pythonlab.dev"

    found = client.get("/api/admin/users?q=alice", headers=admin_headers)
    assert found.status_code == 200
    items = found.json()["data"]["items"]
    assert any(item["username"] == "alice" for item in items)

    by_role = client.get("/api/admin/users?role=user", headers=admin_headers)
    assert by_role.status_code == 200
    assert all(item["role"] == "user" for item in by_role.json()["data"]["items"])

    paged = client.get("/api/admin/users?page=1&page_size=1", headers=admin_headers)
    assert paged.status_code == 200
    body = paged.json()["data"]
    assert len(body["items"]) == 1
    assert body["total"] >= 2
    assert body["page"] == 1 and body["page_size"] == 1


def test_user_update_role_and_display_name(client: TestClient, admin_headers: dict[str, str]) -> None:
    """更新用户角色 / 资料即时生效并留痕。"""
    created = client.post(
        "/api/admin/users",
        json={"email": "bob@pythonlab.dev", "username": "bob", "password": NEW_PASSWORD},
        headers=admin_headers,
    )
    uid = created.json()["data"]["id"]

    updated = client.patch(
        f"/api/admin/users/{uid}",
        json={"role": "admin", "display_name": "鲍勃", "is_verified": False},
        headers=admin_headers,
    )
    assert updated.status_code == 200, updated.text
    data = updated.json()["data"]
    assert data["role"] == "admin"
    assert data["display_name"] == "鲍勃"

    logs = client.get("/api/admin/logs/audit?action=admin.user.update", headers=admin_headers)
    assert any(item["action"] == "admin.user.update" for item in logs.json()["data"]["items"])


def test_user_soft_delete_blocks_login(auth_client: TestClient, admin_headers: dict[str, str]) -> None:
    """软删除后该用户无法再登录（凭据正确也拒绝）。"""
    created = auth_client.post(
        "/api/admin/users",
        json={"email": "carol@pythonlab.dev", "username": "carol", "password": NEW_PASSWORD},
        headers=admin_headers,
    )
    assert created.status_code == 200, created.text
    uid = created.json()["data"]["id"]

    ok = auth_client.post("/api/auth/login", json={"account": "carol@pythonlab.dev", "password": NEW_PASSWORD})
    assert ok.status_code == 200, ok.text

    deleted = auth_client.delete(f"/api/admin/users/{uid}", headers=admin_headers)
    assert deleted.status_code == 200

    blocked = auth_client.post("/api/auth/login", json={"account": "carol@pythonlab.dev", "password": NEW_PASSWORD})
    assert blocked.status_code == 401
    assert blocked.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_user_soft_delete_keeps_row(client: TestClient, admin_headers: dict[str, str], db) -> None:
    """软删除是标记而非物理删除：数据库行仍在，且从活跃列表中消失。"""
    created = client.post(
        "/api/admin/users",
        json={"email": "dave@pythonlab.dev", "username": "dave", "password": NEW_PASSWORD},
        headers=admin_headers,
    )
    uid = created.json()["data"]["id"]
    assert client.delete(f"/api/admin/users/{uid}", headers=admin_headers).status_code == 200

    row = db.get(User, uid)
    assert row is not None, "软删除不应物理删除用户行"
    assert row.deleted_at is not None, "软删除应写入 deleted_at 标记"
    assert row.status == "deleted"

    listed = client.get("/api/admin/users?q=dave", headers=admin_headers)
    assert listed.json()["data"]["items"] == []


def test_user_reset_password(client: TestClient, admin_headers: dict[str, str], db) -> None:
    """重置密码后新密码可校验、旧密码失效。"""
    created = client.post(
        "/api/admin/users",
        json={"email": "erin@pythonlab.dev", "username": "erin", "password": NEW_PASSWORD},
        headers=admin_headers,
    )
    uid = created.json()["data"]["id"]

    reset = client.post(
        f"/api/admin/users/{uid}/reset-password",
        json={"new_password": "Reset@654321"},
        headers=admin_headers,
    )
    assert reset.status_code == 200, reset.text

    db.expire_all()
    row = db.get(User, uid)
    assert verify_password("Reset@654321", row.hashed_password) is True
    assert verify_password(NEW_PASSWORD, row.hashed_password) is False

    logs = client.get("/api/admin/logs/audit?action=admin.user.reset_password", headers=admin_headers)
    assert logs.json()["data"]["items"], "重置密码应写审计日志"
    assert NEW_PASSWORD not in logs.text


def test_user_create_duplicate_email_conflict(client: TestClient, admin_headers: dict[str, str], seeded_users) -> None:
    """邮箱重复返回 409。"""
    r = client.post(
        "/api/admin/users",
        json={"email": "tester@pythonlab.dev", "username": "another", "password": NEW_PASSWORD},
        headers=admin_headers,
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "EMAIL_EXISTS"


def test_user_create_weak_password_rejected(client: TestClient, admin_headers: dict[str, str]) -> None:
    """弱密码（长度够但缺数字）被拒 422 WEAK_PASSWORD。"""
    r = client.post(
        "/api/admin/users",
        json={"email": "weak@pythonlab.dev", "username": "weakuser", "password": "abcdefgh"},
        headers=admin_headers,
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "WEAK_PASSWORD"


# ---------------------------------------------------------------------------
# 课程 / 章节 / 课时
# ---------------------------------------------------------------------------


def test_admin_course_crud_and_audit(client: TestClient, admin_headers: dict[str, str], db) -> None:
    """管理员课程 CRUD 成功且产生审计日志。"""
    create = client.post(
        "/api/admin/courses",
        json={"slug": "test-admin-course", "stage_no": 96, "title": "管理员测试课程", "level": "beginner"},
        headers=admin_headers,
    )
    assert create.status_code == 200, create.text
    course = create.json()["data"]
    assert course["slug"] == "test-admin-course"

    update = client.patch(
        f"/api/admin/courses/{course['id']}", json={"title": "管理员测试课程（改）"}, headers=admin_headers
    )
    assert update.status_code == 200
    assert update.json()["data"]["title"] == "管理员测试课程（改）"

    listed = client.get("/api/admin/courses", headers=admin_headers)
    assert listed.status_code == 200
    assert any(item["slug"] == "test-admin-course" for item in listed.json()["data"]["items"])

    delete = client.delete(f"/api/admin/courses/{course['id']}", headers=admin_headers)
    assert delete.status_code == 200

    logs = client.get("/api/admin/logs/audit?page_size=50", headers=admin_headers)
    assert logs.status_code == 200
    actions = [item["action"] for item in logs.json()["data"]["items"]]
    assert "admin.course.create" in actions
    assert "admin.course.update" in actions
    assert "admin.course.delete" in actions

    # 数据库侧确认审计日志确实落库
    assert db.scalars(select(AuditLog).where(AuditLog.action == "admin.course.create")).first() is not None


def test_chapter_crud(client: TestClient, admin_headers: dict[str, str]) -> None:
    """章节 CRUD。"""
    course_id = _new_course(client, admin_headers)
    created = client.post(
        "/api/admin/chapters",
        json={"course_id": course_id, "slug": "adm-ch", "title": "章节一"},
        headers=admin_headers,
    )
    assert created.status_code == 200, created.text
    cid = created.json()["data"]["id"]
    assert created.json()["data"]["course_id"] == course_id

    updated = client.patch(f"/api/admin/chapters/{cid}", json={"title": "章节一（改）"}, headers=admin_headers)
    assert updated.status_code == 200
    assert updated.json()["data"]["title"] == "章节一（改）"

    assert client.delete(f"/api/admin/chapters/{cid}", headers=admin_headers).status_code == 200
    assert client.delete(f"/api/admin/chapters/{cid}", headers=admin_headers).status_code == 404


def test_lesson_crud_with_topic_sync(client: TestClient, admin_headers: dict[str, str], db) -> None:
    """课时 CRUD，并按 topic_slugs 覆盖式重建知识点关联。"""
    from app.models.course import Topic

    course_id = _new_course(client, admin_headers)
    chapter_id = _new_chapter(client, admin_headers, course_id)
    topic = Topic(slug="adm-topic", name="管理端知识点")
    db.add(topic)
    db.commit()

    created = client.post(
        "/api/admin/lessons",
        json={"chapter_id": chapter_id, "slug": "adm-ls", "title": "课时一", "topic_slugs": ["adm-topic"]},
        headers=admin_headers,
    )
    assert created.status_code == 200, created.text
    lid = created.json()["data"]["id"]

    from app.models.course import LessonTopic

    links = db.scalars(select(LessonTopic).where(LessonTopic.lesson_id == lid)).all()
    assert len(links) == 1 and links[0].topic_id == topic.id
    assert links[0].is_primary is True

    updated = client.patch(
        f"/api/admin/lessons/{lid}", json={"title": "课时一（改）", "topic_slugs": []}, headers=admin_headers
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["title"] == "课时一（改）"
    assert list(db.scalars(select(LessonTopic).where(LessonTopic.lesson_id == lid))) == []

    assert client.delete(f"/api/admin/lessons/{lid}", headers=admin_headers).status_code == 200


def test_course_chapter_lesson_not_found(client: TestClient, admin_headers: dict[str, str]) -> None:
    """课程 / 章节 / 课时不存在时返回 404 且错误码正确。"""
    cases = [
        ("PATCH", "/api/admin/courses/none", {"title": "x"}, "COURSE_NOT_FOUND"),
        ("DELETE", "/api/admin/chapters/none", None, "CHAPTER_NOT_FOUND"),
        ("PATCH", "/api/admin/lessons/none", {"title": "x"}, "LESSON_NOT_FOUND"),
    ]
    for method, url, payload, code in cases:
        kwargs = {"json": payload} if payload is not None else {}
        r = client.request(method, url, headers=admin_headers, **kwargs)
        assert r.status_code == 404, f"{method} {url} -> {r.status_code}"
        assert r.json()["error"]["code"] == code


# ---------------------------------------------------------------------------
# 题目 / 测试用例
# ---------------------------------------------------------------------------


def test_problem_crud_with_nested_test_cases(client: TestClient, admin_headers: dict[str, str], db) -> None:
    """题目 CRUD + 嵌套测试用例覆盖式重建。"""
    created = client.post(
        "/api/admin/problems",
        json={
            "slug": "adm-prob", "title": "求和", "problem_type": "coding", "difficulty": "easy",
            "category": "basics", "starter_code": "print(1)",
            "test_cases": [
                {"name": "t1", "input": "1", "expected_output": "1", "is_sample": True},
                {"name": "t2", "input": "2", "expected_output": "2", "is_hidden": True},
            ],
        },
        headers=admin_headers,
    )
    assert created.status_code == 200, created.text
    pid = created.json()["data"]["id"]
    assert db.query(TestCase).filter(TestCase.problem_id == pid).count() == 2

    updated = client.patch(
        f"/api/admin/problems/{pid}",
        json={"title": "求和（改）", "test_cases": [{"name": "only", "input": "9", "expected_output": "9"}]},
        headers=admin_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["title"] == "求和（改）"
    assert db.query(TestCase).filter(TestCase.problem_id == pid).count() == 1

    assert client.delete(f"/api/admin/problems/{pid}", headers=admin_headers).status_code == 200
    r = client.delete(f"/api/admin/problems/{pid}", headers=admin_headers)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "PROBLEM_NOT_FOUND"


def test_problem_list_filters(client: TestClient, admin_headers: dict[str, str]) -> None:
    """题目列表支持关键字（按标题）/ 难度 / 分类筛选。"""
    created = client.post(
        "/api/admin/problems",
        json={"slug": "adm-filter-prob", "title": "筛选专用题目", "difficulty": "easy", "category": "basics"},
        headers=admin_headers,
    )
    assert created.status_code == 200, created.text

    by_keyword = client.get("/api/admin/problems?q=筛选专用", headers=admin_headers)
    assert by_keyword.status_code == 200
    assert any(item["slug"] == "adm-filter-prob" for item in by_keyword.json()["data"]["items"])

    by_difficulty = client.get("/api/admin/problems?difficulty=easy", headers=admin_headers)
    assert by_difficulty.status_code == 200
    assert by_difficulty.json()["data"]["items"]
    assert all(item["difficulty"] == "easy" for item in by_difficulty.json()["data"]["items"])

    by_category = client.get("/api/admin/problems?category=basics", headers=admin_headers)
    assert by_category.status_code == 200
    assert all(item["category"] == "basics" for item in by_category.json()["data"]["items"])

    # 组合筛选无交集时应为空
    none = client.get("/api/admin/problems?difficulty=expert&category=basics", headers=admin_headers)
    assert none.status_code == 200
    assert none.json()["data"]["items"] == []


def test_test_case_crud_via_problem(client: TestClient, admin_headers: dict[str, str], db) -> None:
    """测试用例的更新 / 删除（创建走题目嵌套，见 BUG-1）。"""
    created = client.post(
        "/api/admin/problems",
        json={"slug": "adm-tc", "title": "TC", "problem_type": "coding",
              "test_cases": [{"name": "c1", "input": "1", "expected_output": "1"},
                             {"name": "c2", "input": "2", "expected_output": "2"}]},
        headers=admin_headers,
    )
    pid = created.json()["data"]["id"]
    case = db.scalars(
        select(TestCase).where(TestCase.problem_id == pid).order_by(TestCase.order_index)
    ).first()

    updated = client.patch(
        f"/api/admin/test-cases/{case.id}", json={"name": "c1-renamed", "is_hidden": False},
        headers=admin_headers,
    )
    assert updated.status_code == 200, updated.text
    db.expire_all()
    assert db.get(TestCase, case.id).name == "c1-renamed"

    assert client.delete(f"/api/admin/test-cases/{case.id}", headers=admin_headers).status_code == 200
    assert db.query(TestCase).filter(TestCase.problem_id == pid).count() == 1

    missing = client.delete("/api/admin/test-cases/none", headers=admin_headers)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"


def test_create_test_case_endpoint_known_defect_bug1(client: TestClient, admin_headers: dict[str, str]) -> None:
    """BUG-1：`POST /admin/test-cases` 恒 500（缺 problem_id 且无法补传）。

    复现：管理员带合法 body（input/expected_output）调用，仍因
    `TestCase.problem_id` 非空约束抛 IntegrityError → 全局 500。
    修复后本用例应改为断言 200。
    """
    # 未处理的 IntegrityError：基座 TestClient 默认 raise_server_exceptions，故此处断言抛异常。
    with pytest.raises(Exception):
        client.post(
            "/api/admin/test-cases",
            json={"name": "t", "input": "1", "expected_output": "1"},
            headers=admin_headers,
        )

    # 显式补 problem_id 也会被 StrictModel 拦下（extra="forbid"），即该端点当前无法被正确调用。
    rejected = client.post(
        "/api/admin/test-cases",
        json={"problem_id": _new_problem(client, admin_headers), "input": "1", "expected_output": "1"},
        headers=admin_headers,
    )
    assert rejected.status_code == 422
    assert rejected.json()["error"]["details"][0]["type"] == "extra_forbidden"


def test_problem_import_empty_payload(client: TestClient, admin_headers: dict[str, str]) -> None:
    """导入空数组：不创建、不失败。"""
    r = client.post(
        "/api/admin/problems/import",
        files={"file": ("empty.json", b"[]", "application/json")},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"] == {"created": 0, "updated": 0, "failed": []}


def test_problem_import_reports_failed_items(client: TestClient, admin_headers: dict[str, str]) -> None:
    """部分非法数据：缺 slug 的条目进入 failed[]，合法条目照常创建。"""
    payload = json.dumps([{"title": "缺少 slug 的条目"}, {"slug": "adm-import-ok"}]).encode()
    r = client.post(
        "/api/admin/problems/import",
        files={"file": ("part.json", payload, "application/json")},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["created"] == 1, data
    assert data["updated"] == 0
    assert len(data["failed"]) == 1
    assert data["failed"][0]["index"] == 0
    assert "slug" in data["failed"][0]["error"]

    # 幂等：同 slug 再次导入走 updated 分支
    again = client.post(
        "/api/admin/problems/import",
        files={"file": ("part.json", payload, "application/json")},
        headers=admin_headers,
    )
    assert again.json()["data"]["updated"] == 1


def test_problem_import_duplicate_title_defect_bug3(client: TestClient, admin_headers: dict[str, str]) -> None:
    """BUG-3：含 `title` 的条目 100% 失败（`Problem() got multiple values for 'title'`）。

    复现：上传 `[{"slug": "x", "title": "T"}]` → created=0 且 failed[0].error 报重复关键字。
    修复后本用例应改为断言 created == 1。
    """
    payload = json.dumps([{"slug": "adm-dup-title", "title": "带标题的条目"}]).encode()
    r = client.post(
        "/api/admin/problems/import",
        files={"file": ("dup.json", payload, "application/json")},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["created"] == 0
    assert len(data["failed"]) == 1
    assert "multiple values for keyword argument 'title'" in data["failed"][0]["error"]


def test_problem_import_invalid_json_defect_bug2(client: TestClient, admin_headers: dict[str, str]) -> None:
    """BUG-2：上传非法 JSON 恒 500（期望 4xx）。

    复现：文件内容 `{not json` → JSONDecodeError 未被捕获，走全局 500。
    修复后本用例应改为断言 4xx。
    """
    # 未捕获的 JSONDecodeError：基座 TestClient 默认 raise_server_exceptions，故此处断言抛异常。
    with pytest.raises(Exception):
        client.post(
            "/api/admin/problems/import",
            files={"file": ("bad.json", b"{not json", "application/json")},
            headers=admin_headers,
        )


# ---------------------------------------------------------------------------
# 项目 / 项目文件
# ---------------------------------------------------------------------------


def test_project_crud(client: TestClient, admin_headers: dict[str, str]) -> None:
    """项目 CRUD。"""
    created = client.post(
        "/api/admin/projects",
        json={"slug": "adm-project", "title": "管理端项目", "level": 3, "difficulty": "medium"},
        headers=admin_headers,
    )
    assert created.status_code == 200, created.text
    pid = created.json()["data"]["id"]
    assert created.json()["data"]["level"] == 3

    updated = client.patch(f"/api/admin/projects/{pid}", json={"title": "管理端项目（改）"}, headers=admin_headers)
    assert updated.status_code == 200
    assert updated.json()["data"]["title"] == "管理端项目（改）"

    listed = client.get("/api/admin/projects", headers=admin_headers)
    assert listed.status_code == 200
    assert any(item["slug"] == "adm-project" for item in listed.json()["data"]["items"])

    assert client.delete(f"/api/admin/projects/{pid}", headers=admin_headers).status_code == 200
    missing = client.delete(f"/api/admin/projects/{pid}", headers=admin_headers)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "PROJECT_NOT_FOUND"


def test_project_file_crud(client: TestClient, admin_headers: dict[str, str]) -> None:
    """项目文件 CRUD。"""
    project = client.post(
        "/api/admin/projects", json={"slug": "adm-pr", "title": "项目"}, headers=admin_headers
    ).json()["data"]["id"]

    created = client.post(
        "/api/admin/project-files",
        json={"project_id": project, "path": "main.py", "content": "print(1)", "is_entry": True},
        headers=admin_headers,
    )
    assert created.status_code == 200, created.text
    fid = created.json()["data"]["id"]

    updated = client.patch(
        f"/api/admin/project-files/{fid}", json={"content": "print(2)"}, headers=admin_headers
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["id"] == fid

    assert client.delete(f"/api/admin/project-files/{fid}", headers=admin_headers).status_code == 200
    missing = client.delete(f"/api/admin/project-files/{fid}", headers=admin_headers)
    assert missing.status_code == 404


# ---------------------------------------------------------------------------
# 标签 / 公告
# ---------------------------------------------------------------------------


def test_tag_crud(client: TestClient, admin_headers: dict[str, str]) -> None:
    """标签 CRUD。"""
    created = client.post(
        "/api/admin/tags", json={"slug": "adm-tag", "name": "管理标签", "color": "#ff0000"},
        headers=admin_headers,
    )
    assert created.status_code == 200, created.text
    tid = created.json()["data"]["id"]
    assert created.json()["data"]["color"] == "#ff0000"

    listed = client.get("/api/admin/tags", headers=admin_headers)
    assert listed.status_code == 200
    assert any(item["slug"] == "adm-tag" for item in listed.json()["data"])

    updated = client.patch(f"/api/admin/tags/{tid}", json={"name": "管理标签（改）"}, headers=admin_headers)
    assert updated.status_code == 200
    assert updated.json()["data"]["name"] == "管理标签（改）"

    assert client.delete(f"/api/admin/tags/{tid}", headers=admin_headers).status_code == 200
    missing = client.delete(f"/api/admin/tags/{tid}", headers=admin_headers)
    assert missing.status_code == 404


def test_announcement_crud_and_offline(client: TestClient, admin_headers: dict[str, str]) -> None:
    """公告 CRUD + 发布 / 下线。"""
    created = client.post(
        "/api/admin/announcements",
        json={"title": "管理端公告", "content_md": "内容", "level": "warning"},
        headers=admin_headers,
    )
    assert created.status_code == 200, created.text
    aid = created.json()["data"]["id"]
    assert created.json()["data"]["level"] == "warning"

    listed = client.get("/api/admin/announcements", headers=admin_headers)
    assert listed.status_code == 200
    assert any(item["title"] == "管理端公告" for item in listed.json()["data"]["items"])

    offline = client.patch(
        f"/api/admin/announcements/{aid}", json={"is_active": False, "is_pinned": True},
        headers=admin_headers,
    )
    assert offline.status_code == 200
    assert offline.json()["data"]["is_pinned"] is True

    online = client.patch(f"/api/admin/announcements/{aid}", json={"is_active": True}, headers=admin_headers)
    assert online.status_code == 200
    assert online.json()["data"]["is_pinned"] is True

    assert client.delete(f"/api/admin/announcements/{aid}", headers=admin_headers).status_code == 200
    missing = client.delete(f"/api/admin/announcements/{aid}", headers=admin_headers)
    assert missing.status_code == 404


# ---------------------------------------------------------------------------
# AI 配置 / 模型（密钥不回显）
# ---------------------------------------------------------------------------


def test_ai_config_put_and_key_masked(client: TestClient, admin_headers: dict[str, str]) -> None:
    """PUT 全局 AI 配置：密钥只写，读取必须脱敏（BUG-4：运行参数不参与断言，见报告）。"""
    r = client.put(
        "/api/admin/ai-config",
        json={"provider": "deepseek", "api_key": RAW_AI_CONFIG_KEY,
              "prompt_overrides": {"tutor": "自定义提示"}},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    assert RAW_AI_CONFIG_KEY not in r.text
    body = r.json()["data"]
    assert body["api_key_configured"] is True
    assert body["api_key_masked"].startswith("sk-****")
    assert body["api_key_masked"].endswith("9876")
    assert body["prompt_overrides"] == {"tutor": "自定义提示"}

    fetched = client.get("/api/admin/ai-config", headers=admin_headers)
    assert fetched.status_code == 200
    assert RAW_AI_CONFIG_KEY not in fetched.text
    assert fetched.json()["data"]["api_key_masked"] == body["api_key_masked"]
    assert fetched.json()["data"]["prompt_overrides"] == {"tutor": "自定义提示"}


def test_ai_model_key_masked(client: TestClient, admin_headers: dict[str, str]) -> None:
    """写入 API Key 后读取返回脱敏值，响应绝不包含原始 key。"""
    create = client.post(
        "/api/admin/models",
        json={
            "provider": "deepseek",
            "name": "测试模型",
            "model": "deepseek-chat",
            "api_key": RAW_KEY,
            "is_active": True,
        },
        headers=admin_headers,
    )
    assert create.status_code == 200, create.text
    data = create.json()["data"]
    assert RAW_KEY not in create.text
    assert data["api_key_masked"] is not None
    assert "****" in data["api_key_masked"]
    assert data["api_key_masked"].endswith("1234")

    listing = client.get("/api/admin/models", headers=admin_headers)
    assert listing.status_code == 200
    assert RAW_KEY not in listing.text
    model = next(item for item in listing.json()["data"] if item["name"] == "测试模型")
    assert "****" in model["api_key_masked"]

    test_result = client.post(f"/api/admin/models/{model['id']}/test", headers=admin_headers)
    assert test_result.status_code == 200
    assert RAW_KEY not in test_result.text


def test_ai_model_crud(client: TestClient, admin_headers: dict[str, str], db) -> None:
    """模型配置的新建 / 更新 / 删除，且默认标记全局唯一。"""
    first = client.post(
        "/api/admin/models",
        json={"provider": "deepseek", "name": "模型A", "model": "a", "api_key": RAW_MODEL_KEY,
              "is_default": True},
        headers=admin_headers,
    )
    assert first.status_code == 200, first.text
    aid = first.json()["data"]["id"]

    second = client.post(
        "/api/admin/models",
        json={"provider": "deepseek", "name": "模型B", "model": "b", "is_default": True},
        headers=admin_headers,
    )
    assert second.status_code == 200
    bid = second.json()["data"]["id"]
    db.expire_all()
    assert db.get(AIModelConfig, aid).is_default is False, "新建默认模型应取消其它模型的默认标记"
    assert db.get(AIModelConfig, bid).is_default is True

    updated = client.patch(
        f"/api/admin/models/{bid}", json={"name": "模型B（改）", "temperature": 0.9}, headers=admin_headers
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["name"] == "模型B（改）"
    assert updated.json()["data"]["temperature"] == 0.9

    assert client.delete(f"/api/admin/models/{bid}", headers=admin_headers).status_code == 200
    assert client.delete(f"/api/admin/models/{bid}", headers=admin_headers).status_code == 404

    from app.models.system import SystemSetting

    leftover = db.scalars(
        select(SystemSetting).where(SystemSetting.key == f"ai.model.{bid}.api_key")
    ).first()
    assert leftover is None, "删除模型应连带清理其密钥设置"


def test_ai_model_test_endpoint_never_echoes_key(client: TestClient, admin_headers: dict[str, str]) -> None:
    """连通性测试接口绝不回显 key（无论成功或缺密钥分支）。"""
    with_key = client.post(
        "/api/admin/models",
        json={"name": "带密钥模型", "model": "m", "api_key": RAW_MODEL_KEY},
        headers=admin_headers,
    ).json()["data"]["id"]
    ok = client.post(f"/api/admin/models/{with_key}/test", headers=admin_headers)
    assert ok.status_code == 200
    assert ok.json()["data"]["ok"] is True
    assert RAW_MODEL_KEY not in ok.text

    without_key = client.post(
        "/api/admin/models", json={"name": "无密钥模型", "model": "m"}, headers=admin_headers
    ).json()["data"]["id"]
    nokey = client.post(f"/api/admin/models/{without_key}/test", headers=admin_headers)
    assert nokey.status_code == 200
    assert nokey.json()["data"]["ok"] is False
    assert nokey.json()["data"]["error"]


# ---------------------------------------------------------------------------
# 系统设置脱敏
# ---------------------------------------------------------------------------


def test_system_settings_masked(client: TestClient, admin_headers: dict[str, str]) -> None:
    """敏感系统设置写入后读取返回脱敏值。"""
    update = client.put(
        "/api/admin/settings/ai.api_key",
        json={"value_json": {"value": RAW_SETTING_KEY}, "description": "测试密钥"},
        headers=admin_headers,
    )
    assert update.status_code == 200, update.text
    assert RAW_SETTING_KEY not in update.text
    body = update.json()["data"]
    assert body["is_sensitive"] is True
    assert "****" in body["value_json"]["value"]

    listing = client.get("/api/admin/settings", headers=admin_headers)
    assert listing.status_code == 200
    assert RAW_SETTING_KEY not in listing.text
    item = next(row for row in listing.json()["data"] if row["key"] == "ai.api_key")
    assert item["is_sensitive"] is True
    assert "****" in item["value_json"]["value"]


def test_settings_non_sensitive_roundtrip(client: TestClient, admin_headers: dict[str, str]) -> None:
    """非敏感设置原样读写（不应被脱敏）。"""
    r = client.put(
        "/api/admin/settings/site.name",
        json={"value_json": "Python Lab", "description": "站点名"},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["is_sensitive"] is False
    assert body["value_json"] == "Python Lab"

    listing = client.get("/api/admin/settings", headers=admin_headers)
    item = next(row for row in listing.json()["data"] if row["key"] == "site.name")
    assert item["value_json"] == "Python Lab"


# ---------------------------------------------------------------------------
# 日志 / 维护
# ---------------------------------------------------------------------------


def test_audit_logs_filter_by_action_and_actor(
    client: TestClient, admin_headers: dict[str, str], seeded_users
) -> None:
    """审计日志可按 action 与 actor 检索。"""
    _new_course(client, admin_headers, "adm-audit-course", 94)

    by_action = client.get("/api/admin/logs/audit?action=admin.course.create", headers=admin_headers)
    assert by_action.status_code == 200
    items = by_action.json()["data"]["items"]
    assert items and all(item["action"] == "admin.course.create" for item in items)

    by_actor = client.get(f"/api/admin/logs/audit?actor_id={seeded_users.admin_id}", headers=admin_headers)
    assert by_actor.status_code == 200
    assert all(item["actor_id"] == seeded_users.admin_id for item in by_actor.json()["data"]["items"])

    paged = client.get("/api/admin/logs/audit?page=1&page_size=1", headers=admin_headers)
    assert paged.status_code == 200
    assert len(paged.json()["data"]["items"]) == 1


def test_ai_usage_and_error_logs(client: TestClient, admin_headers: dict[str, str], db, seeded_users) -> None:
    """AI 用量日志分页 + 错误日志按状态聚合。"""
    empty = client.get("/api/admin/logs/ai-usage", headers=admin_headers)
    assert empty.status_code == 200
    assert empty.json()["data"]["items"] == []

    db.add(Submission(user_id=seeded_users.user_id, status="wrong_answer", score=0))
    db.commit()

    errors = client.get("/api/admin/logs/errors", headers=admin_headers)
    assert errors.status_code == 200
    groups = errors.json()["data"]
    assert any(item["code"] == "wrong_answer" and item["count"] >= 1 for item in groups)


def test_session_overview(client: TestClient, admin_headers: dict[str, str], db, seeded_users) -> None:
    """学习会话概览：总量 / 活跃人数 / 按类型聚合。"""
    from app.models.learning import LearningSession

    db.add(LearningSession(user_id=seeded_users.user_id, session_type="lesson", duration_seconds=1800))
    db.add(LearningSession(user_id=seeded_users.user_id, session_type="practice", duration_seconds=600))
    db.commit()

    r = client.get("/api/admin/logs/sessions", headers=admin_headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["total_sessions"] == 2
    assert data["active_users"] == 1
    assert data["total_minutes"] == 40
    by_type = {row["session_type"]: row for row in data["by_type"]}
    assert by_type["lesson"]["minutes"] == 30
    assert by_type["practice"]["minutes"] == 10


def test_maintenance_rejudge(client: TestClient, admin_headers: dict[str, str], db, seeded_users) -> None:
    """批量重判入队返回待处理数量。"""
    pid = _new_problem(client, admin_headers, "adm-rejudge")
    db.add(Submission(user_id=seeded_users.user_id, problem_id=pid, status="wrong_answer", score=0))
    db.commit()

    scoped = client.post(
        "/api/admin/maintenance/rejudge", json={"problem_id": pid, "limit": 10}, headers=admin_headers
    )
    assert scoped.status_code == 200, scoped.text
    assert scoped.json()["data"] == {"queued": 1, "problem_id": pid}

    all_rows = client.post("/api/admin/maintenance/rejudge", json={"limit": 5}, headers=admin_headers)
    assert all_rows.status_code == 200
    assert all_rows.json()["data"]["problem_id"] is None
    assert all_rows.json()["data"]["queued"] == 1


def test_admin_writes_are_audited(client: TestClient, admin_headers: dict[str, str], db) -> None:
    """跨资源抽查：写操作全部留痕，且审计详情不含密钥明文。"""
    client.put("/api/admin/ai-config", json={"api_key": RAW_AI_CONFIG_KEY}, headers=admin_headers)
    client.post("/api/admin/tags", json={"slug": "adm-audit-tag", "name": "审计标签"}, headers=admin_headers)
    client.post(
        "/api/admin/models",
        json={"name": "审计模型", "model": "m", "api_key": RAW_MODEL_KEY},
        headers=admin_headers,
    )

    logs = client.get("/api/admin/logs/audit?page_size=100", headers=admin_headers)
    assert logs.status_code == 200
    actions = {item["action"] for item in logs.json()["data"]["items"]}
    assert {"admin.ai_config.update", "admin.tag.create", "admin.model.create"} <= actions
    assert RAW_AI_CONFIG_KEY not in logs.text
    assert RAW_MODEL_KEY not in logs.text

    # 审计详情里敏感值以 *** 形式落库，而非明文
    db.expire_all()
    from app.models.system import AuditLog as _AuditLog

    ai_log = db.scalars(
        select(_AuditLog).where(_AuditLog.action == "admin.ai_config.update")
    ).first()
    assert ai_log is not None
    assert RAW_AI_CONFIG_KEY not in json.dumps(ai_log.detail_json, ensure_ascii=False, default=str)
