# PYTHON LAB —— API 契约文档

> 基础路径：`http://localhost:8000/api`（前端通过 Next.js `rewrites` 以 `/api` 同源访问）
> 认证：`Authorization: Bearer <access_token>`；刷新用 `POST /api/auth/refresh`（body 带 refresh_token）
> 全部响应均为统一结构；分页统一 `PageModel[T]`；错误统一 `error.code`。

---

## 1. 统一约定

### 1.1 响应包装

```jsonc
// 成功（单对象）
{ "success": true, "data": { "id": "...", "...": "..." }, "message": "", "error": null }
// 成功（分页）
{ "success": true, "data": { "items": [], "total": 128, "page": 1, "page_size": 20, "pages": 7 }, "message": "", "error": null }
// 失败
{ "success": false, "data": null, "message": "题目不存在", "error": { "code": "PROBLEM_NOT_FOUND", "details": "id=abc" } }
```

HTTP 状态码：业务失败统一用 **400/401/403/404/409/422/429** 对应语义；5xx 仅用于服务端异常；**校验失败返回 422**，body 仍为上述结构（`error.details` 为字段错误数组）。

### 1.2 分页参数

| 参数 | 位置 | 默认 | 约束 | 说明 |
|---|---|---|---|---|
| `page` | query | 1 | ≥1 | |
| `page_size` | query | 20 | 1..100 | 超限自动 clamp |
| `sort` | query | `-created_at` | 白名单 | `created_at/-created_at/difficulty/acceptance_rate/level/order_index/score` |

`PageModel[T]`：`{items: T[], total: int, page: int, page_size: int, pages: int}`。

### 1.3 权限标记

| 标记 | 含义 |
|---|---|
| `公开` | 无需登录 |
| `登录` | 需有效 access token |
| `本人` | 需登录且资源属于本人 |
| `管理员` | `role in (admin, superadmin)` |

### 1.4 限流

| 场景 | 限制 |
|---|---|
| 登录/注册 | 10 次 / 分钟 / IP |
| `/api/python/run` | 30 次 / 分钟 / 用户 |
| `/api/submissions` | 20 次 / 分钟 / 用户 |
| `/api/ai/*` | `AI_RATE_LIMIT_PER_HOUR`（默认 60）/ 用户 |

超限返回 `429` + `code=RATE_LIMITED`。

---

## 2. 路由清单

### 2.1 `/api/auth`（7）

| Method | Path | 权限 | 请求体 | 响应 data |
|---|---|---|---|---|
| POST | `/auth/register` | 公开 | `{email, username, password}` | `TokenPair{access_token, refresh_token, token_type, expires_in, user: UserBrief}` |
| POST | `/auth/login` | 公开 | `{account(email或username), password}` | `TokenPair` |
| POST | `/auth/refresh` | 公开 | `{refresh_token}` | `TokenPair`（刷新轮换，旧 refresh 吊销） |
| POST | `/auth/logout` | 登录 | `{refresh_token?}` | `null`（吊销当前 jti + refresh） |
| GET | `/auth/me` | 登录 | — | `UserMe{id,email,username,role,xp,level,streak_days,profile}` |
| POST | `/auth/change-password` | 登录 | `{old_password, new_password}` | `null` |
| POST | `/auth/reset-password` | 管理员 | `{user_id, new_password}` | `null` |

### 2.2 `/api/users`（8）

| Method | Path | 权限 | 请求体 | 响应 data |
|---|---|---|---|---|
| GET | `/users/me/profile` | 登录 | — | `ProfileOut` |
| PATCH | `/users/me/profile` | 本人 | `{display_name?, avatar_url?, bio?, timezone?}` | `ProfileOut` |
| POST | `/users/me/avatar` | 本人 | `multipart file`（≤2MB，jpg/png/webp） | `{avatar_url}` |
| PATCH | `/users/me/preferences` | 本人 | `{ai_mode?, learning_mode?, theme_preference?, weekly_goal_minutes?}` | `ProfileOut` |
| GET | `/users/me/overview` | 登录 | — | `{xp, level, next_level_xp, streak_days, completed_lessons, solved_problems, today_minutes, daily_tasks_done}` |
| GET | `/users/me/export` | 本人 | `?format=json|zip` | 文件流（学习数据 / 全部代码） |
| DELETE | `/users/me` | 本人 | `{password}` | `null`（软删除） |
| GET | `/users/{id}/public` | 公开 | — | `{id, display_name, avatar_url, level, xp}`（**仅昵称与等级**） |

### 2.3 `/api/courses`（7）

