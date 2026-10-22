"""认证与用户域 API 测试（`docs/API.md` §2.1 auth 7 op + §2.2 users 8 op）。

覆盖重点：
- 注册冲突（邮箱 / 用户名）→ 409，弱密码 → 422 `WEAK_PASSWORD`；
- refresh 轮换与吊销、登出后 access/refresh 双失效；
- **IDOR 红线**：普通用户访问管理员专属端点 → 403；
- **隐私红线**：`/users/{id}/public` 与导出文件均不得泄露 email / 密码哈希；
- 头像上传的类型白名单与大小上限。

数据全部走 conftest 的每用例内存库，不触碰真实种子库。
"""

from __future__ import annotations

import io
import json
from typing import Any

from fastapi.testclient import TestClient
import pytest

from app.api.endpoints import auth as auth_ep
from app.api.endpoints import users as users_ep
from app.models.enums import UserStatus
from app.models.user import Profile, User

DOMAIN_ROUTERS = (auth_ep.router, users_ep.router)
TEST_PASSWORD = "Test@12345"
NEW_PASSWORD = "NewPass@2026"
#: 头像大小上限（与 `app.services.user_service.AVATAR_MAX_BYTES` 对齐）
MAX_AVATAR_BYTES = 2 * 1024 * 1024


@pytest.fixture()
def client(client_factory, db) -> TestClient:
    """仅挂载 auth + users 两个 router 的客户端（会话级复用）。

    显式依赖 `db` 以确保基座的每用例会话工厂已登记（`get_db` 覆盖在请求时解析它）。
    """
    return client_factory(DOMAIN_ROUTERS)


def _register_body(email: str, username: str, password: str = TEST_PASSWORD) -> dict[str, str]:
    """构造注册请求体。"""
    return {"email": email, "username": username, "password": password}


def _make_user(db, password_hash: str, *, email: str, username: str, status: str = "active") -> User:
    """直接造一个用户（用于停用账号等无法经注册构造的场景）。"""
    user = User(
        email=email,
        username=username,
        hashed_password=password_hash,
        role="user",
        status=status,
        is_verified=True,
    )
    db.add(user)
    db.flush()
    db.add(Profile(user_id=user.id, display_name=username))
    db.commit()
    db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# 注册
# ---------------------------------------------------------------------------


def test_register_creates_user_and_profile(client: TestClient, db) -> None:
    """注册成功即登录：返回令牌对，资料自动补建，且响应绝不含密码哈希。"""
    resp = client.post("/api/auth/register", json=_register_body("newbie@pythonlab.dev", "newbie"))
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["token_type"] == "bearer"
    assert data["access_token"] and data["refresh_token"]
    assert data["user"]["email"] == "newbie@pythonlab.dev"
    assert data["user"]["role"] == "user" and data["user"]["level"] == 1

    user = db.query(User).filter(User.email == "newbie@pythonlab.dev").one()
    assert user.hashed_password != TEST_PASSWORD, "密码必须哈希入库"
    assert db.query(Profile).filter(Profile.user_id == user.id).count() == 1, "注册应自动建立 1:1 资料"

    assert "hashed_password" not in resp.text
    assert TEST_PASSWORD not in resp.text


def test_register_normalizes_email_to_lowercase(client: TestClient, db) -> None:
    """邮箱统一小写存储（登录与唯一性都按小写比较）。"""
    resp = client.post("/api/auth/register", json=_register_body("MiXeD@PythonLab.DEV", "mixedcase"))
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["user"]["email"] == "mixed@pythonlab.dev"
    assert db.query(User).filter(User.email == "mixed@pythonlab.dev").count() == 1


