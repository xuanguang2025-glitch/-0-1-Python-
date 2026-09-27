"""判题与运行链路集成测试（`docs/SANDBOX.md` §1.2、`docs/API.md` §2.5–2.7）。

覆盖：编程题 AC / WA / TLE / RE / 输出截断、客观题直接判分、隐藏测试点不泄露、
提交后错题本写入、XP 与知识点掌握度副作用、stub / auto 降级链路。

为验证真实执行，测试将全局执行客户端固定为 `local`（本机降级模式），
TLE 用例验证 8 秒内返回。
"""

from __future__ import annotations

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - 触发全部模型注册
from app.api.endpoints import bookmarks, code_history, editor, mistakes, problems, projects, submissions
from app.core.cache import MemoryCache, cache_container
from app.core.deps import get_db
from app.core.errors import register_exception_handlers
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.models.course import Topic
from app.models.enums import (
    ComparisonMode,
    ProblemCategory,
    ProblemType,
    UserRole,
)
from app.models.learning import KnowledgeMastery, Mistake
from app.models.problem import Problem, ProblemTag, Tag
from app.models.problem import TestCase as ProblemTestCase
from app.models.user import Profile, User
from app.services.sandbox_client import SandboxClient, reset_sandbox_client, set_sandbox_client

HIDDEN_EXPECTED = "你好，小明!"
SAMPLE_EXPECTED = "你好，Python!"
REFERENCE_CODE = 'name = input()\nprint(f"你好，{name}!")\n'


