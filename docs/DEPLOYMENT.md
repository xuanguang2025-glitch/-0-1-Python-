# PYTHON LAB —— 部署手册

> 配套：`docs/ARCHITECTURE.md`（架构）、`docs/SANDBOX.md`（沙箱安全）、`docs/AI.md`（模型接入）
> 目标：**本机零 Docker 也能完整闭环**；有 Docker 时一条命令起全套。

---

## 1. 三种运行形态

| 形态 | 适用 | 数据库 | 缓存/队列 | 代码执行 | 入口 |
|---|---|---|---|---|---|
| A. 本机开发（无 Docker） | 日常开发 | SQLite 文件 | 进程内 TTLCache + inline | backend 内置 `LocalRunner` | `scripts/setup.*` → `scripts/dev.*` |
| B. 本机 + 容器依赖 | 想验 Postgres/Redis | Postgres 16 容器 | Redis 7 容器 | LocalRunner 或沙箱容器 | `docker compose -f docker/docker-compose.dev.yml up -d` |
| C. 服务器全量部署 | 生产 | Postgres 16 容器 | Redis 7 容器 | `sandbox` 容器 | `docker compose up -d --build` |

**降级第一原则**：任一外部依赖（Postgres / Redis / Sandbox / AI Key / RQ）缺失时，系统自动降级且功能不中断，而不是启动失败。

---

## 2. 形态 A：本机开发（Windows，无 Docker）

前置：Python 3.13+、Node 20+（npm 可用）。

```powershell
# 1) 初始化（建 venv、装后端依赖、装前端依赖、生成 .env）
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1

# 2) 起步（后端 :8000 + 前端 :3000）
powershell -ExecutionPolicy Bypass -File scripts\dev.ps1

# 3) 可选：一起起沙箱 :8081（否则后端自动降级 LocalRunner）
#    先建沙箱 venv（见第 3 节），再执行：
powershell -ExecutionPolicy Bypass -File scripts\dev.ps1
```

macOS / Linux / WSL：

```bash
bash scripts/setup.sh
bash scripts/dev.sh
```

浏览器打开 `http://localhost:3000`，用 `.env` 里的 `ADMIN_EMAIL` / `ADMIN_PASSWORD` 登录管理后台。

自检：

```bash
python scripts/healthcheck.py            # 打印 db/cache/queue/runner/ai 的降级状态
curl http://127.0.0.1:8000/api/health    # {"status":"ok",...}
curl http://127.0.0.1:8000/api/health/deps
```

Windows 常见问题：

| 现象 | 原因 | 处理 |
|---|---|---|
| `pip install` 慢/超时 | 默认 PyPI 慢 | 脚本已用清华源；可 `set PIP_INDEX=...` 覆盖 |
| `npm install` 卡住 | 默认 registry 慢 | 脚本已用 `registry.npmmirror.com` |
| 脚本报「禁止运行脚本」 | PowerShell 执行策略 | 统一加 `-ExecutionPolicy Bypass` |
| 端口被占用 | 8000/3000 已被占用 | `netstat -ano \| findstr :8000` 后 `taskkill /PID <pid> /F` |
| 中文乱码 | 控制台编码 | PowerShell 5.1 下脚本以 **UTF-8 with BOM** 保存；必要时 `chcp 65001` |

---

## 3. 本地沙箱（可选，也让判题走独立服务）

```powershell
# 在本机可用 Python 3.13 下
cd sandbox
<你的python> -m venv .venv
.venv\Scripts\python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple fastapi uvicorn psutil httpx pytest
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8081
```

- Windows 无 `rlimit`：`/health` 会返回 `security_level=degraded`（仅超时 kill + 输出截断 + 运行时守卫）
- Linux 容器：`security_level=hardened`（rlimit + 进程组隔离，探测到 `unshare` 时额外禁网）
- 把 `.env` 的 `SANDBOX_MODE` 设为 `remote` 可强制只走远程（探活失败返回 503 `SANDBOX_UNAVAILABLE`）

详见 `docs/SANDBOX.md`。

---

## 4. 形态 C：Docker 一键部署

### 4.1 步骤

```bash
cp .env.example .env            # 必须改：SECRET_KEY / JWT_SECRET_KEY / POSTGRES_PASSWORD / ADMIN_PASSWORD
vi .env                         # AI_API_KEY 可选（留空则 AI 走离线规则助手）
bash scripts/docker-up.sh       # 等价于 docker compose up -d --build
docker compose ps               # 全部 healthy 即成功
docker compose logs -f backend  # 首次启动会执行 alembic upgrade head
```

端口：frontend `3000`、backend `8000`、postgres `5432`、redis `6379`、sandbox `8081`、nginx（可选 profile）`8080/8443`。

可选反代：

```bash
docker compose --profile proxy up -d   # 走 Nginx，/api → backend，/ → frontend
```

### 4.2 服务依赖与健康检查

| 服务 | 健康检查 | 被依赖 |
|---|---|---|
| postgres | `pg_isready -U <user> -d <db>` | backend |
| redis | `redis-cli ping` | backend |
| backend | `GET /api/health` | frontend |
| frontend | `wget :3000` | — |
| sandbox | `GET /health` | backend（`SANDBOX_MODE=remote`） |

