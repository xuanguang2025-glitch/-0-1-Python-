"""游戏化/统计/挑战/通知 API 测试；数据用 uuid 后缀保证可重复执行。"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.endpoints import achievements, challenges, notifications, statistics
from app.core.constants import level_of_xp
from app.core.errors import register_exception_handlers
from app.core.security import create_access_token, hash_password
from app.db.init_db import create_all
from app.db.session import SessionLocal
from app.models.challenge import Challenge
from app.models.gamification import Achievement, DailyTask, UserAchievement, XPTransaction
from app.models.learning import LearningSession
from app.models.notification import Notification
from app.models.problem import Problem
from app.models.submission import Submission
from app.models.user import Profile, User
from app.services import gamification_service, notification_service
from app.utils.time import now_utc

RUN = uuid.uuid4().hex[:8]
USER_EMAIL = f"learner_{RUN}@pythonlab.dev"
USERNAME = f"learner_{RUN}"
DISPLAY_NAME = f"学习者{RUN}"


# ---------------------------------------------------------------------------
# 测试夹具
# ---------------------------------------------------------------------------


def _seed() -> dict[str, Any]:
    """建表并写入本次运行唯一的最小可测数据。"""
    create_all()
    db = SessionLocal()
    try:
        user = User(
            email=USER_EMAIL,
            username=USERNAME,
            hashed_password=hash_password("Learner@123"),
            role="user",
            is_verified=True,
            streak_days=3,
        )
        db.add(user)
        db.flush()
        db.add(Profile(user_id=user.id, display_name=DISPLAY_NAME))

        for code, name, cat, cond in [
            ("first_ac", "首个 AC", "practice", {"type": "problems_accepted", "value": 1}),
            ("streak_3", "连续 3 天", "streak", {"type": "streak_days", "value": 3}),
        ]:
            if db.scalars(select(Achievement).where(Achievement.code == code)).one_or_none() is None:
                db.add(Achievement(code=code, name=name, category=cat, condition_json=cond, xp_reward=10))

        if db.scalars(select(DailyTask).where(DailyTask.code == "daily_submit")).one_or_none() is None:
            db.add(DailyTask(code="daily_submit", title="提交 1 次代码", metric="submissions", target_count=1, xp_reward=10))

        problem = Problem(
            slug=f"test-choice-{RUN}",
            title="测试选择题",
            problem_type="choice",
            difficulty="easy",
            category="basics",
            answer_json=1,
            options_json=["A", "B", "C"],
            score=10,
        )
        db.add(problem)
        db.flush()

        challenge = Challenge(
            slug=f"test-challenge-{RUN}",
            title="测试挑战",
            challenge_type="daily",
            difficulty="easy",
            problem_ids_json=[problem.id],
            start_at=now_utc() - timedelta(hours=1),
            end_at=now_utc() + timedelta(days=1),
            duration_minutes=60,
            xp_reward=50,
        )
        db.add(challenge)
        db.flush()

        # 让统计 / 成就指标非空：一次通过提交 + 一次学习会话
        db.add(
            Submission(
                user_id=user.id,
                problem_id=problem.id,
                status="accepted",
                score=10,
                passed_cases=1,
                total_cases=1,
                finished_at=now_utc(),
            )
        )
        db.add(LearningSession(user_id=user.id, session_type="lesson", duration_seconds=1200, actions_count=3))
        db.commit()
        return {
            "user_id": user.id,
            "user_email": user.email,
            "username": USERNAME,
            "display_name": DISPLAY_NAME,
            "problem_id": problem.id,
            "challenge_id": challenge.id,
        }
    finally:
        db.close()


def _build_app() -> FastAPI:
    """只挂载本模块负责的路由，避免占用端口。"""
    app = FastAPI()
    register_exception_handlers(app)
    for module in (statistics, achievements, challenges, notifications):
        app.include_router(module.router, prefix="/api")
    return app


@pytest.fixture(scope="module")
def seeded() -> dict[str, Any]:
    """初始化数据库与种子数据。"""
    return _seed()


@pytest.fixture(scope="module")
def client() -> TestClient:
    """构造仅包含本域路由的测试客户端。"""
    return TestClient(_build_app())


def _headers(user_id: str, role: str, username: str) -> dict[str, str]:
    """生成 Bearer 认证头。"""
    token, _, _ = create_access_token(user_id, role=role, username=username)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def user_headers(seeded: dict[str, Any]) -> dict[str, str]:
    """普通用户认证头。"""
    return _headers(seeded["user_id"], "user", seeded["username"])


# ---------------------------------------------------------------------------
# 等级与 XP
# ---------------------------------------------------------------------------


def test_level_threshold_boundaries() -> None:
    """7 级阈值边界：0/99→1，100→2，300→3，700→4，1500→5，3000→6，6000→7。"""
    thresholds = [0, 100, 300, 700, 1500, 3000, 6000]
    assert level_of_xp(0, thresholds) == 1
    assert level_of_xp(99, thresholds) == 1
    assert level_of_xp(100, thresholds) == 2
    assert level_of_xp(299, thresholds) == 2
    assert level_of_xp(300, thresholds) == 3
    assert level_of_xp(6000, thresholds) == 7
    assert level_of_xp(99_999, thresholds) == 7


def test_award_xp_level_up(seeded: dict[str, Any]) -> None:
    """发放经验触发升级，并写入等级名与流水。"""
    db = SessionLocal()
    try:
        user = db.get(User, seeded["user_id"])
        user.xp = 95
        user.level = 1
        db.commit()
        earned, level_up = gamification_service.award_xp(db, user, 10, "ac", "problem", seeded["problem_id"])
        db.commit()
        assert earned == 10
        assert level_up is True
        assert user.level == 2
        assert user.xp == 105
        info = gamification_service.level_info(user.xp)
        assert info["level"] == 2
        assert info["level_name"] == "Beginner"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 成就解锁幂等
# ---------------------------------------------------------------------------


def test_check_and_unlock_is_idempotent(seeded: dict[str, Any]) -> None:
    """重复调用不重复发放成就。"""
    db = SessionLocal()
    try:
        user = db.get(User, seeded["user_id"])
        before = len(db.scalars(select(UserAchievement).where(UserAchievement.user_id == user.id)).all())
        first = gamification_service.check_and_unlock(db, user, {"metric": "problems_accepted"})
        after_first = len(db.scalars(select(UserAchievement).where(UserAchievement.user_id == user.id)).all())
        second = gamification_service.check_and_unlock(db, user, {"metric": "problems_accepted"})
        after_second = len(db.scalars(select(UserAchievement).where(UserAchievement.user_id == user.id)).all())

        assert after_first == before + len(first)
        assert "first_ac" in first
        assert second == []
        assert after_second == after_first
    finally:
        db.close()


def test_check_achievements_alias_unlocks_and_is_idempotent(seeded: dict[str, Any]) -> None:
    """内容域/判题域按 `check_achievements` 调用应真实解锁（幂等，含 XP + 通知）。"""
    db = SessionLocal()
    try:
        sfx = uuid.uuid4().hex[:8]
        user = User(email=f"alias_{sfx}@pythonlab.dev", username=f"alias_{sfx}", role="user",
                    hashed_password=hash_password("Learner@123"), is_verified=True, streak_days=0)
        db.add(user)
        db.flush()
        db.add(Profile(user_id=user.id, display_name=f"别名{sfx}"))
        db.add(Submission(user_id=user.id, problem_id=seeded["problem_id"], status="accepted",
                          score=10, passed_cases=1, total_cases=1, finished_at=now_utc()))
        db.commit()

        def snap() -> tuple[int, int, int]:
            uid = user.id
            return (len(db.scalars(select(UserAchievement).where(UserAchievement.user_id == uid)).all()),
                    len(db.scalars(select(XPTransaction).where(XPTransaction.user_id == uid)).all()),
                    len(db.scalars(select(Notification).where(
                        Notification.user_id == uid, Notification.type == "achievement")).all()))

        assert callable(getattr(gamification_service, "check_achievements", None))  # 别名必须存在
        xp0 = int(user.xp or 0)
        ua0, tx0, nt0 = snap()
        first = gamification_service.check_achievements(db, user)
        db.refresh(user)
        ua1, tx1, nt1 = snap()
        assert "first_ac" in first and ua1 == ua0 + len(first)  # 成就行 +1/条
        assert nt1 == nt0 + len(first) and tx1 > tx0            # 通知 +1/条，XP 流水有新增
        assert int(user.xp) > xp0                               # XP 实际上涨
        assert gamification_service.check_achievements(db, user) == []  # 幂等
        assert snap() == (ua1, tx1, nt1)
    finally:
        db.close()


def test_notification_service_create_positional(seeded: dict[str, Any]) -> None:
    """`notification_service.create` 位置参数调用可用（内容/判题域按此签名调用）。"""
    db = SessionLocal()
    try:
        note = notification_service.create(db, db.get(User, seeded["user_id"]), "achievement",
                                           "位置调用标题", "位置调用内容", "/achievements")
        db.commit()
        assert note.title == "位置调用标题" and note.type == "achievement"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 每日任务
# ---------------------------------------------------------------------------


def test_daily_task_complete_and_claim(client: TestClient, user_headers: dict[str, str]) -> None:
    """每日任务按指标达标结算 XP，重复 check 不重复发。"""
    listing = client.get("/api/achievements/daily-tasks", headers=user_headers)
    assert listing.status_code == 200
    tasks = listing.json()["data"]
    assert tasks, "每日任务列表不应为空"
    task = next(t for t in tasks if t["code"] == "daily_submit")

    first = client.post(f"/api/achievements/daily-tasks/{task['id']}/check", headers=user_headers)
    assert first.status_code == 200
    body = first.json()["data"]
    assert body["completed"] is True
    assert body["xp_earned"] >= 10

    second = client.post(f"/api/achievements/daily-tasks/{task['id']}/check", headers=user_headers)
    assert second.json()["data"]["xp_earned"] == 0


# ---------------------------------------------------------------------------
# 挑战：报名与排行榜隐私
# ---------------------------------------------------------------------------


def test_challenge_join_and_leaderboard_privacy(
    client: TestClient, user_headers: dict[str, str], seeded: dict[str, Any]
) -> None:
    """报名成功；重复报名 409；排行榜仅含昵称与成绩。"""
    cid = seeded["challenge_id"]
    join = client.post(f"/api/challenges/{cid}/join", headers=user_headers)
    assert join.status_code == 200, join.text

    dup = client.post(f"/api/challenges/{cid}/join", headers=user_headers)
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "ALREADY_JOINED"

    board = client.get(f"/api/challenges/{cid}/leaderboard", headers=user_headers)
    assert board.status_code == 200
    data = board.json()["data"]
    assert data["entries"], "排行榜不应为空"
    entry = data["entries"][0]
    assert set(entry.keys()) == {"rank", "display_name", "score", "total_time_ms"}
    assert entry["display_name"] == seeded["display_name"]

    raw = board.text
    assert seeded["user_email"] not in raw
    assert "email" not in raw
    assert seeded["user_id"] not in raw


# ---------------------------------------------------------------------------
# 统计：真实库非空
# ---------------------------------------------------------------------------


def test_statistics_overview_and_trend_non_empty(client: TestClient, user_headers: dict[str, str]) -> None:
    """统计接口在含种子内容的库上返回非空且结构正确的数据。"""
    overview = client.get("/api/statistics/overview", headers=user_headers)
    assert overview.status_code == 200
    data = overview.json()["data"]
    assert data["submissions"] >= 1
    assert data["solved"] >= 1
    assert data["total_minutes"] >= 20
    assert data["level"] >= 1
    assert data["rank_percentile"] >= 0

    trend = client.get("/api/statistics/trend?days=7&metric=submissions", headers=user_headers)
    assert trend.status_code == 200
    points = trend.json()["data"]["points"]
    assert len(points) == 7
    assert trend.json()["data"]["total"] >= 1

    categories = client.get("/api/statistics/categories", headers=user_headers)
    assert categories.status_code == 200
    assert categories.json()["data"]["categories"], "分类统计不应为空"

    heatmap = client.get("/api/statistics/heatmap?days=30", headers=user_headers)
    assert heatmap.status_code == 200
    assert len(heatmap.json()["data"]["points"]) == 30

    report = client.get("/api/statistics/report?period=week", headers=user_headers)
    assert report.status_code == 200
    assert report.json()["data"]["summary_md"]

    ranking = client.get("/api/statistics/ranking", headers=user_headers)
    assert ranking.status_code == 200
    assert "email" not in ranking.text
    assert ranking.json()["data"]["my_rank"] >= 1


# ---------------------------------------------------------------------------
# 通知
# ---------------------------------------------------------------------------


def test_notifications_unread_and_read(client: TestClient, user_headers: dict[str, str], seeded: dict[str, Any]) -> None:
    """未读数、标记已读、全部已读。"""
    db = SessionLocal()
    try:
        for index in range(2):
            db.add(
                Notification(
                    user_id=seeded["user_id"],
                    type="system",
                    title=f"测试通知 {index}",
                    content_md="内容",
                )
            )
        db.commit()
    finally:
        db.close()

    before = client.get("/api/notifications/unread-count", headers=user_headers).json()["data"]["count"]
    assert before >= 2

    listing = client.get("/api/notifications?is_read=false", headers=user_headers)
    assert listing.status_code == 200
    items = listing.json()["data"]["items"]
    assert items

    target = items[0]["id"]
    read = client.post(f"/api/notifications/{target}/read", headers=user_headers)
    assert read.status_code == 200
    assert read.json()["data"]["is_read"] is True

    after = client.get("/api/notifications/unread-count", headers=user_headers).json()["data"]["count"]
    assert after == before - 1

    all_read = client.post("/api/notifications/read-all", json={"type": None}, headers=user_headers)
    assert all_read.status_code == 200
    assert all_read.json()["data"]["updated"] >= 0
    assert client.get("/api/notifications/unread-count", headers=user_headers).json()["data"]["count"] == 0
