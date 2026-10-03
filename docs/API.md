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

### 2.1 `/api/auth`（7 op / 7 path）

| Method | Path | 权限 | 请求体 | 响应 data |
|---|---|---|---|---|
| POST | `/auth/register` | 公开 | `{email, username, password}` | `TokenPair{access_token, refresh_token, token_type, expires_in, user: UserBrief}` |
| POST | `/auth/login` | 公开 | `{account(email或username), password}` | `TokenPair` |
| POST | `/auth/refresh` | 公开 | `{refresh_token}` | `TokenPair`（刷新轮换，旧 refresh 吊销） |
| POST | `/auth/logout` | 登录 | `{refresh_token?}` | `null`（吊销当前 jti + refresh） |
| GET | `/auth/me` | 登录 | — | `UserMe{id,email,username,role,xp,level,streak_days,profile}` |
| POST | `/auth/change-password` | 登录 | `{old_password, new_password}` | `null` |
| POST | `/auth/reset-password` | 管理员 | `{user_id, new_password}` | `null` |

### 2.2 `/api/users`（8 op / 7 path）

> 含实挂扩展接口 `GET /users/{id}/public`。

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

### 2.3 `/api/courses`（9 op / 8 path）

> 含实挂扩展接口 `GET /courses/mine`、`DELETE /courses/{id}/enroll`。

| Method | Path | 权限 | 说明 / 参数 | 响应 data |
|---|---|---|---|---|
| GET | `/courses` | 公开 | `?level=&stage_no=&page=&page_size=` | `Page[CourseBrief]`（含 `progress_percent` 当已登录） |
| GET | `/courses/mine` | 登录 | `?page=` | `Page[CourseBrief]`（我报名的课程） |
| GET | `/courses/stages` | 公开 | 18 阶段概览 | `StageOut[18]` |
| GET | `/courses/{slug}` | 公开 | — | `CourseDetail{course, chapters[], progress}` |
| POST | `/courses/{id}/enroll` | 登录 | — | `CourseEnrollmentOut` |
| DELETE | `/courses/{id}/enroll` | 登录 | — | `MessageOut`（退课） |
| GET | `/courses/{slug}/chapters` | 公开 | — | `ChapterOut[]`（含课时列表） |
| GET | `/courses/{slug}/lessons` | 公开 | — | `LessonBrief[]` |
| GET | `/courses/{slug}/lessons/{lessonId}` | 公开 | — | `LessonDetail{lesson, prev, next, progress, topics}` |

### 2.4 `/api/lessons`（6 op / 6 path）

| Method | Path | 权限 | 请求体 | 响应 data |
|---|---|---|---|---|
| GET | `/lessons/{id}` | 公开 | — | `LessonDetail` |
| POST | `/lessons/{id}/progress` | 登录 | `{progress_percent, time_spent_seconds?, code_snapshot?}` | `LearningProgressOut` |
| POST | `/lessons/{id}/complete` | 登录 | `{time_spent_seconds?}` | `{progress, xp_earned, level_up?, unlocked_achievements[]}` |
| POST | `/lessons/{id}/quiz` | 登录 | `{answers: [{qid, value}]}` | `{correct_count, total, passed, details[]}` |
| GET | `/lessons/{id}/next` | 登录 | — | `LessonBrief | null` |
| GET | `/lessons/{id}/topics` | 公开 | — | `TopicOut[]` |

### 2.5 `/api/problems`（7 op / 7 path）

| Method | Path | 权限 | 参数 / 请求体 | 响应 data |
|---|---|---|---|---|
| GET | `/problems` | 公开 | `?type=&difficulty=&category=&tag=&status=&keyword=&sort=&page=`（`status` = all/solved/unsolved，需登录） | `Page[ProblemBrief]` |
| GET | `/problems/filters` | 公开 | — | `{types[], difficulties[], categories[], tags[]}`（含计数） |
| GET | `/problems/random` | 公开 | `?difficulty=&category=&exclude_solved=true` | `ProblemBrief` |
| GET | `/problems/recommend` | 登录 | `?limit=10` | `ProblemBrief[]`（基于掌握度 + 偏好） |
| GET | `/problems/{id}` | 公开 | — | `ProblemDetail{problem, sample_cases[], tags[], my_status, my_last_submission_id}` |
| GET | `/problems/{id}/similar` | 公开 | `?limit=5` | `ProblemBrief[]` |
| GET | `/problems/{id}/discussion-ai` | 登录 | — | `{summary_md}`（AI 生成题解要点，无 key 时模板化） |

### 2.6 `/api/submissions`（6 op / 5 path）