| Method | Path | 权限 | 说明 / 参数 | 响应 data |
|---|---|---|---|---|
| GET | `/courses` | 公开 | `?level=&stage_no=&page=&page_size=` | `Page[CourseBrief]`（含 `progress_percent` 当已登录） |
| GET | `/courses/stages` | 公开 | 18 阶段概览 | `StageOut[18]` |
| GET | `/courses/{slug}` | 公开 | — | `CourseDetail{course, chapters[], progress}` |
| POST | `/courses/{id}/enroll` | 登录 | — | `CourseEnrollmentOut` |
| GET | `/courses/{slug}/chapters` | 公开 | — | `ChapterOut[]`（含课时列表） |
| GET | `/courses/{slug}/lessons` | 公开 | — | `LessonBrief[]` |
| GET | `/courses/{slug}/lessons/{lessonId}` | 公开 | — | `LessonDetail{lesson, prev, next, progress, topics}` |

### 2.4 `/api/lessons`（6）

| Method | Path | 权限 | 请求体 | 响应 data |
|---|---|---|---|---|
| GET | `/lessons/{id}` | 公开 | — | `LessonDetail` |
| POST | `/lessons/{id}/progress` | 登录 | `{progress_percent, time_spent_seconds?, code_snapshot?}` | `LearningProgressOut` |
| POST | `/lessons/{id}/complete` | 登录 | `{time_spent_seconds?}` | `{progress, xp_earned, level_up?, unlocked_achievements[]}` |
| POST | `/lessons/{id}/quiz` | 登录 | `{answers: [{qid, value}]}` | `{correct_count, total, passed, details[]}` |
| GET | `/lessons/{id}/next` | 登录 | — | `LessonBrief | null` |
| GET | `/lessons/{id}/topics` | 公开 | — | `TopicOut[]` |

### 2.5 `/api/problems`（7）

| Method | Path | 权限 | 参数 / 请求体 | 响应 data |
|---|---|---|---|---|
| GET | `/problems` | 公开 | `?type=&difficulty=&category=&tag=&status=&keyword=&sort=&page=`（`status` = all/solved/unsolved，需登录） | `Page[ProblemBrief]` |
| GET | `/problems/filters` | 公开 | — | `{types[], difficulties[], categories[], tags[]}`（含计数） |
| GET | `/problems/random` | 公开 | `?difficulty=&category=&exclude_solved=true` | `ProblemBrief` |
| GET | `/problems/recommend` | 登录 | `?limit=10` | `ProblemBrief[]`（基于掌握度 + 偏好） |
| GET | `/problems/{id}` | 公开 | — | `ProblemDetail{problem, sample_cases[], tags[], my_status, my_last_submission_id}` |
| GET | `/problems/{id}/similar` | 公开 | `?limit=5` | `ProblemBrief[]` |
| GET | `/problems/{id}/discussion-ai` | 登录 | — | `{summary_md}`（AI 生成题解要点，无 key 时模板化） |

### 2.6 `/api/submissions`（6）

| Method | Path | 权限 | 请求体 | 响应 data |
|---|---|---|---|---|
| POST | `/submissions` | 登录 | `{problem_id, code, lesson_id?, language?}` | `SubmissionOut`（同步判题，超时 30s 转异步返回 `status=pending`） |
| GET | `/submissions` | 登录 | `?problem_id=&status=&page=` | `Page[SubmissionBrief]` |
| GET | `/submissions/{id}` | 本人/管理员 | — | `SubmissionOut`（含 `results[]` 非隐藏用例的脱敏输出） |
| GET | `/submissions/{id}/results` | 本人/管理员 | — | `SubmissionResultOut[]` |
| GET | `/submissions/{id}/status` | 本人 | — | `{status, passed_cases, total_cases}`（轮询用） |
| POST | `/submissions/{id}/rejudge` | 管理员 | — | `SubmissionOut` |

### 2.7 `/api/python`（1）

| Method | Path | 权限 | 请求体 | 响应 data |
|---|---|---|---|---|
| POST | `/python/run` | 登录（可配 `ALLOW_ANON_RUN=true` 放开） | `{files[{path,content}], entry?, stdin?, timeout_ms?, memory_limit_mb?}` | `RunResponse{status, stdout, stderr, time_ms, memory_kb, truncated, error, runner, degraded}` |

### 2.8 `/api/projects`（7）

