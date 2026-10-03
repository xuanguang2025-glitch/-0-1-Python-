"""内容与学习域 API 测试（courses / lessons / progress / search / recommendations）。

策略：用 conftest 提供的 `seeded_real_db`（真实库 `backend/data/pythonlab.db` 的一致副本）
构建模块级会话工厂，并通过 `client_factory` 挂载本域 5 个 router，
既能校验真实数据，又不污染真实库。
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.api.endpoints import courses as courses_ep
from app.api.endpoints import lessons as lessons_ep
from app.api.endpoints import progress as progress_ep
from app.api.endpoints import recommendations as rec_ep
from app.api.endpoints import search as search_ep
from app.core.security import create_access_token, hash_password
from app.models.course import LessonTopic
from app.models.learning import LearningSession
from app.models.user import User

API = "/api"


def _auth(token: str) -> dict[str, str]:
    """构造鉴权头。"""
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def env(seeded_real_db: Path, client_factory, install_session_factory) -> SimpleNamespace:
    """构建真实种子库副本 + 临时 app + 两个用户与令牌。

    内容域需要校验真实课程数据，因此用 conftest 提供的 `seeded_real_db`
    （真实库的一致副本）建模块级引擎，并把它持有的会话工厂登记为当前活跃工厂，
    使会话级缓存的 App 能正确解析到该库。模块级共享数据的行为与迁移前一致。
    """
    engine = create_engine(
        f"sqlite:///{seeded_real_db.as_posix()}", connect_args={"check_same_thread": False}, future=True
    )
    testing_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)
    install_session_factory(testing_session)

    with testing_session() as db:
        user_a = User(email="content_a@test.dev", username="content_a", hashed_password=hash_password("Test@12345"))
        user_b = User(email="content_b@test.dev", username="content_b", hashed_password=hash_password("Test@12345"))
        db.add_all([user_a, user_b])
        db.commit()
        db.refresh(user_a)
        db.refresh(user_b)
        token_a, _, _ = create_access_token(user_a.id, role="user", username=user_a.username, display_name="Tester A")
        token_b, _, _ = create_access_token(user_b.id, role="user", username=user_b.username, display_name="Tester B")
        session_b = LearningSession(user_id=user_b.id, session_type="lesson", learning_mode="system")
        db.add(session_b)
        db.commit()
        db.refresh(session_b)
        link = db.scalars(select(LessonTopic).where(LessonTopic.is_primary.is_(True)).limit(1)).one()
        ids = (user_a.id, user_b.id, session_b.id, link.topic_id)

    client = client_factory([courses_ep.router, lessons_ep.router, progress_ep.router, search_ep.router, rec_ep.router])
    yield SimpleNamespace(
        client=client,
        token_a=token_a,
        token_b=token_b,
        user_a_id=ids[0],
        user_b_id=ids[1],
        session_b_id=ids[2],
        topic_id=ids[3],
    )
    engine.dispose()
    install_session_factory(None)


def _pick_lesson_id(env: SimpleNamespace, index: int = 1) -> str:
    """从阶段 1 的课时列表里挑一个（默认第 2 个，保证有上一节）。"""
    lessons = env.client.get(f"{API}/courses/stage-01-python-basics/lessons").json()["data"]
    assert len(lessons) > index
    return lessons[index]["id"]


def test_courses_list_filter_sort_and_stages(env: SimpleNamespace) -> None:
    """课程列表分页 + 难度筛选 + 排序白名单 + 18 阶段概览。"""
    resp = env.client.get(f"{API}/courses", params={"page": 1, "page_size": 5})
    data = resp.json()["data"]
    assert resp.status_code == 200
    assert data["total"] == 18 and len(data["items"]) == 5 and data["pages"] == 4

    items = env.client.get(
        f"{API}/courses", params={"level": "beginner", "page_size": 100, "sort": "stage_no"}
    ).json()["data"]["items"]
    assert items and all(item["level"] == "beginner" for item in items)
    stages = [item["stage_no"] for item in items]
    assert stages == sorted(stages)

    assert len(env.client.get(f"{API}/courses/stages").json()["data"]) == 18


def test_course_detail_chapter_tree(env: SimpleNamespace) -> None:
    """课程详情章节树层级正确（课时归属其所属章节）。"""
    body = env.client.get(f"{API}/courses/stage-01-python-basics").json()
    assert body["data"]["course"]["slug"] == "stage-01-python-basics"
    chapters = body["data"]["chapters"]
    assert chapters
    total = 0
    for chapter in chapters:
        assert chapter["lessons"], "章节下应有课时"
        for lesson in chapter["lessons"]:
            assert lesson["chapter_id"] == chapter["id"]
            total += 1
    assert total >= 1


def test_lesson_detail_position_and_topics(env: SimpleNamespace) -> None:
    """课时详情含课程/章节定位、上一节/下一节、完整目录与知识点（前端左侧目录需求）。"""
    lesson_id = _pick_lesson_id(env, 1)
    data = env.client.get(f"{API}/lessons/{lesson_id}").json()["data"]
    for field in (
        "course_id", "course_title", "course_slug", "chapter_id", "chapter_title",
        "chapter_index", "lesson_index", "total_lessons", "prev_lesson", "next_lesson", "course_outline",
    ):
        assert field in data, f"课时详情缺失字段：{field}"
    assert data["course_slug"] == "stage-01-python-basics"
    assert data["lesson_index"] >= 1 and data["total_lessons"] > 0
    assert data["prev_lesson"] is not None and {"id", "title", "slug"} <= set(data["prev_lesson"])
    assert data["course_outline"]

    topics = env.client.get(f"{API}/lessons/{lesson_id}/topics").json()["data"]
    assert isinstance(topics, list)


def test_lesson_complete_updates_progress_and_next(env: SimpleNamespace) -> None:
    """标记完成后进度变化、发放 XP、总览计数增加，并可取下一节。"""
    lesson_id = _pick_lesson_id(env, 0)
    body = env.client.post(
        f"{API}/lessons/{lesson_id}/complete", json={"time_spent_seconds": 60}, headers=_auth(env.token_a)
    ).json()
    assert body["data"]["progress"]["status"] == "completed"
    assert body["data"]["progress"]["progress_percent"] == 100
    assert body["data"]["xp_earned"] >= 0

    overview = env.client.get(f"{API}/progress", headers=_auth(env.token_a)).json()
    assert overview["data"]["completed_lessons"] >= 1

    nxt = env.client.get(f"{API}/lessons/{lesson_id}/next", headers=_auth(env.token_a)).json()["data"]
    assert nxt is not None and nxt["id"]


def test_lesson_progress_partial(env: SimpleNamespace) -> None:
    """上报部分进度（<100%）状态为 in_progress。"""
    lesson_id = _pick_lesson_id(env, 2)
    data = env.client.post(
        f"{API}/lessons/{lesson_id}/progress",
        json={"progress_percent": 40, "time_spent_seconds": 30},
        headers=_auth(env.token_a),
    ).json()["data"]
    assert data["progress_percent"] == 40 and data["status"] == "in_progress"


def test_mastery_read_and_update(env: SimpleNamespace) -> None:
    """更新并读取知识点掌握度（单点 + 列表）。"""
    updated = env.client.post(
        f"{API}/progress/mastery/{env.topic_id}", json={"correct": True}, headers=_auth(env.token_a)
    ).json()["data"]
    assert updated["mastery_score"] > 0
    single = env.client.get(f"{API}/progress/mastery/{env.topic_id}", headers=_auth(env.token_a)).json()["data"]
    assert single["mastery_score"] > 0
    listing = env.client.get(f"{API}/progress/mastery", headers=_auth(env.token_a)).json()["data"]
    assert len(listing["topics"]) >= 1


def test_dashboard_and_heatmap(env: SimpleNamespace) -> None:
    """学习看板与热力图可读。"""
    dash = env.client.get(f"{API}/progress/dashboard", headers=_auth(env.token_a)).json()["data"]
    assert dash["total_courses"] == 18 and dash["completed_lessons"] >= 1
    heat = env.client.get(
        f"{API}/progress/heatmap", params={"days": 30}, headers=_auth(env.token_a)
    ).json()["data"]
    assert len(heat["points"]) == 30


def test_session_lifecycle(env: SimpleNamespace) -> None:
    """学习会话开始 / 心跳 / 结束。"""
    headers = _auth(env.token_a)
    session_id = env.client.post(
        f"{API}/progress/sessions", json={"session_type": "lesson", "learning_mode": "system"}, headers=headers
    ).json()["data"]["id"]
    beat = env.client.post(
        f"{API}/progress/sessions/{session_id}/heartbeat", json={"seconds": 45, "actions": 2}, headers=headers
    ).json()["data"]
    assert beat["duration_seconds"] == 45
    ended = env.client.post(
        f"{API}/progress/sessions/{session_id}/end", json={"duration_seconds": 120}, headers=headers
    ).json()["data"]
    assert ended["duration_seconds"] == 120 and ended["ended_at"] is not None


def test_enroll_and_my_courses(env: SimpleNamespace) -> None:
    """报名 → 我的课程可见 → 重复报名 409 → 取消报名。"""
    course_id = env.client.get(f"{API}/courses", params={"page_size": 1}).json()["data"]["items"][0]["id"]
    assert env.client.post(f"{API}/courses/{course_id}/enroll", headers=_auth(env.token_a)).status_code == 200
    dup = env.client.post(f"{API}/courses/{course_id}/enroll", headers=_auth(env.token_a))
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "ALREADY_ENROLLED"
    assert env.client.get(f"{API}/courses/mine", headers=_auth(env.token_a)).json()["data"]["total"] >= 1
    assert env.client.delete(f"{API}/courses/{course_id}/enroll", headers=_auth(env.token_a)).status_code == 200


def test_global_search_and_suggest(env: SimpleNamespace) -> None:
    """全局搜索按类型分组返回；联想返回可跳转项。"""
    body = env.client.get(f"{API}/search", params={"q": "python", "limit": 5}).json()
    groups = body["data"]["groups"]
    assert groups and all({"type", "items"} <= set(group) for group in groups)
    assert body["data"]["total"] >= 1
    assert env.client.get(f"{API}/search/suggest", params={"q": "python"}).json()["data"]["suggestions"]


def test_recommendations(env: SimpleNamespace) -> None:
    """推荐接口：下一节 / 题目 / 复习 / 建议。"""
    headers = _auth(env.token_a)
    assert env.client.get(f"{API}/recommendations/next-lesson", headers=headers).json()["success"] is True
    problems = env.client.get(f"{API}/recommendations/problems", params={"limit": 5}, headers=headers).json()["data"]
    assert isinstance(problems, list) and problems
    assert isinstance(env.client.get(f"{API}/recommendations/review", headers=headers).json()["data"], list)
    advice = env.client.get(f"{API}/recommendations/advice", headers=headers).json()["data"]
    assert isinstance(advice, list) and advice


def test_unauthorized_returns_401(env: SimpleNamespace) -> None:
    """未登录访问需鉴权接口 → 401。"""
    resp = env.client.get(f"{API}/progress")
    assert resp.status_code == 401
    assert resp.json()["success"] is False and resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_cannot_end_others_session_403(env: SimpleNamespace) -> None:
    """A 结束 B 的学习会话 → 403（越权防护）。"""
    resp = env.client.post(f"{API}/progress/sessions/{env.session_b_id}/end", json={}, headers=_auth(env.token_a))
    assert resp.status_code == 403
    assert resp.json()["success"] is False and resp.json()["error"]["code"] == "FORBIDDEN"


def test_lesson_not_found_404(env: SimpleNamespace) -> None:
    """不存在的课时 → 404 `LESSON_NOT_FOUND`。"""
    resp = env.client.get(f"{API}/lessons/not-a-real-lesson")
    assert resp.status_code == 404 and resp.json()["error"]["code"] == "LESSON_NOT_FOUND"