| Method | Path | 权限 | 请求体 | 响应 data |
|---|---|---|---|---|
| POST | `/submissions` | 登录 | `{problem_id, code, lesson_id?, language?}` | `SubmissionOut`（同步判题，超时 30s 转异步返回 `status=pending`） |
| GET | `/submissions` | 登录 | `?problem_id=&status=&page=` | `Page[SubmissionBrief]` |
| GET | `/submissions/{id}` | 本人/管理员 | — | `SubmissionOut`（含 `results[]` 非隐藏用例的脱敏输出） |
| GET | `/submissions/{id}/results` | 本人/管理员 | — | `SubmissionResultOut[]` |
| GET | `/submissions/{id}/status` | 本人 | — | `{status, passed_cases, total_cases}`（轮询用） |
| POST | `/submissions/{id}/rejudge` | 管理员 | — | `SubmissionOut` |

### 2.7 `/api/python`（1 op / 1 path）

| Method | Path | 权限 | 请求体 | 响应 data |
|---|---|---|---|---|
| POST | `/python/run` | 登录（可配 `ALLOW_ANON_RUN=true` 放开） | `{files[{path,content}], entry?, stdin?, timeout_ms?, memory_limit_mb?}` | `RunResponse{status, stdout, stderr, time_ms, memory_kb, truncated, error, runner, degraded}` |

### 2.8 `/api/projects`（7 op / 7 path）

| Method | Path | 权限 | 请求体 | 响应 data |
|---|---|---|---|---|
| GET | `/projects` | 公开 | `?level=&category=&status=&page=` | `Page[ProjectBrief]` |
| GET | `/projects/{id}` | 公开 | — | `ProjectDetail{project, files[], steps[], my?}` |
| POST | `/projects/{id}/start` | 登录 | — | `UserProjectOut`（初始化用户文件副本） |
| GET | `/projects/{id}/my` | 登录 | — | `UserProjectOut{files_json, progress_percent, current_step}` |
| PUT | `/projects/{id}/files` | 登录 | `{files: {path: content}}` | `UserProjectOut` |
| POST | `/projects/{id}/run` | 登录 | `{entry?, stdin?}` | `RunResponse` |
| POST | `/projects/{id}/submit` | 登录 | `{notes_md?}` | `{user_project, xp_earned, unlocked_achievements[]}`（校验步骤 + 运行入口文件） |

### 2.9 `/api/editor`（6 op / 5 path）

| Method | Path | 权限 | 请求体 | 响应 data |
|---|---|---|---|---|
| POST | `/editor/save-snapshot` | 登录 | `{context_type, context_id?, file_path, code, label?, source?}` | `CodeHistoryOut` |
| GET | `/editor/history` | 登录 | `?context_type=&context_id=&page=` | `Page[CodeHistoryBrief]` |
| GET | `/editor/history/{id}` | 本人 | — | `CodeHistoryOut` |
| POST | `/editor/history/{id}/restore` | 本人 | — | `CodeHistoryOut`（复制为新版本并返回） |
| POST | `/editor/compare` | 本人 | `{left_id, right_id}` | `{diff_text, hunks[]}` |
| DELETE | `/editor/history/{id}` | 本人 | — | `null` |

### 2.10 `/api/ai`（10 op / 8 path）

> 含实挂扩展接口 `POST /ai/chat/stream`（SSE 流式）。

| Method | Path | 权限 | 请求体 | 响应 data |
|---|---|---|---|---|
| POST | `/ai/chat` | 登录 | `{conversation_id?, message, mode?, scene?, level?(hint/approach/partial/full/explain), context{type,id,code?,error?}, stream?}` | `ChatOut{message_id, content_md, kind, degraded, tokens, suggestions[]}` |
| POST | `/ai/review` | 登录 | `{code, language?, context_type?, context_id?, focus?}` | `ReviewOut{score, summary, issues[{severity,line,title,suggestion}], improved_code, degraded}` |
| POST | `/ai/analyze-error` | 登录 | `{code, error_message, traceback?, problem_id?}` | `ErrorAnalysisOut{error_type, cause, location, fix_steps[], minimal_example, related_topics[]}` |
| POST | `/ai/chat/stream` | 登录 | 同 `/ai/chat` | SSE 流式（`text/event-stream`），前端逐 token 渲染 |
| GET | `/ai/conversations` | 登录 | `?scene=&page=` | `Page[AiConversationBrief]` |
| POST | `/ai/conversations` | 登录 | `{title?, mode?, scene?, context_type?, context_id?}` | `AiConversationOut` |
| GET | `/ai/conversations/{id}` | 本人 | — | `AiConversationDetail{conversation, messages[]}` |
| DELETE | `/ai/conversations/{id}` | 本人 | — | `null` |
| POST | `/ai/conversations/{id}/archive` | 本人 | `{is_archived}` | `AiConversationOut` |
| GET | `/ai/status` | 登录 | — | `{provider, model, degraded, remaining_quota, modes[]}` |

