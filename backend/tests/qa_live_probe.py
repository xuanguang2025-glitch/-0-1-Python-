"""QA 实时探测脚本（严过关）——直接打真实运行中的后端服务。

用法：python tests/qa_live_probe.py [base_url]
默认 base_url = http://127.0.0.1:8021（绕过本机动态代理）。

本脚本只发请求 / 读响应，不修改 app/ 下任何源码。用于产出「攻击输入 → 实际响应」证据。
"""

from __future__ import annotations

import json
import random
import sys
import time
import uuid

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8021"
API = f"{BASE}/api"

results: list[tuple[str, str, str]] = []  # (level, section, detail)


def log(level: str, section: str, detail: str) -> None:
    results.append((level, section, detail))
    print(f"[{level}] {section} :: {detail}")


def _rand_ip() -> str:
    return f"10.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"


def _hook(request: httpx.Request) -> None:
    """每个请求塞一个随机 X-Forwarded-For，避免 auth 限流（10/60s per IP）干扰用例。"""
    if "x-forwarded-for" not in {k.lower() for k in request.headers}:
        request.headers["X-Forwarded-For"] = _rand_ip()


def client() -> httpx.Client:
    # trust_env=False 绕过本机 http_proxy
    return httpx.Client(timeout=30.0, trust_env=False, event_hooks={"request": [_hook]})


def jd(obj: object) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False)[:600]
    except Exception:
        return str(obj)[:600]


def reg(c: httpx.Client, tag: str) -> dict:
    name = f"qa_{tag}_{uuid.uuid4().hex[:8]}"
    r = c.post(
        f"{API}/auth/register",
        json={"email": f"{name}@pythonlab.dev", "username": name, "password": "QaPass12345"},
    )
    body = r.json()
    if not body.get("success"):
        log("FAIL", "setup.register", f"status={r.status_code} body={jd(body)}")
        return {}
    data = body["data"]
    data["_username"] = name
    data["_email"] = f"{name}@pythonlab.dev"
    return data


