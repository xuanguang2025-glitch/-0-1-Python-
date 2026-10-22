"""学习功能域 API 测试：错题本 / 收藏 / 搜索 / 推荐（`docs/API.md` §2.16-2.18 + 推荐域）。

重点断言：
- 错题：新建 → 列表筛选（`resolved` / `error_type`）→ 复习队列排序 → 标记已掌握 → 删除；
- 书签：`kind` 与 `ref_id` 组合约束、分页与 `collection` 分组统计；
- 搜索：`types` 分组过滤与 `total` 一致性、空关键词不报错；
- 推荐：无报名课程时 `/recommendations/next-lesson` 回退到阶段 1 首课。
"""

from __future__ import annotations

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select

from app.api.endpoints import bookmarks as bookmarks_ep
from app.api.endpoints import mistakes as mistakes_ep
from app.api.endpoints import recommendations as rec_ep
from app.api.endpoints import search as search_ep
from app.core.security import create_access_token
from app.models.course import Chapter, Course, Lesson, Topic
from app.models.learning import Mistake
from app.models.user import User
from app.utils.time import add_days, now_utc

DOMAIN_ROUTERS = (mistakes_ep.router, bookmarks_ep.router, search_ep.router, rec_ep.router)


@pytest.fixture()
def client(client_factory, db) -> TestClient:
    """仅挂载本域 4 个 router 的客户端（会话级复用）。

    显式依赖 `db` 以登记基座的每用例会话工厂。
    """
    return client_factory(DOMAIN_ROUTERS)


@pytest.fixture()
def seeded(db) -> dict[str, object]:
    """最小内容种子：一个课程 + 章节 + 课时 + 知识点（供搜索与推荐使用）。"""
    course = Course(
        slug="stage-01-python-basics",
        stage_no=1,
        title="阶段 1 · Python 入门",
        subtitle="装好环境，写出第一行能跑的代码",
        level="beginner",
        lesson_count=1,
        order_index=1,
    )
    db.add(course)
    db.flush()
    chapter = Chapter(course_id=course.id, slug="ch-01", title="环境与第一个程序", order_index=0, lesson_count=1)
    db.add(chapter)
    db.flush()
    lesson = Lesson(
        chapter_id=chapter.id,
        slug="hello-python",
        title="Python 第一个程序",
        summary="打印你的第一行 Python 代码",
        content_md="# Hello\nprint('hi')",
        order_index=0,
        xp_reward=10,
    )
    db.add(lesson)
    db.flush()
    topic = Topic(slug="first-program", name="第一个程序", order_index=0)
    db.add(topic)
    db.commit()
    return {
        "course_id": course.id,
        "chapter_id": chapter.id,
        "lesson_id": lesson.id,
        "topic_id": topic.id,
    }


@pytest.fixture()
def other_headers(db, password_hash: str) -> dict[str, str]:
    """另一个用户的鉴权头（用于 IDOR 校验）。"""
    user = User(
        email="intruder@pythonlab.dev",
        username="intruder",
        hashed_password=password_hash,
        role="user",
        is_verified=True,
    )
    db.add(user)
    db.commit()
    token, _jti, _exp = create_access_token(user.id, role="user", username=user.username)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 错题本
# ---------------------------------------------------------------------------