### 2.11 `/api/progress`（11 op / 10 path）

> 含 5 条实挂扩展接口：`GET /progress/mastery/{topic_id}`、`GET /progress/dashboard`、学习会话三件套 `POST /progress/sessions`、`POST /progress/sessions/{id}/end`、`POST /progress/sessions/{id}/heartbeat`。

| Method | Path | 权限 | 请求体 | 响应 data |
|---|---|---|---|---|
| GET | `/progress` | 登录 | — | `{courses[], completed_lessons, total_lessons, overall_percent, current_stage}` |
| GET | `/progress/courses/{id}` | 登录 | — | `{course_id, percent, completed_lessons[], last_lesson_id}` |
| GET | `/progress/mastery` | 登录 | `?parent_topic_id=` | `{topics[{topic_id,name,score,level,practiced_count}], weak_topics[]}` |
| GET | `/progress/mastery/{topic_id}` | 登录 | — | `KnowledgeMasteryOut`（单知识点掌握度） |
| POST | `/progress/mastery/{topic_id}` | 登录 | `{correct: bool}` | `KnowledgeMasteryOut` |
| GET | `/progress/dashboard` | 登录 | — | `LearningDashboardOut`（学习看板聚合：今日时长/连续天数/待办任务） |
| GET | `/progress/heatmap` | 登录 | `?days=180` | `{points[{date, count, minutes}]}` |
| PUT | `/progress/mode` | 登录 | `{learning_mode}` | `{learning_mode}` |
| POST | `/progress/sessions` | 登录 | `{session_type?, learning_mode?, ref_id?}` | `LearningSessionOut`（开始学习会话） |
| POST | `/progress/sessions/{id}/end` | 登录 | — | `LearningSessionOut`（结束会话，结算时长） |
| POST | `/progress/sessions/{id}/heartbeat` | 登录 | — | `LearningSessionOut`（心跳续时，防误关页计时） |

### 2.12 `/api/statistics`（7 op / 7 path）

| Method | Path | 权限 | 参数 | 响应 data |
|---|---|---|---|---|
| GET | `/statistics/overview` | 登录 | — | `{total_minutes, solved, submissions, acceptance_rate, streak_days, xp, level, rank_percentile}` |
| GET | `/statistics/trend` | 登录 | `?days=30&metric=submissions` | `{points[{date, value}]}` |
| GET | `/statistics/categories` | 登录 | — | `{categories[{category, solved, total, score}]}` |
| GET | `/statistics/heatmap` | 登录 | `?days=180` | 同 progress/heatmap |
| GET | `/statistics/report` | 登录 | `?period=week|month` | `ReportOut{summary_md, highlights[], weak_topics[], recommendations[]}` |
| GET | `/statistics/export` | 登录 | `?type=report|submissions|code&format=md|csv|json` | 文件流（`Content-Disposition`） |
| GET | `/statistics/ranking` | 登录 | — | `{my_rank, total_users, percentile}`（仅名次，不暴露他人信息） |

### 2.13 `/api/recommendations`（4）

> 本组为**实挂扩展接口**（初版契约未规划，依据 `app/services/recommend_service.py` 落地）。4 条 op 全部为 `GET`、全部需登录，返回体不含任何用户隐私字段。

| Method | Path | 权限 | 参数 | 响应 data |
|---|---|---|---|---|
| GET | `/recommendations/advice` | 登录 | — | `RecommendationItem[]`（今日学习建议） |
| GET | `/recommendations/next-lesson` | 登录 | — | `LessonBrief \| null`（推荐继续的下一课时） |
| GET | `/recommendations/problems` | 登录 | `?limit=10`（1..50） | `ProblemBrief[]`（按通过率与难度综合排序的推题） |
| GET | `/recommendations/review` | 登录 | `?limit=10`（1..50） | `RecommendationItem[]`（到期复习 / 薄弱知识点 / 未解决错题） |

**逐条推荐依据**（数据来源全部为当前用户的学习记录，不使用他人数据）：

