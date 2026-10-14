# 安全文档（Security）

> 状态：**两轮自动化探测 + 静态审计全部通过**（2026-09-27）。
> 复跑方式：`cd backend && .venv/Scripts/python.exe scripts/security_probe.py`（第一轮 9 项）、
> `scripts/security_probe_round2.py`（第二轮 11 项）。退出码 0 = 通过。

## 1. 第一轮 · 安全红线（9 项，全 PASS）

| # | 项目 | 结论 |
|---|---|---|
| 1 | 密码加盐哈希 | bcrypt（`$2b$`），库中无明文/可逆存储 |
| 2 | 越权访问 admin | 普通用户访问 `/api/admin/*` → 403 |
| 3 | IDOR | 用户 A 读取用户 B 的提交详情 → 403/404 |
| 4 | 排行榜隐私 | 仅昵称/名次/成绩，不泄露 email、真实姓名、哈希 |
| 5 | 隐藏测试点 | `expected_output` 不出现在任何未判题响应 |
| 6 | SQL 注入 | 排序/搜索参数注入探测无异常，ORM 参数化 |
| 7 | 沙箱环境变量隔离 | 用户代码读不到 `AI_API_KEY` / `JWT_SECRET` |
| 8 | AI 密钥脱敏 | 回显 `sk-****last4`，不回传完整 key |
| 9 | health 口径 | 降级态 `provider=rule_based / model=rule-based`，配置值在 `configured_*` 字段 |

## 2. 第二轮 · XSS / CORS / CSRF（11 项，全 PASS）

### 2.1 XSS（X1–X4）

| # | 探测 | 结论 |
|---|---|---|
| X1 | 富文本字段（display_name/bio/avatar_url）注入 `<script>`/`<img onerror>`/`javascript:` | API 原文存储、JSON 通道回显——**无服务端执行面**；前端 React 默认转义 |
| X2 | 错题/收藏自由文本（title/note_md/code_snippet）注入 | 同上，JSON 响应，无 HTML 面 |
| X3 | AI 对话消息回显（content_md） | JSON 响应；前端 `react-markdown@9` **未启用 rehype-raw**，原始 HTML 不渲染 |
| X4 | 关键端点 Content-Type | 全部 `application/json`，无 `text/html` 响应面 |

**静态审计佐证**（为什么 API 存原文是安全的）：
- 唯一 `dangerouslySetInnerHTML` 在 `code-block.tsx:119`，数据源 `lib/highlight.ts` 为自研高亮器，
  **全路径 escapeHtml**（间隙、token 包裹、标识符兜底、尾部残余均转义），非 Python 语言整体转义。
- `markdown.tsx` 仅 `remarkPlugins=[remarkGfm]`，无 rehype-raw/危险 urlTransform。
- 后续新增渲染入口的红线：**任何注入 HTML 的地方必须先转义或走 react-markdown 默认管线**。

### 2.2 CORS（C1–C4）

| # | 探测 | 结论 |
|---|---|---|
| C1 | 恶意 Origin 预检 `http://evil.com` | HTTP 400，不回显 `Access-Control-Allow-Origin` |
| C2 | 白名单 Origin 预检 | 正确回显 `ACAO=http://localhost:3000` + `ACAC=true` |
| C3 | 恶意 Origin 简单请求 | 200 但**无 ACAO 头**（浏览器拦截读取） |
| C4 | 绕过尝试（子域后缀/锚点/大小写/userinfo/相邻端口） | 全部不回显 ACAO |

配置位于 `app/main.py`：`allow_origins=CORS_ORIGINS`（默认 `http://localhost:3000,http://127.0.0.1:3000` 白名单）。
**部署红线**：上线时把 `CORS_ORIGINS` 改为真实域名列表；禁止改回 `*`（与 `allow_credentials=true` 组合等于全域可携凭据跨站）。

### 2.3 CSRF（R1–R2）+ 安全响应头（H1）

| # | 探测 | 结论 |
|---|---|---|
| R1 | 无凭据状态变更（POST bookmarks/submissions） | 均 401 |
| R2 | 登录响应 Set-Cookie | **无**——token 仅存 JSON body（前端 localStorage），浏览器跨站请求**无法自动携带凭据**，CSRF 不成立 |
| H1 | 安全响应头 | `X-Content-Type-Options: nosniff`、`X-Frame-Options: DENY`、`Referrer-Policy: strict-origin-when-cross-origin` 已由 `SecurityHeadersMiddleware` 统一附加（API-only 不强制 CSP） |

## 3. 部署安全清单（上线前核对）