| Method | Path | 权限 | 请求体 | 响应 data |
|---|---|---|---|---|
| GET | `/projects` | 公开 | `?level=&category=&status=&page=` | `Page[ProjectBrief]` |
| GET | `/projects/{id}` | 公开 | — | `ProjectDetail{project, files[], steps[], my?}` |
| POST | `/projects/{id}/start` | 登录 | — | `UserProjectOut`（初始化用户文件副本） |
| GET | `/projects/{id}/my` | 登录 | — | `UserProjectOut{files_json, progress_percent, current_step}` |
| PUT | `/projects/{id}/files` | 登录 | `{files: {path: content}}` | `UserProjectOut` |
| POST | `/projects/{id}/run` | 登录 | `{entry?, stdin?}` | `RunResponse` |
| POST | `/projects/{id}/submit` | 登录 | `{notes_md?}` | `{user_project, xp_earned, unlocked_achievements[]}`（校验步骤 + 运行入口文件） |

### 2.9 `/api/editor`（6）

| Method | Path | 权限 | 请求体 | 响应 data |
|---|---|---|---|---|
| POST | `/editor/save-snapshot` | 登录 | `{context_type, context_id?, file_path, code, label?, source?}` | `CodeHistoryOut` |
| GET | `/editor/history` | 登录 | `?context_type=&context_id=&page=` | `Page[CodeHistoryBrief]` |
| GET | `/editor/history/{id}` | 本人 | — | `CodeHistoryOut` |
| POST | `/editor/history/{id}/restore` | 本人 | — | `CodeHistoryOut`（复制为新版本并返回） |
| POST | `/editor/compare` | 本人 | `{left_id, right_id}` | `{diff_text, hunks[]}` |
| DELETE | `/editor/history/{id}` | 本人 | — | `null` |

### 2.10 `/api/ai`（9）

| Method | Path | 权限 | 请求体 | 响应 data |
|---|---|---|---|---|
| POST | `/ai/chat` | 登录 | `{conversation_id?, message, mode?, scene?, level?(hint/approach/partial/full/explain), context{type,id,code?,error?}, stream?}` | `ChatOut{message_id, content_md, kind, degraded, tokens, suggestions[]}` |
| POST | `/ai/review` | 登录 | `{code, language?, context_type?, context_id?, focus?}` | `ReviewOut{score, summary, issues[{severity,line,title,suggestion}], improved_code, degraded}` |
| POST | `/ai/analyze-error` | 登录 | `{code, error_message, traceback?, problem_id?}` | `ErrorAnalysisOut{error_type, cause, location, fix_steps[], minimal_example, related_topics[]}` |
| GET | `/ai/conversations` | 登录 | `?scene=&page=` | `Page[AiConversationBrief]` |
| POST | `/ai/conversations` | 登录 | `{title?, mode?, scene?, context_type?, context_id?}` | `AiConversationOut` |
| GET | `/ai/conversations/{id}` | 本人 | — | `AiConversationDetail{conversation, messages[]}` |
| DELETE | `/ai/conversations/{id}` | 本人 | — | `null` |
| POST | `/ai/conversations/{id}/archive` | 本人 | `{is_archived}` | `AiConversationOut` |
| GET | `/ai/status` | 登录 | — | `{provider, model, degraded, remaining_quota, modes[]}` |

### 2.11 `/api/progress`（6）

| Method | Path | 权限 | 请求体 | 响应 data |
|---|---|---|---|---|
| GET | `/progress` | 登录 | — | `{courses[], completed_lessons, total_lessons, overall_percent, current_stage}` |
| GET | `/progress/courses/{id}` | 登录 | — | `{course_id, percent, completed_lessons[], last_lesson_id}` |
| GET | `/progress/mastery` | 登录 | `?parent_topic_id=` | `{topics[{topic_id,name,score,level,practiced_count}], weak_topics[]}` |
| POST | `/progress/mastery/{topic_id}` | 登录 | `{correct: bool}` | `KnowledgeMasteryOut` |
| GET | `/progress/heatmap` | 登录 | `?days=180` | `{points[{date, count, minutes}]}` |
| PUT | `/progress/mode` | 登录 | `{learning_mode}` | `{learning_mode}` |

### 2.12 `/api/statistics`（7）

| Method | Path | 权限 | 参数 | 响应 data |
|---|---|---|---|---|
| GET | `/statistics/overview` | 登录 | — | `{total_minutes, solved, submissions, acceptance_rate, streak_days, xp, level, rank_percentile}` |
| GET | `/statistics/trend` | 登录 | `?days=30&metric=submissions` | `{points[{date, value}]}` |
| GET | `/statistics/categories` | 登录 | — | `{categories[{category, solved, total, score}]}` |
| GET | `/statistics/heatmap` | 登录 | `?days=180` | 同 progress/heatmap |
| GET | `/statistics/report` | 登录 | `?period=week|month` | `ReportOut{summary_md, highlights[], weak_topics[], recommendations[]}` |
| GET | `/statistics/export` | 登录 | `?type=report|submissions|code&format=md|csv|json` | 文件流（`Content-Disposition`） |
| GET | `/statistics/ranking` | 登录 | — | `{my_rank, total_users, percentile}`（仅名次，不暴露他人信息） |