| 路由 | 依据的数据 | 规则 |
|---|---|---|
| `GET /recommendations/next-lesson` | **课程完成度**：最近报名课程（`course_enrollments` 末条）→ 回退到阶段 1 课程；**学习进度**：`learning_progress.status == completed` 的课时集合 | 按课程内 `order_index` 顺序取第一个未完成课时；全部完成时返回第一节课时；无课程返回 `null` |
| `GET /recommendations/problems` | **测试成绩**：`submissions` 中 `status == accepted` 的 `problem_id` 集合（排除已通过）；题库统计 `acceptance_rate` / `difficulty` | 仅取 `is_published` 题目，`NOT IN 已通过`，按 `acceptance_rate DESC, difficulty ASC` 排序（高通过率 = 相对易），`limit` 上限 50 |
| `GET /recommendations/review` | **复习计划**：`knowledge_mastery.next_review_at <= now`（到期复习）；**掌握度**：`mastery_service.weak_topics()`（低分知识点）；**错题**：`mistakes.resolved == false` | 三级瀑布填充至 `limit`：① 到期知识点（`next_review_at ASC`）→ ② 薄弱知识点（`mastery_score` 低）→ ③ 未解决错题（`created_at DESC`） |
| `GET /recommendations/advice` | **学习记录**（连续天数 `users.streak_days`）+ **课程完成度**（下一课时）+ **掌握度**（weak_topics 前 3）+ **错题**（未解决计数） | 生成可执行文案，最多 4 类：① `lesson` 继续学习下一课；② `habit` `streak_days == 0` 时提示「今天还没有学习记录」；③ `review` 最多 3 条薄弱知识点；④ `mistake` 未解决错题数 > 0 时汇总提示 |

`RecommendationItem` 结构：`{type: "lesson"|"topic"|"mistake"|"review"|"habit", id: string|null, title: string, reason: string}`。`type=habit` 时 `id` 恒为 `null`。

### 2.14 `/api/achievements`（7 op / 7 path）

> 含实挂扩展接口 `GET /achievements/badge-wall`。

| Method | Path | 权限 | 请求体 | 响应 data |
|---|---|---|---|---|
| GET | `/achievements` | 公开 | `?category=` | `AchievementOut[]`（含 `unlocked` 标记） |
| GET | `/achievements/badge-wall` | 登录 | — | `BadgeWallOut{total, unlocked, categories[], achievements[]}`（徽章墙） |
| GET | `/achievements/mine` | 登录 | `?page=` | `Page[UserAchievementOut]` |
| POST | `/achievements/{id}/seen` | 登录 | — | `null` |
| GET | `/achievements/daily-tasks` | 登录 | `?date=` | `UserDailyTaskOut[]` |
| POST | `/achievements/daily-tasks/{id}/check` | 登录 | — | `{progress, target, completed, xp_earned}` |
| GET | `/achievements/xp` | 登录 | `?page=` | `Page[XPTransactionOut]` |

### 2.15 `/api/challenges`（7 op / 7 path）

| Method | Path | 权限 | 请求体 | 响应 data |
|---|---|---|---|---|
| GET | `/challenges` | 公开 | `?type=&status=active|ended&page=` | `Page[ChallengeBrief]` |
| GET | `/challenges/{id}` | 公开 | — | `ChallengeDetail{challenge, problems[], my?}` |
| POST | `/challenges/{id}/join` | 登录 | — | `UserChallengeOut` |
| GET | `/challenges/{id}/problems` | 登录 | — | `ProblemBrief[]` |
| POST | `/challenges/{id}/submit` | 登录 | `{solutions: {problem_id: code}}` | `UserChallengeOut{score, passed_cases, total_time_ms, rank}` |
| GET | `/challenges/{id}/leaderboard` | 公开 | `?limit=100` | `{entries[{rank, display_name, score, total_time_ms}]}`（**仅昵称与成绩**） |
| GET | `/challenges/my` | 登录 | `?page=` | `Page[UserChallengeOut]` |

### 2.16 `/api/notifications`（7 op / 7 path）

> 含实挂扩展接口 `GET /notifications/announcements/{id}`（公告详情）。

| Method | Path | 权限 | 请求体 | 响应 data |
|---|---|---|---|---|
| GET | `/notifications` | 登录 | `?is_read=&type=&page=` | `Page[NotificationOut]` |
| GET | `/notifications/unread-count` | 登录 | — | `{count}` |
| POST | `/notifications/{id}/read` | 本人 | — | `NotificationOut` |
| POST | `/notifications/read-all` | 登录 | `{type?}` | `{updated}` |
| DELETE | `/notifications/{id}` | 本人 | — | `null` |
| GET | `/notifications/announcements` | 公开 | `?limit=5` | `AnnouncementOut[]` |
| GET | `/notifications/announcements/{id}` | 公开 | — | `AnnouncementOut`（公告详情） |

### 2.17 `/api/search`（2 op / 2 path）