# ============================================================ A1 认证与密码
def sec_auth(c: httpx.Client, u: dict) -> None:
    log("INFO", "A1.me", f"GET /auth/me status={c.get(f'{API}/auth/me', headers={'Authorization': f'Bearer {u['access_token']}'}).status_code}")

    # 错误密码 vs 不存在用户 —— 响应应一致（不泄露账号是否存在）
    r1 = c.post(f"{API}/auth/login", json={"account": u["_email"], "password": "WrongPass999"})
    r2 = c.post(f"{API}/auth/login", json={"account": "nobody_xyz@pythonlab.dev", "password": "WrongPass999"})
    b1, b2 = r1.json(), r2.json()
    same = (r1.status_code == r2.status_code) and (b1.get("error", {}).get("code") == b2.get("error", {}).get("code"))
    log("PASS" if same else "FAIL", "A1.user_enum",
        f"wrong_pwd={r1.status_code}/{b1.get('error',{}).get('code')} unknown_user={r2.status_code}/{b2.get('error',{}).get('code')} identical={same}")

    # JWT 篡改
    tok = u["access_token"]
    parts = tok.split(".")
    forged = parts[0] + "." + parts[1] + "." + ("A" * len(parts[2]))
    r = c.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {forged}"})
    log("PASS" if r.status_code == 401 else "FAIL", "A1.jwt_tamper",
        f"status={r.status_code} code={r.json().get('error',{}).get('code')}")

    # alg:none 混淆
    import base64

    def b64(d: bytes) -> str:
        return base64.urlsafe_b64encode(d).rstrip(b"=").decode()

    header = b64(json.dumps({"alg": "none", "typ": "JWT"}).encode())
    payload = b64(json.dumps({"sub": u["user"]["id"], "typ": "access", "role": "admin", "exp": int(time.time()) + 3600}).encode())
    none_tok = f"{header}.{payload}."
    r = c.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {none_tok}"})
    log("PASS" if r.status_code == 401 else "FAIL", "A1.alg_none",
        f"status={r.status_code} code={r.json().get('error',{}).get('code')}")

    # refresh 重放：刷新一次，再用旧 refresh 刷新应失败
    old_refresh = u["refresh_token"]
    r = c.post(f"{API}/auth/refresh", json={"refresh_token": old_refresh})
    ok_first = r.status_code == 200
    r2 = c.post(f"{API}/auth/refresh", json={"refresh_token": old_refresh})
    log("PASS" if (ok_first and r2.status_code == 401) else "FAIL", "A1.refresh_replay",
        f"first={r.status_code} replay={r2.status_code} replay_code={r2.json().get('error',{}).get('code')}")

    # 登出后旧 access 应 401（黑名单）
    uu = reg(c, "logout")
    at = uu["access_token"]
    rt = uu["refresh_token"]
    c.post(f"{API}/auth/logout", json={"refresh_token": rt}, headers={"Authorization": f"Bearer {at}"})
    r = c.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {at}"})
    log("PASS" if r.status_code == 401 else "FAIL", "A1.logout_blacklist",
        f"after_logout_status={r.status_code} code={r.json().get('error',{}).get('code')}")

    # 无 token
    r = c.get(f"{API}/auth/me")
    log("PASS" if r.status_code == 401 else "FAIL", "A1.no_token", f"status={r.status_code}")

    # 弱默认密钥伪造：用 config 默认 jwt_secret_key="change-me" 签一个 admin 角色 token
    try:
        from jose import jwt as jjwt

        forged_user = jjwt.encode(
            {"sub": u["user"]["id"], "typ": "access", "role": "superadmin", "usr": "x", "ver": 1,
             "iat": int(time.time()), "exp": int(time.time()) + 3600, "jti": "forged-1"},
            "change-me", algorithm="HS256",
        )
        r = c.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {forged_user}"})
        if r.status_code == 200:
            log("FAIL", "A1.default_secret", f"用默认密钥 'change-me' 伪造的 token 被接受! status=200 user={r.json().get('data',{}).get('username')}")
        else:
            log("PASS", "A1.default_secret", f"默认密钥伪造被拒 status={r.status_code}")
    except Exception as exc:  # noqa: BLE001
        log("INFO", "A1.default_secret", f"跳过：{exc}")


