# PYTHON LAB

> 一个从零到一的 Python 学习平台：18 个阶段系统课程 + 在线判题（7 种题型）+ 浏览器代码运行沙箱 + AI 助教 + 游戏化激励，帮助学习者把「看懂」变成「写出来」。

---

## 一、功能总览

| 模块 | 能力 |
| --- | --- |
| 系统课程 | 18 个阶段 / 54 章节 / 162 课时，含理论、代码、示例、练习、常见错误；支持进度跟踪 |
| 在线判题 | 38 道题，7 种题型（选择 / 判断 / 填空 / 补全 / 编程 / 改错 / 算法）、4 档难度、隐藏用例 |
| 代码运行 | 沙箱执行单文件 / 多文件 Python，返回 stdout / stderr / 耗时 / 内存（远程沙箱优先，本机降级） |
| AI 助教 | 导师对话（含 SSE 流式）、九维度代码评审、报错分析；无 Key 时降级为本地规则助手 |
| 游戏化 | XP / 等级 / 成就（26）/ 每日任务（9）/ 挑战赛（6）/ 连续学习 |
| 统计与考试 | 学习概览、能力雷达、错题本、5 套阶段测评 |
| 个人数据 | 收藏、错题、代码历史快照、学习数据导出 |
| 管理与运维 | 后台（课程 / 题库 / 用户 / 公告 / AI 配置 / 系统设置 / 日志）、健康检查、降级可观测 |

---

## 二、技术栈

- **后端**：Python 3.13 · FastAPI · SQLAlchemy 2.0（类型化 ORM）· Alembic · Pydantic v2 · python-jose(JWT) · bcrypt
- **前端**：Next.js 15 · React 19 · TypeScript · Tailwind CSS
- **沙箱**：独立 FastAPI 服务（subprocess 执行 + 资源限制；无沙箱时后端本机执行器降级）
- **数据**：SQLite（默认 / 零依赖）或 PostgreSQL；缓存 Redis 或进程内内存；队列 RQ 或 inline
- **编排**：Docker Compose + Nginx（可选 profile=proxy）

---

## 三、目录结构

```text
python-learning-platform/
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── main.py          # 应用工厂 + lifespan + 全局异常 + CORS
│   │   ├── core/            # 配置/安全/响应/错误/分页/日志/缓存/队列/依赖
│   │   ├── db/              # base / session / init_db / seed（种子实现）
│   │   ├── models/          # 41 张表（SQLAlchemy 2.0）
│   │   ├── schemas/         # Pydantic v2 模型
│   │   ├── services/        # 业务逻辑（含 ai/ 子系统）
│   │   ├── sandbox/         # 代码执行器（远程 / 本机）
│   │   └── api/endpoints/   # 路由层（23 个分组）
│   ├── alembic/             # 迁移（0001_initial = 41 表）
│   ├── scripts/             # seed.py / smoke_test.py
│   ├── tests/               # API 测试
│   ├── requirements.txt · alembic.ini · Dockerfile · .env.example
├── frontend/                # Next.js 15 前端
├── sandbox/                 # 代码执行沙箱服务
├── database/seeds/          # 种子数据（courses/problems/projects/… + lessons/*.md）
├── docker/                  # Dockerfile / nginx.conf / postgres
├── scripts/                 # 一键脚本 setup / migrate / seed / dev / docker-up / healthcheck
├── docs/                    # ARCHITECTURE / DATABASE / API / DEPLOYMENT / SANDBOX / AI
├── ai/                      # AI 提示词与配置
├── docker-compose.yml       # 一键编排
└── .env.example             # 环境变量模板
```

---

## 四、快速开始

### 路径 A —— 本机无 Docker（推荐新人与低配机器）

> 全程 SQLite，无需 Postgres / Redis / 沙箱 / AI Key，服务自动降级。

```bash
# 0) 生成环境变量（根目录）
cp .env.example .env

# 1) 一键初始化：建 venv + 装依赖 +（可选）迁移与种子
bash scripts/setup.sh --with-migrate --with-seed        # Windows: pwsh scripts/setup.ps1 -WithMigrate -WithSeed
# 若本机设置代理导致默认 pip 源(清华)被拦截，改为官方源：
#   PIP_INDEX=https://pypi.org/simple bash scripts/setup.sh --with-migrate --with-seed

# 2) 启动后端(8000) + 前端(3000) [+ 沙箱(8081)]
bash scripts/dev.sh                                     # 加 --no-sandbox / --no-frontend 可裁剪
```

访问：前端 <http://localhost:3000> · 后端文档 <http://localhost:8000/docs> · 依赖健康 <http://localhost:8000/api/health/deps>

若不用一键脚本，也可手动：

```bash
cd backend
python -m venv .venv && .venv/Scripts/activate          # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt                         # 本机 pip 若被代理拦截，改用 -i https://pypi.org/simple
alembic upgrade head
python scripts/seed.py
uvicorn app.main:app --reload --port 8000
```

### 路径 B —— Docker（一键起全栈）