| Method | Path | 权限 | 参数 | 响应 data |
|---|---|---|---|---|
| GET | `/search` | 公开 | `?q=&types=course,lesson,problem,project,snippet&limit=5` | `{groups[{type, items[{id,title,subtitle,url,highlight}]}], total}` |
| GET | `/search/suggest` | 公开 | `?q=` | `{suggestions[{text, type, url}]}` |

### 2.18 `/api/bookmarks`（5 op / 3 path）

| Method | Path | 权限 | 请求体 | 响应 data |
|---|---|---|---|---|
| GET | `/bookmarks` | 登录 | `?kind=&collection=&page=` | `Page[BookmarkOut]` |
| POST | `/bookmarks` | 登录 | `{kind, ref_id?, title, code_snippet?, collection?, tags[]?}` | `BookmarkOut` |
| PATCH | `/bookmarks/{id}` | 本人 | `{title?, note?, collection?, tags[]?}` | `BookmarkOut` |
| DELETE | `/bookmarks/{id}` | 本人 | — | `null` |
| GET | `/bookmarks/collections` | 登录 | — | `{collections[{name, count}]}` |

### 2.19 `/api/mistakes`（8 op / 5 path）

> 含实挂扩展接口 `GET /mistakes/topics`（高频错误知识点统计）。

| Method | Path | 权限 | 请求体 | 响应 data |
|---|---|---|---|---|
| GET | `/mistakes` | 登录 | `?error_type=&topic_id=&resolved=&page=` | `Page[MistakeOut]` |
| POST | `/mistakes` | 登录 | `{problem_id?, submission_id?, title, user_answer?, note_md?, error_type?}` | `MistakeOut` |
| GET | `/mistakes/review-queue` | 登录 | `?limit=10` | `MistakeOut[]`（按 `next_review_at` 排序） |
| GET | `/mistakes/topics` | 登录 | — | `[{topic, count, ...}]`（高频错误知识点统计） |
| GET | `/mistakes/{id}` | 本人 | — | `MistakeOut` |
| PATCH | `/mistakes/{id}` | 本人 | `{note_md?, topic_id?}` | `MistakeOut` |
| POST | `/mistakes/{id}/resolve` | 本人 | `{resolved}` | `MistakeOut` |
| DELETE | `/mistakes/{id}` | 本人 | — | `null` |

### 2.20 `/api/code-history`（3 op / 2 path）

| Method | Path | 权限 | 说明 |
|---|---|---|---|
| GET | `/code-history` | 登录 | `?context_type=&context_id=&page=` → `Page[CodeHistoryBrief]` |
| GET | `/code-history/{id}` | 本人 | `CodeHistoryOut` |
| DELETE | `/code-history/{id}` | 本人 | `null` |

> 保存/恢复/比较走 `/api/editor/*`（同一服务，避免重复实现）。

### 2.21 `/api/exams`（7 op / 7 path）

> 含实挂扩展接口 `PUT /exams/attempts/{attempt_id}/answers`（考试中自动暂存）。

| Method | Path | 权限 | 请求体 | 响应 data |
|---|---|---|---|---|
| GET | `/exams` | 登录 | `?level=` | `ExamBrief[]`（含我的最好成绩） |
| GET | `/exams/{id}` | 登录 | — | `ExamDetail{exam, questions[]不含答案}` |
| POST | `/exams/{id}/start` | 登录 | — | `ExamAttemptOut{attempt_id, deadline_at, questions[]}` |
| POST | `/exams/{id}/submit` | 登录 | `{attempt_id, answers: {problem_id: value}}` | `ExamReportOut{score, passed, per_question[], weak_topics[]}` |
| PUT | `/exams/attempts/{attempt_id}/answers` | 本人 | 同 `ExamSubmitRequest` | `ExamSaveOut{attempt_id, saved, remaining_seconds, status}`（考试中自动暂存，防中断丢失） |
| GET | `/exams/attempts` | 登录 | `?page=` | `Page[ExamAttemptBrief]` |
| GET | `/exams/attempts/{attempt_id}` | 本人 | — | `ExamReportOut` |

### 2.22 `/api/admin`（53 op / 34 path，全部管理员）

> **实现形式（重要）**：写操作一律为 **item 级** `PATCH|DELETE /admin/<resource>/{id}`；`POST /admin/<resource>` 为集合级「新建」。**不存在** `PATCH|DELETE /admin/<resource>`（无 id 的集合级更新/删除）。
> 集合级仅提供 `GET`（列表）与 `POST`（新建）。每行一个 `method × path`，与实挂 `openapi.json` 逐条对应（53 行 = 53 op）。
> 路径参数名以实现为准：`{user_id}` `{course_id}` `{chapter_id}` `{lesson_id}` `{problem_id}` `{case_id}` `{project_id}` `{file_id}` `{tag_id}` `{announcement_id}` `{model_id}`。