def test_mistake_crud_lifecycle(client: TestClient, user_headers: dict[str, str], seeded) -> None:
    """错题：新建 → 详情 → 更新笔记 → 标记已掌握 → 取消 → 删除。"""
    created = client.post(
        "/api/mistakes",
        json={
            "title": "列表推导式写错",
            "user_answer": "[x*2 for x in xs]",
            "correct_answer": "[x**2 for x in xs]",
            "error_type": "logic",
            "topic_id": seeded["topic_id"],
            "note_md": "注意幂 vs 乘",
        },
        headers=user_headers,
    )
    assert created.status_code == 200, created.text
    mistake = created.json()["data"]
    mistake_id = mistake["id"]
    assert mistake["resolved"] is False
    assert mistake["error_type"] == "logic"
    assert mistake["next_review_at"] is not None, "新建错题应自动安排首次复习"

    detail = client.get(f"/api/mistakes/{mistake_id}", headers=user_headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["title"] == "列表推导式写错"

    patched = client.patch(f"/api/mistakes/{mistake_id}", json={"note_md": "改：平方用 **"}, headers=user_headers)
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["note_md"] == "改：平方用 **"

    resolved = client.post(f"/api/mistakes/{mistake_id}/resolve", json={"resolved": True}, headers=user_headers)
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["data"]["resolved"] is True
    assert resolved.json()["data"]["resolved_at"] is not None

    reopened = client.post(f"/api/mistakes/{mistake_id}/resolve", json={"resolved": False}, headers=user_headers)
    assert reopened.json()["data"]["resolved"] is False
    assert reopened.json()["data"]["resolved_at"] is None

    deleted = client.delete(f"/api/mistakes/{mistake_id}", headers=user_headers)
    assert deleted.status_code == 200, deleted.text
    gone = client.get(f"/api/mistakes/{mistake_id}", headers=user_headers)
    assert gone.status_code == 404
    assert gone.json()["error"]["code"] == "MISTAKE_NOT_FOUND"


def test_mistake_list_filters(client: TestClient, user_headers: dict[str, str], seeded) -> None:
    """错题列表支持 `error_type` / `resolved` 组合筛选与分页。"""
    for title, error_type in (("语法错", "syntax"), ("逻辑错", "logic"), ("运行错", "runtime")):
        resp = client.post("/api/mistakes", json={"title": title, "error_type": error_type}, headers=user_headers)
        assert resp.status_code == 200, resp.text

    logic = client.post("/api/mistakes", json={"title": "待解决逻辑错", "error_type": "logic"}, headers=user_headers)
    logic_id = logic.json()["data"]["id"]
    client.post(f"/api/mistakes/{logic_id}/resolve", json={"resolved": True}, headers=user_headers)

    only_logic = client.get("/api/mistakes", params={"error_type": "logic"}, headers=user_headers).json()["data"]
    assert only_logic["total"] == 2
    assert {item["error_type"] for item in only_logic["items"]} == {"logic"}

    unresolved = client.get("/api/mistakes", params={"resolved": False}, headers=user_headers).json()["data"]
    assert unresolved["total"] == 3
    assert all(item["resolved"] is False for item in unresolved["items"])

    resolved = client.get("/api/mistakes", params={"resolved": True}, headers=user_headers).json()["data"]
    assert resolved["total"] == 1 and resolved["items"][0]["id"] == logic_id

    combined = client.get(
        "/api/mistakes", params={"error_type": "logic", "resolved": True}, headers=user_headers
    ).json()["data"]
    assert combined["total"] == 1 and combined["items"][0]["id"] == logic_id

    paged = client.get("/api/mistakes", params={"page": 1, "page_size": 2}, headers=user_headers).json()["data"]
    assert paged["total"] == 4
    assert len(paged["items"]) == 2 and paged["pages"] == 2


def test_mistake_review_queue_orders_by_next_review_at(
    client: TestClient, user_headers: dict[str, str], db, seeded
) -> None:
    """复习队列按 `next_review_at` 升序，且不含已掌握错题。"""
    user_id = None
    resp = client.get("/api/mistakes", headers=user_headers)
    assert resp.status_code == 200

    # 直接造三条：两个未到期（时间不同）+ 一个已到期
    me = db.scalars(select(User).where(User.email == "tester@pythonlab.dev")).one()
    user_id = me.id
    records = []
    for title, offset_days in (("后天复习", 2), ("今天复习", 0), ("已掌握", 1)):
        item = Mistake(
            user_id=user_id,
            title=title,
            error_type="logic",
            next_review_at=add_days(now_utc(), offset_days),
            resolved=title == "已掌握",
        )
        db.add(item)
        records.append(item)
    db.commit()

    queue = client.get("/api/mistakes/review-queue", params={"limit": 10}, headers=user_headers)
    assert queue.status_code == 200, queue.text
    items = queue.json()["data"]
    titles = [item["title"] for item in items]
    assert "已掌握" not in titles, "复习队列不得包含已掌握的错题"
    assert titles.index("今天复习") < titles.index("后天复习"), "越早到期越靠前"


def test_mistake_topics_stats(client: TestClient, user_headers: dict[str, str], seeded) -> None:
    """高频错误知识点统计按错题条数聚合。"""
    for _ in range(2):
        client.post(
            "/api/mistakes",
            json={"title": "同一知识点的错题", "error_type": "logic", "topic_id": seeded["topic_id"]},
            headers=user_headers,
        )
    client.post("/api/mistakes", json={"title": "无知识点错题", "error_type": "syntax"}, headers=user_headers)

    resp = client.get("/api/mistakes/topics", headers=user_headers)
    assert resp.status_code == 200, resp.text
    rows = resp.json()["data"]
    assert rows, "统计结果不应为空"
    assert rows[0]["topic_id"] == seeded["topic_id"]
    assert rows[0]["name"] == "第一个程序"
    assert rows[0]["mistake_count"] == 2
    assert {row["name"] for row in rows} == {"第一个程序", "未归类"}


def test_mistakes_are_isolated_between_users(
    client: TestClient, user_headers: dict[str, str], other_headers: dict[str, str]
) -> None:
    """**IDOR 红线**：错题是「本人」数据，A 看不到也改不了 B 的错题。"""
    created = client.post("/api/mistakes", json={"title": "A 的私有错题"}, headers=user_headers)
    mistake_id = created.json()["data"]["id"]

    assert client.get("/api/mistakes", headers=other_headers).json()["data"]["total"] == 0

    read = client.get(f"/api/mistakes/{mistake_id}", headers=other_headers)
    assert read.status_code == 403, read.text
    assert read.json()["error"]["code"] == "FORBIDDEN"

    write = client.post(f"/api/mistakes/{mistake_id}/resolve", json={"resolved": True}, headers=other_headers)
    assert write.status_code == 403

    drop = client.delete(f"/api/mistakes/{mistake_id}", headers=other_headers)
    assert drop.status_code == 403


# ---------------------------------------------------------------------------
# 收藏
# ---------------------------------------------------------------------------


def test_bookmark_requires_code_for_snippet(client: TestClient, user_headers: dict[str, str], seeded) -> None:
    """`kind=snippet` 必须带 `code_snippet`，否则 400 `BAD_REQUEST`。"""
    bad = client.post("/api/bookmarks", json={"kind": "snippet", "title": "无代码片段"}, headers=user_headers)
    assert bad.status_code == 400, bad.text
    assert bad.json()["error"]["code"] == "BAD_REQUEST"

    ok = client.post(
        "/api/bookmarks",
        json={"kind": "snippet", "title": "双端队列", "code_snippet": "from collections import deque"},
        headers=user_headers,
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["code_snippet"] == "from collections import deque"
    assert ok.json()["data"]["language"] == "python"


def test_bookmark_unknown_kind_falls_back_to_problem(client: TestClient, user_headers: dict[str, str], seeded) -> None:
    """非法 `kind` 归一化为 `problem`（不抛错，保证前端容错）。"""
    resp = client.post("/api/bookmarks", json={"kind": "not-a-kind", "title": "兜底类型"}, headers=user_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["kind"] == "problem"


def test_bookmark_ref_id_and_filters(client: TestClient, user_headers: dict[str, str], seeded) -> None:
    """`ref_id` 原样保存；`kind` 与 `collection` 筛选生效。"""
    lesson_ref = client.post(
        "/api/bookmarks",
        json={"kind": "lesson", "ref_id": seeded["lesson_id"], "title": "第一课", "collection": "课程"},
        headers=user_headers,
    )
    assert lesson_ref.status_code == 200, lesson_ref.text
    assert lesson_ref.json()["data"]["ref_id"] == seeded["lesson_id"]
    assert lesson_ref.json()["data"]["collection"] == "课程"

    client.post(
        "/api/bookmarks",
        json={"kind": "problem", "ref_id": seeded["topic_id"], "title": "一道题", "collection": "题库"},
        headers=user_headers,
    )
    client.post(
        "/api/bookmarks",
        json={"kind": "snippet", "title": "片段", "code_snippet": "print(1)", "collection": "课程"},
        headers=user_headers,
    )

    lessons = client.get("/api/bookmarks", params={"kind": "lesson"}, headers=user_headers).json()["data"]
    assert lessons["total"] == 1 and lessons["items"][0]["title"] == "第一课"

    in_course = client.get("/api/bookmarks", params={"collection": "课程"}, headers=user_headers).json()["data"]
    assert in_course["total"] == 2

    combined = client.get(
        "/api/bookmarks", params={"kind": "snippet", "collection": "课程"}, headers=user_headers
    ).json()["data"]
    assert combined["total"] == 1 and combined["items"][0]["title"] == "片段"


def test_bookmark_pagination_and_collections(client: TestClient, user_headers: dict[str, str]) -> None:
    """分页元数据正确；集合统计按集合名聚合计数。"""
    for index in range(5):
        resp = client.post(
            "/api/bookmarks",
            json={
                "kind": "problem",
                "title": f"题目收藏 {index}",
                "collection": "默认集" if index < 3 else "面试集",
            },
            headers=user_headers,
        )
        assert resp.status_code == 200, resp.text

    page1 = client.get("/api/bookmarks", params={"page": 1, "page_size": 2}, headers=user_headers).json()["data"]
    assert page1["total"] == 5 and page1["pages"] == 3 and len(page1["items"]) == 2
    page3 = client.get("/api/bookmarks", params={"page": 3, "page_size": 2}, headers=user_headers).json()["data"]
    assert len(page3["items"]) == 1

    collections = client.get("/api/bookmarks/collections", headers=user_headers)
    assert collections.status_code == 200, collections.text
    counts = {row["name"]: row["count"] for row in collections.json()["data"]["collections"]}
    assert counts == {"默认集": 3, "面试集": 2}


def test_bookmark_update_and_delete(client: TestClient, user_headers: dict[str, str]) -> None:
    """收藏可改标题 / 笔记 / 集合 / 标签，可删除；他人不可操作（IDOR 红线）。"""
    created = client.post("/api/bookmarks", json={"kind": "problem", "title": "待改"}, headers=user_headers)
    bookmark_id = created.json()["data"]["id"]

    updated = client.patch(
        f"/api/bookmarks/{bookmark_id}",
        json={"title": "已改标题", "note": "这条笔记很有用", "collection": "归档", "tags": ["算法", "复习"]},
        headers=user_headers,
    )
    assert updated.status_code == 200, updated.text
    data = updated.json()["data"]
    assert data["title"] == "已改标题"
    assert data["description"] == "这条笔记很有用"
    assert data["collection"] == "归档"
    assert data["tags"] == ["算法", "复习"]

    assert client.delete(f"/api/bookmarks/{bookmark_id}", headers=user_headers).status_code == 200
    assert client.get("/api/bookmarks", headers=user_headers).json()["data"]["total"] == 0


def test_bookmark_cannot_touch_others(
    client: TestClient, user_headers: dict[str, str], other_headers: dict[str, str]
) -> None:
    """**IDOR 红线**：B 无法修改 / 删除 A 的收藏。"""
    bookmark_id = client.post(
        "/api/bookmarks", json={"kind": "problem", "title": "A 的收藏"}, headers=user_headers
    ).json()["data"]["id"]

    assert client.get("/api/bookmarks", headers=other_headers).json()["data"]["total"] == 0

    patch = client.patch(f"/api/bookmarks/{bookmark_id}", json={"title": "被篡改"}, headers=other_headers)
    assert patch.status_code == 403, patch.text
    assert patch.json()["error"]["code"] == "FORBIDDEN"

    assert client.delete(f"/api/bookmarks/{bookmark_id}", headers=other_headers).status_code == 403

    # 收藏仍属于 A，未被 B 破坏
    assert client.get("/api/bookmarks", headers=user_headers).json()["data"]["items"][0]["title"] == "A 的收藏"


# ---------------------------------------------------------------------------
# 搜索
# ---------------------------------------------------------------------------


def test_search_groups_and_total_are_consistent(client: TestClient, seeded) -> None:
    """分组结果的 `total` 必须等于各组条目数之和；`types` 可裁剪分组。"""
    resp = client.get("/api/search", params={"q": "Python", "limit": 5})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["keyword"] == "Python"
    assert data["groups"], "应至少命中一个分组"

    grouped = {group["type"]: group for group in data["groups"]}
    assert "course" in grouped, "课程标题命中关键词"
    assert "lesson" in grouped, "课时标题命中关键词"
    assert all(group["label"] for group in data["groups"]), "每组都要有中文标签"
    assert data["total"] == sum(len(group["items"]) for group in data["groups"])

    course_item = grouped["course"]["items"][0]
    assert course_item["url"] == "/courses/stage-01-python-basics"
    assert course_item["id"] == seeded["course_id"]

    limited = client.get("/api/search", params={"q": "Python", "types": "course", "limit": 5}).json()["data"]
    assert [group["type"] for group in limited["groups"]] == ["course"], "types 只保留指定类型"
    assert limited["total"] == len(limited["groups"][0]["items"])


def test_search_with_empty_and_unknown_keyword(client: TestClient, seeded) -> None:
    """空关键词与无结果关键词都返回 200 空分组（不报错）。"""
    empty = client.get("/api/search", params={"q": "   "})
    assert empty.status_code == 200, empty.text
    assert empty.json()["data"]["groups"] == []
    assert empty.json()["data"]["total"] == 0

    none = client.get("/api/search", params={"q": "zzzz-不存在的关键词-zzzz"})
    assert none.status_code == 200
    assert none.json()["data"]["total"] == 0

    # 缺少必填参数 → 422 结构化校验错误
    missing = client.get("/api/search")
    assert missing.status_code == 422
    assert missing.json()["error"]["code"] == "VALIDATION_ERROR"


def test_search_suggest_returns_jumpable_items(client: TestClient, seeded) -> None:
    """搜索联想返回可跳转的建议项。"""
    resp = client.get("/api/search/suggest", params={"q": "Python"})
    assert resp.status_code == 200, resp.text
    suggestions = resp.json()["data"]["suggestions"]
    assert suggestions, "联想结果不应为空"
    assert all({"text", "type", "url"} <= set(item) for item in suggestions)
    assert any(item["type"] == "course" and item["url"] == "/courses/stage-01-python-basics" for item in suggestions)

    empty = client.get("/api/search/suggest", params={"q": ""})
    assert empty.status_code == 422


# ---------------------------------------------------------------------------
# 推荐
# ---------------------------------------------------------------------------


def test_recommend_next_lesson_falls_back_to_first_course(
    client: TestClient, user_headers: dict[str, str], seeded
) -> None:
    """无报名课程时回退到阶段 1 的第一节课。"""
    resp = client.get("/api/recommendations/next-lesson", headers=user_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data is not None, "已有课程数据时不应返回 null"
    assert data["id"] == seeded["lesson_id"]
    assert data["title"] == "Python 第一个程序"


def test_recommend_next_lesson_respects_completed_lessons(
    client: TestClient, user_headers: dict[str, str], seeded, db
) -> None:
    """首课完成后推荐继续往后找；全部完成时回落到第一节课，推荐永不返回空。"""
    from app.models.learning import LearningProgress

    me = db.scalars(select(User).where(User.email == "tester@pythonlab.dev")).one()
    db.add(
        LearningProgress(
            user_id=me.id,
            lesson_id=seeded["lesson_id"],
            status="completed",
            progress_percent=100,
        )
    )
    db.commit()

    resp = client.get("/api/recommendations/next-lesson", headers=user_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data is not None, "全部完成后仍应回落到最后一节，保证推荐不空"
    assert data["id"] == seeded["lesson_id"]


def test_recommend_advice_and_review(client: TestClient, user_headers: dict[str, str], seeded) -> None:
    """学习建议与复习推荐返回结构化列表，且含可执行文案。"""
    advice = client.get("/api/recommendations/advice", headers=user_headers)
    assert advice.status_code == 200, advice.text
    items = advice.json()["data"]
    assert items, "至少应有一条学习建议"
    assert all({"type", "title", "reason"} <= set(item) for item in items)
    assert any(item["type"] == "lesson" for item in items), "应包含继续学习的建议"

    review = client.get("/api/recommendations/review", headers=user_headers)
    assert review.status_code == 200
    assert isinstance(review.json()["data"], list)


def test_recommendations_require_login(client: TestClient, seeded) -> None:
    """推荐域需登录：未带令牌 → 401。"""
    resp = client.get("/api/recommendations/next-lesson")
    assert resp.status_code == 401, resp.text
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"