# ============================================================ A2 越权 IDOR
def sec_idor(c: httpx.Client) -> None:
    a = reg(c, "alice")
    b = reg(c, "bob")
    if not a.get("access_token") or not b.get("access_token"):
        log("FAIL", "A2.idor", f"注册失败无法继续 a={bool(a)} b={bool(b)}")
        return
    ha = {"Authorization": f"Bearer {a['access_token']}"}
    hb = {"Authorization": f"Bearer {b['access_token']}"}

    # b 创建一些个人数据
    bl = c.get(f"{API}/courses?page_size=1").json()["data"]["items"]
    course_slug = bl[0].get("slug")
    # 取第一个 lesson id（课程详情按 slug）
    lesson_id = None
    try:
        lessons = c.get(f"{API}/courses/{course_slug}/lessons").json().get("data") or []
        if lessons:
            lesson_id = lessons[0].get("id") or lessons[0].get("lesson_id")
    except Exception as exc:  # noqa: BLE001
        log("INFO", "A2.setup", f"取课时失败 {exc}")
    if lesson_id:
        rc = c.post(f"{API}/lessons/{lesson_id}/complete", headers=hb)
        log("INFO", "A2.complete", f"B 完成课时 status={rc.status_code}")

    # b 建 bookmark / mistake（若路由可用）
    b_bookmark = c.post(f"{API}/bookmarks", json={"target_type": "lesson", "target_id": lesson_id or "x"}, headers=hb).json()
    b_mistake_id = None
    try:
        r = c.get(f"{API}/mistakes", headers=hb).json()
        items = (r.get("data") or {}).get("items") or []
        if items:
            b_mistake_id = items[0].get("id")
    except Exception:
        pass

    # A 尝试读 B 的 progress
    r = c.get(f"{API}/progress/overview", headers=ha)
    log("INFO", "A2.progress_self", f"A读自己 progress status={r.status_code}")

    # 找 A 越权访问 B 资源：用 B 的资源 id，A 的 token
    # 1) submission（先让 B 提交一次，如果判题可用）
    b_sub_id = None
    probs = c.get(f"{API}/problems?page_size=1").json()
    if probs.get("success") and probs["data"]["items"]:
        pid = probs["data"]["items"][0]["id"]
        sub = c.post(f"{API}/submissions", json={"problem_id": pid, "code": "print(1)", "language": "python"}, headers=hb).json()
        if sub.get("success"):
            b_sub_id = sub["data"]["id"]
    if b_sub_id:
        r = c.get(f"{API}/submissions/{b_sub_id}", headers=ha)
        ok = r.status_code in (403, 404)
        log("PASS" if ok else "FAIL", "A2.idor_submission",
            f"A读B提交 status={r.status_code} body_ok={r.json().get('success')}")

    # 2) bookmark 越权删除
    if b_bookmark.get("success"):
        bid = b_bookmark["data"].get("id")
        r = c.delete(f"{API}/bookmarks/{bid}", headers=ha)
        ok = r.status_code in (403, 404)
        log("PASS" if ok else "FAIL", "A2.idor_bookmark",
            f"A删B收藏 status={r.status_code} body={jd(r.json())[:200]}")

    # 3) mistake 越权
    if b_mistake_id:
        r = c.delete(f"{API}/mistakes/{b_mistake_id}", headers=ha)
        ok = r.status_code in (403, 404)
        log("PASS" if ok else "FAIL", "A2.idor_mistake", f"A删B错题 status={r.status_code}")

    # 4) code-history 越权
    snap = c.post(f"{API}/editor/save-snapshot", json={"context_type": "playground", "file_path": "main.py", "code": "print(1)"}, headers=hb).json()
    if snap.get("success"):
        hid = snap["data"].get("id")
        r = c.get(f"{API}/editor/history/{hid}", headers=ha)
        ok = r.status_code in (403, 404)
        log("PASS" if ok else "FAIL", "A2.idor_code_history", f"A读B快照 status={r.status_code}")

    # 5) 普通用户访问 admin
    r = c.get(f"{API}/admin/users", headers=ha)
    ok = r.status_code == 403
    log("PASS" if ok else "FAIL", "A2.admin_forbidden", f"普通用户访问/api/admin/users status={r.status_code} code={r.json().get('error',{}).get('code')}")


# ============================================================ A3 敏感数据泄露
def sec_leak(c: httpx.Client, admin_h: dict) -> None:
    for path in ["/auth/me", "/users/me", "/statistics/overview"]:
        r = c.get(f"{API}{path}", headers=admin_h)
        if r.status_code != 200:
            continue
        txt = r.text.lower()
        bad = [k for k in ["hashed_password", "password_hash", "\"password\"", "secret_key"] if k in txt]
        log("PASS" if not bad else "FAIL", "A3.no_secret_field", f"{path} 泄露字段={bad}")

    # 排行榜隐私
    r = c.get(f"{API}/challenges?page_size=5", headers=admin_h).json()
    items = (r.get("data") or {}).get("items") or []
    if items:
        cid = items[0]["id"]
        r = c.get(f"{API}/challenges/{cid}/leaderboard", headers=admin_h)
        txt = r.text
        low = txt.lower()
        leaks = [k for k in ["@", "email", "user_id"] if k in low]
        log("PASS" if not leaks else "WARN", "A3.leaderboard_privacy",
            f"status={r.status_code} 可疑字段={leaks} sample={jd(r.json())[:400]}")

    # AI 配置脱敏
    r = c.get(f"{API}/admin/ai-config", headers=admin_h)
    if r.status_code == 200:
        txt = r.text
        data = r.json().get("data") or {}
        key_field = data.get("api_key")
        masked = key_field is None or ("*" in str(key_field)) or key_field == "" or len(str(key_field)) < 12
        log("PASS" if masked else "FAIL", "A3.ai_key_masked", f"api_key={key_field!r}")
    else:
        log("INFO", "A3.ai_key_masked", f"status={r.status_code}")


