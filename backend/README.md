# PYTHON LAB · 后端（Backend）

FastAPI + SQLAlchemy 2.0 + Alembic + Pydantic v2 构建的 Python 学习平台后端。
**所有外部依赖（PostgreSQL / Redis / 远程沙箱 / AI Key）均具备降级路径**，因此本机无 Docker
也能用 SQLite 完整跑通。

---

## 1. 环境要求

- Python 3.13
- 依赖见 `requirements.txt`（运行时）/ `requirements-dev.txt`（开发）

## 2. 快速开始

```bash
cd backend

# 1) 创建虚拟环境
python -m venv .venv
.venv/Scripts/activate            # Windows;  Linux/macOS: source .venv/bin/activate

# 2) 安装依赖（本机 pip 若被代理拦截，改用官方源 -i https://pypi.org/simple）
pip install -r requirements.txt

# 3)（可选）复制环境变量
cp .env.example .env

# 4) 建库（SQLite 无需外部服务）
alembic upgrade head

# 5) 导入种子数据（幂等，可重复执行）
python scripts/seed.py

# 6) 启动服务
uvicorn app.main:app --reload --port 8000
```

启动后访问：

- 接口文档 <http://127.0.0.1:8000/docs>
- 基础健康检查 <http://127.0.0.1:8000/api/health>
- **依赖健康检查** <http://127.0.0.1:8000/api/health/deps>（返回实际生效的 db / cache / queue / runner / ai）

> 默认管理员：`admin@pythonlab.dev` / `Admin@12345`（可用 `ADMIN_*` 环境变量覆盖）。

## 3. 端到端冒烟测试

```bash
# 另开终端，确保服务已在 8000 端口运行
python scripts/smoke_test.py --base-url http://127.0.0.1:8000
```

覆盖：健康检查 → 注册 → 登录 → `/auth/me` → `/users/me/profile` → 刷新令牌 → 登出 → 令牌失效。

## 4. 目录结构

```
backend/
├── app/
│   ├── main.py            # 应用工厂 + lifespan + 全局异常 + CORS
│   ├── core/              # 配置/安全/响应/错误/分页/日志/缓存/队列/依赖
│   ├── db/                # base / session / init_db / seed（种子实现）
│   ├── models/            # 41 张表（SQLAlchemy 2.0 类型化 ORM）
│   ├── schemas/           # Pydantic v2 请求/响应模型
│   ├── services/          # 业务逻辑（auth / user / health / ai ...）
│   ├── sandbox/           # 代码执行器（远程优先，本机降级）
│   ├── api/               # 路由层（endpoints/*）
│   └── utils/             # 通用工具（ids/time/text/files/diff/validators）
├── alembic/               # 迁移（versions/0001_initial.py = 41 表）
├── scripts/               # seed.py / smoke_test.py
├── requirements.txt
├── alembic.ini
├── Dockerfile
└── .env.example
```

## 5. 关键约定

- **统一响应结构**：`{success, data, message, error:{code, details}}`（见 `app/core/response.py`）。
- **可移植性红线**：主键统一 `String(36)` uuid4；`sa.JSON`（不用 JSONB）；`DateTime(timezone=True)` UTC。
- **认证**：JWT 双令牌（access 15 分钟 + refresh 30 天），refresh 只存 sha256 摘要，登出用 jti 黑名单吊销。
- **密码**：bcrypt 哈希，绝不明文；`passlib` 后端不可用时自动回退 bcrypt 原生 API。
- **密钥**：JWT / AI Key 一律从环境变量读取，仅服务端使用。

## 6. 数据库

- 默认 `sqlite:///./data/pythonlab.db`（相对 `backend/` 解析，自动创建目录）。
- 切 PostgreSQL：改 `DATABASE_URL` 为 `postgresql+psycopg2://...` 即可，无需改代码。
- 迁移：`alembic upgrade head` / `alembic revision --autogenerate -m "msg"`。

## 7. 种子数据

数据源在仓库根 `database/seeds/`：

| 文件 | 内容 |
| --- | --- |
| `courses.json` | 18 阶段 / 54 章节 / 162 课时 |
| `lessons/stage-01..18.md` | 课时正文（按 `## <lesson-slug>` 锚点切分） |
| `topics.json` | 知识点树（167 条） |
| `tags.json` | 标签字典（52 条） |
| `problems.json` | 题目（38 道，含测试用例与标签） |
| `projects.json` | 实战项目（6 个，含项目文件） |
| `achievements.json` | 成就（26 条） |
| `daily_tasks.json` | 每日任务（9 条） |
| `challenges.json` | 挑战赛（6 个） |
| `exams.json` | 试卷（5 套） |

命令：

```bash
python scripts/seed.py                 # 幂等导入全部
python scripts/seed.py --reset         # 删表重建后导入（危险，仅开发）
python scripts/seed.py --only courses,problems
python scripts/seed.py --no-admin      # 不创建默认管理员
```

## 8. 当前已实现路由

| 分组 | 前缀 | 数量 | 说明 |
| --- | --- | --- | --- |
| 健康 | `/api/health` | 3 | `/health`、`/health/deps`、`/health/enums` |
| 认证 | `/api/auth` | 7 | register / login / refresh / logout / me / change-password / reset-password |
| 用户 | `/api/users` | 8 | me/profile(GET/PATCH) / me/avatar / me/preferences / me/overview / me/export / me(DELETE) / {id}/public |

其余分组（courses / problems / submissions / ai / projects …）按 `docs/API.md` 在后续阶段挂载到
`app/api/router.py`，挂载方式保持一致。

## 9. 常见问题

- **pip 报 403 / 找不到包**：本机若设置了代理会拦截清华源，改用官方源 `-i https://pypi.org/simple`。
- **`unable to open database file`**：确认 `DATABASE_URL` 的 SQLite 路径正确（相对 backend/ 解析），
  或直接运行 `alembic upgrade head`（会自动创建目录）。
- **`health/deps` 显示 degraded**：属正常降级（无 Redis / 沙箱 / AI Key），`db` 应为 `sqlite`。
