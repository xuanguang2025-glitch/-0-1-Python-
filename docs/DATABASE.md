# PYTHON LAB —— 数据库模型设计（字段级）

> 共 **40 张表**。类型列中的 `CHAR(36)` 表示 `String(36)`（存 `uuid4()` 字符串，跨 SQLite/PostgreSQL 可移植）；`JSON` 表示 `sa.JSON`（SQLite 落 TEXT）；`DATETIME` 表示 `DateTime(timezone=True)`，值一律 UTC。
> 命名约定：主键 `id`；外键 `<单数>_id`；时间 `_at`；布尔 `is_/has_`。
> 通用列：`created_at DATETIME NOT NULL DEFAULT now()`、`updated_at DATETIME NOT NULL DEFAULT now()`（onupdate=now）。下表中若未列出 `created_at/updated_at`，表示该表不需要。

---

## 0. 模型文件划分

| 文件 | 表 | 行数预算 |
|---|---|---|
| `app/models/mixins.py` | UUIDPkMixin / TimestampMixin / SoftDeleteMixin | ≤60 |
| `app/models/enums.py` | 全部枚举（见 §7） | ≤200 |
| `app/models/user.py` | users, profiles, refresh_tokens | ≤180 |
| `app/models/course.py` | courses, chapters, lessons, topics, lesson_topics, course_enrollments | ≤220 |
| `app/models/problem.py` | problems, test_cases, tags, problem_tags | ≤220 |
| `app/models/submission.py` | submissions, submission_results | ≤180 |
| `app/models/project.py` | projects, project_files, user_projects | ≤160 |
| `app/models/learning.py` | learning_progress, knowledge_mastery, mistakes, bookmarks, code_history, learning_sessions | ≤260 |
| `app/models/gamification.py` | achievements, user_achievements, daily_tasks, user_daily_tasks, xp_transactions | ≤200 |
| `app/models/ai.py` | ai_conversations, ai_messages, ai_model_configs, ai_usage_logs | ≤180 |
| `app/models/challenge.py` | challenges, user_challenges | ≤120 |
| `app/models/exam.py` | exams, exam_attempts | ≤120 |
| `app/models/notification.py` | notifications, announcements | ≤120 |
| `app/models/system.py` | audit_logs, system_settings | ≤100 |

**关系注册**：所有 `relationship()` 均指定 `foreign_keys` 与 `back_populates`；一对多父侧用 `Mapped[list["Child"]] = relationship(back_populates="parent", cascade="all, delete-orphan")`。多对多一律用显式关联表（便于附加列）。

---

## 1. 身份与用户

### 1.1 `users`

| 字段 | 类型 | 可空 | 默认 | 索引/约束 | 说明 |
|---|---|---|---|---|---|
| id | CHAR(36) | N | uuid4 | PK | |
| email | VARCHAR(255) | N | — | UNIQUE, idx | 登录用，小写存储 |
| username | VARCHAR(50) | N | — | UNIQUE, idx | 3-20 位字母数字下划线 |
| hashed_password | VARCHAR(255) | N | — | — | bcrypt/argon2，**永不出现在任何 Schema** |
| role | VARCHAR(20) | N | `user` | idx | user/admin/superadmin |
| status | VARCHAR(20) | N | `active` | idx | active/suspended/deleted |
| is_verified | BOOLEAN | N | false | — | 邮箱验证（本机可默认 true） |
| xp | INTEGER | N | 0 | idx | 经验值 |
| level | INTEGER | N | 1 | idx | 1-7，由 XP 阈值推导 |
| streak_days | INTEGER | N | 0 | — | 连续学习天数 |
| max_streak_days | INTEGER | N | 0 | — | 历史最长 |
| last_active_at | DATETIME | Y | NULL | — | |
| last_login_at | DATETIME | Y | NULL | — | |
| login_count | INTEGER | N | 0 | — | |
| locale | VARCHAR(10) | N | `zh-CN` | — | |
| deleted_at | DATETIME | Y | NULL | — | 软删除 |
| created_at / updated_at | DATETIME | N | now() | — | |

### 1.2 `profiles`

| 字段 | 类型 | 可空 | 默认 | 索引/约束 | 说明 |
|---|---|---|---|---|---|
| id | CHAR(36) | N | uuid4 | PK | |
| user_id | CHAR(36) | N | — | FK users.id, UNIQUE, idx | 1:1 |
| display_name | VARCHAR(50) | N | `''` | idx | **昵称，排行榜唯一展示名** |
| avatar_url | VARCHAR(512) | Y | NULL | — | 本地 `/uploads/...` 或外链 |
| bio | VARCHAR(500) | Y | NULL | — | |
| timezone | VARCHAR(50) | N | `UTC` | — | |
| theme_preference | VARCHAR(10) | N | `system` | — | light/dark/system |
| ai_mode | VARCHAR(20) | N | `standard` | — | beginner/standard/advanced |
| learning_mode | VARCHAR(20) | N | `system` | — | free/system/exam/drill/project/challenge/ai |
| public_profile | BOOLEAN | N | true | — | |
| weekly_goal_minutes | INTEGER | N | 300 | — | |
| created_at / updated_at | DATETIME | N | now() | — | |

### 1.3 `refresh_tokens`

| 字段 | 类型 | 可空 | 默认 | 索引/约束 | 说明 |
|---|---|---|---|---|---|
| id | CHAR(36) | N | uuid4 | PK | |
| user_id | CHAR(36) | N | — | FK users.id, idx | |
| jti | CHAR(36) | N | — | UNIQUE, idx | JWT ID，用于吊销 |
| token_hash | VARCHAR(64) | N | — | UNIQUE, idx | sha256(token) |
| user_agent | VARCHAR(255) | Y | NULL | — | |
| ip | VARCHAR(45) | Y | NULL | — | |
| expires_at | DATETIME | N | — | idx | |
| revoked | BOOLEAN | N | false | — | |
| revoked_at | DATETIME | Y | NULL | — | |
| created_at | DATETIME | N | now() | idx | |

