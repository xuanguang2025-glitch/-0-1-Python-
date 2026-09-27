# PYTHON LAB —— 系统架构设计文档

> 版本：v1.0 ｜ 架构师：高见远（Gao） ｜ 状态：已定稿，供工程实现
> 配套文档：`docs/DATABASE.md`（数据模型）、`docs/API.md`（接口契约）、`docs/DEPLOYMENT.md`（部署）、`docs/SANDBOX.md`、`docs/AI.md`、`docs/SEED.md`

---

## 0. 一页速览

| 维度 | 决断 |
|---|---|
| 前端 | Next.js 15（App Router） + React 19 + TypeScript + Tailwind CSS 3.4 + shadcn/ui + Monaco Editor + Zustand + TanStack Query |
| 后端 | Python 3.13 + FastAPI + Pydantic v2 + **同步** SQLAlchemy 2.0 Session + Alembic |
| 数据库 | PostgreSQL 15（生产） / **SQLite 自动降级**（本机开发） |
| 缓存 | Redis 7（生产） / **进程内 TTLCache 自动降级** |
| 队列 | RQ（生产） / **inline 同步执行自动降级** |
| 代码执行 | 独立 Sandbox 服务（FastAPI，Docker） / **backend 内置 LocalRunner 自动降级** |
| AI | 统一 `AIProvider` 协议（默认 DeepSeek，OpenAI 兼容协议） / **无 key 时 RuleBasedProvider 本地规则降级** |
| 认证 | JWT Access（15min，内存）+ Refresh（30d，localStorage），bcrypt 哈希 |
| 本机闭环 | 无需 Docker：`setup.ps1` → `dev.ps1` → 浏览器跑通注册→课程→编辑器→运行→判题→AI→统计 |

**设计第一原则**：任何外部依赖（Postgres / Redis / Sandbox / AI Key / RQ Worker）缺失时，系统**自动降级且功能不中断**，而不是启动失败。

---

## 1. 技术选型与降级策略

### 1.1 核心技术挑战与对策

| # | 挑战 | 对策 |
|---|---|---|
| C1 | 本机无 Docker，无法起 Postgres/Redis/sandbox 容器 | 三套可降级抽象（DB / Cache / Runner），以环境变量 + 启动期探测决定实现，详见 1.3 |
| C2 | Windows 无 `resource.setrlimit`，sandbox 内存/CPU 限制失效 | Linux 用 rlimit + cgroup 限额；Windows 用「子进程超时 kill + 输出截断 + 禁用危险内建 + psutil 轮询 RSS 超限 kill」替代，详见 §5 |
| C3 | Postgres 专有类型（UUID/ARRAY/JSONB）在 SQLite 不可移植 | 主键统一 `String(36)` 存 uuid4 字符串；数组一律用 `JSON` 或关联表；JSON 用 `sa.JSON`（SQLite 落 TEXT）；时间统一 `DateTime(timezone=True)` 存 UTC |
| C4 | Monaco Editor 体积大、SSR 会报错 | `@monaco-editor/react` + `next/dynamic({ ssr: false })` 懒加载，编辑器路由独立 chunk |
| C5 | AI 流式输出 + 同步 ORM 阻塞事件循环 | ORM 走同步 Session（FastAPI 自动线程池执行 `def` 端点）；SSE 通过 `run_in_threadpool` 包装，默认非流式 |
| C6 | 判题耗时（多测试用例）阻塞请求 | 同步判题（≤5s/用例，总超时 30s）走 `asyncio` 线程池；长任务走 RQ/inline 队列 + 轮询状态 |
| C7 | 前后端跨域 + Token 安全 | Next.js `rewrites` 把 `/api/**` 代理到后端（同源），后端同时开启 CORS 允许直连调试；Token 走 `Authorization: Bearer` |
| C8 | 单文件过大难以一次写完 | 后端单文件预算 ≤400 行，按「领域」而非「技术层」切分 service；前端组件 ≤250 行 |

### 1.2 框架选型与理由

| 层 | 选型 | 版本 | 理由 |
|---|---|---|---|
| Web 框架 | FastAPI | ^0.115 | 原生 Pydantic v2 校验、自动 OpenAPI、依赖注入简洁、同步/异步端点混用 |
| ORM | SQLAlchemy | ^2.0.36 | 2.0 风格 `DeclarativeBase` + `Mapped[]`，PG/SQLite 一套模型 |
| 迁移 | Alembic | ^1.14 | 与 SQLAlchemy 官方配套；SQLite 也能跑迁移 |
| 校验 | Pydantic | ^2.10 | v2 性能与类型体验 |
| 密码 | passlib[bcrypt] + bcrypt | ^1.7.4 | bcrypt 加盐哈希（argon2 作为可选 `PWD_HASH_SCHEME=argon2`） |
| JWT | python-jose / PyJWT | ^3.3 | 轻量，HS256 |
| HTTP 客户端 | httpx | ^0.28 | 同步+异步双模，调 Sandbox/AI |
| 缓存 | redis-py | ^5.2 | Redis 客户端；降级用自研 `MemoryCache` |
| 队列 | rq | ^2.1 | 比 Celery 轻，Redis 依赖与缓存共用 |
| 进程/资源 | psutil | ^6.1 | Windows 内存与进程 kill 的唯一可行方案 |
| 测试 | pytest + httpx + pytest-asyncio | — | FastAPI TestClient |
| 前端框架 | Next.js（App Router） | ^15 | RSC + 路由分组，SEO 友好（首页/课程页） |
| UI | Tailwind CSS + shadcn/ui | 3.4 / latest | 用户指定风格；shadcn 组件本地可改，无运行时依赖 |
| 编辑器 | @monaco-editor/react | ^4.6 | Monaco 在 React 最省事的封装，支持多 model（多文件） |
| 状态 | Zustand + TanStack Query | ^5 / ^5 | 客户端 UI 态用 Zustand，服务端数据用 Query（缓存/重试/失效） |
| 图表 | Recharts | ^2.13 | 统计页折线/雷达/热力 |
| Markdown | react-markdown + remark-gfm + shiki | — | 课程内容、AI 回答渲染（**必须做 HTML 白名单**，防 XSS） |
| 图标/字体 | lucide-react / Inter（next/font） | — | 统一视觉 |

### 1.3 三种降级开关（环境变量 + 判定逻辑）

> 所有降级开关都遵循同一模式：**`auto` = 启动期探测，失败则降级并打印 WARN 日志**；可显式强制。

#### ① 数据库降级（Postgres → SQLite）

| 变量 | 默认 | 说明 |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite`? **否** → 默认 `sqlite:///./data/pythonlab.db` | 以 `sqlite` 前缀 → SQLite 模式；以 `postgresql` 前缀 → PG 模式 |

判定逻辑（`backend/app/core/config.py::db_flavor()`）：

```
url = DATABASE_URL
if url.startswith("sqlite"):        flavor = "sqlite"
elif url.startswith("postgresql"):  flavor = "postgres"
else: raise ConfigError

sqlite 模式的额外动作：
  - engine = create_engine(url, connect_args={"check_same_thread": False}, poolclass=StaticPool(测试))
  - 事件监听 connect → PRAGMA foreign_keys=ON; PRAGMA journal_mode=WAL
  - 禁用 Postgres 专有 DDL（不建部分索引 / 不用 ARRAY / 不用 tsvector，搜索退化为 LIKE）
```

可移植性红线（写模型时必须遵守）：
- ✅ 主键：`String(36)` + Python `uuid4()`；禁止 `sqlalchemy.dialects.postgresql.UUID`
- ✅ 数组：用 `sa.JSON` 或关联表；禁止 `postgresql.ARRAY`
- ✅ JSON：`sa.JSON`（PG 落 JSON，SQLite 落 TEXT）
- ✅ 大文本：`Text`（不用 `CITEXT`）
- ✅ 时间：`DateTime(timezone=True)`，一律 `datetime.now(timezone.utc)`
- ✅ 布尔：`Boolean`（SQLite 用 0/1，SQLAlchemy 自动处理）
- ⚠️ 全文检索：PG 用 `ILIKE`/`to_tsvector`，SQLite 用 `LIKE`；`search_service` 内部按 flavor 分支

#### ② 缓存降级（Redis → 内存）

| 变量 | 默认 | 说明 |
|---|---|---|
| `CACHE_BACKEND` | `auto` | `auto` / `redis` / `memory` |
| `REDIS_URL` | `redis://localhost:6379/0` | |
| `CACHE_PROBE_TIMEOUT_MS` | `800` | auto 模式探测超时 |
| `CACHE_DEFAULT_TTL` | `300` | 秒 |

判定逻辑（`core/cache.py::build_cache()`）：
```
if CACHE_BACKEND == "redis":  return RedisCache(REDIS_URL)      # 构造失败直接 raise
if CACHE_BACKEND == "memory": return MemoryCache()
# auto
try:
    r = redis.from_url(REDIS_URL, socket_connect_timeout=probe)
    r.ping(); log INFO "cache=redis"; return RedisCache(r)
except Exception as e:
    log WARN "Redis 不可用，降级为进程内内存缓存: {e}"; return MemoryCache(max_size=5000)
```
统一接口：`get/set/delete/exists/incr/expire/clear + get_or_set(key, ttl, factory)`。`MemoryCache` 用 `collections.OrderedDict` + 惰性过期 + LRU 上限。

#### ③ Sandbox 降级（远程容器 → 本地受限子进程）

| 变量 | 默认 | 说明 |
|---|---|---|
| `SANDBOX_MODE` | `auto` | `auto` / `remote` / `local` / `stub` |
| `SANDBOX_URL` | `http://localhost:8081` | 独立 sandbox 服务地址 |
| `SANDBOX_PROBE_TIMEOUT_MS` | `1500` | |
| `SANDBOX_TIMEOUT_MS` | `5000` | 单用例默认超时 |
| `SANDBOX_MEMORY_MB` | `256` | |
| `SANDBOX_MAX_OUTPUT_BYTES` | `65536` | 输出截断 |
| `SANDBOX_ALLOW_NETWORK` | `false` | |
| `LOCAL_RUNNER_ENABLED` | `true` | 是否允许本地降级执行（生产应设 false） |

判定逻辑（`services/sandbox_service.py::build_runner()`）：
```
if SANDBOX_MODE == "remote": return RemoteRunner(SANDBOX_URL)           # 调用失败 → 抛 SANDBOX_UNAVAILABLE（不静默降级，保证判题可信）
if SANDBOX_MODE == "local" 或 (auto 且 LOCAL_RUNNER_ENABLED):
    probe: httpx.get(SANDBOX_URL + "/health", timeout=probe)
    成功 → RemoteRunner；失败/异常 → log WARN "sandbox 不可用，降级为本地受限执行器" → LocalRunner()
if SANDBOX_MODE == "stub": return StubRunner()   # 仅测试用，返回固定结果
```
⚠️ 判题可信度分级：提交记录写入 `submissions.runner`（`sandbox`/`local`），前端在成绩页以徽章标注；生产环境 `SANDBOX_MODE=remote` + `LOCAL_RUNNER_ENABLED=false`。

#### ④ 队列降级（RQ → inline）

| 变量 | 默认 | 说明 |
|---|---|---|
| `QUEUE_BACKEND` | `auto` | `auto` / `rq` / `inline` |
| `RQ_QUEUE_NAME` | `pythonlab` | |

判定逻辑：`auto` = Redis 可用则 RQ，否则 `InlineQueue`（用 FastAPI `BackgroundTasks`，进程内线程池同步执行）。调用方只依赖 `queue.enqueue(fn, *args, **kw)`，不感知实现。

#### ⑤ AI 降级（远程模型 → 本地规则）