**资源级路由**

| Method | Path | 说明 |
|---|---|---|
| GET | `/admin/dashboard` | 仪表盘：`{users_total, active_today, submissions_today, acceptance_rate, ai_calls_today, error_rate, runner, db_flavor, cache_backend}` |
| GET | `/admin/users` | 用户列表（搜索/筛选/分页，集合级） |
| POST | `/admin/users` | 新建用户（集合级） |
| PATCH | `/admin/users/{user_id}` | 改角色/状态/资料（item 级） |
| DELETE | `/admin/users/{user_id}` | 软删除（item 级） |
| POST | `/admin/users/{user_id}/reset-password` | 重置密码（item 级子资源） |
| GET | `/admin/courses` | 课程列表（集合级） |
| POST | `/admin/courses` | 新建课程（集合级） |
| PATCH | `/admin/courses/{course_id}` | 更新课程（item 级） |
| DELETE | `/admin/courses/{course_id}` | 删除课程（item 级） |
| POST | `/admin/chapters` | 新建章节（集合级，**无集合级 GET/PUT/DELETE**） |
| PATCH | `/admin/chapters/{chapter_id}` | 更新章节（item 级） |
| DELETE | `/admin/chapters/{chapter_id}` | 删除章节（item 级） |
| POST | `/admin/lessons` | 新建课时，含 `content_md`（集合级，**无集合级 GET**） |
| PATCH | `/admin/lessons/{lesson_id}` | 更新课时（item 级） |
| DELETE | `/admin/lessons/{lesson_id}` | 删除课时（item 级） |
| GET | `/admin/problems` | 题目列表（集合级） |
| POST | `/admin/problems` | 新建题目（集合级） |
| PATCH | `/admin/problems/{problem_id}` | 更新题目（item 级） |
| DELETE | `/admin/problems/{problem_id}` | 删除题目（item 级） |
| POST | `/admin/problems/import` | 批量导入题目（`multipart` JSON → `{created, updated, failed[]}`） |
| POST | `/admin/test-cases` | 新建测试用例（集合级，**无集合级 GET**） |
| PATCH | `/admin/test-cases/{case_id}` | 更新测试用例（item 级） |
| DELETE | `/admin/test-cases/{case_id}` | 删除测试用例（item 级） |
| GET | `/admin/projects` | 项目列表（集合级） |
| POST | `/admin/projects` | 新建项目（集合级） |
| PATCH | `/admin/projects/{project_id}` | 更新项目（item 级） |
| DELETE | `/admin/projects/{project_id}` | 删除项目（item 级） |
| POST | `/admin/project-files` | 新建项目文件（集合级，**无集合级 GET**） |
| PATCH | `/admin/project-files/{file_id}` | 更新项目文件（item 级） |
| DELETE | `/admin/project-files/{file_id}` | 删除项目文件（item 级） |
| GET | `/admin/tags` | 标签列表（集合级） |
| POST | `/admin/tags` | 新建标签（集合级） |
| PATCH | `/admin/tags/{tag_id}` | 更新标签（item 级） |
| DELETE | `/admin/tags/{tag_id}` | 删除标签（item 级） |
| GET | `/admin/announcements` | 公告列表（集合级） |
| POST | `/admin/announcements` | 新建公告（集合级） |
| PATCH | `/admin/announcements/{announcement_id}` | 更新/发布/下线公告（item 级） |
| DELETE | `/admin/announcements/{announcement_id}` | 删除公告（item 级） |

**配置 / 模型 / 日志 / 运维路由**

| Method | Path | 说明 |
|---|---|---|
| GET | `/admin/ai-config` | 全局 AI 配置（provider/model/temperature/限流/提示词开关） |
| PUT | `/admin/ai-config` | 更新全局 AI 配置（**单例资源，PUT 作用于固定 key，无 id**） |
| GET | `/admin/models` | 模型配置列表（集合级） |
| POST | `/admin/models` | 新建模型配置（集合级） |
| PATCH | `/admin/models/{model_id}` | 更新模型配置（item 级） |
| DELETE | `/admin/models/{model_id}` | 删除模型配置（item 级） |
| POST | `/admin/models/{model_id}/test` | 连通性测试 → `{ok, latency_ms, error?}`（**不回显 key**） |
| GET | `/admin/settings` | 系统设置列表 → `SystemSettingOut[]` |
| PUT | `/admin/settings/{key}` | 写入单项系统设置（**item 级，参数为业务 key 而非 id**） |
| GET | `/admin/logs/audit` | 审计日志分页 |
| GET | `/admin/logs/ai-usage` | AI 用量日志（按用户/模型聚合） |
| GET | `/admin/logs/errors` | 错误日志（按 code 聚合） |
| GET | `/admin/logs/sessions` | 学习会话概览 → `SessionOverviewOut` |
| POST | `/admin/maintenance/rejudge` | `{problem_id?, limit?}` 批量重判（入队） |