# --------------------------------------------------------------------- 夹具
@pytest.fixture()
def harness():
    """构建隔离的临时数据库 + 只挂载本域路由的测试应用。

    使用内存 SQLite（单连接 `StaticPool`）而非磁盘文件：本机磁盘 DDL 极慢
    （建库约 20s / 20+ 张表），内存建库约 0.1s，可避免整套用例被磁盘拖垮。
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    ids = _seed(TestSession)

    app = FastAPI()
    register_exception_handlers(app)
    for module in (problems, submissions, editor, projects, bookmarks, mistakes, code_history):
        app.include_router(module.router, prefix="/api")
    app.include_router(editor.python_router, prefix="/api")

    def _override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    cache_container.override(MemoryCache())
    set_sandbox_client(SandboxClient(mode="local"))
    client = TestClient(app)
    try:
        yield {"client": client, "session": TestSession, "ids": ids}
    finally:
        reset_sandbox_client()
        cache_container.reset()
        client.close()
        engine.dispose()


def _seed(TestSession) -> dict:
    """写入最小但真实的题目 / 用例 / 知识点数据。"""
    db = TestSession()
    try:
        user = User(
            email="learner@pythonlab.dev",
            username="learner",
            hashed_password=hash_password("Passw0rd!"),
            role=UserRole.USER.value,
        )
        admin = User(
            email="admin@pythonlab.dev",
            username="root_admin",
            hashed_password=hash_password("Passw0rd!"),
            role=UserRole.SUPERADMIN.value,
        )
        db.add_all([user, admin])
        db.flush()
        db.add(Profile(user_id=user.id, display_name="学习者"))
        db.add(Profile(user_id=admin.id, display_name="管理员"))

        topic = Topic(slug="loops", name="循环")
        tag = Tag(slug="loops", name="循环", kind="problem")
        db.add_all([topic, tag])
        db.flush()

        hello = Problem(
            slug="hello-world",
            title="问候世界",
            statement_md="读取一个名字（字符串），输出 `你好，<名字>!`。",
            problem_type=ProblemType.CODING.value,
            difficulty="easy",
            category=ProblemCategory.BASICS.value,
            time_limit_ms=3000,
            memory_limit_mb=128,
            score=100,
            xp_reward=30,
            sample_input="Python\n",
            sample_output=SAMPLE_EXPECTED,
            starter_code="name = input()\n# TODO\n",
        )
        db.add(hello)
        db.flush()
        db.add_all(
            [
                ProblemTestCase(
                    problem_id=hello.id,
                    name="示例",
                    input="Python\n",
                    expected_output=SAMPLE_EXPECTED + "\n",
                    comparison=ComparisonMode.TRIMMED.value,
                    is_sample=True,
                    is_hidden=False,
                    weight=1,
                    order_index=0,
                ),
                ProblemTestCase(
                    problem_id=hello.id,
                    name="隐藏",
                    input="小明\n",
                    expected_output=HIDDEN_EXPECTED + "\n",
                    comparison=ComparisonMode.TRIMMED.value,
                    is_sample=False,
                    is_hidden=True,
                    weight=1,
                    order_index=1,
                ),
            ]
        )
        db.add(ProblemTag(problem_id=hello.id, tag_id=tag.id))

        choice = Problem(
            slug="type-choice",
            title="类型转换选择题",
            problem_type=ProblemType.CHOICE.value,
            difficulty="easy",
            category=ProblemCategory.BASICS.value,
            options_json=["int('3.9')", "int(3.9)", "round(3.9)", "float('3')"],
            answer_json=1,
            score=10,
            xp_reward=5,
        )
        judge = Problem(
            slug="precedence-judge",
            title="运算优先级判断",
            problem_type=ProblemType.JUDGE.value,
            difficulty="easy",
            category=ProblemCategory.BASICS.value,
            answer_json=False,
            score=10,
            xp_reward=5,
        )
        db.add_all([choice, judge])
        db.commit()
        return {
            "user_id": user.id,
            "admin_id": admin.id,
            "hello_id": hello.id,
            "choice_id": choice.id,
            "judge_id": judge.id,
            "topic_id": topic.id,
        }
    finally:
        db.close()


def _auth(client: TestClient, session, user_id: str) -> dict[str, str]:
    """为指定用户生成 Bearer Token 与角色。"""
    db = session()
    try:
        user = db.get(User, user_id)
        token, _jti, _exp = create_access_token(user.id, role=user.role, username=user.username)
    finally:
        db.close()
    return {"Authorization": f"Bearer {token}"}


# ------------------------------------------------------------------ 题库安全
def test_problem_detail_only_exposes_sample_cases(harness) -> None:
    """题目详情只返回样例用例，隐藏用例的 expected_output 绝不出现。"""
    client, ids = harness["client"], harness["ids"]
    resp = client.get(f"/api/problems/{ids['hello_id']}")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["sample_cases"]) == 1
    assert data["sample_cases"][0]["is_sample"] is True
    assert HIDDEN_EXPECTED not in resp.text
    assert data["my_status"] is None


def test_problem_list_filters(harness) -> None:
    """题目列表按题型筛选返回正确结果。"""
    client = harness["client"]
    resp = client.get("/api/problems", params={"type": "choice"})
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["total"] == 1
    assert body["items"][0]["problem_type"] == "choice"


# ------------------------------------------------------------------ 客观题判分
def test_objective_choice_judging(harness) -> None:
    """选择题按选项下标直接判分。"""
    client, session, ids = harness["client"], harness["session"], harness["ids"]
    headers = _auth(client, session, ids["user_id"])

    ok = client.post("/api/submissions", json={"problem_id": ids["choice_id"], "answer": 1}, headers=headers)
    assert ok.status_code == 200
    assert ok.json()["data"]["status"] == "accepted"
    assert ok.json()["data"]["score"] > 0

    bad = client.post("/api/submissions", json={"problem_id": ids["choice_id"], "answer": 0}, headers=headers)
    assert bad.json()["data"]["status"] == "wrong_answer"


def test_objective_judge_bool(harness) -> None:
    """判断题按布尔值判分。"""
    client, session, ids = harness["client"], harness["session"], harness["ids"]
    headers = _auth(client, session, ids["user_id"])
    resp = client.post("/api/submissions", json={"problem_id": ids["judge_id"], "answer": False}, headers=headers)
    assert resp.json()["data"]["status"] == "accepted"


# ------------------------------------------------------------------ 编程题判分
def test_coding_ac_and_side_effects(harness) -> None:
    """编程题 AC：跑真实测试用例，写 XP 与知识点掌握度。"""
    client, session, ids = harness["client"], harness["session"], harness["ids"]
    headers = _auth(client, session, ids["user_id"])
    resp = client.post(
        "/api/submissions",
        json={"problem_id": ids["hello_id"], "code": REFERENCE_CODE},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "accepted"
    assert data["passed_cases"] == data["total_cases"] == 2
    assert data["runner"] == "local"
    assert HIDDEN_EXPECTED not in resp.text

    db = session()
    try:
        user = db.get(User, ids["user_id"])
        assert int(user.xp) >= 30
        mastery = db.scalars(
            select(KnowledgeMastery).where(KnowledgeMastery.user_id == ids["user_id"])
        ).one()
        assert mastery.mastery_level == "mastered"
        mistakes = db.scalars(select(Mistake)).all()
        assert mistakes == []
    finally:
        db.close()


def test_coding_wa_writes_mistake_and_hides_expected(harness) -> None:
    """编程题 WA：状态 wrong_answer、写入错题本、隐藏期望值不泄露。"""
    client, session, ids = harness["client"], harness["session"], harness["ids"]
    headers = _auth(client, session, ids["user_id"])
    resp = client.post(
        "/api/submissions",
        json={"problem_id": ids["hello_id"], "code": 'print("wrong")'},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "wrong_answer"
    assert data["passed_cases"] < data["total_cases"]
    assert HIDDEN_EXPECTED not in resp.text

    detail = client.get(f"/api/submissions/{data['id']}", headers=headers)
    assert HIDDEN_EXPECTED not in detail.text

    mistakes = client.get("/api/mistakes", headers=headers)
    assert mistakes.json()["data"]["total"] >= 1
    item = mistakes.json()["data"]["items"][0]
    assert item["problem_id"] == ids["hello_id"]
    assert item["error_type"] == "output"


def test_ac_resolves_existing_mistake_idempotently(harness) -> None:
    """先错后对：AC 自动解决错题条目；重复 AC 幂等，不产生新条目。"""
    client, session, ids = harness["client"], harness["session"], harness["ids"]
    headers = _auth(client, session, ids["user_id"])
    problem_id = ids["hello_id"]

    # 第一次：错误答案 → 错题本出现 1 条未解决记录
    first = client.post(
        "/api/submissions",
        json={"problem_id": problem_id, "code": 'print("wrong")'},
        headers=headers,
    )
    assert first.status_code == 200
    assert first.json()["data"]["status"] == "wrong_answer"

    with session() as db:
        rows = db.scalars(
            select(Mistake).where(Mistake.user_id == ids["user_id"], Mistake.problem_id == problem_id)
        ).all()
        assert len(rows) == 1
        assert rows[0].resolved is False
        review_count = int(rows[0].review_count or 0)

    # 第二次：正确答案 → 该错题被自动标记为已解决，review_count 保留
    second = client.post(
        "/api/submissions",
        json={"problem_id": problem_id, "code": REFERENCE_CODE},
        headers=headers,
    )
    assert second.status_code == 200
    assert second.json()["data"]["status"] == "accepted"

    with session() as db:
        rows = db.scalars(
            select(Mistake).where(Mistake.user_id == ids["user_id"], Mistake.problem_id == problem_id)
        ).all()
        assert len(rows) == 1
        assert rows[0].resolved is True
        assert int(rows[0].review_count or 0) >= review_count

    # 第三次：换一份正确代码再 AC → 幂等，不产生新错题条目
    third = client.post(
        "/api/submissions",
        json={"problem_id": problem_id, "code": 'name = input()\nprint("你好，" + name + "!")'},
        headers=headers,
    )
    assert third.status_code == 200
    assert third.json()["data"]["status"] == "accepted"

    with session() as db:
        rows = db.scalars(
            select(Mistake).where(Mistake.user_id == ids["user_id"], Mistake.problem_id == problem_id)
        ).all()
        assert len(rows) == 1
        assert rows[0].resolved is True


def test_coding_tle_returns_within_budget(harness) -> None:
    """死循环必须返回 TLE 且在 8 秒内完成。"""
    client, session, ids = harness["client"], harness["session"], harness["ids"]
    headers = _auth(client, session, ids["user_id"])
    started = time.monotonic()
    resp = client.post(
        "/api/submissions",
        json={"problem_id": ids["hello_id"], "code": "while True:\n    pass\n"},
        headers=headers,
    )
    elapsed = time.monotonic() - started
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "time_limit_exceeded"
    assert elapsed < 8.0, f"TLE 判定耗时过长：{elapsed:.2f}s"


def test_coding_re_runtime_error(harness) -> None:
    """抛异常返回 runtime_error 并记录 error_type。"""
    client, session, ids = harness["client"], harness["session"], harness["ids"]
    headers = _auth(client, session, ids["user_id"])
    resp = client.post(
        "/api/submissions",
        json={"problem_id": ids["hello_id"], "code": "raise ValueError('boom')\n"},
        headers=headers,
    )
    data = resp.json()["data"]
    assert data["status"] == "runtime_error"
    assert data["error_type"] == "runtime_error"


def test_coding_compile_error(harness) -> None:
    """语法错误返回 compile_error。"""
    client, session, ids = harness["client"], harness["session"], harness["ids"]
    headers = _auth(client, session, ids["user_id"])
    resp = client.post(
        "/api/submissions",
        json={"problem_id": ids["hello_id"], "code": "def broken(:\n    pass\n"},
        headers=headers,
    )
    assert resp.json()["data"]["status"] == "compile_error"


def test_security_error_blocked(harness) -> None:
    """命中静态黑名单不执行，返回 security_error。"""
    client, session, ids = harness["client"], harness["session"], harness["ids"]
    headers = _auth(client, session, ids["user_id"])
    resp = client.post(
        "/api/submissions",
        json={"problem_id": ids["hello_id"], "code": "import os\nos.system('echo hacked')\n"},
        headers=headers,
    )
    assert resp.json()["data"]["status"] == "security_error"


# ------------------------------------------------------------------ 运行接口
def test_python_run_endpoint(harness) -> None:
    """运行单文件代码返回 stdout / 耗时。"""
    client, session, ids = harness["client"], harness["session"], harness["ids"]
    headers = _auth(client, session, ids["user_id"])
    resp = client.post(
        "/api/python/run",
        json={"files": [{"path": "main.py", "content": "print(6)\n"}]},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "success"
    assert data["stdout"].strip() == "6"
    assert data["runner"] == "local"
    assert data["degraded"] is True


def test_python_run_output_truncated(harness) -> None:
    """超大输出被截断（truncated=True）而不是把测试挂死。"""
    client, session, ids = harness["client"], harness["session"], harness["ids"]
    headers = _auth(client, session, ids["user_id"])
    resp = client.post(
        "/api/python/run",
        json={"files": [{"path": "main.py", "content": "print('A' * 200000)\n"}]},
        headers=headers,
    )
    data = resp.json()["data"]
    assert data["status"] == "success"
    assert data["truncated"] is True
    assert len(data["stdout"]) <= 65_536 + 64


# ------------------------------------------------------------ 提交列表 / 重判
def test_submission_list_status_and_rejudge(harness) -> None:
    """提交列表 / 状态轮询 / 管理员重判。"""
    client, session, ids = harness["client"], harness["session"], harness["ids"]
    user_headers = _auth(client, session, ids["user_id"])
    created = client.post(
        "/api/submissions",
        json={"problem_id": ids["hello_id"], "code": 'print("wrong")'},
        headers=user_headers,
    ).json()["data"]

    listed = client.get("/api/submissions", params={"problem_id": ids["hello_id"]}, headers=user_headers)
    assert listed.json()["data"]["total"] == 1
    assert listed.json()["data"]["items"][0]["problem_title"] == "问候世界"

    status = client.get(f"/api/submissions/{created['id']}/status", headers=user_headers)
    assert status.json()["data"]["finished"] is True

    admin_headers = _auth(client, session, ids["admin_id"])
    rejudged = client.post(f"/api/submissions/{created['id']}/rejudge", headers=admin_headers)
    assert rejudged.status_code == 200
    assert rejudged.json()["data"]["status"] == "wrong_answer"

    # 普通用户重判应 403
    forbidden = client.post(f"/api/submissions/{created['id']}/rejudge", headers=user_headers)
    assert forbidden.status_code == 403


def test_submission_requires_auth(harness) -> None:
    """未登录提交返回 401。"""
    client, ids = harness["client"], harness["ids"]
    resp = client.post("/api/submissions", json={"problem_id": ids["hello_id"], "code": "print(1)"})
    assert resp.status_code == 401


# --------------------------------------------------------------- 降级链路
def test_stub_mode_returns_fixed_result() -> None:
    """stub 模式返回固定结果，`runner=stub`。"""
    stub = SandboxClient(mode="stub")
    run = stub.run({"main.py": "print('x')"})
    assert run.status == "success"
    assert run.runner == "stub"
    assert run.degraded is True
    judged = stub.judge({"main.py": "print('x')"}, [{"id": "tc1", "input": "", "expected": "x"}])
    assert judged.runner == "stub"
    assert judged.total_cases == 1


def test_auto_mode_falls_back_to_local() -> None:
    """auto 模式远程不可达时回落本机执行。"""
    client = SandboxClient(mode="auto", url="http://127.0.0.1:9", probe_timeout_ms=300)
    result = client.run({"main.py": "print('fallback')"})
    assert result.runner == "local"
    assert result.degraded is True
    assert result.status == "success"
    assert "fallback" in result.stdout


def test_remote_mode_falls_back_to_local_on_error() -> None:
    """remote 模式远程不可达时不报错，自动回落本机（runner=local, degraded）。"""
    client = SandboxClient(mode="remote", url="http://127.0.0.1:9")
    result = client.run({"main.py": "print('remote-down')"})
    assert result.runner == "local"
    assert result.degraded is True
    assert result.status == "success"
    assert "remote-down" in result.stdout
    judged = client.judge(
        {"main.py": "print(2)"},
        [{"id": "c1", "input": "", "expected": "2\n", "comparison": "trimmed"}],
    )
    assert judged.runner == "local"
    assert judged.total_cases == 1


def test_endpoints_degrade_gracefully_under_stub_mode(harness) -> None:
    """端点级降级：执行器切到 stub（模拟沙箱不可用）仍返回 200 并标记降级，绝不 500。"""
    client, session, ids = harness["client"], harness["session"], harness["ids"]
    headers = _auth(client, session, ids["user_id"])
    set_sandbox_client(SandboxClient(mode="stub"))
    try:
        run = client.post(
            "/api/python/run",
            json={"files": [{"path": "main.py", "content": "print(1)"}]},
            headers=headers,
        )
        assert run.status_code == 200
        assert run.json()["data"]["runner"] == "stub"
        assert run.json()["data"]["degraded"] is True

        sub = client.post(
            "/api/submissions",
            json={"problem_id": ids["hello_id"], "code": "print(1)"},
            headers=headers,
        )
        assert sub.status_code == 200
        assert sub.json()["data"]["runner"] == "stub"
    finally:
        set_sandbox_client(SandboxClient(mode="local"))