### 2.13 `/api/achievements`（6）

| Method | Path | 权限 | 请求体 | 响应 data |
|---|---|---|---|---|
| GET | `/achievements` | 公开 | `?category=` | `AchievementOut[]`（含 `unlocked` 标记） |
| GET | `/achievements/mine` | 登录 | `?page=` | `Page[UserAchievementOut]` |
| POST | `/achievements/{id}/seen` | 登录 | — | `null` |
| GET | `/achievements/daily-tasks` | 登录 | `?date=` | `UserDailyTaskOut[]` |
| POST | `/achievements/daily-tasks/{id}/check` | 登录 | — | `{progress, target, completed, xp_earned}` |
| GET | `/achievements/xp` | 登录 | `?page=` | `Page[XPTransactionOut]` |

### 2.14 `/api/challenges`（7）

| Method | Path | 权限 | 请求体 | 响应 data |
|---|---|---|---|---|
| GET | `/challenges` | 公开 | `?type=&status=active|ended&page=` | `Page[ChallengeBrief]` |
| GET | `/challenges/{id}` | 公开 | — | `ChallengeDetail{challenge, problems[], my?}` |
| POST | `/challenges/{id}/join` | 登录 | — | `UserChallengeOut` |
| GET | `/challenges/{id}/problems` | 登录 | — | `ProblemBrief[]` |
| POST | `/challenges/{id}/submit` | 登录 | `{solutions: {problem_id: code}}` | `UserChallengeOut{score, passed_cases, total_time_ms, rank}` |
| GET | `/challenges/{id}/leaderboard` | 公开 | `?limit=100` | `{entries[{rank, display_name, score, total_time_ms}]}`（**仅昵称与成绩**） |
| GET | `/challenges/my` | 登录 | `?page=` | `Page[UserChallengeOut]` |

### 2.15 `/api/notifications`（6）

| Method | Path | 权限 | 请求体 | 响应 data |
|---|---|---|---|---|
| GET | `/notifications` | 登录 | `?is_read=&type=&page=` | `Page[NotificationOut]` |
| GET | `/notifications/unread-count` | 登录 | — | `{count}` |
| POST | `/notifications/{id}/read` | 本人 | — | `NotificationOut` |
| POST | `/notifications/read-all` | 登录 | `{type?}` | `{updated}` |
| DELETE | `/notifications/{id}` | 本人 | — | `null` |
| GET | `/notifications/announcements` | 公开 | `?limit=5` | `AnnouncementOut[]` |

### 2.16 `/api/search`（2）

| Method | Path | 权限 | 参数 | 响应 data |
|---|---|---|---|---|
| GET | `/search` | 公开 | `?q=&types=course,lesson,problem,project,snippet&limit=5` | `{groups[{type, items[{id,title,subtitle,url,highlight}]}], total}` |
| GET | `/search/suggest` | 公开 | `?q=` | `{suggestions[{text, type, url}]}` |

### 2.17 `/api/bookmarks`（5）

| Method | Path | 权限 | 请求体 | 响应 data |
|---|---|---|---|---|
| GET | `/bookmarks` | 登录 | `?kind=&collection=&page=` | `Page[BookmarkOut]` |
| POST | `/bookmarks` | 登录 | `{kind, ref_id?, title, code_snippet?, collection?, tags[]?}` | `BookmarkOut` |
| PATCH | `/bookmarks/{id}` | 本人 | `{title?, note?, collection?, tags[]?}` | `BookmarkOut` |
| DELETE | `/bookmarks/{id}` | 本人 | — | `null` |
| GET | `/bookmarks/collections` | 登录 | — | `{collections[{name, count}]}` |

### 2.18 `/api/mistakes`（7）