```bash
cp .env.example .env
docker compose up -d --build
# 前端 http://localhost:3000 · 后端 :8000 · 沙箱 :8081（Postgres / Redis 由 compose 提供）
```

> 首次启动会自动执行迁移与种子；`docker compose --profile proxy up -d` 可额外启用 Nginx（:8080）。

---

## 五、默认管理员

| 项 | 值 |
| --- | --- |
| 邮箱 | `admin@pythonlab.dev` |
| 用户名 | `admin` |
| 密码 | `Admin@12345`（**生产必须修改**） |

密码来源优先级：环境变量 `ADMIN_PASSWORD`（见根 `.env` / `backend/.env.example`）→ 缺省则由 `app/db/seed/extras.py::seed_admin_user` 使用内置默认值创建。**非明文存储**：入库前经 bcrypt 哈希。

---

## 六、环境变量（节选）

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `APP_ENV` | development | 环境（production 时关闭 /docs 并启用 JSON 日志） |
| `DATABASE_URL` | `sqlite:///./data/pythonlab.db` | 数据库；换 `postgresql+psycopg2://…` 即切 PG |
| `JWT_SECRET_KEY` / `SECRET_KEY` | change-me | JWT 签名密钥（生产必须改） |
| `ACCESS_TOKEN_TTL_MIN` / `REFRESH_TOKEN_TTL_DAYS` | 15 / 30 | 令牌有效期 |
| `CACHE_BACKEND` / `REDIS_URL` | auto / redis://localhost:6379/0 | 缓存，Redis 不通自动降级内存 |
| `QUEUE_BACKEND` | auto | 队列，Redis 不通降级 inline |
| `SANDBOX_MODE` / `SANDBOX_URL` | auto / http://localhost:8081 | 沙箱，不通降级本机执行器 |
| `AI_PROVIDER` / `AI_MODEL` / `AI_API_KEY` | deepseek / deepseek-chat / 空 | AI；无 Key 降级规则助手（**Key 仅服务端**） |
| `SEED_ON_STARTUP` | true | 启动自动种子（生产建议 false） |
| `SEEDS_DIR` | ../database/seeds | 种子目录（相对 backend/） |
| `DEFAULT_PAGE_SIZE` / `MAX_PAGE_SIZE` | 20 / 100 | 分页 |
| `CORS_ORIGINS` | localhost:3000,… | 跨域白名单 |

完整清单见根 `.env.example`（与 `app/core/config.py` 逐项对齐）。

---

## 七、常用命令

```bash
# 数据库迁移
alembic upgrade head                 # 应用到最新
alembic revision --autogenerate -m "msg"   # 生成迁移
alembic current / alembic history

# 种子数据（幂等）
python scripts/seed.py               # 全部
python scripts/seed.py --reset       # 删表重建（危险）
python scripts/seed.py --only courses,problems

# 测试
pytest -q                            # 全量（testpaths = app/tests tests）
pytest tests/test_content_api.py -q  # 单文件

# 健康与冒烟
curl http://localhost:8000/api/health/deps
python scripts/smoke_test.py --base-url http://127.0.0.1:8000
bash scripts/healthcheck.sh
```

---

## 八、五档降级策略

本平台所有外部依赖可降级，**无 Docker 也能完整跑通**；`GET /api/health/deps` 会返回**实际生效**的实现（而非配置声明值）。

| 依赖 | 生产实现 | 降级实现 | 触发条件 | 生产解除方式 |
| --- | --- | --- | --- | --- |
| 数据库 | PostgreSQL | **sqlite** | `DATABASE_URL` 以 sqlite 开头 | 改 `DATABASE_URL` 为 `postgresql+psycopg2://…` |
| 缓存 | Redis | **memory**（进程内 LRU） | Redis 探测不通 | 起 Redis 并配 `REDIS_URL` |
| 队列 | RQ | **inline**（线程池） | Redis 探测不通 | 起 Redis，`QUEUE_BACKEND=rq` |
| 沙箱 | 远程沙箱 | **local**（本机 subprocess） | 沙箱探测不通 | 起沙箱服务并配 `SANDBOX_URL` |
| AI | LLM Provider | **rule**（本地规则助手） | 无 `AI_API_KEY` 或 `AI_OFFLINE=true` | 配 `AI_API_KEY`（+ `AI_BASE_URL`） |

降级时 `/api/health/deps` 的 `status` 为 `degraded`，并逐项标注实际后端，便于排查。

---

## 九、文档索引（`docs/`）

| 文档 | 内容 |
| --- | --- |
| `ARCHITECTURE.md` | 系统架构、模块边界、降级设计、类图/时序图 |
| `DATABASE.md` | 41 张表结构、字段约定、可移植性红线 |
| `API.md` | 全部接口契约、统一响应结构、错误码 |
| `DEPLOYMENT.md` | 部署、Docker、Nginx、环境变量 |
| `SANDBOX.md` | 代码执行沙箱设计与安全策略 |
| `AI.md` | AI 子系统（Provider / Tutor / Review / RAG）设计 |
| `backend/README.md` | 后端开发细则（本机运行、种子、迁移） |

---

## 十、许可

仅供学习与教学用途。