| 变量 | 默认 | 说明 |
|---|---|---|
| `AI_PROVIDER` | `deepseek` | `openai / anthropic / gemini / deepseek / qwen / zhipu / moonshot / custom` |
| `AI_API_KEY` | 空 | **只在服务端环境变量**，绝不入库、绝不返回前端 |
| `AI_BASE_URL` | `https://api.deepseek.com/v1` | OpenAI 兼容端点 |
| `AI_MODEL` | `deepseek-chat` | |
| `AI_TEMPERATURE` | `0.3` | |
| `AI_MAX_TOKENS` | `2048` | |
| `AI_TIMEOUT_MS` | `30000` | |
| `AI_OFFLINE` | `false` | 强制离线（演示/测试） |

判定逻辑（`services/ai_provider.py::build_provider()`）：
```
if AI_OFFLINE == true 或 AI_API_KEY 为空/占位值("sk-your-..."):
    provider = RuleBasedProvider()      # 本地规则：错误类型识别 + 模板化提示/思路/讲解
else:
    provider = OpenAICompatibleProvider(...)  # anthropic/gemini 走各自适配器
调用失败（超时/401/429/5xx）→ 单次重试 → 仍失败则回落 RuleBasedProvider 并在响应 meta 标记 degraded=true
```

### 1.4 架构模式

- 后端：**分层架构（Router → Service → Model）** + 依赖注入。Router 只做参数校验与响应包装；Service 承载业务与事务；Model 只做结构。禁止 Router 直接写 ORM。
- 前端：**Feature-Sliced 轻量版**（`app/` 路由 + `components/<domain>/` + `services/` + `stores/`），服务端数据统一走 TanStack Query。
- 跨进程：**Sandbox 协议（HTTP + JSON）** 与 **AI Provider 协议（Python Protocol）** 两处抽象是系统解耦核心。

---

## 2. 完整目录树与文件职责

> 约定：`#` 后为该文件职责；`[预算行数]` 为单文件规模上限（后端 ≤400 行，前端组件 ≤250 行）。
> 总计约 **380 个文件**。

### 2.1 仓库根

```
python-learning-platform/
├── README.md                          # 项目说明、快速开始（Windows/Unix 双版本命令）
├── .env.example                       # 全量环境变量示例（含注释，提交到仓库）
├── .env                               # 本地真实配置（git 忽略，由 setup 脚本生成）
├── .gitignore                         # 忽略 .env / node_modules / __pycache__ / data/ / .next
├── .editorconfig                      # UTF-8、LF、2/4 空格统一
├── docs/                              # 文档目录（本文件所在）
└── data/                              # 本地 SQLite/上传文件落盘（git 忽略）
```

### 2.2 `frontend/`（Next.js）

```
frontend/
├── package.json                       # 依赖与 scripts（dev/build/lint/typecheck/test）
├── next.config.mjs                    # rewrites: /api/* → BACKEND_URL；Monaco worker；图片域名
├── tsconfig.json                      # paths: "@/*" → "./src/*"
├── tailwind.config.ts                 # 主题色（python-blue #3776AB / python-yellow #FFD43B）、字体 Inter、暗色 class 策略
├── postcss.config.mjs                 # tailwind + autoprefixer
├── components.json                    # shadcn/ui 配置（aliases, cssVariables=true）
├── .eslintrc.json                     # next/core-web-vitals
├── .env.local.example                 # NEXT_PUBLIC_API_BASE_URL=/api，NEXT_PUBLIC_SITE_NAME
└── public/
    ├── logo.svg                       # PYTHON LAB 主 Logo（蓝黄双色）
    ├── favicon.ico
    ├── python-logo.svg                # 装饰用 Python 标识（避免版权风险，自绘）
    ├── og-cover.png                   # 社交分享封面
    └── manifest.json                  # PWA 元信息（可选）

frontend/src/
├── app/
│   ├── layout.tsx                     # 根布局：html lang=zh、Inter 字体、Providers、ThemeProvider
│   ├── globals.css                    # Tailwind 指令 + CSS 变量（浅/深主题）+ 滚动条/代码块基础样式
│   ├── providers.tsx                  # QueryClientProvider + ThemeProvider + AuthProvider + Toast(Sonner)
│   ├── error.tsx                      # 全局错误边界
│   ├── not-found.tsx                  # 404 页
│   ├── loading.tsx                    # 全局骨架屏
│   ├── page.tsx                       # 首页：Hero「从零开始，系统掌握 Python」+ 副标题 + CTA + 阶段路线图 + 数据统计
│   ├── (auth)/
│   │   ├── layout.tsx                 # 认证页居中卡片布局
│   │   ├── login/page.tsx             # 登录表单（邮箱/用户名 + 密码 + 记住我）
│   │   └── register/page.tsx          # 注册表单（邮箱/用户名/密码强度/协议勾选）
│   ├── courses/
│   │   ├── page.tsx                   # 课程总览：18 阶段卡片网格 + 进度条 + 筛选
│   │   ├── [slug]/page.tsx            # 课程详情：章节树 + 学习进度 + 开始/继续按钮
│   │   └── [slug]/[lessonId]/page.tsx # 课时学习页：Markdown 正文 + 内嵌编辑器 + 随堂练习 + 上一/下一
│   ├── playground/page.tsx            # 自由编程：多文件 Monaco + 运行/清空/保存/历史/收藏
│   ├── problems/
│   │   ├── page.tsx                   # 题库列表：类型/难度/分类/标签筛选 + 搜索 + 排序
│   │   └── [id]/page.tsx              # 题目详情：题干 + 编辑器 + 自测运行 + 提交 + 结果面板 + AI 求助入口
│   ├── projects/
│   │   ├── page.tsx                   # 项目中心：10 个 Level 项目卡片 + 状态筛选
│   │   └── [id]/page.tsx              # 项目实战：需求文档 + 文件树 + 多文件编辑器 + 步骤清单 + 运行 + 提交
│   ├── ai/page.tsx                     # AI 导师：会话列表 + 聊天区 + 三模式切换 + 提示阶梯 + 代码导入
│   ├── challenges/
│   │   ├── page.tsx                   # 挑战列表：日/周/月 + 进行中/已结束
│   │   └── [id]/page.tsx              # 挑战详情：题目集 + 提交 + 排行榜（仅昵称与成绩）+ 倒计时
│   ├── dashboard/page.tsx             # 学习看板：XP/等级/连续天数 + 热力图 + 掌握度雷达 + 周报 + 每日任务
│   ├── bookmarks/page.tsx             # 收藏夹：题目/课时/项目/代码片段，分集合管理
│   ├── mistakes/page.tsx              # 错题本：按错误类型/知识点筛选 + 重做 + 掌握标记 + 复习提醒
│   ├── exams/
│   │   ├── page.tsx                   # 模拟考试列表：基础/中级/高级 + 历史成绩
│   │   └── [id]/page.tsx              # 考试进行页：计时 + 答题 + 交卷；结束后展示报告
│   ├── notifications/page.tsx         # 通知中心：已读/未读、批量标记、跳转
│   ├── search/page.tsx                # 全局搜索结果页：课程/课时/题目/项目/代码片段分组展示
│   ├── settings/
│   │   ├── page.tsx                   # 设置：资料/昵称头像/主题/AI 模式/学习模式/密码修改/导出数据
│   │   └── layout.tsx                 # 设置侧边导航
│   └── admin/
│       ├── layout.tsx                 # Admin 布局：侧边栏 + 权限校验（非 admin 跳转 403）
│       ├── page.tsx                   # 仪表盘：用户量/活跃/提交量/AI 用量/错误率
│       ├── users/page.tsx             # 用户管理：列表/搜索/禁用/改角色/重置密码
│       ├── courses/page.tsx           # 课程管理：课程-章节-课时树形 CRUD
│       ├── problems/page.tsx          # 题目管理：题目 CRUD + 测试用例编辑 + 批量导入(JSON)
│       ├── projects/page.tsx          # 项目管理：项目 CRUD + 文件编辑
│       ├── tags/page.tsx              # 标签管理
│       ├── announcements/page.tsx     # 公告管理：发布/置顶/有效期
│       ├── ai-config/page.tsx         # AI 配置：Provider/模型/temperature/提示词模板/限流
│       ├── models/page.tsx            # 模型清单：多模型配置与默认切换、连通性测试
│       └── logs/page.tsx              # 日志：审计日志 + AI 调用日志 + 错误日志
├── components/
│   ├── ui/                            # shadcn/ui 原语（不改逻辑，只改主题）
│   │   ├── button.tsx  card.tsx  input.tsx  textarea.tsx  label.tsx  select.tsx
│   │   ├── dialog.tsx  sheet.tsx  dropdown-menu.tsx  popover.tsx  tooltip.tsx
│   │   ├── tabs.tsx  badge.tsx  avatar.tsx  progress.tsx  switch.tsx  separator.tsx
│   │   ├── table.tsx  skeleton.tsx  scroll-area.tsx  alert.tsx  sonner.tsx  form.tsx  toggle-group.tsx
│   ├── layout/
│   │   ├── SiteHeader.tsx             # 顶部导航：首页 课程 编程 题库 项目 AI导师 挑战 + 搜索框 + 主题切换
│   │   ├── SiteFooter.tsx             # 页脚：链接/版权/版本
│   │   ├── MobileNav.tsx              # 移动端抽屉导航（PC 重编辑器，移动端重阅读/AI/统计）
│   │   ├── ThemeToggle.tsx            # 浅色/深色/系统 三态切换
│   │   ├── UserMenu.tsx               # 头像下拉：看板/设置/通知/退出
│   │   ├── AppSidebar.tsx             # 学习页/Admin 的侧边树形导航
│   │   └── CommandPalette.tsx         # ⌘K 全局搜索（可选增强）
│   ├── editor/
│   │   ├── CodeEditor.tsx             # Monaco 封装（dynamic ssr:false，主题跟随系统，Python 语言）
│   │   ├── MultiFileEditor.tsx        # 多文件 tab + model 复用 + 脏标记
│   │   ├── FileExplorer.tsx           # 项目文件树（新建/重命名/删除）
│   │   ├── EditorToolbar.tsx          # 运行/提交/格式化/保存快照/收藏/历史
│   │   ├── OutputPanel.tsx            # stdout/stderr/耗时/内存/截断提示 分 Tab 展示
│   │   ├── TestCasePanel.tsx          # 自测输入 + 用例结果对比 + diff
│   │   └── EditorSettings.tsx         # 字号/缩进/Tab/自动补全/主题
│   ├── course/
│   │   ├── StageTimeline.tsx          # 18 阶段路线图（首页 + 课程页复用）
│   │   ├── ChapterList.tsx            # 章节手风琴 + 完成态
│   │   ├── LessonContent.tsx          # Markdown 正文渲染（代码高亮 + 复制）
│   │   ├── LessonNav.tsx              # 上一课/下一课 + 标记完成
│   │   ├── LessonQuiz.tsx             # 随堂练习（选择/判断）
│   │   └── CourseProgressCard.tsx     # 课程进度卡（百分比 + 已学课时）
│   ├── problem/
│   │   ├── ProblemStatement.tsx       # 题干/输入输出/样例/约束
│   │   ├── ProblemFilters.tsx         # 类型/难度/分类/标签/状态 筛选器
│   │   ├── DifficultyBadge.tsx        # 4 档难度徽章
│   │   ├── VerdictBadge.tsx           # AC/WA/RE/TLE/MLE 判定徽章
│   │   ├── SubmitResultPanel.tsx      # 通过率/耗时/内存/失败用例/错误信息
│   │   ├── ProblemTags.tsx            # 标签展示
│   │   └── AiHelpButton.tsx           # 「问 AI」按钮（携带题目+代码+错误上下文）
│   ├── ai/
│   │   ├── ChatPanel.tsx              # 会话窗口 + 输入框 + 快捷提问
│   │   ├── MessageBubble.tsx          # Markdown 消息气泡（含代码块复制/插入到编辑器）
│   │   ├── ModeSelector.tsx           # 初学者/标准/进阶 三模式
│   │   ├── HintLadder.tsx             # 提示→思路→局部提示→错误分析→完整解释 阶梯按钮
│   │   ├── ErrorAnalysisCard.tsx      # 错误分析卡片（错误类型/原因/修复建议/最小示例）
│   │   ├── ReviewReportCard.tsx       # Code Review 报告（问题分级 + 行级建议 + 改进后代码）
│   │   └── ConversationList.tsx       # 历史会话列表
│   ├── project/
│   │   ├── ProjectCard.tsx            # 项目卡片（等级/难度/时长/进度）
│   │   ├── ProjectSteps.tsx           # 步骤清单勾选
│   │   ├── ProjectFileTree.tsx        # 项目文件树
│   │   ├── ProjectRequirement.tsx     # 需求文档渲染
│   │   └── ProjectSubmitDialog.tsx    # 提交项目成果
│   ├── gamification/
│   │   ├── XPBar.tsx                  # 经验值与下一等级进度
│   │   ├── LevelBadge.tsx             # 7 等级徽章
│   │   ├── AchievementCard.tsx        # 成就卡（已解锁/未解锁）
│   │   ├── StreakCalendar.tsx         # 连续学习天数日历
│   │   ├── DailyTaskList.tsx          # 每日任务与完成状态
│   │   └── LevelUpDialog.tsx          # 升级/解锁成就庆祝弹窗（轻量动画）
│   ├── stats/
│   │   ├── StatCard.tsx               # 指标卡
│   │   ├── HeatmapChart.tsx           # 学习热力图（按天）
│   │   ├── MasteryRadar.tsx           # 知识点掌握度雷达
│   │   └── TrendChart.tsx             # 提交/正确率趋势折线
│   ├── challenge/
│   │   ├── ChallengeCard.tsx          # 挑战卡（类型/时间/参与数）
│   │   ├── CountdownTimer.tsx         # 倒计时
│   │   └── LeaderboardTable.tsx       # 排行榜（**仅昵称 + 成绩 + 用时**，不含邮箱等）
│   ├── admin/
│   │   ├── DataTable.tsx              # 通用表格（分页/排序/筛选/行操作）
│   │   ├── CrudDialog.tsx             # 通用新增/编辑表单弹窗
│   │   ├── TagInput.tsx               # 标签输入
│   │   ├── ModelConfigForm.tsx        # 模型配置表单（含连通性测试按钮）
│   │   └── MarkdownEditor.tsx         # 简易 Markdown 编辑（textarea + 预览）
│   └── common/
│       ├── Pagination.tsx  SearchBar.tsx  EmptyState.tsx  LoadingSpinner.tsx
│       ├── ErrorBoundary.tsx  CopyButton.tsx  MarkdownRenderer.tsx  CodeBlock.tsx
│       ├── RelativeTime.tsx  ExportMenu.tsx  PageHeader.tsx  AuthGuard.tsx
├── lib/
│   ├── axios.ts                       # axios 实例：baseURL=/api、拦截器注入 Token、401 自动 refresh、统一解包/抛错
│   ├── api-client.ts                  # 统一请求封装 get/post/put/patch/delete（返回 data，抛 ApiError）
│   ├── auth.ts                        # Token 存取（access 内存 / refresh localStorage）、过期判断
│   ├── utils.ts                       # cn()、格式化（时长/内存/数字）、debounce、下载文件
│   ├── constants.ts                   # 难度/类型/分类枚举与中文映射、等级阈值、主题色
│   ├── storage.ts                     # localStorage 安全读写（SSR 保护）
│   ├── monaco-config.ts               # Monaco loader 配置与主题定义（python-dark / python-light）
│   └── cn.ts                          # clsx + tailwind-merge
├── hooks/
│   ├── useAuth.ts                     # 登录/注册/登出/刷新/当前用户
│   ├── useCourses.ts                  # 课程/章节/课时查询与进度变更
│   ├── useProblems.ts                 # 题目列表/详情/筛选
│   ├── useSubmissions.ts              # 提交与轮询判定结果
│   ├── useRunner.ts                   # 运行代码（/api/python/run）状态机
│   ├── useAiChat.ts                   # AI 会话与消息发送、阶梯提示
│   ├── useProgress.ts                 # 进度与统计
│   ├── useDebounce.ts                 # 防抖（搜索/自动保存）
│   └── useLocalStorage.ts             # 本地持久化（编辑器草稿）
├── stores/
│   ├── auth-store.ts                  # 当前用户、Token、角色
│   ├── editor-store.ts                # 打开的文件、内容、草稿、运行输出
│   ├── course-store.ts                # 当前课程/章节/课时、目录展开态
│   ├── ui-store.ts                    # 侧边栏、主题、命令面板、Toast
│   └── challenge-store.ts             # 挑战上下文与倒计时
├── types/
│   ├── api.ts                         # ApiResponse<T>、Page<T>、ApiError、错误码枚举
│   ├── models.ts                      # 各实体 DTO（与后端 schema 对齐）
│   ├── enums.ts                       # 难度/题型/判定/角色/AI 模式等枚举
│   └── editor.ts                      # 编辑器与沙箱相关类型
├── services/
│   ├── auth.service.ts  user.service.ts  course.service.ts  lesson.service.ts
│   ├── problem.service.ts  submission.service.ts  editor.service.ts  project.service.ts
│   ├── ai.service.ts  progress.service.ts  statistics.service.ts  achievement.service.ts
│   ├── challenge.service.ts  notification.service.ts  search.service.ts  bookmark.service.ts
│   ├── mistake.service.ts  code-history.service.ts  exam.service.ts  admin.service.ts
└── styles/theme.css                    # 主题变量补充（公告条、代码块、滚动条）
```