---

## 2. 课程内容

### 2.1 `courses`（18 阶段）

| 字段 | 类型 | 可空 | 默认 | 索引/约束 | 说明 |
|---|---|---|---|---|---|
| id | CHAR(36) | N | uuid4 | PK | |
| slug | VARCHAR(120) | N | — | UNIQUE, idx | `stage-01-python-basics` |
| stage_no | INTEGER | N | — | UNIQUE, idx | 1..18 |
| title | VARCHAR(200) | N | — | — | 阶段 1 · Python 起步 |
| subtitle | VARCHAR(300) | Y | NULL | — | |
| description_md | TEXT | Y | NULL | — | |
| level | VARCHAR(20) | N | `beginner` | idx | beginner/intermediate/advanced |
| icon | VARCHAR(50) | Y | NULL | — | lucide 图标名 |
| cover_url | VARCHAR(512) | Y | NULL | — | |
| estimated_hours | INTEGER | N | 0 | — | |
| lesson_count | INTEGER | N | 0 | — | 冗余，seed 时计算 |
| order_index | INTEGER | N | 0 | idx | 同 stage_no |
| is_published | BOOLEAN | N | true | idx | |
| created_at / updated_at | DATETIME | N | now() | — | |

### 2.2 `chapters`

| 字段 | 类型 | 可空 | 默认 | 索引/约束 | 说明 |
|---|---|---|---|---|---|
| id | CHAR(36) | N | uuid4 | PK | |
| course_id | CHAR(36) | N | — | FK courses.id ON DELETE CASCADE, idx | |
| slug | VARCHAR(120) | N | — | UNIQUE(course_id, slug) | |
| title | VARCHAR(200) | N | — | — | |
| summary_md | TEXT | Y | NULL | — | |
| order_index | INTEGER | N | 0 | idx | |
| lesson_count | INTEGER | N | 0 | — | |
| is_published | BOOLEAN | N | true | — | |
| created_at / updated_at | DATETIME | N | now() | — | |

### 2.3 `lessons`

| 字段 | 类型 | 可空 | 默认 | 索引/约束 | 说明 |
|---|---|---|---|---|---|
| id | CHAR(36) | N | uuid4 | PK | |
| chapter_id | CHAR(36) | N | — | FK chapters.id CASCADE, idx | |
| slug | VARCHAR(120) | N | — | UNIQUE(chapter_id, slug) | |
| title | VARCHAR(200) | N | — | — | |
| summary | VARCHAR(500) | Y | NULL | — | |
| content_md | TEXT | N | `''` | — | 正文 Markdown |
| content_html | TEXT | Y | NULL | — | 可选缓存（渲染后） |
| lesson_type | VARCHAR(20) | N | `concept` | idx | concept/practice/quiz/project |
| difficulty | VARCHAR(20) | N | `easy` | idx | easy/medium/hard/expert |
| estimated_minutes | INTEGER | N | 15 | — | |
| order_index | INTEGER | N | 0 | idx | |
| xp_reward | INTEGER | N | 10 | — | |
| has_playground | BOOLEAN | N | true | — | 是否内嵌编辑器 |
| starter_code | TEXT | Y | NULL | — | |
| solution_code | TEXT | Y | NULL | — | |
| quiz_json | JSON | Y | NULL | — | 随堂练习 `[{q,options,answer,explain}]` |
| is_published | BOOLEAN | N | true | idx | |
| created_at / updated_at | DATETIME | N | now() | — | |

### 2.4 `topics`（知识点树，≥120 条）

| 字段 | 类型 | 可空 | 默认 | 索引/约束 | 说明 |
|---|---|---|---|---|---|
| id | CHAR(36) | N | uuid4 | PK | |
| slug | VARCHAR(120) | N | — | UNIQUE, idx | `list-comprehension` |
| name | VARCHAR(120) | N | — | — | 列表推导式 |
| parent_id | CHAR(36) | Y | NULL | FK topics.id, idx | 自引用树 |
| description | TEXT | Y | NULL | — | |
| order_index | INTEGER | N | 0 | idx | |
| created_at | DATETIME | N | now() | — | |

### 2.5 `lesson_topics`（关联）

| 字段 | 类型 | 可空 | 默认 | 索引/约束 | 说明 |
|---|---|---|---|---|---|
| lesson_id | CHAR(36) | N | — | FK lessons.id CASCADE, PK(lesson_id, topic_id) | |
| topic_id | CHAR(36) | N | — | FK topics.id CASCADE, idx | |
| is_primary | BOOLEAN | N | false | — | 主知识点（计入掌握度主权重） |

### 2.6 `course_enrollments`

| 字段 | 类型 | 可空 | 默认 | 索引/约束 | 说明 |
|---|---|---|---|---|---|
| id | CHAR(36) | N | uuid4 | PK | |
| user_id | CHAR(36) | N | — | FK users.id CASCADE, UNIQUE(user_id, course_id), idx | |
| course_id | CHAR(36) | N | — | FK courses.id CASCADE | |
| progress_percent | INTEGER | N | 0 | — | 0-100 |
| completed_lessons | INTEGER | N | 0 | — | |
| last_lesson_id | CHAR(36) | Y | NULL | — | 继续学习用 |
| enrolled_at | DATETIME | N | now() | — | |
| completed_at | DATETIME | Y | NULL | — | |
| updated_at | DATETIME | N | now() | — | |

---

## 3. 题目与判题

### 3.1 `problems`