| Method | Path | 权限 | 请求体 | 响应 data |
|---|---|---|---|---|
| GET | `/mistakes` | 登录 | `?error_type=&topic_id=&resolved=&page=` | `Page[MistakeOut]` |
| POST | `/mistakes` | 登录 | `{problem_id?, submission_id?, title, user_answer?, note_md?, error_type?}` | `MistakeOut` |
| GET | `/mistakes/review-queue` | 登录 | `?limit=10` | `MistakeOut[]`（按 `next_review_at` 排序） |
| GET | `/mistakes/{id}` | 本人 | — | `MistakeOut` |
| PATCH | `/mistakes/{id}` | 本人 | `{note_md?, topic_id?}` | `MistakeOut` |
| POST | `/mistakes/{id}/resolve` | 本人 | `{resolved}` | `MistakeOut` |
| DELETE | `/mistakes/{id}` | 本人 | — | `null` |

### 2.19 `/api/code-history`（3）

| Method | Path | 权限 | 说明 |
|---|---|---|---|
| GET | `/code-history` | 登录 | `?context_type=&context_id=&page=` → `Page[CodeHistoryBrief]` |
| GET | `/code-history/{id}` | 本人 | `CodeHistoryOut` |
| DELETE | `/code-history/{id}` | 本人 | `null` |

> 保存/恢复/比较走 `/api/editor/*`（同一服务，避免重复实现）。

### 2.20 `/api/exams`（6）

| Method | Path | 权限 | 请求体 | 响应 data |
|---|---|---|---|---|
| GET | `/exams` | 登录 | `?level=` | `ExamBrief[]`（含我的最好成绩） |
| GET | `/exams/{id}` | 登录 | — | `ExamDetail{exam, questions[]不含答案}` |
| POST | `/exams/{id}/start` | 登录 | — | `ExamAttemptOut{attempt_id, deadline_at, questions[]}` |
| POST | `/exams/{id}/submit` | 登录 | `{attempt_id, answers: {problem_id: value}}` | `ExamReportOut{score, passed, per_question[], weak_topics[]}` |
| GET | `/exams/attempts` | 登录 | `?page=` | `Page[ExamAttemptBrief]` |
| GET | `/exams/attempts/{attempt_id}` | 本人 | — | `ExamReportOut` |

### 2.21 `/api/admin`（22，全部管理员）

| Method | Path | 说明 |
|---|---|---|
| GET | `/admin/dashboard` | `{users_total, active_today, submissions_today, acceptance_rate, ai_calls_today, error_rate, runner, db_flavor, cache_backend}` |
| GET/POST | `/admin/users` | 列表（搜索/筛选/分页） / 新建 |
| PATCH/DELETE | `/admin/users/{id}` | 改角色/状态/资料 / 软删除 |
| POST | `/admin/users/{id}/reset-password` | 重置密码 |
| GET/POST | `/admin/courses` | 课程 CRUD（列表 + 新建） |
| PATCH/DELETE | `/admin/courses/{id}` | 更新 / 删除 |
| POST/PATCH/DELETE | `/admin/chapters`、`/admin/chapters/{id}` | 章节 CRUD |
| POST/PATCH/DELETE | `/admin/lessons`、`/admin/lessons/{id}` | 课时 CRUD（含 `content_md`） |
| GET/POST | `/admin/problems` | 题目列表 / 新建 |
| PATCH/DELETE | `/admin/problems/{id}` | 更新 / 删除 |
| POST | `/admin/problems/import` | 批量导入（`multipart` JSON 文件，返回 `{created, updated, failed[]}`） |
| POST/PATCH/DELETE | `/admin/test-cases`、`/admin/test-cases/{id}` | 测试用例 CRUD |
| GET/POST/PATCH/DELETE | `/admin/projects`、`/admin/projects/{id}` | 项目 CRUD |
| POST/PATCH/DELETE | `/admin/project-files`、`/admin/project-files/{id}` | 项目文件 CRUD |
| GET/POST/PATCH/DELETE | `/admin/tags`、`/admin/tags/{id}` | 标签 CRUD |
| GET/POST/PATCH/DELETE | `/admin/announcements`、`/admin/announcements/{id}` | 公告 CRUD |
| GET/PUT | `/admin/ai-config` | 全局 AI 配置（provider/model/temperature/限流/提示词开关） |
| GET/POST/PATCH/DELETE | `/admin/models`、`/admin/models/{id}` | 模型配置 CRUD |
| POST | `/admin/models/{id}/test` | 连通性测试 → `{ok, latency_ms, error?}`（**不回显 key**） |
| GET | `/admin/logs/audit` | 审计日志分页 |
| GET | `/admin/logs/ai-usage` | AI 用量日志（按用户/模型聚合） |
| GET | `/admin/logs/errors` | 错误日志（按 code 聚合） |
| POST | `/admin/maintenance/rejudge` | `{problem_id? , limit?}` 批量重判（入队） |

### 2.22 健康检查（2）