### 2.3 `backend/`（FastAPI）

```
backend/
├── pyproject.toml                     # 项目元信息 + 依赖分组（用 requirements.txt 亦可，二者选一：本设计用 requirements.txt 便于 Windows pip）
├── requirements.txt                   # 运行时依赖（锁定下界）
├── requirements-dev.txt               # pytest/ruff/black/mypy
├── alembic.ini                        # Alembic 配置（script_location=migrations）
├── pytest.ini                         # 测试配置
├── .env.example                       # 后端环境变量示例
└── app/
    ├── main.py                        # FastAPI 应用工厂：中间件(CORS/GZip/RequestID/耗时)、异常处理器、路由挂载、启动事件(探测降级、建表、种子检查) [≤150行]
    ├── core/
    │   ├── config.py                  # pydantic-settings BaseSettings；db_flavor()/build 开关；跨域/上传/分页常量 [≤200行]
    │   ├── security.py                # 密码哈希(bcrypt/argon2)、JWT 签发/解析、Token 黑名单、密码强度校验 [≤180行]
    │   ├── response.py                # success_response()/error_response() 统一封装 + ResponseModel[T] [≤80行]
    │   ├── errors.py                  # AppError 体系 + 错误码表 + 全局 exception_handler（HTTPException/ValidationError/AppError/Exception）[≤200行]
    │   ├── pagination.py              # PageParams(page,page_size,sort)、build_page()、游标分页 [≤80行]
    │   ├── deps.py                    # get_db / get_current_user / require_role / get_cache / get_runner / get_ai / get_pagination [≤180行]
    │   ├── cache.py                   # Cache 协议 + RedisCache + MemoryCache + build_cache() 探测降级 [≤200行]
    │   ├── queue.py                   # Queue 协议 + RQQueue + InlineQueue + build_queue() [≤120行]
    │   ├── logging.py                 # 结构化日志（request_id、耗时）、按环境切换格式 [≤100行]
    │   ├── constants.py               # 枚举常量、等级阈值、XP 规则、限流阈值 [≤120行]
    │   └── events.py                  # 领域事件总线（用于 XP/成就/通知解耦，进程内发布订阅）[≤80行]
    ├── db/
    │   ├── base.py                    # DeclarativeBase + 命名约定（索引/外键约束名）[≤60行]
    │   ├── session.py                 # engine/sessionmaker 工厂（按 flavor 设置 PRAGMA）、SessionLocal [≤120行]
    │   ├── init_db.py                 # 启动时建表 + 首次种子检查 + 默认管理员创建 [≤120行]
    │   └── seed/
    │       ├── __init__.py            # seed_all() 编排
    │       ├── loader.py              # 读取 database/seeds/*.json 并幂等写入（upsert by slug/code）[≤150行]
    │       ├── seed_courses.py        # 18 阶段课程/章节/课时 + topics 关联 [≤250行]
    │       ├── seed_problems.py       # 题目 + 测试用例 + 标签（每类 ≥10 题）[≤200行]
    │       ├── seed_projects.py       # 10 个 Level 项目 + 初始文件 [≤180行]
    │       ├── seed_achievements.py   # 成就/徽章/每日任务模板 [≤150行]
    │       └── seed_challenges.py     # 日/周/月挑战样例 [≤100行]
    ├── models/
    │   ├── __init__.py                # 统一导出（供 Alembic autogenerate）
    │   ├── mixins.py                  # UUIDPkMixin、TimestampMixin、SoftDeleteMixin [≤60行]
    │   ├── enums.py                   # 全部 Python Enum（与前端 enums.ts 对齐）[≤200行]
    │   ├── user.py                    # User, Profile, RefreshToken [≤180行]
    │   ├── course.py                  # Course, Chapter, Lesson, Topic, LessonTopic, CourseEnrollment [≤220行]
    │   ├── problem.py                 # Problem, TestCase, Tag, ProblemTag [≤220行]
    │   ├── submission.py              # Submission, SubmissionResult [≤180行]
    │   ├── project.py                 # Project, ProjectFile, UserProject [≤160行]
    │   ├── learning.py                # LearningProgress, KnowledgeMastery, Mistake, Bookmark, CodeHistory, LearningSession [≤260行]
    │   ├── gamification.py            # Achievement, UserAchievement, DailyTask, UserDailyTask, XPTransaction [≤200行]
    │   ├── ai.py                      # AiConversation, AiMessage, AiModelConfig, AiUsageLog [≤180行]
    │   ├── challenge.py               # Challenge, UserChallenge [≤120行]
    │   ├── exam.py                    # Exam, ExamAttempt [≤120行]
    │   ├── notification.py            # Notification, Announcement [≤120行]
    │   └── system.py                  # AuditLog, SystemSetting [≤100行]
    ├── schemas/
    │   ├── __init__.py                # 统一导出
    │   ├── common.py                  # ResponseModel, PageModel, ORMBase(BaseModel, from_attributes) [≤80行]
    │   ├── auth.py                    # Register/Login/Token/Refresh/ChangePassword [≤120行]
    │   ├── user.py                    # UserOut/ProfileUpdate/AdminUserUpdate [≤120行]
    │   ├── course.py                  # Course/Chapter/Lesson 的 Out/List/Create/Update [≤180行]
    │   ├── problem.py                 # Problem Out/List/Create/Update/Brief, TestCase [≤180行]
    │   ├── submission.py              # SubmitIn/SubmissionOut/RunResult/JudgeResult [≤150行]
    │   ├── project.py                 # Project Out/Detail/FileOut/UserProjectOut/SubmitIn [≤150行]
    │   ├── editor.py                  # RunRequest/RunResponse/SaveSnapshotIn/HistoryOut [≤120行]
    │   ├── ai.py                      # ChatIn/ChatOut/ReviewIn/ReviewOut/ConversationOut/MessageOut [≤150行]
    │   ├── progress.py                # ProgressOut/LessonProgressIn/MasteryOut [≤100行]
    │   ├── statistics.py              # OverviewOut/TrendOut/MasteryOut/ReportOut [≤120行]
    │   ├── gamification.py            # AchievementOut/UserAchievementOut/DailyTaskOut/XPOut [≤120行]
    │   ├── challenge.py               # ChallengeOut/LeaderboardOut/JoinIn/SubmitIn [≤120行]
    │   ├── notification.py            # NotificationOut/AnnouncementOut [≤80行]
    │   ├── search.py                  # SearchIn/SearchOut/SearchGroupOut [≤80行]
    │   ├── exam.py                    # ExamOut/ExamAttemptOut/SubmitAnswersIn/ReportOut [≤120行]
    │   ├── bookmark.py                # BookmarkIn/BookmarkOut [≤60行]
    │   ├── mistake.py                 # MistakeOut/MistakeCreate/ResolveIn [≤80行]
    │   ├── code_history.py            # HistoryOut/RestoreIn/CompareOut/DiffOut [≤80行]
    │   └── admin.py                   # Admin 各资源 CRUD + DashboardOut + AiConfigIn/ModelConfigIn [≤220行]
    ├── api/
    │   ├── __init__.py
    │   └── v1/
    │       ├── __init__.py
    │       ├── router.py              # 聚合所有 endpoint router，统一 prefix=/api [≤80行]
    │       ├── deps.py                # 路由级依赖（CommonQuery、资源存在性校验、权限断言）[≤120行]
    │       └── endpoints/
    │           ├── health.py          # GET /api/health, /api/health/deps（展示降级状态）[≤80行]
    │           ├── auth.py            # 注册/登录/刷新/登出/重置密码/me [≤200行]
    │           ├── users.py           # 用户资料 CRUD、头像、学习偏好 [≤180行]
    │           ├── courses.py         # 课程/章节列表与详情（含进度）[≤180行]
    │           ├── lessons.py         # 课时详情、完成打卡、随堂练习 [≤160行]
    │           ├── problems.py        # 题目列表/详情/筛选/随机一题/相似推荐 [≤200行]
    │           ├── submissions.py     # 提交、查询、详情、重判 [≤180行]
    │           ├── python_run.py      # POST /api/python/run 即时运行（不判题）[≤120行]
    │           ├── projects.py        # 项目列表/详情/文件/进度/提交 [≤200行]
    │           ├── editor.py          # 保存快照、历史列表/详情/恢复/比较/收藏 [≤200行]
    │           ├── ai.py              # /api/ai/chat、/api/ai/review、会话管理、提示阶梯 [≤220行]
    │           ├── progress.py        # 进度读写、知识点掌握度、学习模式设置 [≤160行]
    │           ├── statistics.py      # 概览/趋势/报告/导出(PDF/MD/CSV) [≤180行]
    │           ├── achievements.py    # 成就列表、我的成就、每日任务、XP 流水 [≤160行]
    │           ├── challenges.py      # 挑战列表/详情/参与/提交/排行榜 [≤180行]
    │           ├── notifications.py   # 通知列表/已读/删除 + 公告 [≤120行]
    │           ├── search.py          # 全局搜索 [≤100行]
    │           ├── bookmarks.py       # 收藏 CRUD [≤100行]
    │           ├── mistakes.py        # 错题本 CRUD + 复习队列 [≤120行]
    │           ├── code_history.py    # 代码历史（也可并入 editor.py；此处单独承载查询）[≤100行]
    │           ├── exams.py           # 模拟考试：列表/开始/交卷/报告 [≤180行]
    │           └── admin.py           # Admin 全部 CRUD + 配置 + 日志 [≤300行]
    ├── services/
    │   ├── auth_service.py            # 注册/登录/刷新/登出/密码策略 [≤250行]
    │   ├── user_service.py            # 资料、头像、偏好、管理员操作 [≤180行]
    │   ├── course_service.py          # 课程/章节树、报名、进度汇总 [≤220行]
    │   ├── lesson_service.py          # 课时详情、完成打卡、随堂练习判分 [≤200行]
    │   ├── problem_service.py         # 题目查询/筛选/随机/相似推荐/CRUD [≤250行]
    │   ├── sandbox_service.py         # Runner 抽象与降级选择、超时/重试 [≤180行]
    │   ├── judge_service.py           # 判题编排：多用例、对比模式、计分、错误归类 [≤300行]
    │   ├── submission_service.py      # 提交记录、结果落库、统计更新、判分回调 [≤220行]
    │   ├── project_service.py         # 项目与文件、用户项目进度 [≤200行]
    │   ├── editor_service.py          # 运行快照、代码历史（版本/恢复/diff）、收藏 [≤220行]
    │   ├── ai_provider.py             # AIProvider Protocol + build_provider() + 降级 [≤200行]
    │   ├── ai_providers/
    │   │   ├── __init__.py
    │   │   ├── openai_compatible.py   # OpenAI/DeepSeek/通义/智谱/Moonshot/任意兼容端点 [≤200行]
    │   │   ├── anthropic.py           # Claude 适配器 [≤150行]
    │   │   ├── gemini.py              # Gemini 适配器 [≤150行]
    │   │   └── rule_based.py          # 无 Key 时本地规则提示（错误分类 + 模板库）[≤300行]
    │   ├── prompt_service.py          # 从 ai/prompts/*.md 加载并渲染模板（含模式/阶梯/题目上下文）[≤200行]
    │   ├── ai_service.py              # 会话管理、调用编排、用量日志、限流、内容安全 [≤300行]
    │   ├── progress_service.py        # 学习进度、课程进度、学习模式 [≤200行]
    │   ├── mastery_service.py         # 知识点掌握度计算（SM-2 简化版）[≤180行]
    │   ├── statistics_service.py      # 概览/趋势/热力/报告聚合 [≤250行]
    │   ├── gamification_service.py    # XP/等级/连续天数/成就解锁/每日任务 [≤280行]
    │   ├── challenge_service.py       # 挑战参与、计分、排行榜（脱敏）[≤220行]
    │   ├── notification_service.py    # 通知生成与推送、公告 [≤150行]
    │   ├── search_service.py          # 课程/课时/题目/项目/片段 聚合搜索（按 flavor 分支）[≤200行]
    │   ├── exam_service.py            # 组卷、计时、判分、报告 [≤220行]
    │   ├── mistake_service.py         # 错题入库、复习队列、同类推荐 [≤160行]
    │   ├── bookmark_service.py        # 收藏（含代码片段库）[≤120行]
    │   ├── code_history_service.py    # 版本、恢复、diff（difflib）[≤150行]
    │   ├── recommend_service.py       # 推荐：基于掌握度 + 分类偏好 + 热门 [≤180行]
    │   ├── export_service.py          # 导出：学习报告 PDF/MD、代码/ZIP、项目 ZIP [≤250行]
    │   ├── admin_service.py           # Admin 聚合操作与审计 [≤220行]
    │   ├── storage_service.py         # 本地磁盘 / S3 抽象（默认本地 data/uploads）[≤120行]
    │   └── audit_service.py           # 审计日志写入 [≤80行]
    ├── sandbox/
    │   ├── protocol.py                # 沙箱请求/响应 Pydantic 模型（与 sandbox 服务共享契约）[≤150行]
    │   ├── local_runner.py            # 本地受限子进程执行器（Windows/Linux 双路径）[≤350行]
    │   ├── limits.py                  # 限额策略：Linux rlimit / Windows psutil 轮询 [≤200行]
    │   ├── preload.py                 # 注入到用户脚本前的守卫代码：禁用危险内建、限制 import、输出截断、递归深度
    │   └── security.py                # 源码静态检查（黑名单 import/关键字）、路径遍历防护 [≤180行]
    ├── utils/
    │   ├── ids.py                     # new_uuid()
    │   ├── time.py                    # now_utc()、日期区间、时长格式化
    │   ├── text.py                    # 归一化输出（换行/尾空格）、截断、脱敏
    │   ├── validators.py              # 邮箱/用户名/密码强度/文件名合法
    │   ├── files.py                   # 临时目录与清理、ZIP 打包（跨平台）
    │   ├── diff.py                    # 统一 diff / 行级对比（difflib 封装）
    │   └── decorators.py              # tx 事务装饰、重试、耗时统计
    ├── migrations/
    │   ├── env.py                     # Alembic 环境（离线/在线、按 flavor 跳过专有 DDL）
    │   ├── script.py.mako             # 迁移模板
    │   └── versions/0001_initial.py   # 初始全表迁移
    ├── scripts/
    │   ├── create_admin.py            # 创建/提升管理员
    │   ├── seed_data.py               # 命令行种子导入（--only courses|problems|...）
    │   └── run_dev.py                 # uvicorn --reload 启动（读取 .env）
    └── tests/
        ├── conftest.py                # 测试用 SQLite 内存库、client、鉴权夹具
        ├── test_auth.py  test_courses.py  test_problems.py  test_judge.py
        ├── test_local_runner.py  test_ai.py  test_progress.py  test_admin.py
```

