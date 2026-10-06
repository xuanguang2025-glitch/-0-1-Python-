"""挑战 / 考试 / 通知域 API 测试（`docs/API.md` §2.14 / §2.20 / §2.15）。

重点断言：
- 挑战：join → submit → leaderboard **只返回昵称与成绩，不含 email / user_id**；
- 考试：start → 中途保存作答（`PUT /exams/attempts/{id}/answers`）→ submit → 成绩单；
- 通知：未读数 → 标记已读 → read-all → 删除，且他人通知不可操作（IDOR 红线）。
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.api.endpoints import challenges as challenges_ep
from app.api.endpoints import exams as exams_ep
from app.api.endpoints import notifications as notifications_ep
from app.core.security import create_access_token
from app.models.challenge import Challenge
from app.models.exam import Exam
from app.models.notification import Notification
from app.models.problem import Problem
from app.models.problem import TestCase as ProblemTestCase  # 别名避免 pytest 误收集为测试类
from app.models.user import User
from app.utils.time import now_utc

DOMAIN_ROUTERS = (challenges_ep.router, exams_ep.router, notifications_ep.router)


@pytest.fixture()
def client(client_factory, db) -> TestClient:
    """仅挂载本域 3 个 router 的客户端（会话级复用）。

    显式依赖 `db` 以登记基座的每用例会话工厂。
    """
    return client_factory(DOMAIN_ROUTERS)


@pytest.fixture()
def seeded(db) -> dict[str, object]:
    """种子：两道客观题（选择 + 判断）+ 一个进行中挑战 + 一份基础试卷。"""
    choice = Problem(
        slug="seed-choice",
        title="选择题：1+1=?",
        problem_type="choice",
        difficulty="easy",
        category="basics",
        statement_md="1+1 等于几？",
        options_json=["1", "2", "3"],
        answer_json=1,
        score=10,
        is_published=True,
    )
    judge = Problem(
        slug="seed-judge",
        title="判断题：Python 大小写敏感",
        problem_type="judge",
        difficulty="easy",
        category="basics",
        statement_md="Python 区分大小写吗？",
        answer_json=True,
        score=10,
        is_published=True,
    )
    db.add_all([choice, judge])
    db.flush()

    # 给选择题补一个测试用例（代码判分路径需要），此处不依赖其结果
    db.add(
        ProblemTestCase(
            problem_id=choice.id, name="样例", input="", expected_output="2", is_sample=True, is_hidden=False
        )
    )

    challenge = Challenge(
        slug="seed-daily-challenge",
        title="每日挑战",
        challenge_type="daily",
        difficulty="easy",
        problem_ids_json=[choice.id, judge.id],
        start_at=now_utc() - timedelta(hours=1),
        end_at=now_utc() + timedelta(days=1),
        duration_minutes=60,
        xp_reward=50,
    )
    closed = Challenge(
        slug="seed-closed-challenge",
        title="已结束挑战",
        challenge_type="weekly",
        difficulty="easy",
        problem_ids_json=[choice.id],
        start_at=now_utc() - timedelta(days=10),
        end_at=now_utc() - timedelta(days=1),
        duration_minutes=60,
    )
    exam = Exam(
        code="seed-basic-01",
        title="Python 基础测验",
        level="basic",
        duration_minutes=30,
        total_score=20,
        pass_score=10,
        question_ids_json=[
            {"id": choice.id, "score": 10, "order": 0},
            {"id": judge.id, "score": 10, "order": 1},
        ],
        shuffle=False,
        is_published=True,
    )
    db.add_all([challenge, closed, exam])
    db.commit()
    return {
        "choice_id": choice.id,
        "judge_id": judge.id,
        "challenge_id": challenge.id,
        "closed_id": closed.id,
        "exam_id": exam.id,
    }


@pytest.fixture()
def other_headers(db, password_hash: str) -> dict[str, str]:
    """另一个用户的鉴权头（用于 IDOR 校验）。"""
    user = User(
        email="challenger@pythonlab.dev",
        username="challenger",
        hashed_password=password_hash,
        role="user",
        is_verified=True,
    )
    db.add(user)
    db.commit()
    token, _jti, _exp = create_access_token(user.id, role="user", username=user.username)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 挑战
# ---------------------------------------------------------------------------


def test_challenge_join_list_and_detail(client: TestClient, user_headers: dict[str, str], seeded) -> None:
    """挑战列表 / 详情可读；报名成功并记录参与状态。"""
    listing = client.get("/api/challenges", params={"status": "active"}, headers=user_headers)
    assert listing.status_code == 200, listing.text
    page = listing.json()["data"]
    assert page["total"] >= 1
    brief = next(item for item in page["items"] if item["id"] == seeded["challenge_id"])
    assert brief["is_open"] is True
    assert brief["problem_count"] == 2
    assert brief["my_status"] is None

    detail = client.get(f"/api/challenges/{seeded['challenge_id']}", headers=user_headers)
    assert detail.status_code == 200
    assert len(detail.json()["data"]["problems"]) == 2

    join = client.post(f"/api/challenges/{seeded['challenge_id']}/join", headers=user_headers)
    assert join.status_code == 200, join.text
    assert join.json()["data"]["status"] == "joined"

    after = client.get(f"/api/challenges/{seeded['challenge_id']}", headers=user_headers).json()["data"]
    assert after["my"]["status"] == "joined"
    assert after["challenge"]["participant_count"] >= 1


def test_challenge_join_duplicate_and_closed(client: TestClient, user_headers: dict[str, str], seeded) -> None:
    """重复报名 → 409 `ALREADY_JOINED`；已结束挑战 → 400 `CHALLENGE_CLOSED`。"""
    assert client.post(f"/api/challenges/{seeded['challenge_id']}/join", headers=user_headers).status_code == 200

    dup = client.post(f"/api/challenges/{seeded['challenge_id']}/join", headers=user_headers)
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "ALREADY_JOINED"

    closed = client.post(f"/api/challenges/{seeded['closed_id']}/join", headers=user_headers)
    assert closed.status_code == 400
    assert closed.json()["error"]["code"] == "CHALLENGE_CLOSED"


def test_challenge_submit_and_leaderboard_privacy(
    client: TestClient, user_headers: dict[str, str], seeded, other_headers
) -> None:
    """提交判分计分；排行榜**仅昵称与成绩**，不含 email / user_id 等隐私。"""
    cid = seeded["challenge_id"]
    assert client.post(f"/api/challenges/{cid}/join", headers=user_headers).status_code == 200

    # 契约：solutions 为 {problem_id: code}，值必须是字符串。
    # 选择题判分对纯数字字符串走「按选项下标比较」分支，故填 "1"（下标 1）；
    # 判断题走宽松布尔转换，填 "true"。
    submit = client.post(
        f"/api/challenges/{cid}/submit",
        json={"solutions": {seeded["choice_id"]: "1", seeded["judge_id"]: "true"}},
        headers=user_headers,
    )
    assert submit.status_code == 200, submit.text
    body = submit.json()["data"]
    assert body["passed_cases"] >= 1
    assert body["user_challenge"]["status"] == "completed"
    assert body["user_challenge"]["score"] > 0, "全部答对应得分"
    assert all(item["correct"] for item in body["details"]), "两道题都应判对"

    # 第二位用户也参与，制造多条榜单
    assert client.post(f"/api/challenges/{cid}/join", headers=other_headers).status_code == 200
    client.post(
        f"/api/challenges/{cid}/submit",
        json={"solutions": {seeded["choice_id"]: "1", seeded["judge_id"]: "true"}},
        headers=other_headers,
    )

    board = client.get(f"/api/challenges/{cid}/leaderboard", headers=user_headers)
    assert board.status_code == 200, board.text
    data = board.json()["data"]
    assert data["entries"], "排行榜不应为空"
    assert data["total"] == len(data["entries"])

    entry = data["entries"][0]
    assert set(entry.keys()) == {"rank", "display_name", "score", "total_time_ms"}
    assert entry["rank"] == 1
    # 排名按分数降序
    scores = [item["score"] for item in data["entries"]]
    assert scores == sorted(scores, reverse=True)

    # **隐私红线**：整段响应不得出现邮箱、用户 id 或密码哈希
    raw = board.text
    assert "tester@pythonlab.dev" not in raw
    assert "challenger@pythonlab.dev" not in raw
    assert "email" not in raw
    assert "hashed_password" not in raw


def test_challenge_submit_requires_join(client: TestClient, user_headers: dict[str, str], seeded) -> None:
    """未报名直接提交 → 400（必须先报名）。"""
    resp = client.post(
        f"/api/challenges/{seeded['challenge_id']}/submit",
        json={"solutions": {seeded["choice_id"]: "2"}},
        headers=user_headers,
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["error"]["code"] == "BAD_REQUEST"


def test_challenge_my_records_are_isolated(
    client: TestClient, user_headers: dict[str, str], other_headers: dict[str, str], seeded
) -> None:
    """**IDOR 红线**：我的挑战列表只含本人记录。"""
    cid = seeded["challenge_id"]
    assert client.post(f"/api/challenges/{cid}/join", headers=user_headers).status_code == 200

    mine = client.get("/api/challenges/my", headers=user_headers).json()["data"]
    assert mine["total"] == 1 and mine["items"][0]["challenge_id"] == cid

    theirs = client.get("/api/challenges/my", headers=other_headers).json()["data"]
    assert theirs["total"] == 0, "B 不得看到 A 的挑战记录"


def test_challenge_unknown_returns_404(client: TestClient, user_headers: dict[str, str]) -> None:
    """不存在的挑战 → 404 `CHALLENGE_NOT_FOUND`。"""
    resp = client.get("/api/challenges/00000000-0000-0000-0000-000000000000", headers=user_headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "CHALLENGE_NOT_FOUND"


# ---------------------------------------------------------------------------
# 考试
# ---------------------------------------------------------------------------


def test_exam_list_and_detail_hide_answers(client: TestClient, user_headers: dict[str, str], seeded) -> None:
    """试卷列表 / 详情可读，且题目**绝不包含答案字段**。"""
    listing = client.get("/api/exams", headers=user_headers)
    assert listing.status_code == 200, listing.text
    exams = listing.json()["data"]
    assert exams, "试卷列表不应为空"
    brief = next(item for item in exams if item["id"] == seeded["exam_id"])
    assert brief["question_count"] == 2
    assert brief["my_best_score"] is None

    detail = client.get(f"/api/exams/{seeded['exam_id']}", headers=user_headers)
    assert detail.status_code == 200, detail.text
    raw = detail.text
    assert "answer_json" not in raw and "reference_solution" not in raw
    for question in detail.json()["data"]["questions"]:
        assert {"problem_id", "title", "problem_type", "score"} <= set(question)
        assert "answer_json" not in question


def test_exam_start_save_and_submit(client: TestClient, user_headers: dict[str, str], seeded) -> None:
    """完整考试流程：开始 → 中途保存 → 交卷 → 成绩单可回查。"""
    exam_id = seeded["exam_id"]

    start = client.post(f"/api/exams/{exam_id}/start", headers=user_headers)
    assert start.status_code == 200, start.text
    attempt = start.json()["data"]
    attempt_id = attempt["attempt_id"]
    assert attempt["deadline_at"]
    assert attempt["remaining_seconds"] > 0
    assert len(attempt["questions"]) == 2

    # 中途保存：只答第一题
    saved = client.put(
        f"/api/exams/attempts/{attempt_id}/answers",
        json={"attempt_id": attempt_id, "answers": {seeded["choice_id"]: 1}},
        headers=user_headers,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["saved"] == 1
    assert saved.json()["data"]["status"] == "in_progress"

    # 续答：start 命中未超时记录，返回同一 attempt
    resumed = client.post(f"/api/exams/{exam_id}/start", headers=user_headers)
    assert resumed.json()["data"]["attempt_id"] == attempt_id, "未超时应续答而非新建"

    # 交卷：两题都答对
    submit = client.post(
        f"/api/exams/{exam_id}/submit",
        json={
            "attempt_id": attempt_id,
            "answers": {seeded["choice_id"]: 1, seeded["judge_id"]: True},
        },
        headers=user_headers,
    )
    assert submit.status_code == 200, submit.text
    report = submit.json()["data"]
    assert report["score"] == 20, "两题各 10 分全对"
    assert report["total_score"] == 20
    assert report["passed"] is True
    assert len(report["per_question"]) == 2
    assert all(item["correct"] for item in report["per_question"])
    assert report["weak_topics"] == []
    assert report["submitted_at"]

    # 成绩单可回查
    again = client.get(f"/api/exams/attempts/{attempt_id}", headers=user_headers)
    assert again.status_code == 200, again.text
    assert again.json()["data"]["score"] == 20

    # 提交后不允许再保存
    late = client.put(
        f"/api/exams/attempts/{attempt_id}/answers",
        json={"attempt_id": attempt_id, "answers": {seeded["choice_id"]: 1}},
        headers=user_headers,
    )
    assert late.status_code == 400

    # 列表与历史回填最好成绩
    brief = next(
        item for item in client.get("/api/exams", headers=user_headers).json()["data"]
        if item["id"] == exam_id
    )
    assert brief["my_best_score"] == 20 and brief["my_passed"] is True

    history = client.get("/api/exams/attempts", headers=user_headers).json()["data"]
    assert history["total"] == 1
    assert history["items"][0]["status"] == "graded"


def test_exam_wrong_answers_reduce_score(client: TestClient, user_headers: dict[str, str], seeded) -> None:
    """答错时得分下降并产出薄弱知识点分类。"""
    exam_id = seeded["exam_id"]
    attempt_id = client.post(f"/api/exams/{exam_id}/start", headers=user_headers).json()["data"]["attempt_id"]

    submit = client.post(
        f"/api/exams/{exam_id}/submit",
        json={"attempt_id": attempt_id, "answers": {seeded["choice_id"]: 0, seeded["judge_id"]: False}},
        headers=user_headers,
    )
    assert submit.status_code == 200, submit.text
    report = submit.json()["data"]
    assert report["score"] == 0
    assert report["passed"] is False
    assert all(item["correct"] is False for item in report["per_question"])
    assert {row["category"] for row in report["weak_topics"]} == {"basics"}


def test_exam_attempt_of_other_user_is_hidden(
    client: TestClient, user_headers: dict[str, str], other_headers: dict[str, str], seeded
) -> None:
    """**IDOR 红线**：B 不得读取 A 的作答记录（404，不泄露存在性）。"""
    exam_id = seeded["exam_id"]
    attempt_id = client.post(f"/api/exams/{exam_id}/start", headers=user_headers).json()["data"]["attempt_id"]

    resp = client.get(f"/api/exams/attempts/{attempt_id}", headers=other_headers)
    assert resp.status_code == 404, resp.text
    assert resp.json()["error"]["code"] == "NOT_FOUND"

    assert client.get("/api/exams/attempts", headers=other_headers).json()["data"]["total"] == 0


def test_exam_unknown_returns_404(client: TestClient, user_headers: dict[str, str]) -> None:
    """不存在的试卷 → 404 `EXAM_NOT_FOUND`。"""
    resp = client.get("/api/exams/00000000-0000-0000-0000-000000000000", headers=user_headers)
    assert resp.status_code == 404, resp.text
    assert resp.json()["error"]["code"] == "EXAM_NOT_FOUND"


# ---------------------------------------------------------------------------
# 通知
# ---------------------------------------------------------------------------


def test_notification_unread_read_all_and_delete(
    client: TestClient, user_headers: dict[str, str], db, seeded
) -> None:
    """通知：未读数 → 标记单条已读 → 全部已读 → 删除。"""
    me = db.query(User).filter(User.email == "tester@pythonlab.dev").one()
    for index in range(3):
        db.add(Notification(user_id=me.id, type="system", title=f"通知 {index}", content_md="内容"))
    db.add(Notification(user_id=me.id, type="achievement", title="成就通知"))
    db.commit()

    assert client.get("/api/notifications/unread-count", headers=user_headers).json()["data"]["count"] == 4

    unread = client.get("/api/notifications", params={"is_read": "false"}, headers=user_headers).json()["data"]
    assert unread["total"] == 4

    target = unread["items"][0]["id"]
    read = client.post(f"/api/notifications/{target}/read", headers=user_headers)
    assert read.status_code == 200, read.text
    assert read.json()["data"]["is_read"] is True
    assert read.json()["data"]["read_at"] is not None
    assert client.get("/api/notifications/unread-count", headers=user_headers).json()["data"]["count"] == 3

    by_type = client.get("/api/notifications", params={"type": "achievement"}, headers=user_headers).json()["data"]
    assert by_type["total"] == 1 and by_type["items"][0]["title"] == "成就通知"

    all_read = client.post("/api/notifications/read-all", json={"type": None}, headers=user_headers)
    assert all_read.status_code == 200, all_read.text
    assert all_read.json()["data"]["updated"] == 3
    assert client.get("/api/notifications/unread-count", headers=user_headers).json()["data"]["count"] == 0

    deleted = client.delete(f"/api/notifications/{target}", headers=user_headers)
    assert deleted.status_code == 200, deleted.text
    assert client.get("/api/notifications", headers=user_headers).json()["data"]["total"] == 3


def test_notification_read_all_filtered_by_type(
    client: TestClient, user_headers: dict[str, str], db, seeded
) -> None:
    """read-all 支持按类型批量，只影响该类型。"""
    me = db.query(User).filter(User.email == "tester@pythonlab.dev").one()
    db.add_all(
        [
            Notification(user_id=me.id, type="system", title="系统 1"),
            Notification(user_id=me.id, type="system", title="系统 2"),
            Notification(user_id=me.id, type="challenge", title="挑战 1"),
        ]
    )
    db.commit()

    resp = client.post("/api/notifications/read-all", json={"type": "system"}, headers=user_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["updated"] == 2
    assert client.get("/api/notifications/unread-count", headers=user_headers).json()["data"]["count"] == 1


def test_notifications_are_isolated_between_users(
    client: TestClient, user_headers: dict[str, str], other_headers: dict[str, str], db, seeded
) -> None:
    """**IDOR 红线**：B 看不到、也读不了 / 删不了 A 的通知。"""
    me = db.query(User).filter(User.email == "tester@pythonlab.dev").one()
    note = Notification(user_id=me.id, type="system", title="A 的私有通知")
    db.add(note)
    db.commit()
    note_id = note.id

    assert client.get("/api/notifications/unread-count", headers=other_headers).json()["data"]["count"] == 0
    assert client.get("/api/notifications", headers=other_headers).json()["data"]["total"] == 0

    read = client.post(f"/api/notifications/{note_id}/read", headers=other_headers)
    assert read.status_code == 404, read.text
    assert read.json()["error"]["code"] == "NOTIFICATION_NOT_FOUND"

    assert client.delete(f"/api/notifications/{note_id}", headers=other_headers).status_code == 404

    # 通知仍属于 A，未被 B 影响
    assert client.get("/api/notifications/unread-count", headers=user_headers).json()["data"]["count"] == 1


def test_notifications_require_login(client: TestClient, seeded) -> None:
    """通知域需登录：未带令牌 → 401。"""
    resp = client.get("/api/notifications")
    assert resp.status_code == 401, resp.text
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"