| Method | Path | 权限 | 响应 |
|---|---|---|---|
| GET | `/health` | 公开 | `{status:"ok", version, env}` |
| GET | `/health/deps` | 公开 | `{db:{flavor, ok}, cache:{backend, ok}, queue:{backend}, runner:{mode, ok}, ai:{provider, degraded}}` |

### 路由总数统计

| 前缀 | 路由数 |
|---|---|
| /api/auth | 7 |
| /api/users | 8 |
| /api/courses | 7 |
| /api/lessons | 6 |
| /api/problems | 7 |
| /api/submissions | 6 |
| /api/python | 1 |
| /api/projects | 7 |
| /api/editor | 6 |
| /api/ai | 9 |
| /api/progress | 6 |
| /api/statistics | 7 |
| /api/achievements | 6 |
| /api/challenges | 7 |
| /api/notifications | 6 |
| /api/search | 2 |
| /api/bookmarks | 5 |
| /api/mistakes | 7 |
| /api/code-history | 3 |
| /api/exams | 6 |
| /api/admin | 22 |
| /api/health | 2 |
| **合计** | **135** |

---

## 3. 核心请求 / 响应 Schema

### 3.1 `TokenPair`

```jsonc
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 900,
  "user": { "id": "...", "email": "...", "username": "...", "display_name": "...", "role": "user", "level": 1, "xp": 0 }
}
```

### 3.2 `RunResponse`（`/api/python/run`、`/api/projects/{id}/run`）

```jsonc
{
  "request_id": "...", "status": "success", "exit_code": 0,
  "stdout": "6\n", "stderr": "", "truncated": false,
  "time_ms": 31, "memory_kb": 20123,
  "error": null, "runner": "local", "degraded": true
}
```

### 3.3 `SubmissionOut`

```jsonc
{
  "id": "...", "problem_id": "...", "status": "accepted",
  "score": 100, "passed_cases": 8, "total_cases": 8,
  "time_ms": 210, "memory_kb": 24576,
  "error_type": null, "error_message": null,
  "runner": "local", "created_at": "2026-09-26T12:00:00Z",
  "results": [
    { "test_case_id": "tc1", "passed": true, "time_ms": 20, "actual_output": "6", "diff": null }
  ]
}
```

### 3.4 `ChatOut`

```jsonc
{
  "conversation_id": "...", "message_id": "...",
  "role": "assistant", "kind": "approach",
  "content_md": "### 思路\n1. 先把输入转成整数 ...\n",
  "degraded": true,            // true = 本地规则助手
  "tokens_in": 320, "tokens_out": 180, "latency_ms": 1420,
  "suggestions": ["给我一个提示", "帮我看看哪里错了", "直接讲解答案"]
}
```

### 3.5 `ReviewOut`

```jsonc
{
  "score": 78,
  "summary_md": "整体结构清晰，但存在 ...",
  "issues": [
    { "severity": "warning", "line": 12, "title": "可变默认参数", "suggestion": "改用 None 作为默认值" }
  ],
  "improved_code": "def f(a, xs=None):\n    xs = xs or []\n ...",
  "degraded": false
}
```

### 3.6 `ReportOut`

```jsonc
{
  "period": "week",
  "start_date": "2026-09-20", "end_date": "2026-09-26",
  "summary_md": "本周你学习了 12 个课时 ...",
  "highlights": ["完成阶段 3 全部课时", "连续学习 5 天"],
  "metrics": { "minutes": 320, "lessons": 12, "submissions": 40, "accepted": 31, "acceptance_rate": 0.775 },
  "weak_topics": [{ "topic_id": "...", "name": "列表推导式", "score": 32 }],
  "recommendations": [{ "type": "problem", "id": "...", "title": "...", "reason": "强化列表推导式" }]
}
```

---

## 4. 错误码表