### 2.4 `sandbox/`（独立执行服务，Docker 中运行）

```
sandbox/
├── Dockerfile                         # python:3.13-slim + 非 root 用户 + 只读根 + seccomp
├── requirements.txt                   # fastapi uvicorn psutil
├── README.md                          # 协议说明与独立启动方式
├── app/
│   ├── main.py                        # FastAPI：POST /execute、GET /health、GET /limits [≤150行]
│   ├── protocol.py                    # 与 backend 共享的请求/响应模型（复制自 backend/app/sandbox/protocol.py）[≤150行]
│   ├── executor.py                    # 落盘临时目录 → 写文件 → 子进程执行 → 收集输出/耗时/内存 [≤300行]
│   ├── limits.py                      # rlimit(cgroup) 预执行函数 + Windows 降级路径 [≤200行]
│   └── security.py                    # 源码黑名单检查、禁止网络（socket 禁用）、import 白名单 [≤180行]
└── tests/test_executor.py             # 超时/无限循环/大输出/禁网 用例
```

### 2.5 `database/`

```
database/
├── README.md                          # 初始化与种子说明
├── init/
│   ├── 01-schema.sql                  # 生产 PG 初始化（库、扩展 uuid-ossp/pg_trgm、只读用户）
│   └── 02-index.sql                   # 全文检索索引与部分索引
└── seeds/
    ├── courses.json                   # 18 阶段课程结构（stage_no 1..18，含章节/课时元数据）
    ├── lessons/                       # 按阶段拆分的课时正文 Markdown（stage-01.md ... stage-18.md）
    ├── problems.json                  # 题目（含测试用例、标签、分类）
    ├── projects.json                  # 10 个实战项目（含初始文件）
    ├── topics.json                    # 知识点树（≥120 个知识点）
    ├── tags.json                      # 标签字典（≥40）
    ├── achievements.json              # 成就与徽章（≥30）
    ├── daily_tasks.json               # 每日任务模板（≥12）
    ├── challenges.json                # 挑战模板
    └── exams.json                     # 模拟考试卷（基础/中级/高级各 1+）
```

### 2.6 `ai/`

```
ai/
├── README.md                          # Provider 接入说明、密钥配置（仅环境变量名）
├── config/models.yaml                 # 模型清单：provider/model/base_url/api_key_env/价格/能力标记
└── prompts/
    ├── tutor_system.md                # 导师系统提示（角色、语气、绝不直接给完整答案的约束）
    ├── hint_ladder.md                 # 五级提示阶梯模板
    ├── code_review.md                 # Code Review 评分维度与输出 JSON schema
    ├── error_analysis.md              # 错误分析模板（类型/原因/定位/修复/最小复现）
    ├── exam_generator.md              # 组卷与解析生成
    ├── mode_beginner.md               # 初学者模式：类比 + 一步一动
    ├── mode_standard.md               # 标准模式
    └── mode_advanced.md               # 进阶模式：复杂度/惯用法/最佳实践
```

### 2.7 `docker/` 与 `scripts/`