| 字段 | 类型 | 可空 | 默认 | 索引/约束 | 说明 |
|---|---|---|---|---|---|
| id | CHAR(36) | N | uuid4 | PK | |
| slug | VARCHAR(150) | N | — | UNIQUE, idx | |
| title | VARCHAR(200) | N | — | idx | |
| statement_md | TEXT | N | `''` | — | 题干（含输入/输出/约束/样例） |
| problem_type | VARCHAR(20) | N | `coding` | idx | choice/judge/blank/completion/coding/debug/algorithm |
| difficulty | VARCHAR(20) | N | `easy` | idx | easy/medium/hard/expert（4 档） |
| category | VARCHAR(40) | N | `basics` | idx | ≥10 类（见 §7.3） |
| input_format | TEXT | Y | NULL | — | |
| output_format | TEXT | Y | NULL | — | |
| sample_input | TEXT | Y | NULL | — | |
| sample_output | TEXT | Y | NULL | — | |
| constraints | TEXT | Y | NULL | — | |
| options_json | JSON | Y | NULL | — | 选择题选项/填空题空位定义 |
| answer_json | JSON | Y | NULL | — | 客观题标准答案 |
| hint_md | TEXT | Y | NULL | — | |
| solution_md | TEXT | Y | NULL | — | 题解（默认不展示） |
| starter_code | TEXT | Y | NULL | — | |
| reference_solution | TEXT | Y | NULL | — | 判题参考/AI 讲解用 |
| buggy_code | TEXT | Y | NULL | — | debug 题型的错误代码 |
| time_limit_ms | INTEGER | N | 5000 | — | clamp 1000-10000 |
| memory_limit_mb | INTEGER | N | 256 | — | clamp 32-512 |
| score | INTEGER | N | 10 | — | |
| xp_reward | INTEGER | N | 20 | — | |
| submission_count | INTEGER | N | 0 | — | |
| accepted_count | INTEGER | N | 0 | — | |
| acceptance_rate | FLOAT | N | 0.0 | idx | 冗余，通过率 |
| avg_time_ms | INTEGER | N | 0 | — | |
| is_published | BOOLEAN | N | true | idx | |
| created_by | CHAR(36) | Y | NULL | FK users.id | |
| created_at / updated_at | DATETIME | N | now() | idx | |

### 3.2 `test_cases`

| 字段 | 类型 | 可空 | 默认 | 索引/约束 | 说明 |
|---|---|---|---|---|---|
| id | CHAR(36) | N | uuid4 | PK | |
| problem_id | CHAR(36) | N | — | FK problems.id CASCADE, idx | |
| name | VARCHAR(100) | Y | NULL | — | |
| input | TEXT | N | `''` | — | 标准输入 |
| expected_output | TEXT | N | `''` | — | |
| comparison | VARCHAR(20) | N | `trimmed` | — | exact/trimmed/float/custom |
| float_tolerance | FLOAT | Y | 1e-6 | — | float 模式 |
| is_sample | BOOLEAN | N | false | idx | 样例（前端可展示） |
| is_hidden | BOOLEAN | N | true | — | |
| weight | INTEGER | N | 1 | — | 计分权重 |
| timeout_ms | INTEGER | Y | NULL | — | 覆盖题目默认 |
| order_index | INTEGER | N | 0 | idx | |
| created_at | DATETIME | N | now() | — | |

### 3.3 `tags` / 3.4 `problem_tags`

`tags`: id / slug(UNIQUE) / name / color / kind(problem|course|project|lesson|snippet) / order_index / created_at。
`problem_tags`: problem_id(FK, PK 复合) / tag_id(FK, idx) / created_at。

---

## 4. 提交与判题结果

### 4.1 `submissions`

| 字段 | 类型 | 可空 | 默认 | 索引/约束 | 说明 |
|---|---|---|---|---|---|
| id | CHAR(36) | N | uuid4 | PK | |
| user_id | CHAR(36) | N | — | FK users.id CASCADE, idx | |
| problem_id | CHAR(36) | Y | NULL | FK problems.id, idx | 客观题也可能为空 |
| lesson_id | CHAR(36) | Y | NULL | FK lessons.id | 随堂练习 |
| challenge_id | CHAR(36) | Y | NULL | FK challenges.id | |
| language | VARCHAR(20) | N | `python` | — | |
| code | TEXT | N | `''` | — | |
| status | VARCHAR(30) | N | `pending` | idx | pending/judging/accepted/wrong_answer/runtime_error/time_limit_exceeded/memory_limit_exceeded/compile_error/internal_error/security_error |
| score | INTEGER | N | 0 | — | |
| passed_cases | INTEGER | N | 0 | — | |
| total_cases | INTEGER | N | 0 | — | |
| time_ms | INTEGER | N | 0 | — | 最大单用例耗时 |
| memory_kb | INTEGER | N | 0 | — | |
| error_type | VARCHAR(60) | Y | NULL | idx | ValueError/IndexError/… |
| error_message | TEXT | Y | NULL | — | 截断到 2000 字符 |
| runner | VARCHAR(20) | N | `local` | idx | sandbox/local |
| judged_by | VARCHAR(20) | N | `local` | — | sandbox/local/rule |
| ip | VARCHAR(45) | Y | NULL | — | |
| created_at | DATETIME | N | now() | idx | |
| finished_at | DATETIME | Y | NULL | — | |

> 复合索引：`(user_id, created_at DESC)`、`(problem_id, status)`、`(user_id, problem_id)`。

### 4.2 `submission_results`

| 字段 | 类型 | 可空 | 默认 | 索引/约束 | 说明 |
|---|---|---|---|---|---|
| id | CHAR(36) | N | uuid4 | PK | |
| submission_id | CHAR(36) | N | — | FK submissions.id CASCADE, idx | |
| test_case_id | CHAR(36) | Y | NULL | FK test_cases.id | |
| passed | BOOLEAN | N | false | — | |
| actual_output | TEXT | Y | NULL | — | 截断 8000 |
| expected_output | TEXT | Y | NULL | — | |
| stdout | TEXT | Y | NULL | — | |
| stderr | TEXT | Y | NULL | — | |
| diff | TEXT | Y | NULL | — | 行级差异 |
| time_ms | INTEGER | N | 0 | — | |
| memory_kb | INTEGER | N | 0 | — | |
| message | VARCHAR(300) | Y | NULL | — | |

---