**未实现 / 待定（文档与实挂均无，勿误用）**

| 设想中的路由 | 状态 | 说明 |
|---|---|---|
| `PATCH\|DELETE /admin/<resource>`（无 id 批量更新/删除） | **未实现** | 无需支持：批量操作请由前端并发调用 item 级接口 |
| `GET /admin/chapters`、`GET /admin/lessons`、`GET /admin/test-cases`、`GET /admin/project-files` | **未实现** | 列表随父资源详情返回（`GET /admin/courses/{id}` 风格）或走前台 `/api/*` 只读接口 |
| 集合级 `PUT /admin/<resource>` 整体替换 | **未实现** | 更新一律 item 级 `PATCH` |

### 2.23 `/api/health`（3 op / 3 path）

> 含实挂扩展接口 `GET /health/enums`（枚举字典，前后端一致性校验用）。

| Method | Path | 权限 | 响应 |
|---|---|---|---|
| GET | `/health` | 公开 | `{status:"ok", version, env}` |
| GET | `/health/deps` | 公开 | `{db:{flavor, ok}, cache:{backend, ok}, queue:{backend}, runner:{mode, ok}, ai:{provider, model, degraded, available}}` |
| GET | `/health/enums` | 公开 | 枚举字典（题型/难度/状态等，前后端一致性校验用） |

### 路由总数统计

> **口径**：以实挂 `GET /openapi.json` 为唯一事实来源，快照时间 **2026-09-27**。本文 §2 各分节标题的 `N op / M path`、下方统计表的 `op`/`path` 列、统计表合计三者**已逐项核对一致**；`path < op` 属正常（同一路径承载多个方法，如 `GET+DELETE /users/me`、`GET+POST /bookmarks`）。

| 前缀 | path | op | 备注 |
|---|---|---|---|
| /api/auth | 7 | 7 | |
| /api/users | 7 | 8 | 含扩展 `/users/{id}/public` |
| /api/health | 3 | 3 | 含扩展 `/health/enums` |
| /api/courses | 8 | 9 | 含扩展 `/courses/mine`、`DELETE /courses/{id}/enroll` |
| /api/lessons | 6 | 6 | |
| /api/progress | 10 | 11 | 含 5 条扩展（单知识点掌握度 / dashboard / 会话三件套） |
| /api/search | 2 | 2 | |
| /api/recommendations | 4 | 4 | **整组为实挂扩展接口** |
| /api/statistics | 7 | 7 | |
| /api/achievements | 7 | 7 | 含扩展 `/achievements/badge-wall` |
| /api/challenges | 7 | 7 | |
| /api/exams | 7 | 7 | 含扩展 `PUT /exams/attempts/{id}/answers` |
| /api/notifications | 7 | 7 | 含扩展 `/notifications/announcements/{id}` |
| /api/admin | 34 | 53 | 写操作全部 item 级 `/{id}`，详见 §2.22 |
| /api/problems | 7 | 7 | |
| /api/submissions | 5 | 6 | |
| /api/projects | 7 | 7 | |
| /api/editor | 5 | 6 | |
| /api/python | 1 | 1 | 代码运行 |
| /api/ai | 8 | 10 | 含扩展 `POST /ai/chat/stream` |
| /api/bookmarks | 3 | 5 | |
| /api/mistakes | 5 | 8 | 含扩展 `/mistakes/topics` |
| /api/code-history | 2 | 3 | |
| **合计** | **159** | **191** | **正文 §2 表格行数 = 191，与实挂 op 双向零差异** |

**数字不一致问题已闭环（历史记录）**：初版正文「路由总数统计」自报合计 **135**，而其表格逐项相加为 **143**（差 8）。根因是初版遗漏 `/api/recommendations` 整组 4 条、admin 集合级/item 级口径混乱，以及 courses/ai/progress/achievements/notifications/mistakes/exams/health 的实挂扩展接口未回填。现已按实挂逐条回填，**正文 = 统计表 = 实挂 = 191 op / 159 path**。核对方法：

```powershell
cd backend
.venv\Scripts\python.exe -c "import sys;sys.path.insert(0,'.');from app.main import app;s=app.openapi();print(len(s['paths']),sum(len([m for m in v if m!='parameters']) for v in s['paths'].values()))"
# 期望输出：159 191
```

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

> **2026-09-27 更新**：正文 §2 已回填全部实挂路由（159 path / 191 op），下表「文档规划 op」列为回填前快照，供追溯。