```
docker/
├── docker-compose.yml                 # postgres + redis + backend + frontend + sandbox + nginx（生产）
├── docker-compose.dev.yml             # 仅 postgres + redis（有 Docker 的开发者用）
├── backend.Dockerfile  frontend.Dockerfile  nginx.conf
└── README.md                          # 生产部署说明（本机无 Docker 时不可用，仅供服务器）

scripts/
├── setup.ps1                          # Windows 一键初始化：建 venv、pip install -r（国内源）、npm i（npmmirror）、生成 .env、init db、seed
├── setup.sh                           # Unix 等价
├── dev.ps1 / dev.sh                   # 并排启动 backend(8000) + frontend(3000)
├── seed.ps1 / seed.sh                 # 导入种子数据
├── migrate.ps1 / migrate.sh           # alembic upgrade head
├── test.ps1 / test.sh                 # 后端 pytest + 前端 typecheck
└── smoke.ps1                          # 冒烟：curl 健康检查 + 注册 + 运行代码 + 提交判题
```

### 2.8 `docs/` 与 `tests/`

```
docs/
├── ARCHITECTURE.md                    # 本文档
├── DATABASE.md                        # 40 张表字段级定义
├── API.md                             # 路由清单、分页与错误码
├── DEPLOYMENT.md                      # 部署（Docker）与本机无 Docker 降级运行手册
├── SANDBOX.md                         # 沙箱协议与本地 Runner 安全边界说明
├── AI.md                              # AI Provider 接入与提示词规范
└── SEED.md                            # 种子数据规范（尤其 18 阶段课程结构）
tests/e2e/
├── smoke.spec.ts                      # Playwright 冒烟（可选，非阻塞）
└── README.md
```

---

## 3. 数据模型设计（摘要，字段级详见 `docs/DATABASE.md`）

共 **40 张表**，按领域划分为 6 个模型文件组：

| 组 | 模型文件 | 表 |
|---|---|---|
| 身份 | `models/user.py` | users, profiles, refresh_tokens |
| 内容 | `models/course.py` | courses, chapters, lessons, topics, lesson_topics, course_enrollments |
| 题目 | `models/problem.py` | problems, test_cases, tags, problem_tags |
| 判题 | `models/submission.py` | submissions, submission_results |
| 项目 | `models/project.py` | projects, project_files, user_projects |
| 学习 | `models/learning.py` | learning_progress, knowledge_mastery, mistakes, bookmarks, code_history, learning_sessions |
| 游戏化 | `models/gamification.py` | achievements, user_achievements, daily_tasks, user_daily_tasks, xp_transactions |
| AI | `models/ai.py` | ai_conversations, ai_messages, ai_model_configs, ai_usage_logs |
| 挑战/考试 | `models/challenge.py`, `models/exam.py` | challenges, user_challenges, exams, exam_attempts |
| 系统 | `models/notification.py`, `models/system.py` | notifications, announcements, audit_logs, system_settings |

**通用列约定**：所有表主键 `id CHAR(36)`；业务表含 `created_at`、`updated_at`（`DateTime(timezone=True)`）；软删除用 `deleted_at` 而非物理删除（仅 users/problems 需要）。

**索引策略**：外键列必建索引；高频查询组合索引 `(user_id, created_at)`、`(problem_id, status)`、`(user_id, lesson_id) UNIQUE`、`(user_id, topic_id) UNIQUE`；列表页排序用 `(order_index)`、`(created_at DESC)`。SQLite 下不建部分索引与 GIN。

> 完整字段表（类型/可空/默认/索引/外键/说明）见 `docs/DATABASE.md`。

---

## 4. 关键运行时流程（详见 `docs/API.md` 时序图）

1. **注册登录**：`POST /api/auth/register` → bcrypt 哈希 → 建 user+profile → 签 access(15min)/refresh(30d) → 响应 `TokenPair`。
2. **学习课时**：`GET /api/courses/{slug}/{lessonId}` → 课时 Markdown + 内置编辑器初始代码 → `POST /api/lessons/{id}/complete` → 写 learning_progress + 触发 XP/成就/连续天数事件。
3. **运行代码**：前端 `/api/python/run` → `sandbox_service` 选 Runner → 本地则 `LocalRunner`（临时目录 + preload 守卫 + 子进程 + 超时/截断）→ 返回 RunResponse。
4. **提交判题**：`POST /api/submissions` → 入库 status=pending → `judge_service` 逐用例调用 Runner（或一次批量）→ 归一化对比 → 计算 verdict/score → 更新 submission + submission_results + problem 统计 + 掌握度 + 错题本 + XP。
5. **AI 导师**：`POST /api/ai/chat` → 组装模式提示 + 阶梯提示 + 题目/代码/错误上下文 → `ai_provider.chat()` → 写 ai_messages + 用量日志 → 失败回落 RuleBasedProvider（`meta.degraded=true`）。

---

## 5. 沙箱执行协议（`docs/SANDBOX.md` 为权威版）

### 5.1 请求 `POST {SANDBOX_URL}/execute`

```json
{
  "request_id": "9f3c...",              // string(uuid4)，必填，用于日志串联
  "language": "python",                 // 目前仅 python
  "version": "3.13",                    // 可选，仅记录
  "mode": "run",                        // "run" 单次运行 | "judge" 多用例判题 | "batch_run" 多文件项目运行
  "files": [                            // 多文件项目：按 path 落盘到临时目录
    { "path": "main.py", "content": "print(int(input())+1)" },
    { "path": "utils/helper.py", "content": "def add(a,b): return a+b" }
  ],
  "entry": "main.py",                   // 入口文件，默认 main.py
  "stdin": "3\n",                       // run 模式的标准输入
  "test_cases": [                       // judge 模式必填；run 模式忽略
    { "id": "tc1", "input": "1\n", "expected": "2", "comparison": "trimmed" }
  ],
  "timeout_ms": 5000,                   // 单用例上限，服务端再 clamp 到 [1000, 10000]
  "memory_limit_mb": 256,               // 服务端 clamp 到 [32, 512]
  "cpu_limit_ms": 4000,
  "max_output_bytes": 65536,            // 超出截断并置 truncated=true
  "allow_network": false,               // 服务端硬编码 false（服务端配置优先）
  "env": {}                             // 允许注入的非敏感环境变量（白名单）
}
```

### 5.2 响应 `200 OK`

```json
{
  "request_id": "9f3c...",
  "status": "success",                  // success|compile_error|runtime_error|timeout|memory_exceeded|output_exceeded|internal_error
  "exit_code": 0,
  "stdout": "2\n",
  "stderr": "",
  "truncated": false,
  "time_ms": 23,
  "memory_kb": 18432,
  "results": [                          // judge 模式
    { "test_case_id": "tc1", "passed": true, "actual": "2", "expected": "2",
      "time_ms": 12, "memory_kb": 18000, "diff": null }
  ],
  "passed_cases": 1,
  "total_cases": 1,
  "error": null,                        // { "type": "ValueError", "message": "...", "traceback": "...", "line": 3 }
  "runner": "sandbox",                  // sandbox | local
  "degraded": false                     // true 表示由本地降级执行器产出（成绩页提示）
}
```

错误响应：`4xx/5xx` + `{"success":false,"error":{"code":"SANDBOX_TIMEOUT","details":"..."}}`。

### 5.3 本地降级 Runner 的安全边界（`backend/app/sandbox/local_runner.py`）

| 风险 | Linux 方案 | Windows 方案（本机） |
|---|---|---|
| CPU 时间 | `resource.setrlimit(RLIMIT_CPU)` | 无 → `subprocess.communicate(timeout)` 后 `kill()` 进程树 |
| 内存 | `RLIMIT_AS`（256MB） | 无 → `psutil` 每 100ms 采样 RSS，超限 `kill()`（尽力而为） |
| 墙钟时间 | `RLIMIT_CPU` + alarm | `communicate(timeout=...)` + `taskkill /F /T`（进程树） |
| 输出爆炸 | 管道 + 字节上限截断 | 同（读取到上限后 kill） |
| 文件写入 | 临时目录 + 只读其他路径（容器） | 临时目录 `tempfile.mkdtemp()`，退出即 `shutil.rmtree` |
| 网络 | 容器网络隔离 | preload 守卫：`socket.socket = _blocked`、`urllib` 钩子禁用 |
| 危险调用 | seccomp + 非 root | preload 移除/替换：`open`(仅允许临时目录)、`exec/eval/compile/__import__` 受限、`os.system/os.popen/subprocess`、`sys.exit` 允许 |
| 无限递归 | `sys.setrecursionlimit(300)` | 同 |
| 卡死输入 | `input()` 无 stdin 时阻塞 | preload 把 `input` 换成带 EOF/次数上限的版本 |

**执行步骤（本地）**：
1. `security.scan_source()` 静态黑名单检查（命中 → 直接返回 `security_error`，不执行）。
2. `tempfile.mkdtemp(prefix="plab_")` → 写 `files` → 写 `preload.py`（守卫）→ 生成 `__plab_main__.py`（`exec(compile(source))` 包裹）。
3. `subprocess.Popen([sys.executable, "-I", "-B", "__plab_main__.py"], cwd=tmp, stdout=PIPE, stderr=PIPE, stdin=PIPE, env=clean_env, text=True)`。
4. Linux：`preexec_fn=apply_limits`；Windows：启动 `psutil.Process` 采样线程。
5. 写入 stdin → `communicate(timeout)` → 超时则 `kill_process_tree()` 并置 `status=timeout`。
6. 截断输出 → 清理临时目录 → 组装 `RunResponse`。

> ⚠️ 明确告知用户：本地 Runner **不是安全沙箱**，仅用于本机开发/离线演示；生产必须使用 `sandbox/` 容器。UI 上以徽章提示「本地执行（非隔离）」。

---

## 6. AI Provider 接口签名

```python
# backend/app/services/ai_provider.py
from typing import Protocol, AsyncIterator

class ProviderConfig(BaseModel):
    provider: str                 # openai|anthropic|gemini|deepseek|qwen|zhipu|moonshot|custom|rule
    model: str
    base_url: str | None = None
    api_key_env: str | None = None   # 只保存环境变量名，如 "DEEPSEEK_API_KEY"
    temperature: float = 0.3
    max_tokens: int = 2048
    timeout_ms: int = 30_000
    extra: dict = {}

class ChatMessage(BaseModel):
    role: str        # system|user|assistant
    content: str

class ChatResult(BaseModel):
    content: str
    provider: str
    model: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    degraded: bool = False        # True = 由 RuleBasedProvider 兜底
    raw: dict | None = None

class AIProvider(Protocol):
    name: str
    def __init__(self, cfg: ProviderConfig) -> None: ...
    async def chat(self, messages: list[ChatMessage], *, temperature: float | None = None,
                   max_tokens: int | None = None, stop: list[str] | None = None) -> ChatResult: ...
    async def stream(self, messages: list[ChatMessage], **kw) -> AsyncIterator[str]: ...
    def count_tokens(self, text: str) -> int: ...
    async def health(self) -> bool: ...

def build_provider(cfg: ProviderConfig | None = None) -> AIProvider:
    """cfg 为空则读全局配置；AI_OFFLINE=1 或 key 缺失 → RuleBasedProvider()"""
```

- **消息组装**：`prompt_service.render(template, ctx)` → `system(mode) + context(题目/代码/错误/课程) + history(最近 10 轮) + user`。
- **输出约束**：Code Review 场景要求模型输出 **JSON**（`{"score":int,"issues":[{"severity","line","title","suggestion"}],"improved_code":str}`），解析失败重试一次并降级为纯文本展示。
- **练习模式**：默认 `answer_level ≤ partial`（不给完整答案），用户显式点击「看完整解答」才提升到 `full`，并在 `ai_messages.kind` 记录。
- **限流**：按用户 `AI_RATE_LIMIT_PER_HOUR`（默认 60），超限返回 `AI_RATE_LIMITED`；缓存相同 `(conversation, prompt_hash)` 结果 10 分钟降本。
- **用量**：每次调用写 `ai_usage_logs`，Admin 可查。

---

## 7. 任务分解（T1–T6，含并行分组）