### 4.3 数据卷与初始化

- 卷：`pythonlab-pgdata`、`pythonlab-redisdata`、`pythonlab-uploads`
- `docker/postgres/init.sql` 仅在**首次**创建数据卷时执行（扩展、UTC、只读账号、pg_trgm 索引）
- 业务表由 backend 的 Alembic 迁移创建；若镜像里未带迁移命令，手动执行：

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend python scripts/seed_data.py     # 可选
```

- 迁移建表后，如需 `pg_trgm` 模糊检索索引（首次 init 时表还不存在会跳过），再跑一次：

```bash
docker compose exec -T postgres psql -U pythonlab -d pythonlab < docker/postgres/init.sql
```

---

## 5. 生产环境清单（上线前逐项打勾）

### 5.1 密钥与配置

- [ ] `APP_ENV=production`、`DEBUG=false`
- [ ] `SECRET_KEY` / `JWT_SECRET_KEY` 各自用 `openssl rand -hex 32` 生成（**不相同**、不入库、不入 Git）
- [ ] `POSTGRES_PASSWORD`、`ADMIN_PASSWORD` 强随机；登录后立刻改管理员密码
- [ ] `REGISTER_ENABLED` 按需关闭；`AI_API_KEY` 只在服务端注入
- [ ] `CORS_ORIGINS` 只列真实域名（不要 `*`）
- [ ] `LOCAL_RUNNER_ENABLED=false`（生产禁止本地降级执行）
- [ ] `SANDBOX_MODE=remote`、`SANDBOX_ALLOW_NETWORK=false`
- [ ] `SEED_ON_STARTUP=false`（改手动 seed，避免误覆盖）

### 5.2 沙箱

- [ ] 沙箱容器：非 root、`read_only`、`cap_drop: ALL`、`no-new-privileges`、内存/CPU/PID 上限
- [ ] 更好的隔离：把 `sandbox` 放到 `internal: true` 的独立网络，或加 seccomp/AppArmor
- [ ] 只让 backend 访问 `sandbox:8081`；**不要**把 8081 映射到公网
- [ ] `.env` 的 `SANDBOX_TIMEOUT_MS=5000`、`SANDBOX_MEMORY_MB=256`、`SANDBOX_MAX_OUTPUT_BYTES=65536`

### 5.3 HTTPS 与反向代理

- [ ] 域名证书放到 `docker/certs/{fullchain.pem,privkey.pem}`，启用 `docker/nginx.conf` 里注释的 443 server 块
- [ ] HTTP 301 跳 HTTPS；HSTS 开启（确认全站 HTTPS 后再开）
- [ ] `client_max_body_size 12m`（头像 2MB / 导入 10MB）
- [ ] `/api/auth/*` 限流更严（配置里已是 10r/m）

### 5.4 数据库与备份

- [ ] Postgres 每日全量 + WAL 归档；保留 ≥14 天
- [ ] 备份脚本示例：

```bash
docker compose exec -T postgres pg_dump -U pythonlab -Fc pythonlab > backup_$(date +%F).dump
docker compose exec -T postgres pg_restore -U pythonlab -d pythonlab --clean < backup_2026-09-26.dump
```

- [ ] 恢复演练一次（确认备份可用，而不是只看文件存在）
- [ ] 生产别用 SQLite；`DATABASE_URL` 指向容器内 `postgres:5432`

### 5.5 可观测性与运维

- [ ] `LOG_LEVEL=INFO`，日志接采集（JSON 结构化，便于检索 `request_id`）
- [ ] 监控 `/api/health/deps`，对 `runner.mode=local`、`degraded=true` 告警
- [ ] 磁盘告警（上传目录、备份盘、容器日志）
- [ ] `docker compose pull` 定期更新基础镜像并重扫漏洞

---

## 6. 常见故障排查

| 症状 | 排查 | 处理 |
|---|---|---|
| backend unhealthy | `docker compose logs backend` | 多为 DATABASE_URL 不通或迁移失败 |
| 注册后接口 401 | `.env` 的 JWT key 变更导致旧 token 失效 | 重新登录 |
| 判题一直 `SANDBOX_UNAVAILABLE` | `docker compose logs sandbox`；`curl :8081/health` | 修复沙箱或临时 `SANDBOX_MODE=local` |
| 运行代码返回 `security_error` | 代码命中静态黑名单或守卫 | 见 `docs/SANDBOX.md` 规则表 |
| AI 一直 `degraded=true` | `AI_API_KEY` 为空或 Base URL 不可达 | 按 `docs/AI.md` 配置；离线规则助手属预期行为 |
| 前端 502 | backend 未就绪 / BACKEND_URL 写错 | 容器内应为 `http://backend:8000` |
| 数据丢失 | 误执行 `docker compose down -v` | 从备份恢复；卷名见 `docker volume ls` |

---

## 7. 升级与回滚

```bash
git pull
docker compose build backend frontend sandbox
docker compose up -d
docker compose exec backend alembic upgrade head
# 回滚代码后：docker compose exec backend alembic downgrade -1
```

迁移前务必先备份；`alembic downgrade` 不保证数据可逆。