## 5. 项目中心

### 5.1 `projects`

| 字段 | 类型 | 可空 | 默认 | 索引/约束 | 说明 |
|---|---|---|---|---|---|
| id | CHAR(36) | N | uuid4 | PK | |
| slug | VARCHAR(150) | N | — | UNIQUE, idx | |
| title | VARCHAR(200) | N | — | — | |
| summary | VARCHAR(500) | Y | NULL | — | |
| description_md | TEXT | N | `''` | — | 需求文档 |
| level | INTEGER | N | 1 | idx | 1..10 |
| difficulty | VARCHAR(20) | N | `easy` | idx | |
| category | VARCHAR(40) | N | `basics` | idx | |
| cover_url | VARCHAR(512) | Y | NULL | — | |
| estimated_hours | INTEGER | N | 4 | — | |
| xp_reward | INTEGER | N | 100 | — | |
| steps_json | JSON | Y | NULL | — | `[{title, detail, done_hint}]` |
| rubric_json | JSON | Y | NULL | — | 评分维度 |
| is_published | BOOLEAN | N | true | idx | |
| order_index | INTEGER | N | 0 | idx | |
| created_at / updated_at | DATETIME | N | now() | — | |

### 5.2 `project_files`

| 字段 | 类型 | 可空 | 默认 | 索引/约束 | 说明 |
|---|---|---|---|---|---|
| id | CHAR(36) | N | uuid4 | PK | |
| project_id | CHAR(36) | N | — | FK projects.id CASCADE, idx | |
| path | VARCHAR(512) | N | — | UNIQUE(project_id, path) | `main.py` |
| content | TEXT | N | `''` | — | 初始模板内容 |
| language | VARCHAR(20) | N | `python` | — | |
| is_entry | BOOLEAN | N | false | — | |
| is_readonly | BOOLEAN | N | false | — | 只读文件（如 README） |
| description | VARCHAR(300) | Y | NULL | — | |
| order_index | INTEGER | N | 0 | — | |

### 5.3 `user_projects`

| 字段 | 类型 | 可空 | 默认 | 索引/约束 | 说明 |
|---|---|---|---|---|---|
| id | CHAR(36) | N | uuid4 | PK | |
| user_id | CHAR(36) | N | — | FK users.id CASCADE, UNIQUE(user_id, project_id), idx | |
| project_id | CHAR(36) | N | — | FK projects.id CASCADE | |
| status | VARCHAR(20) | N | `not_started` | idx | not_started/in_progress/completed |
| progress_percent | INTEGER | N | 0 | — | |
| current_step | INTEGER | N | 0 | — | |
| files_json | JSON | Y | NULL | — | 用户当前文件快照 `{path: content}` |
| notes_md | TEXT | Y | NULL | — | |
| last_run_status | VARCHAR(30) | Y | NULL | — | |
| started_at | DATETIME | Y | NULL | — | |
| completed_at | DATETIME | Y | NULL | — | |
| updated_at | DATETIME | N | now() | — | |

---

## 6. 学习过程

### 6.1 `learning_progress`

| 字段 | 类型 | 可空 | 默认 | 索引/约束 | 说明 |
|---|---|---|---|---|---|
| id | CHAR(36) | N | uuid4 | PK | |
| user_id | CHAR(36) | N | — | FK users.id CASCADE, UNIQUE(user_id, lesson_id), idx | |
| lesson_id | CHAR(36) | N | — | FK lessons.id CASCADE, idx | |
| status | VARCHAR(20) | N | `not_started` | idx | not_started/in_progress/completed |
| progress_percent | INTEGER | N | 0 | — | |
| time_spent_seconds | INTEGER | N | 0 | — | |
| code_snapshot | TEXT | Y | NULL | — | 最近一次编辑器内容 |
| attempt_count | INTEGER | N | 0 | — | |
| started_at | DATETIME | Y | NULL | — | |
| completed_at | DATETIME | Y | NULL | idx | |
| updated_at | DATETIME | N | now() | — | |

### 6.2 `knowledge_mastery`

| 字段 | 类型 | 可空 | 默认 | 索引/约束 | 说明 |
|---|---|---|---|---|---|
| id | CHAR(36) | N | uuid4 | PK | |
| user_id | CHAR(36) | N | — | FK users.id CASCADE, UNIQUE(user_id, topic_id), idx | |
| topic_id | CHAR(36) | N | — | FK topics.id CASCADE, idx | |
| mastery_score | FLOAT | N | 0.0 | idx | 0-100 |
| mastery_level | VARCHAR(20) | N | `none` | idx | none/weak/medium/strong/mastered |
| practiced_count | INTEGER | N | 0 | — | |
| correct_count | INTEGER | N | 0 | — | |
| mistake_count | INTEGER | N | 0 | — | |
| last_practiced_at | DATETIME | Y | NULL | — | |
| next_review_at | DATETIME | Y | NULL | idx | 间隔复习 |
| updated_at | DATETIME | N | now() | — | |

> 更新算法（SM-2 简化）：正确 `score += (100-score)*0.2`，错误 `score -= score*0.25`；连续正确 3 次升级别。

### 6.3 `mistakes`（错题本）

| 字段 | 类型 | 可空 | 默认 | 索引/约束 | 说明 |
|---|---|---|---|---|---|
| id | CHAR(36) | N | uuid4 | PK | |
| user_id | CHAR(36) | N | — | FK users.id CASCADE, idx | |
| problem_id | CHAR(36) | Y | NULL | FK problems.id, idx | |
| submission_id | CHAR(36) | Y | NULL | FK submissions.id | |
| lesson_id | CHAR(36) | Y | NULL | — | |
| topic_id | CHAR(36) | Y | NULL | FK topics.id | |
| title | VARCHAR(200) | N | `''` | — | |
| question_snapshot_md | TEXT | Y | NULL | — | 题干快照（题目可改） |
| user_answer | TEXT | Y | NULL | — | 用户答案/代码 |
| correct_answer | TEXT | Y | NULL | — | |
| error_type | VARCHAR(30) | N | `logic` | idx | concept/syntax/logic/runtime/timeout/style/output |
| error_message | TEXT | Y | NULL | — | |
| note_md | TEXT | Y | NULL | — | 用户笔记 |
| resolved | BOOLEAN | N | false | idx | |
| resolved_at | DATETIME | Y | NULL | — | |
| review_count | INTEGER | N | 0 | — | |
| next_review_at | DATETIME | Y | NULL | idx | |
| created_at / updated_at | DATETIME | N | now() | idx | |