> 顶层 **6 个任务包**（每包 ≥3 文件，按依赖排序）。每个包内部标注 **A/B/C 并行组**，主理人可按组派工：
> - **组 B** = 后端（Python）
> - **组 F** = 前端（React）
> - **组 I** = 基础设施（Sandbox / Docker / 脚本 / 种子）

### T1（P0，无依赖）—— 契约与基座
**文件数：约 40** ｜ **接口数：2**（`/api/health`, `/api/health/deps`）

| 分组 | 文件 |
|---|---|
| I | 仓库根 `README.md`、`.env.example`、`.gitignore`、`.editorconfig`；`scripts/setup.ps1`、`setup.sh`、`dev.ps1`、`dev.sh`、`migrate.ps1`、`seed.ps1`、`test.ps1`、`smoke.ps1` |
| B | `backend/requirements*.txt`、`alembic.ini`、`pytest.ini`、`app/main.py`、`app/core/*`（config/response/errors/pagination/logging/constants/cache/queue/deps/security/events）、`app/db/base.py`、`app/db/session.py`、`app/utils/*`、`app/sandbox/protocol.py` |
| F | `frontend/package.json`、`next.config.mjs`、`tsconfig.json`、`tailwind.config.ts`、`postcss.config.mjs`、`components.json`、`.eslintrc.json`、`.env.local.example`、`src/app/layout.tsx`、`globals.css`、`providers.tsx`、`src/lib/*`、`src/types/api.ts|enums.ts`、`src/components/ui/*`(22个) |

**验收**：`setup.ps1` 一键跑通 → 后端 `/api/health/deps` 返回 `{"db":"sqlite","cache":"memory","runner":"local","ai":"rule"}`；前端 `localhost:3000` 出首页骨架。

### T2（P0，依赖 T1）—— 数据层 + 种子
**文件数：约 45** ｜ **接口数：0**（为 T3 提供模型与服务基座）

| 分组 | 文件 |
|---|---|
| B1 | `app/models/*`（mixins/enums/user/course/problem/submission/project/learning/gamification/ai/challenge/exam/notification/system） |
| B2 | `app/schemas/*`（全部 22 个 schema 模块） |
| B3 | `migrations/env.py`、`script.py.mako`、`versions/0001_initial.py`、`app/db/init_db.py` |
| I | `database/init/*.sql`、`database/seeds/*.json`、`database/seeds/lessons/stage-01..18.md`、`docs/SEED.md` |
| B4 | `app/db/seed/*`（loader + 6 个 seed 脚本）、`backend/scripts/seed_data.py`、`create_admin.py`、`run_dev.py`、`tests/conftest.py` |

**并行提示**：B1→B2→B3 串行；B4 与 I 可在模型定稿后并行（两个工程师）。
**验收**：`alembic upgrade head` 在 SQLite 成功；`seed_data.py` 全量导入 18 阶段课程 + ≥80 题 + 10 项目，可重复执行幂等。

### T3（P0，依赖 T2）—— 后端核心服务与 API
**文件数：约 55** ｜ **接口数：约 95**

| 分组（可并行） | 文件 | 覆盖路由 |
|---|---|---|
| B-a 身份与用户 | `services/auth_service.py`、`user_service.py`、`audit_service.py`、`endpoints/auth.py`、`users.py`、`health.py` | `/api/auth/*`、`/api/users/*`（12） |
| B-b 内容与学习 | `services/course_service.py`、`lesson_service.py`、`progress_service.py`、`mastery_service.py`、`endpoints/courses.py`、`lessons.py`、`progress.py` | `/api/courses`、`/api/lessons`、`/api/progress`（18） |
| B-c 题目与判题 | `services/problem_service.py`、`judge_service.py`、`submission_service.py`、`sandbox_service.py`、`sandbox/local_runner.py`、`limits.py`、`preload.py`、`security.py`、`endpoints/problems.py`、`submissions.py`、`python_run.py` | `/api/problems`、`/api/submissions`、`/api/python/run`（20） |
| B-d 编辑器与项目 | `services/editor_service.py`、`project_service.py`、`code_history_service.py`、`bookmark_service.py`、`storage_service.py`、`endpoints/editor.py`、`projects.py`、`code_history.py`、`bookmarks.py` | `/api/editor`、`/api/projects`、`/api/code-history`、`/api/bookmarks`（26） |
| B-e 游戏化/统计/挑战/考试 | `services/gamification_service.py`、`statistics_service.py`、`challenge_service.py`、`exam_service.py`、`mistake_service.py`、`notification_service.py`、`recommend_service.py`、`export_service.py`、`search_service.py`、`endpoints/achievements.py`、`statistics.py`、`challenges.py`、`exams.py`、`mistakes.py`、`notifications.py`、`search.py` | `/api/achievements`、`/api/statistics`、`/api/challenges`、`/api/exams`、`/api/mistakes`、`/api/notifications`、`/api/search`（30） |
| B-f AI | `services/ai_provider.py`、`ai_providers/*`（4）、`prompt_service.py`、`ai_service.py`、`endpoints/ai.py`、`ai/prompts/*.md` | `/api/ai/*`（9） |
| B-g Admin | `services/admin_service.py`、`endpoints/admin.py` | `/api/admin/*`（约 20） |

**并行提示**：B-a 完成后，B-b/B-c/B-d/B-e/B-f 可 **5 路并行**；B-g 依赖 B-b/B-c 的服务。
**验收**：`pytest` 全绿；`smoke.ps1` 串起 注册→登录→课程→运行→提交→AI→统计。

### T4（P1，依赖 T1；可与 T2/T3 并行）—— Sandbox 服务 + Docker + 文档
**文件数：约 20** ｜ **接口数：3**（sandbox 内部）

| 分组 | 文件 |
|---|---|
| I1 | `sandbox/Dockerfile`、`requirements.txt`、`app/main.py`、`protocol.py`、`executor.py`、`limits.py`、`security.py`、`tests/test_executor.py`、`README.md` |
| I2 | `docker/docker-compose.yml`、`docker-compose.dev.yml`、`backend.Dockerfile`、`frontend.Dockerfile`、`nginx.conf`、`README.md` |
| I3 | `docs/DEPLOYMENT.md`、`docs/SANDBOX.md`、`docs/AI.md`、`docs/DATABASE.md`、`docs/API.md` |

**验收**：本机不启 Docker 不影响闭环；有 Docker 的机器 `docker compose -f docker/docker-compose.yml up` 可起全套，且 `SANDBOX_MODE=remote` 时判题走容器。

### T5（P0，依赖 T1；接口契约来自 T3 文档，可与 T3 并行）—— 前端核心体验
**文件数：约 90** ｜ **依赖接口：约 60**

| 分组（可并行） | 文件 |
|---|---|
| F-a 框架与通用 | `components/layout/*`(7)、`components/common/*`(12)、`hooks/*`(9)、`stores/*`(5)、`services/*`(16)、`types/models.ts|editor.ts`、`app/error|not-found|loading.tsx` |
| F-b 首页与认证 | `app/page.tsx`、`components/course/StageTimeline.tsx`、`app/(auth)/*` |
| F-c 课程学习 | `app/courses/*`(3)、`components/course/*`(5) |
| F-d 编辑器与题库 | `app/playground/page.tsx`、`app/problems/*`(2)、`components/editor/*`(7)、`components/problem/*`(6) |
| F-e AI 导师 | `app/ai/page.tsx`、`components/ai/*`(7) |
| F-f 项目与挑战 | `app/projects/*`(2)、`app/challenges/*`(2)、`components/project/*`(5)、`components/challenge/*`(3) |

**并行提示**：F-a 先行（被所有人依赖），随后 F-b~F-f **5 路并行**。
**验收**：注册登录 → 课程 → 编辑器跑通 → 提交判题 → AI 对话（无 key 时出本地规则提示）→ 看板有数据。

### T6（P1，依赖 T3 + T5）—— 前端进阶页面、Admin、联调与打磨
**文件数：约 60** ｜ **依赖接口：约 35**

| 分组（可并行） | 文件 |
|---|---|
| F-g 进阶页 | `app/dashboard`、`bookmarks`、`mistakes`、`exams/*`、`notifications`、`search`、`settings/*`、`components/gamification/*`(6)、`components/stats/*`(4) |
| F-h Admin | `app/admin/*`(11 个页面)、`components/admin/*`(5) |
| F-i 联调打磨 | 响应式适配（PC 重编辑器 / 移动重阅读）、深色主题走查、错误态与骨架屏、导出功能联调、`tests/e2e/smoke.spec.ts` |

**验收**：7 个主导航页面 + Admin 全部可用；移动端断点（<768px）无横向滚动；深色模式无对比度事故。

### 任务依赖图

```mermaid
graph TD
    T1[T1 契约与基座] --> T2[T2 数据层与种子]
    T1 --> T4[T4 Sandbox/Docker/文档]
    T1 --> T5[T5 前端核心体验]
    T2 --> T3[T3 后端核心服务与API]
    T3 --> T6[T6 前端进阶/Admin/联调]
    T5 --> T6
    T4 -.独立并行.-> T6

    subgraph 并行组
      B1[B-a 身份] ; B2[B-b 内容] ; B3[B-c 判题] ; B4[B-d 编辑器] ; B5[B-e 游戏化] ; B6[B-f AI]
      F1[F-b 首页] ; F2[F-c 课程] ; F3[F-d 编辑器题库] ; F4[F-e AI] ; F5[F-f 项目挑战]
    end
```

### 预计规模汇总

| 任务包 | 文件数 | 新增/依赖接口数 | 并行度 | 优先级 |
|---|---|---|---|---|
| T1 契约与基座 | ~40 | 2 | 3 组（B/F/I） | P0 |
| T2 数据层 + 种子 | ~45 | 0 | 2 组 | P0 |
| T3 后端服务与 API | ~55 | ~95 | 5 路 | P0 |
| T4 Sandbox/Docker/文档 | ~20 | 3 | 3 组 | P1 |
| T5 前端核心体验 | ~90 | ~60 | 5 路 | P0 |
| T6 进阶页/Admin/联调 | ~60 | ~35 | 3 组 | P1 |
| **合计** | **~310（不含生成物）** | **~195** | | |

---

## 8. 共享知识（跨文件硬约定）

### 8.1 命名规范

| 对象 | 规范 | 示例 |
|---|---|---|
| Python 模块/包 | `snake_case` | `judge_service.py` |
| Python 类 | `PascalCase` | `SubmissionService` |
| Python 函数/变量 | `snake_case`；私有 `_x` | `build_page()` |
| 数据库表 | `snake_case` 复数 | `learning_progress` |
| 数据库列 | `snake_case`；外键 `<表单数>_id`；时间 `_at`；布尔 `is_/has_` | `problem_id`, `created_at`, `is_published` |
| 枚举 | Python `class XxxEnum(str, Enum)`，值用 `snake_case` 小写 | `Difficulty.EASY = "easy"` |
| Pydantic Schema | `<Entity>Out` / `<Entity>Create` / `<Entity>Update` / `<Entity>Brief` | `ProblemOut` |
| Service 方法 | 动词开头：`get_/list_/create_/update_/delete_/calc_/sync_` | `list_problems()` |
| TS 文件 | 组件 `PascalCase.tsx`；工具/服务 `kebab-case.ts`；hooks `useXxx.ts` | `CodeEditor.tsx` |
| TS 服务方法 | `camelCase`，与后端资源对应 | `problem.list()` |
| 路由 | `/api/<resource>`；资源复数；子资源 `/api/<resource>/{id}/<sub>` | `/api/problems/{id}/submit` |
| 前端目录 | 领域分组 `components/<domain>/` | `components/ai/` |

### 8.2 后端分层约定（写代码的硬规则）