# ============================================================ A4 注入
def sec_injection(c: httpx.Client, h: dict) -> None:
    payloads = ["' OR 1=1--", "1; DROP TABLE users--", "1' UNION SELECT 1,2,3--"]
    for p in payloads:
        r = c.get(f"{API}/problems", params={"keyword": p}, headers=h)
        log("PASS" if r.status_code in (200, 422) else "FAIL", "A4.sql_keyword",
            f"keyword={p!r} status={r.status_code}")

    # 排序参数注入 / 白名单
    for p in ["id; DELETE FROM users", "id desc; DROP TABLE users", "1 OR 1=1"]:
        r = c.get(f"{API}/problems", params={"sort": p}, headers=h)
        log("INFO", "A4.sort_param", f"sort={p!r} status={r.status_code} body={jd(r.json())[:200]}")

    # 搜索端点
    for ep in ["/search", "/courses", "/lessons"]:
        r = c.get(f"{API}{ep}", params={"q": "' OR 1=1--"}, headers=h)
        log("INFO", "A4.sql_misc", f"{ep}?q=' OR 1=1-- status={r.status_code}")

    # XSS：用户名 / 题解是否转义
    name = f"qa_xss_{uuid.uuid4().hex[:6]}"
    r = c.post(f"{API}/auth/register",
               json={"email": f"{name}@pythonlab.dev", "username": name, "password": "QaPass12345",
                     "display_name": "<script>alert(1)</script>"})
    body = r.json()
    stored = ""
    if body.get("success"):
        me = c.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {body['data']['access_token']}"}).json()
        stored = json.dumps(me, ensure_ascii=False)
    log("INFO", "A4.xss_display_name", f"回显含原样<script>={('<script>' in stored)} raw={stored[:200]}")


# ============================================================ A5 路径遍历
def sec_path(c: httpx.Client, h: dict) -> None:
    attempts = [
        "/uploads/../../etc/passwd",
        "/uploads/..%2F..%2Fetc%2Fpasswd",
        "/uploads/%2e%2e%2f%2e%2e%2fWindows%2Fwin.ini",
        "/uploads/....//....//etc/passwd",
        "/uploads/C:/Windows/win.ini",
    ]
    for p in attempts:
        r = c.get(f"{BASE}{p}")
        leaked = "root:" in r.text or "[extensions]" in r.text or "for 16-bit app" in r.text
        log("PASS" if not leaked else "FAIL", "A5.path_traversal",
            f"{p} status={r.status_code} leaked={leaked}")