### 6.4 `bookmarks`（收藏 / 代码片段库）

| 字段 | 类型 | 可空 | 默认 | 索引/约束 | 说明 |
|---|---|---|---|---|---|
| id | CHAR(36) | N | uuid4 | PK | |
| user_id | CHAR(36) | N | — | FK users.id CASCADE, idx | |
| kind | VARCHAR(20) | N | `problem` | idx | problem/lesson/project/snippet/challenge |
| ref_id | CHAR(36) | Y | NULL | idx | 被收藏对象 id |
| title | VARCHAR(200) | N | `''` | — | |
| description | VARCHAR(500) | Y | NULL | — | |
| code_snippet | TEXT | Y | NULL | — | kind=snippet 必填 |
| language | VARCHAR(20) | N | `python` | — | |
| collection | VARCHAR(50) | N | `default` | idx | 集合名 |
| tags_json | JSON | Y | NULL | — | |
| created_at | DATETIME | N | now() | idx | |

### 6.5 `code_history`

| 字段 | 类型 | 可空 | 默认 | 索引/约束 | 说明 |
|---|---|---|---|---|---|
| id | CHAR(36) | N | uuid4 | PK | |
| user_id | CHAR(36) | N | — | FK users.id CASCADE, idx | |
| context_type | VARCHAR(20) | N | `playground` | idx | lesson/problem/project/playground |
| context_id | CHAR(36) | Y | NULL | idx | |
| file_path | VARCHAR(255) | N | `main.py` | — | |
| code | TEXT | N | `''` | — | |
| label | VARCHAR(120) | Y | NULL | — | 「提交前」「自动保存」 |
| version_no | INTEGER | N | 1 | — | 同上下文递增 |
| parent_id | CHAR(36) | Y | NULL | FK code_history.id | 版本链 |
| source | VARCHAR(20) | N | `manual` | — | manual/auto/submit |
| size_bytes | INTEGER | N | 0 | — | |
| created_at | DATETIME | N | now() | idx | |

> 保留策略：同一 `(user_id, context_type, context_id)` 仅保留最近 30 版，写入新版本时异步清理更早的 `source=auto` 记录。

### 6.6 `learning_sessions`

| 字段 | 类型 | 可空 | 默认 | 索引/约束 | 说明 |
|---|---|---|---|---|---|
| id | CHAR(36) | N | uuid4 | PK | |
| user_id | CHAR(36) | N | — | FK users.id CASCADE, idx | |
| session_type | VARCHAR(20) | N | `lesson` | idx | lesson/problem/project/exam/playground/challenge/ai |
| learning_mode | VARCHAR(20) | N | `system` | idx | free/system/exam/drill/project/challenge/ai |
| ref_id | CHAR(36) | Y | NULL | — | |
| started_at | DATETIME | N | now() | idx | |
| ended_at | DATETIME | Y | NULL | — | |
| duration_seconds | INTEGER | N | 0 | — | |
| xp_earned | INTEGER | N | 0 | — | |
| actions_count | INTEGER | N | 0 | — | 提交/运行次数 |

---

## 7. 游戏化

### 7.1 `achievements`

| 字段 | 类型 | 可空 | 默认 | 索引/约束 | 说明 |
|---|---|---|---|---|---|
| id | CHAR(36) | N | uuid4 | PK | |
| code | VARCHAR(60) | N | — | UNIQUE, idx | `first_ac` |
| name | VARCHAR(120) | N | — | — | |
| description | VARCHAR(300) | Y | NULL | — | |
| icon | VARCHAR(50) | Y | NULL | — | |
| category | VARCHAR(20) | N | `learning` | idx | learning/practice/streak/project/social/special |
| condition_json | JSON | N | `{}` | — | `{"metric":"accepted_count","op":">=","value":1}` |
| xp_reward | INTEGER | N | 10 | — | |
| badge_color | VARCHAR(20) | N | `blue` | — | |
| is_secret | BOOLEAN | N | false | — | |
| is_active | BOOLEAN | N | true | idx | |
| order_index | INTEGER | N | 0 | — | |

### 7.2 `user_achievements`

| 字段 | 类型 | 可空 | 默认 | 索引/约束 | 说明 |
|---|---|---|---|---|---|
| id | CHAR(36) | N | uuid4 | PK | |
| user_id | CHAR(36) | N | — | FK users.id CASCADE, UNIQUE(user_id, achievement_id), idx | |
| achievement_id | CHAR(36) | N | — | FK achievements.id CASCADE | |
| unlocked_at | DATETIME | N | now() | — | |
| seen | BOOLEAN | N | false | idx | 是否已弹窗提示 |

### 7.3 `daily_tasks` / 7.4 `user_daily_tasks`

`daily_tasks`: id / code(UNIQUE) / title / description / metric(VARCHAR 40) / target_count(INTEGER) / xp_reward / is_active / order_index。
`user_daily_tasks`: id / user_id(FK, idx) / daily_task_id(FK) / date(DATE, idx) / progress(INTEGER 默认0) / completed(BOOLEAN 默认false, idx) / completed_at / **UNIQUE(user_id, daily_task_id, date)**。

### 7.5 `xp_transactions`