| 分组 | 文档规划 op | 实挂 path | 实挂 op | 差异说明 |
|---|---|---|---|---|
| `/auth` | 7 | 7 | 7 | 一致 |
| `/users` | 8 | 7 | 8 | 一致（`/users/me` 由 GET+DELETE 同路径承载） |
| `/health` | 2 | 3 | 3 | 已回填 `/health/enums`（§2.23） |
| `/courses` | 7 | 8 | 9 | 已回填 `/courses/mine`、`DELETE /enroll`（§2.3） |
| `/lessons` | 6 | 6 | 6 | 一致 |
| `/problems` | 7 | 7 | 7 | 一致 |
| `/submissions` | 6 | 5 | 6 | 一致（`/submissions/{id}/status` 等与主路径合并） |
| `/python` | 1 | 1 | 1 | 一致（`POST /python/run`，实现在 `editor.py` 的 `python_router`） |
| `/projects` | 7 | 7 | 7 | 一致 |
| `/editor` | 6 | 5 | 6 | 一致 |
| `/ai` | 9 | 8 | 10 | 已回填 `POST /ai/chat/stream`（SSE，§2.10） |
| `/progress` | 6 | 10 | 11 | 已回填 `dashboard` / `sessions` 系列（§2.11） |
| `/statistics` | 7 | 7 | 7 | 一致 |
| `/recommendations` | 0（未规划） | 4 | 4 | 已回填整组（§2.13） |
| `/achievements` | 6 | 7 | 7 | 已回填 `badge-wall`（§2.14） |
| `/challenges` | 7 | 7 | 7 | 一致 |
| `/notifications` | 6 | 7 | 7 | 已回填公告详情（§2.16） |
| `/search` | 2 | 2 | 2 | 一致 |
| `/bookmarks` | 5 | 3 | 5 | 一致（`/bookmarks` 与 `/bookmarks/{id}` 同路径多方法） |
| `/mistakes` | 7 | 5 | 8 | 已回填 `topics`（§2.19） |
| `/code-history` | 3 | 2 | 3 | 一致 |
| `/exams` | 6 | 7 | 7 | 已回填 `PUT /attempts/{id}/answers`（§2.21） |
| `/admin` | 22 | 34 | 53 | 已回填全量 CRUD + `settings` + `logs/sessions`（§2.22，拆行书写） |
| **合计** | **143\*** | **159** | **191** | \*回填前正文自报 135 与其表格逐项和 143 不一致；**回填后正文 = 实挂 = 191 op** |

### A.2 文档未规划但已实现 → **已回填（2026-09-27）**

以下差异已全部回填进正文 §2，正文与实挂一致：

- **整组新增**：`/api/recommendations`（4 op）→ §2.13。
- **组内新增/扩展 op**：
  - `/health/enums` → §2.23
  - `/courses/mine`、`DELETE /courses/{id}/enroll` → §2.3
  - `/progress/dashboard`、`/progress/sessions`（start/end/heartbeat）、`GET /mastery/{topic_id}` → §2.11
  - `/ai/chat/stream` → §2.10
  - `/achievements/badge-wall` → §2.14
  - `/notifications/announcements/{id}` → §2.16
  - `/mistakes/topics` → §2.19
  - `/exams/attempts/{id}/answers`（PUT）→ §2.21
  - `/admin` 全量 CRUD + `/admin/settings` + `/admin/logs/sessions` → §2.22

### A.3 规划了但未实现 → **已修正（2026-09-27）**

经 method×path 归一化比对，**真正缺失的 operation = 0**。原 16 条「文档集合级写法 vs 实现 item 级」的路径书写差异，已通过正文 §2.22 拆行（集合级 GET/POST 与 item 级 PATCH/DELETE 分行）消除。

### A.4 已知语义差异 → **已统一（2026-09-27）**

- ~~`/api/ai/status` 降级态返回配置 model 的矛盾~~ **已修复**：降级态 `provider = model = "rule-based"`；真实配置值移至 `configured_provider` / `configured_model` 字段，两个口径不再混淆。
- `/api/health/deps` 的 `ai` 项已含 `available` 字段（`true/false`），与 `degraded` 互补可读（§2.23 已同步）。

### A.5 校验方式（可复现）

```bash
# 1) 起服务后取 openapi 统计 path / operation
curl -s http://127.0.0.1:8000/openapi.json

# 2) 冲突检查：展开全部 APIRoute，按 (method, normalized_path) 去重，
#    无重复即无「同 method+path 被两处注册」的覆盖隐患。
#    本轮结论：零前缀冲突、零重复 method+path。
```