1. **Router 只做三件事**：解析参数 → 调 Service → `success_response(data)`。禁止在 Router 内写 SQL/ORM、禁止写业务逻辑。
2. **Service 不依赖 Request/Response**：入参为 Pydantic Schema 或基础类型，出参为 Model 或 Schema；异常一律 `raise AppError(code=...)`。
3. **事务**：写操作在 Service 内用 `with session.begin()` 或 `utils.decorators.tx`；跨 Service 组合由上层 Service 统一提交。
4. **Session 获取**：端点签名 `db: Session = Depends(get_db)`，FastAPI 以线程池执行同步端点，不会阻塞事件循环。
5. **当前用户**：`current_user: User = Depends(get_current_user)`；管理员 `Depends(require_role("admin"))`；可选用 `get_current_user_optional`。
6. **响应**：所有端点返回 `ResponseModel[T]`；用 `response_model=` 声明，禁止 `Dict[str, Any]` 裸返回。
7. **分页**：`page: int = 1, page_size: int = 20 (max 100)` → `PageModel[T]{items,total,page,page_size,pages}`，统一由 `build_page()` 生成。
8. **排序**：`sort` 参数白名单（`created_at`, `-created_at`, `difficulty`, `acceptance_rate`…），禁止直接拼接用户字符串（防注入）。
9. **软删除**：查询默认 `deleted_at.is_(None)`。
10. **敏感字段**：`User` 的 `hashed_password` 永不出现在任何 Schema 中；`ai_model_configs.api_key_env` 只存变量名。

### 8.3 环境变量全清单

```ini
# ---- 应用 ----
APP_ENV=development                # development|testing|production
APP_NAME=PYTHON LAB
APP_VERSION=1.0.0
DEBUG=true
LOG_LEVEL=INFO
SECRET_KEY=change-me-in-production
API_PREFIX=/api
BACKEND_HOST=127.0.0.1
BACKEND_PORT=8000
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
REQUEST_TIMEOUT_MS=30000
UPLOAD_DIR=./data/uploads
MAX_UPLOAD_MB=10

# ---- 数据库（sqlite 前缀自动降级）----
DATABASE_URL=sqlite:///./data/pythonlab.db
# DATABASE_URL=postgresql+psycopg2://pythonlab:pythonlab@localhost:5432/pythonlab
DB_ECHO=false
DB_POOL_SIZE=10
SQLITE_WAL=true

# ---- 缓存（auto 探测）----
CACHE_BACKEND=auto                 # auto|redis|memory
REDIS_URL=redis://localhost:6379/0
CACHE_PROBE_TIMEOUT_MS=800
CACHE_DEFAULT_TTL=300

# ---- 队列（auto 探测）----
QUEUE_BACKEND=auto                 # auto|rq|inline
RQ_QUEUE_NAME=pythonlab

# ---- 认证 ----
JWT_ALGORITHM=HS256
JWT_SECRET_KEY=change-me
ACCESS_TOKEN_TTL_MIN=15
REFRESH_TOKEN_TTL_DAYS=30
PWD_HASH_SCHEME=bcrypt             # bcrypt|argon2
PWD_MIN_LENGTH=8
REGISTER_ENABLED=true
DEFAULT_USER_ROLE=user

# ---- 沙箱（auto 探测）----
SANDBOX_MODE=auto                  # auto|remote|local|stub
SANDBOX_URL=http://localhost:8081
SANDBOX_PROBE_TIMEOUT_MS=1500
SANDBOX_TIMEOUT_MS=5000
SANDBOX_MEMORY_MB=256
SANDBOX_CPU_LIMIT_MS=4000
SANDBOX_MAX_OUTPUT_BYTES=65536
SANDBOX_ALLOW_NETWORK=false
LOCAL_RUNNER_ENABLED=true          # 生产设 false
SANDBOX_ALLOWED_IMPORTS=math,json,itertools,collections,re,string,sys,random,datetime,functools,heapq,bisect,typing

# ---- AI（无 key 自动降级本地规则）----
AI_PROVIDER=deepseek
AI_MODEL=deepseek-chat
AI_BASE_URL=https://api.deepseek.com/v1
AI_API_KEY=                        # 留空即降级
AI_TEMPERATURE=0.3
AI_MAX_TOKENS=2048
AI_TIMEOUT_MS=30000
AI_OFFLINE=false
AI_RATE_LIMIT_PER_HOUR=60
AI_CACHE_TTL=600
AI_DEFAULT_MODE=standard           # beginner|standard|advanced
AI_ALLOW_FULL_ANSWER_IN_DRILL=false
DEEPSEEK_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
QWEN_API_KEY=
ZHIPU_API_KEY=

# ---- 游戏化 ----
XP_PER_LESSON=10
XP_PER_AC=20
XP_PER_PROJECT=100
LEVEL_THRESHOLDS=0,100,300,700,1500,3000,6000
DAILY_TASK_COUNT=3

# ---- 种子/管理员 ----
SEED_ON_STARTUP=true
ADMIN_EMAIL=admin@pythonlab.dev
ADMIN_PASSWORD=Admin@12345
ADMIN_USERNAME=admin

# ---- 前端（frontend/.env.local）----
NEXT_PUBLIC_API_BASE_URL=/api
NEXT_PUBLIC_SITE_NAME=PYTHON LAB
BACKEND_URL=http://127.0.0.1:8000   # 供 next.config rewrites 使用（服务端变量）
NEXT_TELEMETRY_DISABLED=1
```

### 8.4 JWT 载荷结构

```jsonc
// Access Token（TTL 15min，前端仅内存保存）
{
  "sub": "<user_id uuid>",
  "typ": "access",
  "role": "user",            // user|admin|superadmin
  "usr": "<username>",
  "nick": "<display_name>",  // 排行榜昵称也取此字段
  "ver": 1,
  "iat": 1730000000,
  "exp": 1730000900,
  "jti": "<uuid>"
}
// Refresh Token（TTL 30d，localStorage；服务端存 refresh_tokens.token_hash）
{ "sub":"<user_id>", "typ":"refresh", "ver":1, "iat":..., "exp":..., "jti":"<uuid>" }
```

- 登出：把 `jti` 放入缓存黑名单（TTL=剩余有效期），并从 `refresh_tokens` 置 `revoked=true`。
- 401 处理：前端 axios 拦截器捕获 → 用 refresh 换 access（并发请求只刷新一次，用 Promise 锁）→ 失败则清空登录态跳 `/login?redirect=...`。

### 8.5 当前用户依赖注入

```python
# app/core/deps.py
def get_db() -> Iterator[Session]: ...                 # 每请求一个 Session，finally close
def get_current_user(token: str = Depends(oauth2_scheme), db=Depends(get_db)) -> User:
    """解析 JWT → 校验 typ/黑名单 → 查 user → 校验 status == active"""
def get_current_user_optional(...) -> User | None: ...
def require_role(*roles: str) -> Callable: ...
def get_cache() -> Cache: ...        # 全局单例（启动时探测）
def get_runner() -> Runner: ...      # 全局单例
def get_ai() -> AIProvider: ...
def get_pagination(page: int = 1, page_size: int = 20) -> PageParams: ...   # page_size clamp 1..100
```

### 8.6 统一响应与错误码（错误码完整表见 `docs/API.md`）

```jsonc
// 成功
{ "success": true, "data": { ... } | [ ... ] | { "items": [], "total": 0 }, "message": "", "error": null }
// 失败
{ "success": false, "data": null, "message": "题目不存在", "error": { "code": "PROBLEM_NOT_FOUND", "details": "id=xxx" } }
```

### 8.7 种子数据约定（18 阶段课程如何结构化）

`database/seeds/courses.json` 结构（**约定即契约，seed 脚本按此解析**）：

```jsonc
{
  "version": 1,
  "courses": [
    {
      "slug": "stage-01-python-basics",
      "stage_no": 1,
      "title": "阶段 1 · Python 起步",
      "subtitle": "环境、语法骨架与第一个程序",
      "level": "beginner",
      "estimated_hours": 6,
      "topics": ["dev-env", "print", "comment"],
      "chapters": [
        {
          "slug": "ch1-setup",
          "title": "搭建环境",
          "order_index": 1,
          "lessons": [
            {
              "slug": "install-python",
              "title": "安装 Python",
              "lesson_type": "concept",
              "difficulty": "easy",
              "estimated_minutes": 20,
              "content_file": "lessons/stage-01.md#install-python",   // 正文从 md 按锚点切分
              "xp_reward": 10,
              "starter_code": "print('Hello, Python!')",
              "solution_code": "print('Hello, Python!')",
              "has_playground": true,
              "topics": ["dev-env"]
            }
          ]
        }
      ]
    }
  ]
}
```

**18 个阶段**（`stage_no` 1..18，seed 必须严格按序）：
1 Python 起步 → 2 变量与数据类型 → 3 运算符与表达式 → 4 流程控制 → 5 字符串 → 6 列表与元组 → 7 字典与集合 → 8 函数 → 9 作用域与模块 → 10 文件与异常 → 11 面向对象 → 12 迭代器生成器 → 13 函数式与高阶函数 → 14 标准库精要 → 15 正则表达式 → 16 并发与异步 → 17 测试与调试 → 18 工程化与实战。

**课时正文**：统一放 `database/seeds/lessons/stage-XX.md`，用 `## <lesson-slug>` 二级标题切分，`seed_courses.py` 按 `content_file` 的锚点定位段落，避免单个超长 JSON。
**题目分类（≥10）**：`basics / strings / lists / dicts / functions / oop / files / exceptions / regex / algorithms / data-structures / stdlib / debug / concurrency`。
**项目 10 个 Level**：1 猜数字 → 2 Todo CLI → 3 计算器 → 4 文本分析器 → 5 学生成绩管理 → 6 爬虫(离线模拟) → 7 待办 Web API → 8 数据可视化脚本 → 9 简易解释器 → 10 综合项目（博客/电商 CLI）。

### 8.8 前端共享约定

1. **请求统一走 `lib/api-client.ts`**，禁止组件内直接 `fetch`。所有返回已解包为 `data`，错误抛 `ApiError{code,message,status}`。
2. **服务端数据用 TanStack Query**：key 规范 `['resource', ...params]`，例如 `['problems', filters]`；写操作成功后 `invalidateQueries`。
3. **客户端 UI 态用 Zustand**（编辑器内容、侧边栏、命令面板）。
4. **主题**：`next-themes` + `class` 策略，CSS 变量定义在 `globals.css`；Monaco 主题随 `resolvedTheme` 切换。
5. **Markdown 渲染**统一走 `components/common/MarkdownRenderer.tsx`，**禁用 raw HTML**（`rehype-raw` 不启用），代码块用 shiki 高亮 + 复制按钮。
6. **权限**：`<AuthGuard>` 包裹需登录页面；Admin 页在 `app/admin/layout.tsx` 内校验 `role`。
7. **表单**：react-hook-form + zod，错误统一展示在字段下方。
8. **移动端**：断点 `<768px` 隐藏多级侧栏、编辑器高度降到 40vh、题库/统计改为单列卡片。

### 8.9 类图（核心服务与模型关系）

