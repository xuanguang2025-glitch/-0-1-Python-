"""QA 沙箱深度探测：环境变量泄露 / 任意文件读写 / 网络访问 / 黑名绕过。"""

from __future__ import annotations

import os
import uuid

import httpx

BASE = "http://127.0.0.1:8021"
API = f"{BASE}/api"


def main() -> None:
    c = httpx.Client(timeout=40.0, trust_env=False, headers={"X-Forwarded-For": "10.11.0.9"})
    u = "qa_sb_" + uuid.uuid4().hex[:6]
    reg = c.post(f"{API}/auth/register", json={"email": f"{u}@pythonlab.dev", "username": u, "password": "QaPass12345"}).json()
    h = {"Authorization": f"Bearer {reg['data']['access_token']}", "X-Forwarded-For": "10.11.0.9"}

    def run(code: str) -> dict:
        r = c.post(f"{API}/python/run", json={"files": [{"path": "main.py", "content": code}], "entry": "main.py"}, headers=h).json()
        return r.get("data") or {}

    cases = {
        "env_keys": "import os\nprint(sorted(os.environ.keys()))",
        "env_secret_values": "import os\nprint('AI=', repr(os.environ.get('AI_API_KEY')))\nprint('JWT=', repr(os.environ.get('JWT_SECRET_KEY')))\nprint('SECRET=', repr(os.environ.get('SECRET_KEY')))\nprint('DB=', repr(os.environ.get('DATABASE_URL')))",
        "net_localhost": "import urllib.request\nprint(urllib.request.urlopen('http://127.0.0.1:8021/api/health/deps', timeout=3).read()[:100])",
        "net_external": "import urllib.request, socket\nsocket.setdefaulttimeout(3)\nprint(urllib.request.urlopen('http://example.com', timeout=3).status)",
        "write_public": "print(open('C:/Users/Public/qa_pwned.txt','w').write('pwned'))",
        "read_app_source": "print(open('app/core/config.py').read()[:80])",
        "os_popen_getattr": "import os\nprint(getattr(os,'popen')('echo hi_from_popen').read())",
        "dir_listing_abs": "import os\nprint(os.listdir('C:/'))",
    }
    for name, code in cases.items():
        d = run(code)
        print(f"--- {name} | status={d.get('status')} err={d.get('error')!r}")
        print("    stdout:", repr((d.get('stdout') or "")[:400]))

    c.close()
    print("### disk check qa_pwned.txt exists:", os.path.exists("C:/Users/Public/qa_pwned.txt"))


if __name__ == "__main__":
    main()