# ============================================================ A6 沙箱逃逸
def sec_sandbox(c: httpx.Client, h: dict) -> None:
    cases = {
        "os.system": "import os\nos.system('echo pwned')",
        "subprocess": "import subprocess\nsubprocess.run(['whoami'])",
        "win_ini_read": "print(open('C:/Windows/win.ini').read()[:80])",
        "etc_passwd_read": "print(open('/etc/passwd').read()[:80])",
        "dunder_import_single": "__import__('os').system('dir')",
        "dunder_import_double": "__import__(\"os\").system(\"echo pwned2\")",
        "getattr_os_system": "import os\ngetattr(os, 'system')('echo pwned3')",
        "os_environ_dump": "import os\nprint('KEYS=', sorted(os.environ.keys()))\nprint('AI=', os.environ.get('AI_API_KEY'))\nprint('JWT=', os.environ.get('JWT_SECRET_KEY'))\nprint('SECRET=', os.environ.get('SECRET_KEY'))",
        "eval_compile": "eval(compile('print(1337)', '<s>', 'exec'))",
        "import_os_probe": "import os\nprint('cwd=', os.getcwd())\nprint('listdir=', os.listdir('.')[:5])",
        "dunder_subclasses": "print([c.__name__ for c in ().__class__.__base__.__subclasses__()][:3])",
    }
    for name, code in cases.items():
        t0 = time.time()
        r = c.post(f"{API}/python/run", json={"files": [{"path": "main.py", "content": code}], "entry": "main.py"}, headers=h)
        dt = time.time() - t0
        try:
            d = r.json().get("data") or {}
        except Exception:
            d = {}
        status = d.get("status") or d.get("error_type") or r.status_code
        out = (d.get("stdout") or "")[:120].replace("\n", "\\n")
        err = (d.get("error") or "")[:120]
        detail = f"{name}: http={r.status_code} status={status} stdout={out!r} err={err!r} {dt:.1f}s"
        # 判定：能否读到敏感文件 / 环境变量 / 执行系统命令
        if name in ("win_ini_read", "etc_passwd_read") and ("for 16-bit app" in (d.get("stdout") or "") or "root:" in (d.get("stdout") or "")):
            log("FAIL", "A6.sandbox_escape", f"文件读取成功! {detail}")
        elif name == "os_environ_dump" and ("AI_API_KEY" in (d.get("stdout") or "") or "JWT_SECRET" in (d.get("stdout") or "")):
            log("FAIL", "A6.env_leak", f"环境变量泄露! {detail}")
        elif name == "dunder_import_double" and "pwned2" in (d.get("stdout") or ""):
            log("FAIL", "A6.blacklist_bypass", f"双引号绕过黑名单并执行命令! {detail}")
        elif name == "getattr_os_system" and "pwned3" in (d.get("stdout") or ""):
            log("FAIL", "A6.blacklist_bypass", f"getattr 绕过 blacklist 并执行命令! {detail}")
        else:
            log("INFO", "A6.sandbox_case", detail)

    # TLE
    t0 = time.time()
    r = c.post(f"{API}/python/run", json={"files": [{"path": "main.py", "content": "while True:\n    pass\n"}], "entry": "main.py", "timeout_ms": 2000}, headers=h)
    dt = time.time() - t0
    d = r.json().get("data") or {}
    log("PASS" if d.get("status") == "timeout" else "FAIL", "A6.tle",
        f"status={d.get('status')} time_ms={d.get('time_ms')} wall={dt:.1f}s")

    # 输出爆炸
    r = c.post(f"{API}/python/run", json={"files": [{"path": "main.py", "content": "print('A'*10**8)"}], "entry": "main.py"}, headers=h)
    d = r.json().get("data") or {}
    stdout_len = len(d.get("stdout") or "")
    log("PASS" if d.get("truncated") and stdout_len <= 70000 else "INFO", "A6.output_bomb",
        f"truncated={d.get('truncated')} stdout_len={stdout_len} status={d.get('status')}")


# ============================================================ A7 资源限制 / 体积
def sec_limits(c: httpx.Client) -> None:
    # 未登录运行代码
    r = c.post(f"{API}/python/run", json={"files": [{"path": "main.py", "content": "print(1)"}], "entry": "main.py"})
    log("PASS" if r.status_code == 401 else "FAIL", "A7.anon_run",
        f"匿名运行 status={r.status_code} code={r.json().get('error',{}).get('code')}")

    # 10MB 代码
    big = "x = 1\n" * 2_000_000
    u = reg(c, "bigbody")
    h = {"Authorization": f"Bearer {u['access_token']}"}
    r = c.post(f"{API}/python/run", json={"files": [{"path": "main.py", "content": big}], "entry": "main.py"}, headers=h)
    log("INFO", "A7.body_limit", f"10MB代码 status={r.status_code} body={jd(r.json())[:200]}")


# ============================================================ A8 CORS / CSRF
def sec_cors(c: httpx.Client) -> None:
    r = c.get(f"{API}/courses", headers={"Origin": "http://evil.example.com"})
    acao = r.headers.get("access-control-allow-origin")
    acac = r.headers.get("access-control-allow-credentials")
    log("PASS" if acao != "*" or acac != "true" else "FAIL", "A8.cors",
        f"evil origin -> ACAO={acao!r} ACAC={acac!r}")

    r = c.options(f"{API}/courses", headers={
        "Origin": "http://evil.example.com",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization",
    })
    log("INFO", "A8.cors_preflight", f"status={r.status_code} ACAO={r.headers.get('access-control-allow-origin')!r} ACAC={r.headers.get('access-control-allow-credentials')!r}")


