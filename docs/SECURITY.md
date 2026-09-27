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
- [ ] `JWT_SECRET` 换为 ≥32 位随机值（禁用默认值）
- [ ] `AI_API_KEY` 仅存服务端环境变量；`/admin/models/{id}/test` 不回显 key
- [ ] 生产沙箱必须容器隔离（`SANDBOX_MODE=remote` 指向 hardened 容器，本机 runner 仅限开发）
- [ ] `docs_url/redoc/openapi_url` 生产已自动关闭
- [ ] 管理员初始密码 `Admin@12345` 首登后立即修改
- [ ] 数据库切换 PostgreSQL；SQLite 文件不放公网可达目录

## 4. 变更记录

- 2026-09-27：第一轮 9 项上线（`security_probe.py`）；判题域补 `_resolve_mistakes`（AC 自动解决错题，幂等）；
  第二轮 11 项上线（`security_probe_round2.py`）；新增 `SecurityHeadersMiddleware`（nosniff / DENY / Referrer-Policy）。