| 字段 | 类型 | 可空 | 默认 | 索引/约束 | 说明 |
|---|---|---|---|---|---|
| id | CHAR(36) | N | uuid4 | PK | |
| user_id | CHAR(36) | N | — | FK users.id CASCADE, idx | |
| amount | INTEGER | N | 0 | — | 正负 |
| reason | VARCHAR(60) | N | `''` | idx | lesson_complete/ac/daily_task/achievement/project/challenge |
| ref_type | VARCHAR(30) | Y | NULL | — | |
| ref_id | CHAR(36) | Y | NULL | — | |
| balance_after | INTEGER | N | 0 | — | |
| created_at | DATETIME | N | now() | idx | |

---

## 8. AI

### 8.1 `ai_conversations`

| 字段 | 类型 | 可空 | 默认 | 索引/约束 | 说明 |
|---|---|---|---|---|---|
| id | CHAR(36) | N | uuid4 | PK | |
| user_id | CHAR(36) | N | — | FK users.id CASCADE, idx | |
| title | VARCHAR(200) | N | `新对话` | — | 首次提问后自动生成 |
| mode | VARCHAR(20) | N | `standard` | idx | beginner/standard/advanced |
| scene | VARCHAR(20) | N | `free` | idx | tutor/review/error/exam/free |
| context_type | VARCHAR(20) | Y | NULL | — | lesson/problem/project/playground |
| context_id | CHAR(36) | Y | NULL | idx | |
| provider | VARCHAR(30) | Y | NULL | — | |
| model | VARCHAR(60) | Y | NULL | — | |
| message_count | INTEGER | N | 0 | — | |
| total_tokens | INTEGER | N | 0 | — | |
| is_archived | BOOLEAN | N | false | idx | |
| created_at / updated_at | DATETIME | N | now() | idx | |

### 8.2 `ai_messages`

| 字段 | 类型 | 可空 | 默认 | 索引/约束 | 说明 |
|---|---|---|---|---|---|
| id | CHAR(36) | N | uuid4 | PK | |
| conversation_id | CHAR(36) | N | — | FK ai_conversations.id CASCADE, idx | |
| role | VARCHAR(20) | N | `user` | — | system/user/assistant |
| content_md | TEXT | N | `''` | — | |
| kind | VARCHAR(30) | Y | NULL | idx | hint/approach/partial/full/explain/review/error_analysis/answer |
| tokens_in | INTEGER | N | 0 | — | |
| tokens_out | INTEGER | N | 0 | — | |
| latency_ms | INTEGER | N | 0 | — | |
| degraded | BOOLEAN | N | false | — | 是否本地规则兜底 |
| meta_json | JSON | Y | NULL | — | 模型原始片段、代码引用等 |
| created_at | DATETIME | N | now() | idx | |

### 8.3 `ai_model_configs`

| 字段 | 类型 | 可空 | 默认 | 索引/约束 | 说明 |
|---|---|---|---|---|---|
| id | CHAR(36) | N | uuid4 | PK | |
| provider | VARCHAR(30) | N | `deepseek` | idx | openai/anthropic/gemini/deepseek/qwen/zhipu/moonshot/custom |
| name | VARCHAR(80) | N | — | — | 显示名 |
| model | VARCHAR(80) | N | — | — | `deepseek-chat` |
| base_url | VARCHAR(255) | Y | NULL | — | |
| api_key_env | VARCHAR(80) | Y | NULL | — | **只存环境变量名**，如 `DEEPSEEK_API_KEY` |
| temperature | FLOAT | N | 0.3 | — | |
| max_tokens | INTEGER | N | 2048 | — | |
| is_default | BOOLEAN | N | false | idx | |
| is_active | BOOLEAN | N | true | idx | |
| capability_json | JSON | Y | NULL | — | `{"stream":true,"json_mode":true}` |
| created_at / updated_at | DATETIME | N | now() | — | |

### 8.4 `ai_usage_logs`

| 字段 | 类型 | 可空 | 默认 | 索引/约束 | 说明 |
|---|---|---|---|---|---|
| id | CHAR(36) | N | uuid4 | PK | |
| user_id | CHAR(36) | Y | NULL | FK users.id, idx | |
| conversation_id | CHAR(36) | Y | NULL | idx | |
| provider | VARCHAR(30) | N | `''` | idx | |
| model | VARCHAR(60) | N | `''` | — | |
| scene | VARCHAR(20) | Y | NULL | — | |
| tokens_in / tokens_out | INTEGER | N | 0 | — | |
| latency_ms | INTEGER | N | 0 | — | |
| success | BOOLEAN | N | true | idx | |
| error_code | VARCHAR(40) | Y | NULL | — | |
| degraded | BOOLEAN | N | false | — | |
| created_at | DATETIME | N | now() | idx | |

---

## 9. 挑战与考试

### 9.1 `challenges`

| 字段 | 类型 | 可空 | 默认 | 索引/约束 | 说明 |
|---|---|---|---|---|---|
| id | CHAR(36) | N | uuid4 | PK | |
| slug | VARCHAR(150) | N | — | UNIQUE, idx | |
| title | VARCHAR(200) | N | — | — | |
| description_md | TEXT | Y | NULL | — | |
| challenge_type | VARCHAR(20) | N | `daily` | idx | daily/weekly/monthly/special |
| difficulty | VARCHAR(20) | N | `easy` | idx | |
| problem_ids_json | JSON | N | `[]` | — | 题目 id 数组 |
| rules_md | TEXT | Y | NULL | — | |
| start_at | DATETIME | N | now() | idx | |
| end_at | DATETIME | N | — | idx | |
| duration_minutes | INTEGER | N | 60 | — | |
| xp_reward | INTEGER | N | 50 | — | |
| participant_count | INTEGER | N | 0 | — | |
| is_published | BOOLEAN | N | true | idx | |
| created_at / updated_at | DATETIME | N | now() | — | |

### 9.2 `user_challenges`