| HTTP | code | 含义 | 前端处理 |
|---|---|---|---|
| 400 | `BAD_REQUEST` | 请求参数错误 | Toast |
| 401 | `UNAUTHORIZED` | 未认证 / Token 失效 | 触发刷新，失败跳登录 |
| 401 | `TOKEN_EXPIRED` | Access 过期 | 自动 refresh |
| 401 | `INVALID_CREDENTIALS` | 账号或密码错误 | 表单错误 |
| 401 | `TOKEN_REVOKED` | 已登出/被吊销 | 跳登录 |
| 403 | `FORBIDDEN` | 权限不足 | 403 页 |
| 403 | `ACCOUNT_SUSPENDED` | 账号被禁用 | 提示联系管理员 |
| 403 | `AI_FULL_ANSWER_DISABLED` | 练习模式禁止直接给完整答案 | 提示切换模式 |
| 404 | `NOT_FOUND` | 资源不存在 | 空态 |
| 404 | `USER_NOT_FOUND` / `PROBLEM_NOT_FOUND` / `LESSON_NOT_FOUND` / `COURSE_NOT_FOUND` / `PROJECT_NOT_FOUND` / `SUBMISSION_NOT_FOUND` | 具体资源缺失 | 空态 |
| 409 | `EMAIL_EXISTS` / `USERNAME_EXISTS` | 注册冲突 | 表单错误 |
| 409 | `ALREADY_ENROLLED` / `ALREADY_JOINED` | 重复操作 | Toast |
| 422 | `VALIDATION_ERROR` | Pydantic 校验失败（`details` 为字段数组） | 字段级错误 |
| 422 | `WEAK_PASSWORD` | 密码强度不足 | 表单错误 |
| 429 | `RATE_LIMITED` | 限流 | 倒计时提示 |
| 429 | `AI_RATE_LIMITED` | AI 配额用尽 | 提示明日再来 |
| 400 | `SANDBOX_TIMEOUT` | 执行超时（TLE 用 submission 状态表达） | 输出面板提示 |
| 503 | `SANDBOX_UNAVAILABLE` | 远程沙箱不可用且未开启本地降级 | 提示维护中 |
| 400 | `SANDBOX_REJECTED` | 源码命中安全黑名单 | 提示禁用语法 |
| 400 | `OUTPUT_TOO_LARGE` | 输出超出上限被截断 | 提示截断 |
| 503 | `AI_PROVIDER_UNAVAILABLE` | 模型不可用（且无法降级） | 提示稍后重试 |
| 502 | `AI_BAD_RESPONSE` | 模型返回无法解析 | 自动降级展示 |
| 400 | `FILE_TOO_LARGE` / `INVALID_FILE_TYPE` | 上传校验 | 表单错误 |
| 400 | `INVALID_PATH` | 文件路径非法（路径遍历） | 拒绝 |
| 400 | `CHALLENGE_CLOSED` | 挑战已结束 | 提示 |
| 400 | `EXAM_EXPIRED` | 考试已超时 | 自动交卷 |
| 500 | `INTERNAL_ERROR` | 未捕获异常（记录 request_id） | 错误页 + 上报入口 |
| 500 | `DB_ERROR` | 数据库异常 | 错误页 |

> `error.details` 对 `VALIDATION_ERROR` 结构为 `[{"loc":["body","email"],"msg":"...","type":"value_error"}]`。

---

## 5. 前端调用约定

1. 所有请求经 `lib/api-client.ts`，自动注入 `Authorization`，自动解包 `data`，失败抛 `ApiError{status, code, message, details}`。
2. 401 且 `code in (TOKEN_EXPIRED, UNAUTHORIZED)` → 单飞刷新（`refreshPromise` 锁），成功后重放原请求；失败清空登录态。
3. 分页列表统一用 `useQuery(['resource', params])`，`keepPreviousData: true`；写成功 `invalidateQueries(['resource'])`。
4. 提交判题：`POST /submissions` 同步返回；若 `status === 'pending'`，以 1s 间隔轮询 `/submissions/{id}/status`，最多 30 次。
5. AI 请求携带 `AbortController`，用户可中断；`degraded=true` 时在消息卡片上显示「离线助手」徽章。
6. 文件上传走 `multipart/form-data`，最大 2MB（头像）/ 10MB（导入）。
7. 导出请求需 `responseType: 'blob'`，从 `Content-Disposition` 解析文件名。

---

## 附录 A · 实挂路由对照（自动生成）

> 生成方式：由运行中的服务 `GET /openapi.json` 统计 `paths` 与 operation；生成时间 **2026-09-27**。
> 本附录为**实挂快照**，接口契约以本文正文为准；如遇字段级差异，一律以 `GET /openapi.json` 为最终依据。
> 说明：实挂 path 数为去重后的路径模板数，op 数为 method×path 展开数；二者不等（path<op）属正常，表示同一路径承载多个方法。

### A.1 分组对照表

