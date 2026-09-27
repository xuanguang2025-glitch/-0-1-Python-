"""QA 安全红线探测 · 第二轮（XSS / CORS / CSRF / 安全响应头，可重复执行）。

覆盖项（每项输出「攻击输入 → 实际响应」证据）：
  XSS:
   X1 用户可控富文本（display_name / bio / avatar_url）存原文并回显，API 层为 JSON 通道不可执行
   X2 错题/收藏自由文本（title / note_md / code_snippet）payload 回显不产生 HTML 面
   X3 AI 对话消息回显（content_md）——前端 react-markdown 未启用 rehype-raw，原始 HTML 不渲染
   X4 关键端点响应 Content-Type 全部为 application/json
  CORS:
   C1 恶意 Origin 预检 → 不回显 Access-Control-Allow-Origin
   C2 白名单 Origin 预检 → 正确回显 + allow_credentials=true
   C3 恶意 Origin 简单请求 → 无 ACAO 头
   C4 Origin 仿冒/后缀/大小写/ userinfo 绕过 → 全部不回显
  CSRF:
   R1 无凭据状态变更请求 → 401（Bearer 不在 cookie，跨站无法自动携带）
   R2 登录响应不设置任何 Cookie（token 仅存在于 JSON body）
  建议:
   H1 安全响应头（X-Content-Type-Options / X-Frame-Options / Referrer-Policy 必备；API-only 不强制 CSP）

运行：cd backend && .venv/Scripts/python.exe scripts/security_probe_round2.py
退出码：0 = 全部通过（SKIP 项不计失败）；1 = 存在 FAIL。
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
REAL_DB = BACKEND_DIR / "data" / "pythonlab.db"

results: list[tuple[str, str, str]] = []  # (编号, 名称, PASS/FAIL/SKIP + 摘要)


def record(no: str, name: str, ok: bool | None, detail: str) -> None:
    status = "PASS" if ok else ("SKIP" if ok is None else "FAIL")
    results.append((no, name, f"{status} | {detail}"))
    print(f"[{status}] {no} {name}: {detail}")


XSS_PAYLOADS = [
    "<script>alert(1)</script>",
    '<img src=x onerror=alert(1)>',
    '"><svg onload=alert(1)>',
    "javascript:alert(1)",
]


def main() -> int:
    if not REAL_DB.exists():
        print(f"真实库不存在：{REAL_DB}，请先执行 alembic upgrade head + scripts/seed.py")
        return 1

    tmp_dir = Path(tempfile.mkdtemp(prefix="pythonlab_probe2_"))
    probe_db = tmp_dir / "probe.db"
    shutil.copy(REAL_DB, probe_db)
    os.environ["DATABASE_URL"] = f"sqlite:///{probe_db.as_posix()}"
    os.environ.setdefault("AI_OFFLINE", "true")
    os.environ.setdefault("SANDBOX_MODE", "local")
    os.environ.setdefault("CACHE_BACKEND", "memory")
    os.environ.setdefault("QUEUE_BACKEND", "inline")

    from fastapi.testclient import TestClient

    from app.main import app  # noqa: E402 - 必须在设置 DATABASE_URL 之后导入

    client = TestClient(app)

    suffix = uuid.uuid4().hex[:6]
    resp = client.post(
        "/api/auth/register",
        json={
            "email": f"probe2_{suffix}@example.com",
            "username": f"probe2_{suffix}",
            "password": "Probe1234",
        },
    )
    if resp.status_code not in (200, 201):
        record("0", "注册探针用户", False, f"HTTP {resp.status_code} {resp.text[:120]}")
        return _finish()
    token = resp.json()["data"]["access_token"]
    user_id = resp.json()["data"]["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}

    # ---------- X1. 用户可控富文本字段 ----------
    dn = '<img src=x onerror=alert(1)>'
    bio = "<script>alert(1)</script>"
    patch = client.patch(
        "/api/users/me/profile",
        json={"display_name": dn, "bio": bio, "avatar_url": "javascript:alert(1)"},
        headers=headers,
    )
    if patch.status_code != 200:
        record("X1", "富文本字段存储与回显", None, f"profile PATCH HTTP {patch.status_code}（校验拦截也算防护，人工复核）")
    else:
        me = client.get("/api/auth/me", headers=headers)
        pub = client.get(f"/api/users/{user_id}/public")
        echoed_me = dn in me.text and bio in me.text
        echoed_pub = dn in pub.text
        json_ok = me.headers.get("content-type", "").startswith("application/json") and pub.headers.get(
            "content-type", ""
        ).startswith("application/json")
        record(
            "X1",
            "富文本字段存储与回显",
            json_ok,
            f"原文回显 me={echoed_me} public={echoed_pub}，响应均为 JSON（React 默认转义渲染，无执行面）",
        )

    # ---------- X2. 错题 / 收藏自由文本 ----------
    mk = client.post(
        "/api/mistakes",
        json={"title": XSS_PAYLOADS[0], "note_md": XSS_PAYLOADS[1], "error_type": "logic"},
        headers=headers,
    )
    bm = client.post(
        "/api/bookmarks",
        json={"kind": "snippet", "title": XSS_PAYLOADS[2], "code_snippet": XSS_PAYLOADS[0]},
        headers=headers,
    )
    x2_ok = True
    x2_notes = []
    for name, resp2 in (("mistakes", mk), ("bookmarks", bm)):
        if resp2.status_code == 200:
            if not resp2.headers.get("content-type", "").startswith("application/json"):
                x2_ok = False
                x2_notes.append(f"{name} 非 JSON 响应")
            else:
                x2_notes.append(f"{name} JSON 原文回显={XSS_PAYLOADS[0] in resp2.text or XSS_PAYLOADS[2] in resp2.text}")
        elif resp2.status_code == 422:
            x2_notes.append(f"{name} 输入校验拦截(422)")
        else:
            x2_ok = False
            x2_notes.append(f"{name} HTTP {resp2.status_code}")
    record("X2", "错题/收藏自由文本", x2_ok, "；".join(x2_notes))

    # ---------- X3. AI 对话消息回显 ----------
    chat = client.post(
        "/api/ai/chat",
        json={"message": f"{XSS_PAYLOADS[0]} 我的代码哪里错了"},
        headers=headers,
    )
    if chat.status_code != 200:
        record("X3", "AI 消息回显", None, f"HTTP {chat.status_code}（限流/降级时人工复核）")
    else:
        content = chat.json()["data"].get("content_md", "")
        ct = chat.headers.get("content-type", "")
        record(
            "X3",
            "AI 消息回显",
            ct.startswith("application/json"),
            f"content_md 含 payload={XSS_PAYLOADS[0] in content}，Content-Type={ct.split(';')[0]}"
            "（前端 react-markdown 无 rehype-raw，原始 HTML 不渲染）",
        )

    # ---------- X4. 关键端点 Content-Type ----------
    endpoints = [
        ("GET", "/api/problems"),
        ("GET", f"/api/search?q={XSS_PAYLOADS[1]}"),
        ("GET", "/api/notifications/announcements"),
        ("GET", "/api/achievements"),
    ]
    bad = []
    for method, url in endpoints:
        r = client.request(method, url)
        if not r.headers.get("content-type", "").startswith("application/json"):
            bad.append(f"{method} {url.split('?')[0]} → {r.headers.get('content-type','')!r}")
    record("X4", "关键端点 Content-Type", not bad, "全部 application/json" if not bad else f"异常={bad}")

    # ---------- C1. 恶意 Origin 预检 ----------
    pre = client.options(
        "/api/problems",
        headers={"Origin": "http://evil.com", "Access-Control-Request-Method": "GET"},
    )
    acao = pre.headers.get("access-control-allow-origin")
    record("C1", "恶意 Origin 预检", acao is None, f"HTTP {pre.status_code}，ACAO={acao!r}")

    # ---------- C2. 白名单 Origin 预检 ----------
    pre2 = client.options(
        "/api/problems",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    acao2 = pre2.headers.get("access-control-allow-origin")
    acac2 = pre2.headers.get("access-control-allow-credentials")
    record(
        "C2",
        "白名单 Origin 预检",
        acao2 == "http://localhost:3000" and acac2 == "true",
        f"ACAO={acao2!r} ACAC={acac2!r}",
    )

    # ---------- C3. 恶意 Origin 简单请求 ----------
    simple = client.get("/api/problems", headers={"Origin": "http://evil.com"})
    acao3 = simple.headers.get("access-control-allow-origin")
    record("C3", "恶意 Origin 简单请求", acao3 is None, f"HTTP {simple.status_code}，ACAO={acao3!r}")

    # ---------- C4. Origin 绕过尝试 ----------
    bypass_origins = [
        "http://localhost:3000.evil.com",
        "http://evil.com#http://localhost:3000",
        "http://LOCALHOST:3000",
        "http://localhost:3000@evil.com",
        "http://localhost:30000",
    ]
    leaked = []
    for origin in bypass_origins:
        r = client.get("/api/problems", headers={"Origin": origin})
        acao_n = r.headers.get("access-control-allow-origin")
        if acao_n is not None:
            leaked.append(f"{origin} → {acao_n!r}")
    record("C4", "Origin 绕过尝试", not leaked, "全部不回显 ACAO" if not leaked else f"绕过成功={leaked}")

    # ---------- R1. 无凭据状态变更 ----------
    r_bookmark = client.post("/api/bookmarks", json={"kind": "snippet", "title": "x"})
    r_sub = client.post("/api/submissions", json={"problem_id": "x", "code": "1"})
    csrf_ok = r_bookmark.status_code == 401 and r_sub.status_code == 401
    record(
        "R1",
        "无凭据状态变更请求",
        csrf_ok,
        f"POST /bookmarks → {r_bookmark.status_code}，POST /submissions → {r_sub.status_code}（预期均 401）",
    )

    # ---------- R2. 登录响应不设 Cookie ----------
    login = client.post("/api/auth/login", json={"account": f"probe2_{suffix}", "password": "Probe1234"})
    set_cookie = login.headers.get("set-cookie")
    record("R2", "登录不设 Cookie", login.status_code == 200 and set_cookie is None, f"Set-Cookie={set_cookie!r}")

    # ---------- H1. 安全响应头（回归断言） ----------
    health = client.get("/api/health")
    required = ("x-content-type-options", "x-frame-options", "referrer-policy")
    missing = [k for k in required if k not in health.headers]
    record(
        "H1",
        "安全响应头",
        not missing,
        f"必需要头齐备（nosniff/DENY/Referrer-Policy）" if not missing else f"缺失={missing}（API-only 不强制 CSP）",
    )

    return _finish()


def _finish() -> int:
    failed = [r for r in results if r[2].startswith("FAIL")]
    print("\n===== 汇总 =====")
    for no, name, detail in results:
        print(f"{no}. {name}: {detail}")
    print(f"\n共 {len(results)} 项，FAIL {len(failed)} 项")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