| 字段 | 类型 | 可空 | 默认 | 索引/约束 | 说明 |
|---|---|---|---|---|---|
| id | CHAR(36) | N | uuid4 | PK | |
| user_id | CHAR(36) | N | — | FK users.id CASCADE, UNIQUE(user_id, challenge_id), idx | |
| challenge_id | CHAR(36) | N | — | FK challenges.id CASCADE, idx | |
| status | VARCHAR(20) | N | `joined` | idx | joined/in_progress/completed |
| score | INTEGER | N | 0 | idx | 排行榜排序键 |
| passed_cases | INTEGER | N | 0 | — | |
| total_time_ms | INTEGER | N | 0 | idx | 用时（升序优先） |
| rank | INTEGER | Y | NULL | idx | 结算后写入 |
| submitted_at | DATETIME | Y | NULL | — | |
| created_at | DATETIME | N | now() | — | |

> 排行榜查询：`SELECT display_name, score, total_time_ms FROM user_challenges JOIN profiles ... ORDER BY score DESC, total_time_ms ASC LIMIT 100`。**只返回昵称与成绩**。

### 9.3 `exams`

| 字段 | 类型 | 可空 | 默认 | 索引/约束 | 说明 |
|---|---|---|---|---|---|
| id | CHAR(36) | N | uuid4 | PK | |
| code | VARCHAR(60) | N | — | UNIQUE, idx | `py-basic-01` |
| title | VARCHAR(200) | N | — | — | |
| level | VARCHAR(20) | N | `basic` | idx | basic/intermediate/advanced |
| duration_minutes | INTEGER | N | 60 | — | |
| total_score | INTEGER | N | 100 | — | |
| pass_score | INTEGER | N | 60 | — | |
| question_ids_json | JSON | N | `[]` | — | 题目 id + 分值 |
| shuffle | BOOLEAN | N | true | — | |
| is_published | BOOLEAN | N | true | idx | |
| created_at / updated_at | DATETIME | N | now() | — | |

### 9.4 `exam_attempts`

| 字段 | 类型 | 可空 | 默认 | 索引/约束 | 说明 |
|---|---|---|---|---|---|
| id | CHAR(36) | N | uuid4 | PK | |
| user_id | CHAR(36) | N | — | FK users.id CASCADE, idx | |
| exam_id | CHAR(36) | N | — | FK exams.id CASCADE, idx | |
| status | VARCHAR(20) | N | `in_progress` | idx | in_progress/graded/abandoned |
| answers_json | JSON | N | `{}` | — | `{problem_id: {answer/code}}` |
| report_json | JSON | Y | NULL | — | 逐题结果 + 知识点分析 |
| score | INTEGER | N | 0 | — | |
| passed | BOOLEAN | N | false | — | |
| started_at | DATETIME | N | now() | — | |
| deadline_at | DATETIME | N | — | — | 服务端计时 |
| submitted_at | DATETIME | Y | NULL | — | |

---

## 10. 通知与系统

### 10.1 `notifications`

| 字段 | 类型 | 可空 | 默认 | 索引/约束 | 说明 |
|---|---|---|---|---|---|
| id | CHAR(36) | N | uuid4 | PK | |
| user_id | CHAR(36) | N | — | FK users.id CASCADE, idx | NULL 表示广播（本设计不启用） |
| type | VARCHAR(20) | N | `system` | idx | system/achievement/daily/challenge/ai/admin |
| title | VARCHAR(200) | N | `''` | — | |
| content_md | TEXT | Y | NULL | — | |
| link_url | VARCHAR(255) | Y | NULL | — | |
| icon | VARCHAR(50) | Y | NULL | — | |
| is_read | BOOLEAN | N | false | idx | |
| read_at | DATETIME | Y | NULL | — | |
| created_at | DATETIME | N | now() | idx | |

### 10.2 `announcements`

| 字段 | 类型 | 可空 | 默认 | 索引/约束 | 说明 |
|---|---|---|---|---|---|
| id | CHAR(36) | N | uuid4 | PK | |
| title | VARCHAR(200) | N | — | — | |
| content_md | TEXT | N | `''` | — | |
| level | VARCHAR(20) | N | `info` | — | info/warning/important |
| is_pinned | BOOLEAN | N | false | idx | |
| is_active | BOOLEAN | N | true | idx | |
| published_at | DATETIME | N | now() | — | |
| expires_at | DATETIME | Y | NULL | — | |
| created_by | CHAR(36) | Y | NULL | FK users.id | |
| created_at / updated_at | DATETIME | N | now() | — | |

### 10.3 `audit_logs`

| 字段 | 类型 | 可空 | 默认 | 索引/约束 | 说明 |
|---|---|---|---|---|---|
| id | CHAR(36) | N | uuid4 | PK | |
| actor_id | CHAR(36) | Y | NULL | idx | |
| action | VARCHAR(60) | N | `''` | idx | `admin.user.ban` |
| target_type | VARCHAR(40) | Y | NULL | — | |
| target_id | CHAR(36) | Y | NULL | idx | |
| detail_json | JSON | Y | NULL | — | before/after 快照 |
| ip | VARCHAR(45) | Y | NULL | — | |
| user_agent | VARCHAR(255) | Y | NULL | — | |
| created_at | DATETIME | N | now() | idx | |

### 10.4 `system_settings`

| 字段 | 类型 | 可空 | 默认 | 索引/约束 | 说明 |
|---|---|---|---|---|---|
| id | CHAR(36) | N | uuid4 | PK | |
| key | VARCHAR(80) | N | — | UNIQUE, idx | `site.announcement` |
| value_json | JSON | N | `{}` | — | |
| description | VARCHAR(300) | Y | NULL | — | |
| updated_by | CHAR(36) | Y | NULL | — | |
| updated_at | DATETIME | N | now() | — | |

---

## 11. 枚举字典（前后端必须一致，值均为小写 snake_case）