| 分组 | 文档规划 op | 实挂 path | 实挂 op | 差异说明 |
|---|---|---|---|---|
| `/auth` | 7 | 7 | 7 | 一致 |
| `/users` | 8 | 7 | 8 | 一致（`/users/me` 由 GET+DELETE 同路径承载） |
| `/health` | 2 | 3 | 3 | **+1** `/health/enums`（枚举字典，文档未列） |
| `/courses` | 7 | 8 | 9 | **+2** 扩展（课程内课时/报名等） |
| `/lessons` | 6 | 6 | 6 | 一致 |
| `/problems` | 7 | 7 | 7 | 一致 |
| `/submissions` | 6 | 5 | 6 | 一致（`/submissions/{id}/status` 等与主路径合并） |
| `/python` | 1 | 1 | 1 | 一致（`POST /python/run`，实现在 `editor.py` 的 `python_router`） |
| `/projects` | 7 | 7 | 7 | 一致 |
| `/editor` | 6 | 5 | 6 | 一致 |
| `/ai` | 9 | 8 | 10 | **+1** `POST /ai/chat/stream`（SSE 流式，文档未单列） |
| `/progress` | 6 | 10 | 11 | **+5** 扩展（`sessions` / `heatmap` / `dashboard` / `mastery`） |
| `/statistics` | 7 | 7 | 7 | 一致 |
| `/achievements` | 6 | 7 | 7 | **+1** `GET /achievements/badge-wall` |
| `/challenges` | 7 | 7 | 7 | 一致 |
| `/notifications` | 6 | 7 | 7 | **+1**（公告已读等） |
| `/search` | 2 | 2 | 2 | 一致 |
| `/bookmarks` | 5 | 3 | 5 | 一致（`/bookmarks` 与 `/bookmarks/{id}` 同路径多方法） |
| `/mistakes` | 7 | 5 | 8 | **+1** `GET /mistakes/topics` |
| `/code-history` | 3 | 2 | 3 | 一致 |
| `/exams` | 6 | 7 | 7 | **+1** `PUT /exams/attempts/{id}/answers` |
| `/admin` | 22 | 34 | 53 | **+31**（管理域实现了完整 CRUD：章节/课时/题库/用例/项目/标签/公告/模型/设置/日志，文档仅给概览） |
| `/recommendations` | 0（未规划） | 4 | 4 | **文档完全未列**：新增组（`advice` / `next-lesson` / `problems` / `review`） |
| **合计** | **143\*** | **159** | **191** | \*文档正文「路由总数统计」自报合计 **135**，与其表格逐项相加（**143**）不一致，差 **8**；实挂较逐项规划多 **+48** |

### A.2 文档未规划但已实现（需回填契约）

- **整组新增**：`/api/recommendations`（4 op）——文档《2.x》章节中完全没有该分组，建议补充契约条目。
- **组内新增/扩展 op**（与上表「+」项对应）：
  - `/health/enums`（+1）
  - `/courses`（+2）、`/progress`（+5）、`/ai/chat/stream`（+1）
  - `/achievements/badge-wall`（+1）、`/notifications`（+1）、`/mistakes/topics`（+1）、`/exams/attempts/{id}/answers`（+1）
  - `/admin` 由概览（22）扩展为全量 CRUD（53，+31）

### A.3 规划了但未实现（逐条核实）

经 method×path 归一化（路径参数统一为 `{}`）比对，**真正缺失的 operation = 0**。以下 16 条为**文档路径写法差异**（文档在同一行同时写了集合级与 item 级路径，实现仅提供 item 级——更符合 REST），**功能等价、已在 `/{id}` 实现**，非缺失：

| 文档写法（集合级） | 实际实现（item 级） |
|---|---|
| `PATCH /admin/{chapters,lessons,projects,project-files,tags,announcements,models,test-cases}` | `PATCH /admin/<资源>/{id}` |
| `DELETE /admin/{chapters,lessons,projects,project-files,tags,announcements,models,test-cases}` | `DELETE /admin/<资源>/{id}` |

> 结论：无需补实现；如需与文档逐字一致，建议将文档行拆分为「集合级 POST」+「item 级 PATCH/DELETE」。

### A.4 已知语义差异（记录，不在本附录处理）

- `/api/ai/status`（AI 域）在**降级态**返回 `model="deepseek-chat"`（配置值），而 `/api/health/deps` 的 `ai.model` 返回 `"rule-based"`（降级语义）。二者语义口径不同，**已派由 AI 域负责人统一**，本附录仅作记录。
- `/api/health/deps` 的 `ai` 项已补 `available` 字段（`true/false`），与 `degraded` 互补可读。

### A.5 校验方式（可复现）

```bash
# 1) 起服务后取 openapi 统计 path / operation
curl -s http://127.0.0.1:8000/openapi.json

# 2) 冲突检查：展开全部 APIRoute，按 (method, normalized_path) 去重，
#    无重复即无「同 method+path 被两处注册」的覆盖隐患。
#    本轮结论：零前缀冲突、零重复 method+path。
```