def sec_rate_limit() -> None:
    """限流是否可被伪造的 X-Forwarded-For 绕过。"""
    with httpx.Client(timeout=10.0, trust_env=False) as raw:
        fixed = {"X-Forwarded-For": "203.0.113.7"}
        codes = []
        for _ in range(15):
            r = raw.post(f"{API}/auth/login", json={"account": "nobody@x.dev", "password": "x"}, headers=fixed)
            codes.append(r.status_code)
        limited = codes.count(429)
        # 轮换 XFF
        codes2 = []
        for i in range(15):
            r = raw.post(f"{API}/auth/login", json={"account": "nobody@x.dev", "password": "x"},
                         headers={"X-Forwarded-For": f"198.51.100.{i+1}"})
            codes2.append(r.status_code)
        limited2 = codes2.count(429)
        log("WARN" if (limited > 0 and limited2 == 0) else "INFO", "A8.ratelimit_xff",
            f"固定XFF触发429次数={limited}/15, 轮换XFF触发429次数={limited2}/15")


def main() -> None:
    print(f"### QA live probe against {BASE}\n")
    with client() as c:
        # 健康
        r = c.get(f"{API}/health/deps")
        log("INFO", "health", f"status={r.status_code} body={jd(r.json())[:500]}")

        # 管理员登录
        admin_login = c.post(f"{API}/auth/login", json={"account": "admin@pythonlab.dev", "password": "Admin@12345"})
        admin_h = {}
        admin_id = None
        if admin_login.status_code == 200:
            admin_h = {"Authorization": f"Bearer {admin_login.json()['data']['access_token']}"}
            log("PASS", "setup.admin_login", "默认管理员密码 Admin@12345 可登录")
            me = c.get(f"{API}/auth/me", headers=admin_h).json()
            admin_id = (me.get("data") or {}).get("id")
        else:
            log("FAIL", "setup.admin_login", f"status={admin_login.status_code} body={jd(admin_login.json())[:200]}")

        # 用默认密钥伪造 admin 身份 → 访问 admin 接口（提权验证）
        if admin_id:
            try:
                from jose import jwt as jjwt

                forged_admin = jjwt.encode(
                    {"sub": admin_id, "typ": "access", "role": "superadmin", "usr": "x", "ver": 1,
                     "iat": int(time.time()), "exp": int(time.time()) + 3600, "jti": "forged-admin"},
                    "change-me", algorithm="HS256",
                )
                r = c.get(f"{API}/admin/users", headers={"Authorization": f"Bearer {forged_admin}"})
                if r.status_code == 200:
                    log("FAIL", "A1.forge_admin", f"用默认密钥伪造 admin token 成功访问 /admin/users! status=200 n={len((r.json().get('data') or {}).get('items') or [])}")
                else:
                    log("PASS", "A1.forge_admin", f"伪造 admin 被拒 status={r.status_code}")
            except Exception as exc:  # noqa: BLE001
                log("INFO", "A1.forge_admin", f"跳过 {exc}")

        u = reg(c, "main")
        if not u:
            print("无法注册用户，终止")
            return

        sec_auth(c, u)
        sec_idor(c)
        sec_leak(c, admin_h)
        sec_injection(c, admin_h)
        sec_path(c, admin_h)
        sec_sandbox(c, u and {"Authorization": f"Bearer {u['access_token']}"})
        sec_limits(c)
        sec_cors(c)
        sec_rate_limit()

    print("\n### SUMMARY")
    from collections import Counter

    cnt = Counter(level for level, _, _ in results)
    print(dict(cnt))
    print("### FAILS")
    for level, section, detail in results:
        if level == "FAIL":
            print(f"  - {section}: {detail}")


if __name__ == "__main__":
    main()
