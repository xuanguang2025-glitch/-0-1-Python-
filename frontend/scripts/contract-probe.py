"""PYTHON LAB 前后端联调探针（只读，不改后端）。

走通最小闭环并打印关键响应字段，用于契约对齐核对：
register -> login -> courses -> lesson detail -> complete -> progress/dashboard
-> statistics/overview -> achievements。

用法：
    python scripts/contract-probe.py [base_url]
默认 base_url = http://127.0.0.1:8000
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"


def call(method: str, path: str, body: dict | None = None, token: str | None = None) -> tuple[int, dict]:
    url = f"{BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:  # pragma: no cover - 探针脚本
        raw = exc.read().decode("utf-8", "replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"raw": raw[:500]}


def show(label: str, obj: object, limit: int = 400) -> None:
    text = json.dumps(obj, ensure_ascii=False)
    if len(text) > limit:
        text = text[:limit] + " …"
    print(f"  {label}: {text}")


def main() -> int:
    stamp = int(time.time())
    email = f"probe{stamp}@example.com"
    username = f"probe{stamp}"

    print("== 1) health / enums ==")
    status, health = call("GET", "/api/health")
    print(f"  GET /api/health -> {status}")
    show("data", health.get("data"))
    status, enums = call("GET", "/api/health/enums")
    print(f"  GET /api/health/enums -> {status}, keys={list((enums.get('data') or {}).keys())}")

    print("== 2) register / login ==")
    status, reg = call(
        "POST",
        "/api/auth/register",
        {"email": email, "username": username, "password": "Passw0rd!"},
    )
    print(f"  POST /api/auth/register -> {status}")
    show("data", reg.get("data"))
    reg_tokens = reg.get("data") or {}
    token = reg_tokens.get("access_token")

    status, login = call("POST", "/api/auth/login", {"account": email, "password": "Passw0rd!"})
    print(f"  POST /api/auth/login -> {status}")
    login_tokens = login.get("data") or {}
    token = login_tokens.get("access_token") or token
    show("data", login_tokens)

    status, me = call("GET", "/api/auth/me", token=token)
    print(f"  GET /api/auth/me -> {status}")
    show("data", me.get("data"))

    print("== 3) courses ==")
    status, courses = call("GET", "/api/courses?page=1&page_size=5", token=token)
    print(f"  GET /api/courses -> {status}")
    cdata = courses.get("data") or {}
    print(f"  total={cdata.get('total')} page={cdata.get('page')} page_size={cdata.get('page_size')} pages={cdata.get('pages')}")
    items = cdata.get("items") or []
    if items:
        show("items[0]", items[0])
    first_slug = items[0]["slug"] if items else "stage-01-python-basics"

    print("== 4) lesson detail（含 course_outline）==")
    status, detail = call("GET", f"/api/courses/{first_slug}/lessons", token=token)
    print(f"  GET /api/courses/{first_slug}/lessons -> {status}")
    lessons = detail.get("data") or []
    if lessons:
        show("lessons[0]", lessons[0])
    lesson_id = lessons[0]["id"] if lessons else None

    status, ldetail = call("GET", f"/api/lessons/{lesson_id}", token=token) if lesson_id else (0, {})
    print(f"  GET /api/lessons/{lesson_id} -> {status}")
    ld = ldetail.get("data") or {}
    print(f"  flat? keys={sorted(k for k in ld.keys())[:40]}")
    print(
        "  course_id=", ld.get("course_id"),
        "chapter_title=", ld.get("chapter_title"),
        "lesson_index=", ld.get("lesson_index"),
        "total_lessons=", ld.get("total_lessons"),
    )
    show("prev_lesson", ld.get("prev_lesson"))
    show("next_lesson", ld.get("next_lesson"))
    outline = ld.get("course_outline") or []
    print(f"  course_outline chapters={len(outline)}")
    if outline:
        ch0 = outline[0]
        print(f"    chapter[0]: title={ch0.get('title')} lesson_count={ch0.get('lesson_count')} lessons={len(ch0.get('lessons') or [])}")
        if ch0.get("lessons"):
            show("    lessons[0]", ch0["lessons"][0])

    print("== 5) complete lesson ==")
    if lesson_id:
        status, done = call("POST", f"/api/lessons/{lesson_id}/complete", {"time_spent_seconds": 120}, token=token)
        print(f"  POST /api/lessons/{lesson_id}/complete -> {status}")
        show("data", done.get("data"))

    print("== 6) progress dashboard ==")
    status, dash = call("GET", "/api/progress/dashboard", token=token)
    print(f"  GET /api/progress/dashboard -> {status}")
    show("data", dash.get("data"))
    status, prog = call("GET", "/api/progress", token=token)
    print(f"  GET /api/progress -> {status}")
    show("data", prog.get("data"))
    status, heat = call("GET", "/api/progress/heatmap?days=180", token=token)
    print(f"  GET /api/progress/heatmap -> {status}")
    show("data", heat.get("data"))
    status, mastery = call("GET", "/api/progress/mastery", token=token)
    print(f"  GET /api/progress/mastery -> {status}")
    show("data", mastery.get("data"))

    print("== 7) statistics ==")
    status, overview = call("GET", "/api/statistics/overview", token=token)
    print(f"  GET /api/statistics/overview -> {status}")
    show("data", overview.get("data"))
    status, trend = call("GET", "/api/statistics/trend?days=30&metric=submissions", token=token)
    print(f"  GET /api/statistics/trend -> {status}")
    show("data", trend.get("data"))
    status, cats = call("GET", "/api/statistics/categories", token=token)
    print(f"  GET /api/statistics/categories -> {status}")
    show("data", cats.get("data"))
    status, rank = call("GET", "/api/statistics/ranking", token=token)
    print(f"  GET /api/statistics/ranking -> {status}")
    show("data", rank.get("data"))

    print("== 8) achievements / notifications / search ==")
    status, ach = call("GET", "/api/achievements", token=token)
    print(f"  GET /api/achievements -> {status}")
    a = ach.get("data") or []
    print(f"  count={len(a)}")
    if a:
        show("achievements[0]", a[0])
    status, bw = call("GET", "/api/achievements/badge-wall", token=token)
    print(f"  GET /api/achievements/badge-wall -> {status}")
    show("data", bw.get("data"), 300)
    status, dt = call("GET", "/api/achievements/daily-tasks", token=token)
    print(f"  GET /api/achievements/daily-tasks -> {status}")
    d = dt.get("data") or []
    if d:
        show("daily_tasks[0]", d[0])
    status, notif = call("GET", "/api/notifications?page=1&page_size=5", token=token)
    print(f"  GET /api/notifications -> {status}")
    show("data", notif.get("data"), 300)
    status, uc = call("GET", "/api/notifications/unread-count", token=token)
    print(f"  GET /api/notifications/unread-count -> {status}")
    show("data", uc.get("data"))
    status, srch = call("GET", "/api/search?q=python&limit=5", token=token)
    print(f"  GET /api/search -> {status}")
    show("data", srch.get("data"), 300)

    print("== 9) 未挂载分组探测（预期 404）==")
    for probe in ("/api/problems?page=1", "/api/submissions?page=1", "/api/projects?page=1", "/api/bookmarks", "/api/mistakes", "/api/ai/status"):
        status, payload = call("GET", probe, token=token)
        print(f"  GET {probe} -> {status} code={(payload.get('error') or {}).get('code')}")

    print("== 10) 401 预期 ==")
    status, payload = call("GET", "/api/admin/dashboard", token=token)
    print(f"  GET /api/admin/dashboard (普通用户) -> {status} code={(payload.get('error') or {}).get('code')}")
    status, payload = call("GET", "/api/courses?page=1")
    print(f"  GET /api/courses (无 token) -> {status} code={(payload.get('error') or {}).get('code')}")

    print("\nDONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