1. **role**：`user` / `admin` / `superadmin`
2. **difficulty**：`easy` / `medium` / `hard` / `expert`
3. **problem_type**：`choice` / `judge` / `blank` / `completion` / `coding` / `debug` / `algorithm`
4. **submission_status**：`pending` / `judging` / `accepted` / `wrong_answer` / `runtime_error` / `time_limit_exceeded` / `memory_limit_exceeded` / `compile_error` / `security_error` / `internal_error`
5. **problem_category（≥10）**：`basics` / `strings` / `lists` / `dicts` / `sets_tuples` / `functions` / `oop` / `files` / `exceptions` / `regex` / `algorithms` / `data_structures` / `stdlib` / `debug` / `concurrency`
6. **lesson_type**：`concept` / `practice` / `quiz` / `project`
7. **ai_mode**：`beginner` / `standard` / `advanced`
8. **ai_message_kind**：`hint` / `approach` / `partial` / `full` / `explain` / `review` / `error_analysis` / `answer`
9. **learning_mode**：`free` / `system` / `exam` / `drill` / `project` / `challenge` / `ai`
10. **error_type**：`concept` / `syntax` / `logic` / `runtime` / `timeout` / `style` / `output`
11. **challenge_type**：`daily` / `weekly` / `monthly` / `special`
12. **mastery_level**：`none` / `weak` / `medium` / `strong` / `mastered`
13. **runner**：`sandbox` / `local`
14. **bookmark_kind**：`problem` / `lesson` / `project` / `snippet` / `challenge`

---

## 12. 索引汇总（Alembic 迁移必须建立）

| 表 | 索引 |
|---|---|
| users | `ix_users_email`(U), `ix_users_username`(U), `ix_users_role`, `ix_users_status`, `ix_users_xp` |
| refresh_tokens | `ix_rt_jti`(U), `ix_rt_user_id`, `ix_rt_expires_at` |
| courses | `ix_courses_slug`(U), `ix_courses_stage_no`(U), `ix_courses_level`, `ix_courses_published` |
| chapters | `ix_chapters_course_id`, `ix_chapters_order` |
| lessons | `ix_lessons_chapter_id`, `ix_lessons_type`, `ix_lessons_difficulty`, `ix_lessons_published` |
| topics | `ix_topics_slug`(U), `ix_topics_parent_id` |
| problems | `ix_problems_slug`(U), `ix_problems_type`, `ix_problems_difficulty`, `ix_problems_category`, `ix_problems_published`, `ix_problems_acceptance` |
| test_cases | `ix_tc_problem_id`, `ix_tc_is_sample` |
| submissions | `ix_sub_user_id`, `ix_sub_problem_id`, `ix_sub_status`, `ix_sub_created_at`, `ix_sub_user_created(user_id, created_at DESC)`, `ix_sub_problem_status(problem_id, status)` |
| submission_results | `ix_sr_submission_id` |
| projects | `ix_projects_slug`(U), `ix_projects_level`, `ix_projects_category` |
| project_files | `ix_pf_project_id`, `uq_pf_project_path(project_id, path)` |
| user_projects | `uq_up_user_project(user_id, project_id)`, `ix_up_status` |
| learning_progress | `uq_lp_user_lesson(user_id, lesson_id)`, `ix_lp_status`, `ix_lp_completed_at` |
| knowledge_mastery | `uq_km_user_topic(user_id, topic_id)`, `ix_km_level`, `ix_km_score` |
| mistakes | `ix_mk_user_id`, `ix_mk_problem_id`, `ix_mk_resolved`, `ix_mk_next_review` |
| bookmarks | `ix_bm_user_id`, `ix_bm_kind`, `ix_bm_collection`, `ix_bm_ref` |
| code_history | `ix_ch_user_id`, `ix_ch_context(context_type, context_id)`, `ix_ch_created_at` |
| learning_sessions | `ix_ls_user_id`, `ix_ls_started_at`, `ix_ls_mode` |
| user_achievements | `uq_ua_user_ach(user_id, achievement_id)`, `ix_ua_seen` |
| user_daily_tasks | `uq_udt(user_id, daily_task_id, date)`, `ix_udt_completed` |
| xp_transactions | `ix_xp_user_id`, `ix_xp_reason`, `ix_xp_created_at` |
| ai_conversations | `ix_aic_user_id`, `ix_aic_updated_at`, `ix_aic_scene` |
| ai_messages | `ix_aim_conversation_id`, `ix_aim_kind`, `ix_aim_created_at` |
| ai_usage_logs | `ix_aul_user_id`, `ix_aul_created_at`, `ix_aul_success` |
| user_challenges | `uq_uc_user_challenge(user_id, challenge_id)`, `ix_uc_score`, `ix_uc_rank` |
| exam_attempts | `ix_ea_user_id`, `ix_ea_exam_id`, `ix_ea_status` |
| notifications | `ix_nt_user_id`, `ix_nt_is_read`, `ix_nt_created_at` |
| audit_logs | `ix_al_actor_id`, `ix_al_action`, `ix_al_created_at` |

> **SQLite 注意事项**：不创建 `GIN`/`pg_trgm` 索引与部分索引（`WHERE` 子句索引）；`init/02-index.sql` 仅在 PG 模式执行（Alembic 迁移内以 `if dialect.name == "postgresql"` 分支处理）。

---

## 13. 数据完整性与级联约定

| 关系 | 删除行为 |
|---|---|
| users → 所有 user 级表 | `ON DELETE CASCADE`（软删用户时物理删子表） |
| courses → chapters → lessons | `ON DELETE CASCADE` |
| problems → test_cases / problem_tags | `ON DELETE CASCADE` |
| problems → submissions | `ON DELETE SET NULL`（保留提交历史） |
| submissions → submission_results | `ON DELETE CASCADE` |
| projects → project_files | `ON DELETE CASCADE` |
| topics → lesson_topics / knowledge_mastery | `ON DELETE CASCADE` |
| ai_conversations → ai_messages | `ON DELETE CASCADE` |
| challenges → user_challenges | `ON DELETE CASCADE` |

**SQLite 必须开启外键**：`PRAGMA foreign_keys=ON`（在 `db/session.py` 的 connect 事件中执行）。