```mermaid
classDiagram
    class User {
        +str id
        +str email
        +str username
        +str hashed_password
        +str role
        +int xp
        +int level
        +int streak_days
        +datetime created_at
    }
    class Profile {
        +str user_id
        +str display_name
        +str avatar_url
        +str ai_mode
        +str theme_preference
    }
    class Course {
        +str id
        +int stage_no
        +str slug
        +str title
    }
    class Chapter { +str course_id +int order_index }
    class Lesson { +str chapter_id +str content_md +int xp_reward }
    class Topic { +str slug +str name +str parent_id }
    class Problem {
        +str id
        +str problem_type
        +str difficulty
        +str category
        +int time_limit_ms
        +int memory_limit_mb
        +float acceptance_rate
    }
    class TestCase { +str problem_id +str input +str expected_output +str comparison }
    class Submission {
        +str id +str user_id +str problem_id
        +str status +int score +int time_ms +int memory_kb +str runner
    }
    class SubmissionResult { +str submission_id +str test_case_id +bool passed +str actual_output }
    class Project { +str id +int level +str slug }
    class ProjectFile { +str project_id +str path +str content }
    class LearningProgress { +str user_id +str lesson_id +str status +int progress_percent }
    class KnowledgeMastery { +str user_id +str topic_id +float mastery_score }
    class Mistake { +str user_id +str problem_id +str error_type +bool resolved }
    class Bookmark { +str user_id +str kind +str ref_id +str code_snippet }
    class CodeHistory { +str user_id +str context_type +str code +int version_no }
    class Achievement { +str code +str condition_json +int xp_reward }
    class UserAchievement { +str user_id +str achievement_id +datetime unlocked_at }
    class Challenge { +str slug +str challenge_type +datetime start_at +datetime end_at }
    class UserChallenge { +str user_id +str challenge_id +int score +int rank }
    class AiConversation { +str user_id +str mode +str scene +str model }
    class AiMessage { +str conversation_id +str role +str kind +str content_md }
    class Notification { +str user_id +str type +bool is_read }

    class SandboxService {
        +Runner runner
        +build_runner() Runner
        +run(RunRequest) RunResponse
        +judge(Problem, code, cases) JudgeResult
    }
    class Runner {
        <<interface>>
        +execute(RunRequest) RunResponse
        +health() bool
    }
    class RemoteRunner { +str base_url }
    class LocalRunner { +execute(RunRequest) RunResponse }
    class JudgeService {
        +judge_submission(Submission) JudgeResult
        +compare(actual, expected, mode) bool
    }
    class AIProvider {
        <<interface>>
        +chat(messages) ChatResult
        +stream(messages)
    }
    class OpenAICompatibleProvider { +ProviderConfig cfg }
    class RuleBasedProvider { +chat(messages) ChatResult }
    class AIService {
        +chat(user, ChatIn) ChatOut
        +review(user, ReviewIn) ReviewOut
        +build_messages(ctx) list
    }
    class GamificationService {
        +add_xp(user, amount, reason)
        +check_achievements(user)
        +update_streak(user)
    }
    class ProgressService {
        +complete_lesson(user, lesson_id)
        +update_mastery(user, topic_id, correct)
    }
    class StatisticsService { +overview(user) +trend(user, days) +report(user) }

    User "1" --> "1" Profile
    User "1" --> "*" Submission
    User "1" --> "*" LearningProgress
    User "1" --> "*" KnowledgeMastery
    User "1" --> "*" Mistake
    User "1" --> "*" Bookmark
    User "1" --> "*" CodeHistory
    User "1" --> "*" UserAchievement
    User "1" --> "*" UserChallenge
    User "1" --> "*" AiConversation
    User "1" --> "*" Notification
    Course "1" --> "*" Chapter
    Chapter "1" --> "*" Lesson
    Lesson "*" --> "*" Topic
    Problem "1" --> "*" TestCase
    Problem "1" --> "*" Submission
    Submission "1" --> "*" SubmissionResult
    Project "1" --> "*" ProjectFile
    Achievement "1" --> "*" UserAchievement
    Challenge "1" --> "*" UserChallenge
    AiConversation "1" --> "*" AiMessage
    SandboxService --> Runner
    Runner <|.. RemoteRunner
    Runner <|.. LocalRunner
    JudgeService --> SandboxService
    AIService --> AIProvider
    AIProvider <|.. OpenAICompatibleProvider
    AIProvider <|.. RuleBasedProvider
    GamificationService --> User
    ProgressService --> LearningProgress
    ProgressService --> GamificationService
```

### 8.10 时序图（最小闭环：注册 → 学习 → 运行 → 判题 → AI）

```mermaid
sequenceDiagram
    autonumber
    participant U as 用户(浏览器)
    participant N as Next.js(3000)
    participant B as FastAPI(8000)
    participant DB as SQLite/PG
    participant R as Runner(Remote/Local)
    participant AI as AIProvider

    U->>N: 打开 /register
    N->>B: POST /api/auth/register
    B->>DB: bcrypt 哈希后插入 users+profiles
    B-->>N: {success:true,data:{access_token,refresh_token,user}}
    N-->>U: 写入内存 + localStorage，跳首页

    U->>N: 打开 /courses/stage-01-python-basics/lesson-xxx
    N->>B: GET /api/courses/{slug}
    B->>DB: 查询课程/章节/进度
    B-->>N: CourseDetail(含 progress_percent)
    N->>B: GET /api/lessons/{id}
    B->>DB: 查询课时正文 + starter_code
    B-->>N: LessonDetail

    U->>N: 在 Monaco 中点击「运行」
    N->>B: POST /api/python/run {files,stdin,timeout_ms}
    B->>R: execute(RunRequest)
    alt SANDBOX 可用
        R-->>B: RunResponse(runner=sandbox)
    else 降级
        R->>R: 临时目录 + preload 守卫 + 子进程 + 超时/截断
        R-->>B: RunResponse(runner=local, degraded=true)
    end
    B-->>N: {stdout,stderr,time_ms,memory_kb}
    N-->>U: OutputPanel 展示

    U->>N: 点击「提交」
    N->>B: POST /api/submissions {problem_id, code}
    B->>DB: 插入 submissions(status=pending)
    B->>R: judge(test_cases)
    R-->>B: results[]
    B->>DB: 写 submission_results + 更新 verdict/score
    B->>DB: 更新 knowledge_mastery / mistakes / xp_transactions
    B-->>N: SubmissionOut(status=accepted, passed=8/8)
    N-->>U: VerdictBadge + 结果面板 + XP 动画

    U->>N: 点击「问 AI」→ 选「思路提示」
    N->>B: POST /api/ai/chat {scene:hint, level:approach, context}
    alt 有 API Key
        B->>AI: chat(messages)
        AI-->>B: ChatResult
    else 无 Key / 失败
        B->>AI: RuleBasedProvider.chat(messages)
        AI-->>B: ChatResult(degraded=true)
    end
    B->>DB: 写 ai_messages + ai_usage_logs
    B-->>N: {content, degraded}
    N-->>U: 渲染提示卡片（degraded 时标注「离线助手」）
```

---

## 9. 待明确事项（已由架构师决断，工程师照此执行）

| # | 事项 | 决断 | 理由 |
|---|---|---|---|
| D1 | ORM 用同步还是异步 | **同步 SQLAlchemy + 同步端点** | SQLite/PG 一套代码无需 aiosqlite/asyncpg 差异；FastAPI 自动线程池保证不阻塞；本机最快跑通 |
| D2 | 主键类型 | **`String(36)` + `uuid4()` 字符串** | 跨 SQLite/PG 可移植，避免 PG 专有 UUID 类型 |
| D3 | Token 存储 | **Access 内存 + Refresh localStorage（Bearer）** | 前后端分离 + Next rewrites 同源；比 httpOnly Cookie 简单可靠，配合 CSP 与 React 转义缓解 XSS；后续可平滑迁移 Cookie 模式 |
| D4 | 无 Docker 时如何验证判题 | **内置 LocalRunner，并在 UI/DB 标注 `runner=local`** | 保证最小闭环；生产 `LOCAL_RUNNER_ENABLED=false` 强制容器 |
| D5 | 无 AI Key 时 | **RuleBasedProvider 本地模板**（错误分类 + 知识点提示 + 讲解模板） | 保证 AI 导师入口在离线环境可用且不报错 |
| D6 | 队列选型 | **RQ（有 Redis）/ inline BackgroundTasks（无 Redis）** | RQ 比 Celery 轻；降级路径简单 |
| D7 | 多文件项目如何执行 | **整个 files 数组落盘临时目录，指定 entry 执行** | 与 sandbox 容器方案一致，本地/远程同一协议 |
| D8 | 判题对比规则 | **默认 `trimmed`（去首尾空白 + 统一换行），支持 `exact`/`float(1e-6)`/`custom`** | 初学者题最常见问题是行尾空格，默认宽松更友好 |
| D9 | 排行榜隐私 | **仅展示 `display_name`（昵称）+ 成绩 + 用时**，绝不返回 email/id | 用户明确要求 |
| D10 | 搜索实现 | **不加全文索引表**：PG 用 `ILIKE`+`pg_trgm`，SQLite 用 `LIKE`；启动时缓存标题索引到 cache 做前缀匹配 | 控制复杂度，数据量小（<10k 条）足够 |
| D11 | 课程内容从哪来 | **仓库内 JSON + Markdown 种子**（`database/seeds/`），启动时幂等导入 | 无外部依赖，可版本化 |
| D12 | 18 阶段是否需要付费/权限分层 | **全部免费开放**（仅 Admin 区分） | 需求未提付费，避免过度设计 |
| D13 | 导出 PDF 方案 | **后端 WeasyPrint 不可用（Windows 依赖重）→ 用 `markdown` + 浏览器打印**：后端导出 Markdown/CSV/JSON，PDF 由前端 `window.print()` 打印样式生成 | 保证本机可跑通；服务器上可选装 weasyprint 走 `EXPORT_PDF_ENGINE=weasyprint` |
| D14 | 编辑器持久化 | **自动保存到 localStorage 草稿 + 手动「保存快照」写 `code_history`** | 断网也不丢代码；历史版本可控增长（每个上下文保留最近 30 版） |
| D15 | 前端是否需要 SSR 数据获取 | **仅首页/课程/题目详情用 RSC 拉取（利于 SEO），其余交互页用客户端 Query** | 平衡 SEO 与交互复杂度 |
| D16 | Windows 内存限制 | **psutil 轮询 RSS + kill**，无法严格限制；文档明确其为 best-effort | Windows 无 rlimit/cgroup，唯一可行替代 |
| D17 | 考试防作弊 | **仅服务端计时 + 题目顺序打乱 + 交卷截止**，不做锁屏/切屏检测 | 无客户端监控需求，避免过度设计 |
| D18 | 是否需要 GraphQL / WebSocket | **否，仅 REST + 轮询**（提交结果 1s 轮询，最多 30s）；通知用轮询 30s | 降低实现与运维复杂度 |

---

## 10. 本机（无 Docker）最小闭环验证清单

```powershell
# 1) 初始化（建 venv、装依赖、生成 .env、建表、导入种子）
.\scripts\setup.ps1

# 2) 启动（backend :8000 + frontend :3000）
.\scripts\dev.ps1

# 3) 冒烟
.\scripts\smoke.ps1
# 期望：health/deps = {db:sqlite, cache:memory, runner:local, ai:rule}
#       register 200 → login 200 → GET /api/courses 200（18 条）
#       POST /api/python/run → stdout 正确
#       POST /api/submissions → status=accepted
#       POST /api/ai/chat → content 非空且 degraded=true
#       GET /api/statistics/overview → 有数据

# 4) 浏览器
# http://localhost:3000 → 注册 → 课程 → 课时编辑器 → 运行 → 做题提交 → AI 导师 → 学习看板
```

**降级组合矩阵（必须全部可启动）**：

| 场景 | DATABASE_URL | Redis | Sandbox | AI Key | 期望行为 |
|---|---|---|---|---|---|
| 本机默认 | sqlite | 关 | 关 | 无 | 全部降级，闭环可用 |
| 本机 + Redis | sqlite | 开 | 关 | 无 | cache=redis, queue=rq(需 worker，否则 inline) |
| 本机 + AI | sqlite | 关 | 关 | 有 | ai=deepseek |
| 服务器 | postgres | 开 | 开 | 有 | 全量，无降级 |
| 服务器无 sandbox | postgres | 开 | 关 | 有 | runner=local（若 LOCAL_RUNNER_ENABLED=true）否则报错提示 |

---

*文档结束。字段级数据模型见 `docs/DATABASE.md`，接口契约见 `docs/API.md`。*