def test_register_rejects_duplicate_email_and_username(client: TestClient) -> None:
    """重复邮箱 → 409 `EMAIL_EXISTS`；重复用户名 → 409 `USERNAME_EXISTS`。"""
    first = client.post("/api/auth/register", json=_register_body("dup@pythonlab.dev", "dupuser"))
    assert first.status_code == 200, first.text

    same_email = client.post("/api/auth/register", json=_register_body("dup@pythonlab.dev", "otheruser"))
    assert same_email.status_code == 409
    assert same_email.json()["error"]["code"] == "EMAIL_EXISTS"

    same_name = client.post("/api/auth/register", json=_register_body("other@pythonlab.dev", "dupuser"))
    assert same_name.status_code == 409
    assert same_name.json()["error"]["code"] == "USERNAME_EXISTS"


def test_register_rejects_weak_password(client: TestClient) -> None:
    """弱密码（≥8 位但缺字母）→ 422 `WEAK_PASSWORD`；强密码可注册。"""
    weak = client.post("/api/auth/register", json=_register_body("weak@pythonlab.dev", "weakuser", "12345678"))
    assert weak.status_code == 422, weak.text
    assert weak.json()["error"]["code"] == "WEAK_PASSWORD"

    strong = client.post("/api/auth/register", json=_register_body("weak@pythonlab.dev", "weakuser", "abcd1234"))
    assert strong.status_code == 200, strong.text


def test_register_rejects_malformed_payload(client: TestClient) -> None:
    """非法邮箱 / 过短用户名 → 422 `VALIDATION_ERROR`（结构化字段错误）。"""
    bad_email = client.post("/api/auth/register", json=_register_body("not-an-email", "validname"))
    assert bad_email.status_code == 422
    assert bad_email.json()["error"]["code"] == "VALIDATION_ERROR"

    bad_name = client.post("/api/auth/register", json=_register_body("ok@pythonlab.dev", "a"))
    assert bad_name.status_code == 422
    assert bad_name.json()["error"]["code"] == "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# 登录 / 刷新 / 登出
# ---------------------------------------------------------------------------


def test_login_with_email_or_username_and_wrong_password(client: TestClient) -> None:
    """邮箱或用户名均可登录；密码错误统一 401 `INVALID_CREDENTIALS`（不区分账号是否存在）。"""
    reg = client.post("/api/auth/register", json=_register_body("login@pythonlab.dev", "loginuser"))
    assert reg.status_code == 200, reg.text

    by_email = client.post("/api/auth/login", json={"account": "login@pythonlab.dev", "password": TEST_PASSWORD})
    assert by_email.status_code == 200, by_email.text

    by_name = client.post("/api/auth/login", json={"account": "loginuser", "password": TEST_PASSWORD})
    assert by_name.status_code == 200, by_name.text

    wrong = client.post("/api/auth/login", json={"account": "loginuser", "password": "Wrong@1234"})
    assert wrong.status_code == 401
    assert wrong.json()["error"]["code"] == "INVALID_CREDENTIALS"

    ghost = client.post("/api/auth/login", json={"account": "nobody@pythonlab.dev", "password": TEST_PASSWORD})
    assert ghost.status_code == 401, "不存在的账号也必须返回 401，避免账号枚举"
    assert ghost.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_suspended_account_cannot_login(client: TestClient, db, password_hash: str) -> None:
    """被停用账号登录 → 403 `ACCOUNT_SUSPENDED`。"""
    _make_user(
        db,
        password_hash,
        email="banned@pythonlab.dev",
        username="banned",
        status=UserStatus.SUSPENDED.value,
    )
    resp = client.post("/api/auth/login", json={"account": "banned", "password": TEST_PASSWORD})
    assert resp.status_code == 403, resp.text
    assert resp.json()["error"]["code"] == "ACCOUNT_SUSPENDED"


def test_refresh_rotates_and_revokes_old_token(client: TestClient) -> None:
    """刷新令牌会轮换：旧 refresh 立即失效（401 `TOKEN_REVOKED`），新对可用。"""
    reg = client.post("/api/auth/register", json=_register_body("refresh@pythonlab.dev", "refreshuser"))
    old_refresh = reg.json()["data"]["refresh_token"]

    rotated = client.post("/api/auth/refresh", json={"refresh_token": old_refresh})
    assert rotated.status_code == 200, rotated.text
    new_pair = rotated.json()["data"]
    assert new_pair["refresh_token"] != old_refresh, "refresh 必须轮换出新令牌"

    reuse = client.post("/api/auth/refresh", json={"refresh_token": old_refresh})
    assert reuse.status_code == 401
    assert reuse.json()["error"]["code"] == "TOKEN_REVOKED"