- [ ] `CORS_ORIGINS` 改为真实前端域名（禁 `*`）
- [ ] **`JWT_SECRET_KEY` 与 `SECRET_KEY` 各自设为 ≥32 字符的强随机值**（两者不得相同）。
      二者只要仍是默认值 / 占位符 / 长度不足，`app_env=production` 下**应用会直接拒绝启动**
      （`_startup_self_check` → `enforce_secret_policy` 抛 `RuntimeError`）。
      原因：HS256 是对称签名，密钥即权限 —— 弱密钥可被离线用来伪造 `role=superadmin` 的合法 token。
      生成方式：`python -c "import secrets; print(secrets.token_urlsafe(48))"`。
      非生产环境缺 `.env` 时会自动生成随机临时密钥并打 WARNING（重启后变化，不可用于多实例）。
- [ ] `TRUSTED_PROXIES` 按实际反代填写（IP 或 CIDR，逗号分隔）；**留空表示不信任任何代理**。
      限流取 IP 的规则：仅当 TCP 对端在名单内才读 `X-Forwarded-For`，并取**最右侧**一跳；
      否则一律用 `request.client.host`。留空可防止伪造/轮换 XFF 绕过登录与运行限流。
- [ ] `AI_API_KEY` 仅存服务端环境变量；`/admin/models/{id}/test` 不回显 key
- [ ] 生产沙箱必须容器隔离（`SANDBOX_MODE=remote` 指向 hardened 容器，本机 runner 仅限开发）
- [ ] `docs_url/redoc/openapi_url` 生产已自动关闭
- [ ] 管理员初始密码 `Admin@12345` 首登后立即修改
- [ ] 数据库切换 PostgreSQL；SQLite 文件不放公网可达目录

## 4. 变更记录

- 2026-10-14（第四轮 · 第三轮 AST 白名单的回归加固与误杀收窄）：
  ① **保留名不再跳过校验**（第三轮引入的新 P0）：`scan_source` 曾把整个
  `RESERVED_FILENAMES` 按 basename 跳过，载荷写进 `_plab_guard.py` 并以其为入口
  即可免检执行。现只有系统生成的引导文件 `__plab_boot__.py` 免检；保留名在
  schema 层（`RunRequest`，HTTP 400 `INVALID_PATH`）与路径校验层
  （`validate_relative_path`，覆盖判题 / 项目运行 / 代码快照所有入口）直接拒绝，
  执行器层仍照常 AST 校验（四层防线，回归见 `tests/test_sandbox_reserved_name.py`）。
  ② **目录逃逸拦截**：`os.chdir('..')`、`os.makedirs` / `os.mkdir`、
  `Path('../x').write_text()`、`Path('C:/...')` 及 `from os import chdir` 等
  别名导入形态，全部 `security_error`（QA 已用「工作目录外是否出现证明文件」复现）。
  ③ **误杀收窄**：放行 `sys.exit(0)` / `exit()` / `quit()`（OJ 标准写法，
  stage-16 课程正文用到；最坏只是退出子进程，而子进程本来就会被超时 kill）；
  `path_literal` 收窄为仅 `open()` / `Path()` **实参位置**检查，
  `print("path example:", "/usr", "/tmp")` 等纯展示用法放行。
  ④ **已知权衡**：`os.remove` 保留拦截（删工作目录外文件的前提是路径已逃逸，
  而逃逸路径本身被 open / Path / chdir 规则拦下）；工作目录内建目录的正当需求
  用 `pathlib.Path('sub').mkdir()`（未拦截）。
  ⑤ QA 攻击面回归脚本（47 种绕过手法 + 45 条误杀检查）移至
  `backend/scripts/security/` 并补 README；判定口径修正为「stdout 非空才算泄漏」
  （拒绝原因按契约写在 stderr）。
- 2026-09-27（第三轮 · QA 挖掘的 3 个 P0 + 2 个 P2）：
  ① 代码执行由**字符串黑名单**改为 **AST 白名单**（`app/sandbox/ast_guard.py`）：
  `__import__("os")`、`getattr(os,"system")`、`open("C:/Windows/win.ini")`、`os.listdir("C:/")`
  等绕过手法全部返回 `security_error` 且无输出；语法解析失败一律拒绝执行；
  同时保留 `os.path` / `dict.get` / `str.replace` / `list.remove` / 相对路径 `open` / `input()`
  与「多文件项目自带模块 import」的正常能力（详见 `tests/test_sandbox_security.py` 的正向用例）。
  ② 生产环境弱 JWT 密钥**拒绝启动**（见 §3）。
  ③ 限流不再无条件信任 `X-Forwarded-For`，改为可信代理白名单（见 §3）。
  ④ 测试不再以读写方式连接真实库（`tests/conftest.py` 改 `mode=ro` 只读打开）。
- 2026-09-27：第一轮 9 项上线（`security_probe.py`）；判题域补 `_resolve_mistakes`（AC 自动解决错题，幂等）；
  第二轮 11 项上线（`security_probe_round2.py`）；新增 `SecurityHeadersMiddleware`（nosniff / DENY / Referrer-Policy）。
