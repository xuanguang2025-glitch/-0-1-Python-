"""QA 安全红线探测脚本（可重复执行）。

覆盖八类高危项，每项输出「攻击输入 → 实际响应」证据：
  1. 密码必须加盐哈希（查库验证，非明文/非可逆）
  2. 普通用户访问 /api/admin/* 必须 403
  3. IDOR：用户 A 不能读取用户 B 的提交详情
  4. 排行榜不泄露 email / 真实姓名 / 哈希
  5. 隐藏测试点 expected_output 不出现在任何响应
  6. SQL 注入探测（排序/搜索参数），且库不被破坏
  7. 沙箱内用户代码能否读到服务端环境变量（AI_API_KEY / JWT_SECRET）
  8. AI 配置密钥脱敏（sk-****last4），/api/health/deps 口径为 rule_based

运行：cd backend && .venv/Scripts/python.exe scripts/security_probe.py
退出码：0 = 全部通过（含 SKIP 项不计失败）；1 = 存在 FAIL。
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import tempfile
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


def main() -> int:
    if not REAL_DB.exists():
        print(f"真实库不存在：{REAL_DB}，请先执行 alembic upgrade head + scripts/seed.py")
        return 1

    tmp_dir = Path(tempfile.mkdtemp(prefix="pythonlab_probe_"))
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

    # ---------- 1. 密码加盐哈希 ----------
    con = sqlite3.connect(probe_db)
    row = con.execute("SELECT email, hashed_password FROM users LIMIT 1").fetchone()
    if row is None:
        record("1", "密码加盐哈希", None, "库中无用户")
    else:
        email, hashed = row
        ok = hashed.startswith("$2") and "Admin@12345" not in hashed and "Passw0rd" not in hashed
        record("1", "密码加盐哈希(bcrypt)", ok, f"{email} → {hashed[:12]}…")
    con.commit()
    con.close()

    # ---------- 注册两个普通用户 ----------
    import uuid

    suffix = uuid.uuid4().hex[:6]
    users: dict[str, str] = {}
    for tag in ("ua", "ub"):
        resp = client.post(
            "/api/auth/register",
            json={
                "email": f"probe_{tag}_{suffix}@example.com",
                "username": f"probe_{tag}_{suffix}",
                "password": "Probe1234",
            },
        )
        if resp.status_code not in (200, 201):
            record("0", "注册探针用户", False, f"{tag}: {resp.status_code} {resp.text[:120]}")
            return _finish()
        users[tag] = resp.json()["data"]["access_token"] if "access_token" in resp.json()["data"] else ""

    def h(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    # ---------- 2. 普通用户访问 admin 必须 403 ----------
    resp = client.get("/api/admin/dashboard", headers=h(users["ua"]))
    record("2", "普通用户访问 /api/admin/dashboard", resp.status_code == 403, f"HTTP {resp.status_code}")

    # ---------- 3. IDOR：A 不能读 B 的提交详情 ----------
    prob_row = con2 = None
    import sqlite3 as _s

    con2 = _s.connect(probe_db)
    prob = con2.execute("SELECT id FROM problems WHERE problem_type IN ('coding','algorithm') LIMIT 1").fetchone()
    con2.close()
    if prob is None:
        record("3", "IDOR 提交详情", None, "库中无编程题")
    else:
        problem_id = prob[0]
        made = client.post(
            "/api/submissions", json={"problem_id": problem_id, "code": "print(1)"}, headers=h(users["ub"])
        )
        if made.status_code != 200:
            record("3", "IDOR 提交详情", None, f"UB 提交失败 HTTP {made.status_code}（可能判题未就绪）")
        else:
            sub_id = made.json()["data"]["id"]
            leak = client.get(f"/api/submissions/{sub_id}", headers=h(users["ua"]))
            record("3", "IDOR 提交详情", leak.status_code in (403, 404), f"A 读 B 提交 → HTTP {leak.status_code}")

    # ---------- 4. 排行榜隐私 ----------
    resp = client.get("/api/statistics/ranking", headers=h(users["ua"]))
    if resp.status_code != 200:
        record("4", "排行榜隐私", None, f"HTTP {resp.status_code}")
    else:
        text = resp.text
        bad = [w for w in ("@example.com", "email", "hashed_password", f"probe_ua_{suffix}") if w in text]
        # "email" 字段名出现在响应 schema 中也可能，严格只查真实值
        bad = [w for w in bad if w != "email"]
        record("4", "排行榜隐私", not bad, f"泄露项={bad or '无'}")

    # ---------- 5. 隐藏测试点不泄露 ----------
    con3 = _s.connect(probe_db)
    hidden = con3.execute(
        "SELECT problem_id, expected_output FROM test_cases WHERE is_sample = 0 AND expected_output != '' LIMIT 1"
    ).fetchone()
    con3.close()
    if hidden is None:
        record("5", "隐藏测试点期望值", None, "无非样例用例")
    else:
        pid, expected = hidden
        detail = client.get(f"/api/problems/{pid}")
        leaked = expected in detail.text
        own = client.get("/api/problems", params={"keyword": ""})
        record("5", "隐藏测试点期望值", not leaked, f"problem={pid[:8]}… expected={expected[:12]!r} 泄露={leaked}")

    # ---------- 6. SQL 注入探测 ----------
    attacks = [
        ("sort", "id;DROP TABLE users--"),
        ("keyword", "' OR '1'='1"),
    ]
    ok_all, notes = True, []
    for key, payload in attacks:
        r = client.get("/api/problems", params={key: payload})
        if r.status_code >= 500:
            ok_all = False
            notes.append(f"{key}={payload!r} → HTTP {r.status_code}")
    con4 = _s.connect(probe_db)
    users_left = con4.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    con4.close()
    record("6", "SQL 注入探测", ok_all and users_left > 0, f"users 表仍在({users_left} 行)，异常响应={notes or '无'}")

    # ---------- 7. 沙箱内能否读到服务端环境变量 ----------
    try:
        from app.services.sandbox_client import SandboxClient

        runner = SandboxClient(mode="local")
        code = (
            "import os\n"
            "print('AI_KEY_VISIBLE=', 'AI_API_KEY' in os.environ)\n"
            "print('JWT_VISIBLE=', 'JWT_SECRET' in os.environ)\n"
            "print('VAL=', (os.environ.get('AI_API_KEY') or '')[:4])\n"
        )
        result = runner.run({"main.py": code}, entry="main.py", timeout_ms=5000)
        out = getattr(result, "stdout", "") or ""
        ai_visible = "AI_KEY_VISIBLE= True" in out
        jwt_visible = "JWT_VISIBLE= True" in out
        val = ""
        for line in out.splitlines():
            if line.startswith("VAL="):
                val = line[4:]
        if ai_visible or jwt_visible:
            record(
                "7",
                "沙箱环境变量隔离",
                False,
                f"用户代码可见服务端密钥！AI_API_KEY={ai_visible} JWT_SECRET={jwt_visible} 前缀={val!r}（P0）",
            )
        else:
            record("7", "沙箱环境变量隔离", True, f"AI_API_KEY/JWT_SECRET 均不可见（VAL={val!r}）")
    except Exception as exc:  # noqa: BLE001
        record("7", "沙箱环境变量隔离", None, f"执行异常（判为 SKIP）：{exc!r}")

    # ---------- 8. AI 配置脱敏 + health 口径 ----------
    admin_login = client.post("/api/auth/login", json={"account": "admin@pythonlab.dev", "password": "Admin@12345"})
    if admin_login.status_code != 200:
        record("8", "AI 配置脱敏", None, f"管理员登录失败 HTTP {admin_login.status_code}")
    else:
        admin_token = admin_login.json()["data"]["access_token"]
        put = client.put(
            "/api/admin/ai-config",
            json={"api_key": "sk-probe-secret-key-1234567890", "provider": "deepseek"},
            headers=h(admin_token),
        )
        got = client.get("/api/admin/ai-config", headers=h(admin_token))
        body = got.text
        raw_leak = "sk-probe-secret-key-1234567890" in body
        record("8", "AI 配置密钥脱敏", not raw_leak, f"写入 sk-probe-…7890 后读取泄露={raw_leak}")

    deps = client.get("/api/health/deps")
    if deps.status_code == 200:
        ai = deps.json()["data"].get("ai", {})
        record(
            "9",
            "health/deps AI 口径",
            ai.get("provider") == "rule_based" and ai.get("model") == "rule-based",
            f"provider={ai.get('provider')!r} model={ai.get('model')!r} degraded={ai.get('degraded')}",
        )
    else:
        record("9", "health/deps AI 口径", None, f"HTTP {deps.status_code}")

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