def test_logout_revokes_access_and_refresh(client: TestClient) -> None:
    """登出后：原 access 被拉黑（`TOKEN_REVOKED`），原 refresh 同步吊销。"""
    reg = client.post("/api/auth/register", json=_register_body("bye@pythonlab.dev", "byeuser"))
    pair = reg.json()["data"]
    headers = {"Authorization": f"Bearer {pair['access_token']}"}

    assert client.get("/api/auth/me", headers=headers).status_code == 200

    out = client.post("/api/auth/logout", json={"refresh_token": pair["refresh_token"]}, headers=headers)
    assert out.status_code == 200, out.text

    after = client.get("/api/auth/me", headers=headers)
    assert after.status_code == 401
    assert after.json()["error"]["code"] == "TOKEN_REVOKED"

    reuse = client.post("/api/auth/refresh", json={"refresh_token": pair["refresh_token"]})
    assert reuse.status_code == 401
    assert reuse.json()["error"]["code"] == "TOKEN_REVOKED"


def test_me_returns_profile_brief_without_password(client: TestClient, user_headers: dict[str, str]) -> None:
    """`/auth/me` 含资料摘要，但绝不包含密码哈希。"""
    resp = client.get("/api/auth/me", headers=user_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["email"] == "tester@pythonlab.dev"
    assert data["role"] == "user"
    assert data["profile"]["display_name"] == "测试用户"
    assert "hashed_password" not in resp.text
    assert set(data["profile"]) == {
        "display_name",
        "avatar_url",
        "bio",
        "theme_preference",
        "ai_mode",
        "learning_mode",
    }


# ---------------------------------------------------------------------------
# 改密与管理员重置（含 IDOR 红线）
# ---------------------------------------------------------------------------


def test_change_password_invalidates_old_password(client: TestClient) -> None:
    """改密后旧密码登录失败、新密码可登录，且旧 refresh 全部吊销。"""
    reg = client.post("/api/auth/register", json=_register_body("rotate@pythonlab.dev", "rotateuser"))
    pair = reg.json()["data"]
    headers = {"Authorization": f"Bearer {pair['access_token']}"}

    changed = client.post(
        "/api/auth/change-password",
        json={"old_password": TEST_PASSWORD, "new_password": NEW_PASSWORD},
        headers=headers,
    )
    assert changed.status_code == 200, changed.text

    old_pw = client.post("/api/auth/login", json={"account": "rotateuser", "password": TEST_PASSWORD})
    assert old_pw.status_code == 401
    assert old_pw.json()["error"]["code"] == "INVALID_CREDENTIALS"

    new_pw = client.post("/api/auth/login", json={"account": "rotateuser", "password": NEW_PASSWORD})
    assert new_pw.status_code == 200, new_pw.text

    stale = client.post("/api/auth/refresh", json={"refresh_token": pair["refresh_token"]})
    assert stale.status_code == 401, "改密必须吊销全部 refresh，强制其它设备重登"


def test_change_password_rejects_wrong_old_password(client: TestClient, user_headers: dict[str, str]) -> None:
    """原密码错误 → 401 `INVALID_CREDENTIALS`。"""
    resp = client.post(
        "/api/auth/change-password",
        json={"old_password": "Totally@Wrong1", "new_password": NEW_PASSWORD},
        headers=user_headers,
    )
    assert resp.status_code == 401, resp.text
    assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_idor_non_admin_cannot_reset_password(
    client: TestClient, user_headers: dict[str, str], seeded_users, db
) -> None:
    """**IDOR 红线**：普通用户调用管理员专属的重置密码端点 → 403 `FORBIDDEN`。"""
    resp = client.post(
        "/api/auth/reset-password",
        json={"user_id": seeded_users.admin_id, "new_password": NEW_PASSWORD},
        headers=user_headers,
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["error"]["code"] == "FORBIDDEN"

    admin = db.get(User, seeded_users.admin_id)
    assert admin.hashed_password != NEW_PASSWORD, "越权请求不得改动管理员密码"


def test_admin_can_reset_password(client: TestClient, admin_headers: dict[str, str], seeded_users) -> None:
    """管理员可重置指定用户密码，重置后该用户可用新密码登录。"""
    resp = client.post(
        "/api/auth/reset-password",
        json={"user_id": seeded_users.user_id, "new_password": NEW_PASSWORD},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text

    login = client.post("/api/auth/login", json={"account": "tester", "password": NEW_PASSWORD})
    assert login.status_code == 200, login.text


# ---------------------------------------------------------------------------
# 用户资料 / 偏好 / 头像
# ---------------------------------------------------------------------------


def test_profile_read_and_update(client: TestClient, user_headers: dict[str, str]) -> None:
    """资料可读可改；只接受白名单字段（多传字段 422）。"""
    read = client.get("/api/users/me/profile", headers=user_headers)
    assert read.status_code == 200, read.text
    assert read.json()["data"]["display_name"] == "测试用户"

    updated = client.patch(
        "/api/users/me/profile",
        json={"display_name": "新昵称", "bio": "热爱 Python", "timezone": "Asia/Shanghai"},
        headers=user_headers,
    )
    assert updated.status_code == 200, updated.text
    data = updated.json()["data"]
    assert data["display_name"] == "新昵称"
    assert data["bio"] == "热爱 Python"
    assert data["timezone"] == "Asia/Shanghai"

    # display_name 长度超限 → 422
    too_long = client.patch("/api/users/me/profile", json={"display_name": "x" * 51}, headers=user_headers)
    assert too_long.status_code == 422
    assert too_long.json()["error"]["code"] == "VALIDATION_ERROR"


def test_preferences_update_and_validation(client: TestClient, user_headers: dict[str, str]) -> None:
    """偏好可更新；非法枚举值 → 422 `VALIDATION_ERROR`。"""
    ok = client.patch(
        "/api/users/me/preferences",
        json={"ai_mode": "advanced", "learning_mode": "drill", "theme_preference": "dark", "weekly_goal_minutes": 600},
        headers=user_headers,
    )
    assert ok.status_code == 200, ok.text
    data = ok.json()["data"]
    assert data["ai_mode"] == "advanced"
    assert data["learning_mode"] == "drill"
    assert data["theme_preference"] == "dark"
    assert data["weekly_goal_minutes"] == 600

    bad = client.patch("/api/users/me/preferences", json={"ai_mode": "godlike"}, headers=user_headers)
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "VALIDATION_ERROR"


def test_avatar_upload_accepts_png(client: TestClient, user_headers: dict[str, str]) -> None:
    """合法 PNG 头像上传成功并回写资料。"""
    resp = client.post(
        "/api/users/me/avatar",
        files={"file": ("avatar.png", io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * 64), "image/png")},
        headers=user_headers,
    )
    assert resp.status_code == 200, resp.text
    url = resp.json()["data"]["avatar_url"]
    assert url.startswith("/uploads/avatars/")

    profile = client.get("/api/users/me/profile", headers=user_headers).json()["data"]
    assert profile["avatar_url"] == url


def test_avatar_upload_rejects_disallowed_type(client: TestClient, user_headers: dict[str, str]) -> None:
    """非 jpg/png/webp → 400 `INVALID_FILE_TYPE`。"""
    resp = client.post(
        "/api/users/me/avatar",
        files={"file": ("evil.exe", io.BytesIO(b"MZ"), "application/x-msdownload")},
        headers=user_headers,
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["error"]["code"] == "INVALID_FILE_TYPE"


def test_avatar_upload_rejects_oversize(client: TestClient, user_headers: dict[str, str]) -> None:
    """超过 2MB → 400 `FILE_TOO_LARGE`。"""
    payload = b"\x89PNG\r\n\x1a\n" + b"0" * MAX_AVATAR_BYTES
    resp = client.post(
        "/api/users/me/avatar",
        files={"file": ("big.png", io.BytesIO(payload), "image/png")},
        headers=user_headers,
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["error"]["code"] == "FILE_TOO_LARGE"


# ---------------------------------------------------------------------------
# 概览 / 导出 / 注销 / 公开资料隐私
# ---------------------------------------------------------------------------


def test_overview_returns_expected_shape(client: TestClient, user_headers: dict[str, str]) -> None:
    """学习概览字段齐全。"""
    resp = client.get("/api/users/me/overview", headers=user_headers)
    assert resp.status_code == 200, resp.text
    data: dict[str, Any] = resp.json()["data"]
    assert set(data) == {
        "xp",
        "level",
        "next_level_xp",
        "streak_days",
        "completed_lessons",
        "solved_problems",
        "today_minutes",
        "daily_tasks_done",
    }
    assert data["level"] >= 1 and data["next_level_xp"] >= 0


def test_export_json_masks_email(client: TestClient, user_headers: dict[str, str]) -> None:
    """**隐私红线**：导出文件里的邮箱必须是脱敏形式，不出现明文与密码哈希。"""
    resp = client.get("/api/users/me/export", params={"format": "json"}, headers=user_headers)
    assert resp.status_code == 200, resp.text
    assert "attachment" in resp.headers.get("content-disposition", "")

    payload = json.loads(resp.content.decode("utf-8"))
    email = payload["user"]["email"]
    assert email != "tester@pythonlab.dev", "导出必须脱敏邮箱"
    assert "*" in email or "@" in email
    assert "hashed_password" not in resp.content.decode("utf-8")


def test_delete_account_soft_deletes(client: TestClient, user_headers: dict[str, str], db) -> None:
    """注销需校验密码；成功后账号被软删除，原令牌立即失效。"""
    wrong = client.request("DELETE", "/api/users/me", json={"password": "Nope@12345"}, headers=user_headers)
    assert wrong.status_code == 401, wrong.text

    ok = client.request("DELETE", "/api/users/me", json={"password": TEST_PASSWORD}, headers=user_headers)
    assert ok.status_code == 200, ok.text

    user = db.query(User).filter(User.email == "tester@pythonlab.dev").one()
    assert user.deleted_at is not None, "注销必须是软删除（保留数据可审计）"
    assert user.status == "deleted"

    after = client.get("/api/auth/me", headers=user_headers)
    assert after.status_code == 404
    assert after.json()["error"]["code"] == "USER_NOT_FOUND"


def test_public_profile_privacy_redline(client: TestClient, seeded_users, db) -> None:
    """**隐私红线**：`/users/{id}/public` 只返回昵称与等级等公开字段。

    断言三件事：字段集合白名单、响应体不含邮箱、不含用户真实 id 之外的隐私信息。
    """
    user = db.get(User, seeded_users.user_id)
    user.xp = 250
    user.level = 3
    db.commit()

    resp = client.get(f"/api/users/{seeded_users.user_id}/public")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    assert set(data) == {"id", "display_name", "avatar_url", "level", "xp"}
    assert data["display_name"] == "测试用户"
    assert data["level"] == 3 and data["xp"] == 250

    # 隐私断言：不得出现邮箱、用户名、密码哈希等任何可识别信息
    assert "tester@pythonlab.dev" not in resp.text
    assert "hashed_password" not in resp.text
    assert user.hashed_password not in resp.text
    assert "tester_admin@pythonlab.dev" not in resp.text


def test_public_profile_unknown_user_returns_404(client: TestClient) -> None:
    """不存在的用户 → 404 `USER_NOT_FOUND`。"""
    resp = client.get("/api/users/00000000-0000-0000-0000-000000000000/public")
    assert resp.status_code == 404, resp.text
    assert resp.json()["error"]["code"] == "USER_NOT_FOUND"
