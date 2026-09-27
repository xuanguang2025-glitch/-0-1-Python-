/**
 * PYTHON LAB 前端类型定义。
 *
 * 严格对齐后端 openapi（116 paths / 138 operations）+ `GET /api/health/enums`
 * 权威枚举字典。字段名一律以后端为准，前端不再自定义同义字段。
 */

/* ------------------------------ 通用响应 ------------------------------ */

export interface ApiErrorPayload {
  code: string;
  details?: unknown;
}

export interface ApiResponse<T> {
  success: boolean;
  data: T | null;
  message: string;
  error: ApiErrorPayload | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface QueryParams {
  [key: string]: string | number | boolean | undefined | null;
}

/* ------------------------------ 枚举类型 ------------------------------ */

export type UserRole = 'user' | 'admin' | 'superadmin';
export type UserStatus = 'active' | 'suspended' | 'deleted';
export type Difficulty = 'easy' | 'medium' | 'hard' | 'expert';
export type CourseLevel = 'beginner' | 'intermediate' | 'advanced';
export type LessonType = 'concept' | 'practice' | 'quiz' | 'project';
export type ProblemType = 'choice' | 'judge' | 'blank' | 'completion' | 'coding' | 'debug' | 'algorithm';
export type SubmissionStatus =
  | 'pending'
  | 'judging'
  | 'accepted'
  | 'wrong_answer'
  | 'runtime_error'
  | 'time_limit_exceeded'
  | 'memory_limit_exceeded'
  | 'compile_error'
  | 'security_error'
  | 'internal_error';
export type AiMode = 'beginner' | 'standard' | 'advanced';
/** 对齐后端 ai_scene 枚举。 */
export type AiScene = 'tutor' | 'review' | 'error' | 'exam' | 'free';
/** 对齐后端 ai_message_kind 枚举。 */
export type AiMessageKind =
  | 'hint'
  | 'approach'
  | 'partial'
  | 'full'
  | 'explain'
  | 'review'
  | 'error_analysis'
  | 'answer';
/** AI 提示级别（ai_message_kind 的子集，用于对话式答疑）。 */
export type AiHintLevel = 'hint' | 'approach' | 'partial' | 'full' | 'explain';
export type RunnerKind = 'sandbox' | 'local';
export type BookmarkKind = 'problem' | 'lesson' | 'project' | 'snippet' | 'challenge';
export type NotificationType = 'system' | 'achievement' | 'daily' | 'challenge' | 'ai' | 'admin';
export type ProgressStatus = 'not_started' | 'in_progress' | 'completed';
export type MasteryLevel = 'none' | 'weak' | 'medium' | 'strong' | 'mastered';
export type LearningMode = 'free' | 'system' | 'exam' | 'drill' | 'project' | 'challenge' | 'ai';
export type SessionType = 'lesson' | 'problem' | 'project' | 'exam' | 'playground' | 'challenge' | 'ai';
export type ChallengeType = 'daily' | 'weekly' | 'monthly' | 'special';
export type UserChallengeStatus = 'joined' | 'in_progress' | 'completed';
export type Comparison = 'exact' | 'trimmed' | 'float' | 'custom';

/** `GET /api/health/enums` 返回的权威枚举字典。 */
export interface EnumDictionary {
  role: UserRole[];
  user_status: UserStatus[];
  difficulty: Difficulty[];
  course_level: CourseLevel[];
  lesson_type: LessonType[];
  problem_type: ProblemType[];
  problem_category: string[];
  submission_status: SubmissionStatus[];
  comparison: Comparison[];
  runner: RunnerKind[];
  progress_status: ProgressStatus[];
  mastery_level: MasteryLevel[];
  mistake_error_type: string[];
  bookmark_kind: BookmarkKind[];
  code_context_type: string[];
  code_source: string[];
  learning_mode: LearningMode[];
  session_type: SessionType[];
  ai_mode: AiMode[];
  ai_scene: AiScene[];
  ai_message_role: string[];
  ai_message_kind: AiMessageKind[];
  achievement_category: string[];
  challenge_type: ChallengeType[];
  challenge_status: UserChallengeStatus[];
  user_project_status: string[];
  exam_level: string[];
  exam_attempt_status: string[];
  notification_type: NotificationType[];
  announcement_level: string[];
  tag_kind: string[];
  theme_preference: string[];
  ai_provider: string[];
}

/* ------------------------------ 认证与用户 ------------------------------ */

export interface UserBrief {
  id: string;
  email: string;
  username: string;
  display_name: string;
  role: string;
  level: number;
  xp: number;
}

export interface ProfileBrief {
  display_name: string;
  avatar_url: string | null;
  bio: string | null;
  theme_preference: string;
  ai_mode: string;
  learning_mode: string;
}

/** 对齐后端 ProfileOut（含 id / created_at / updated_at）。 */
export interface ProfileOut {
  id: string;
  user_id: string;
  display_name: string;
  avatar_url: string | null;
  bio: string | null;
  timezone: string;
  theme_preference: string;
  ai_mode: string;
  learning_mode: string;
  public_profile: boolean;
  weekly_goal_minutes: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface UserMe {
  id: string;
  email: string;
  username: string;
  role: UserRole;
  status: string;
  is_verified: boolean;
  xp: number;
  level: number;
  streak_days: number;
  max_streak_days: number;
  login_count: number;
  created_at: string | null;
  last_login_at: string | null;
  profile: ProfileBrief | null;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: UserBrief;
}

/** 对齐后端 UserOverviewOut。 */
export interface UserOverview {
  xp: number;
  level: number;
  next_level_xp: number;
  streak_days: number;
  completed_lessons: number;
  solved_problems: number;
  today_minutes: number;
  daily_tasks_done: number;
}

/** 对齐后端 PublicUserOut。 */
export interface PublicUserOut {
  id: string;
  display_name: string;
  avatar_url: string | null;
  level: number;
  xp: number;
}

/* ------------------------------ 课程与课时 ------------------------------ */

export interface CourseBrief {
  id: string;
  slug: string;
  stage_no: number;
  title: string;
  subtitle: string | null;
  /** 后端 CourseBrief 未返回该字段，仅后台表单使用，故可选。 */
  description_md?: string | null;
  level: CourseLevel;
  icon: string | null;
  cover_url: string | null;
  estimated_hours: number;
  lesson_count: number;
  order_index: number;
  is_published: boolean;
  progress_percent: number;
}

export interface StageOut {
  stage_no: number;
  slug: string;
  title: string;
  subtitle: string | null;
  level: CourseLevel;
  icon: string | null;
  lesson_count: number;
  estimated_hours: number;
  progress_percent: number;
  is_current: boolean;
}

export interface LessonBrief {
  id: string;
  chapter_id: string;
  slug: string;
  title: string;
  summary: string | null;
  lesson_type: LessonType;
  difficulty: Difficulty;
  estimated_minutes: number;
  order_index: number;
  xp_reward: number;
  has_playground: boolean;
  is_published: boolean;
  progress_percent: number;
  status: ProgressStatus;
  /** 便利字段：由 status 推导，兼容旧渲染逻辑。 */
  completed?: boolean;
}

export interface ChapterOut {
  id: string;
  course_id: string;
  slug: string;
  title: string;
  summary_md: string | null;
  order_index: number;
  lesson_count: number;
  is_published: boolean;
  lessons: LessonBrief[];
}

export interface TopicOut {
  id: string;
  slug: string;
  name: string;
  parent_id: string | null;
  description: string | null;
  order_index: number;
  is_primary: boolean;
  mastery_score: number | null;
  mastery_level: string | null;
}

/** 对齐后端 LearningProgressOut。 */
export interface LearningProgressOut {
  id: string;
  lesson_id: string;
  status: string;
  progress_percent: number;
  time_spent_seconds: number;
  attempt_count: number;
  started_at: string | null;
  completed_at: string | null;
  updated_at: string | null;
}

/** 上/下节导航（对齐后端 LessonNav）。 */
export interface LessonNav {
  id: string;
  title: string;
  slug: string;
}

/** 对齐后端 LessonDetail —— 扁平结构（不再嵌套在 `.lesson` 下）。 */
export interface LessonDetail {
  id: string;
  chapter_id: string;
  slug: string;
  title: string;
  summary: string | null;
  content_md: string;
  lesson_type: LessonType;
  difficulty: Difficulty;
  estimated_minutes: number;
  order_index: number;
  xp_reward: number;
  has_playground: boolean;
  starter_code: string | null;
  solution_code: string | null;
  quiz_json: LessonQuizItem[] | null;
  topics: TopicOut[];
  prev: LessonBrief | null;
  next: LessonBrief | null;
  progress: LearningProgressOut | null;
  course_id: string | null;
  course_title: string | null;
  course_slug: string | null;
  chapter_title: string | null;
  chapter_index: number;
  lesson_index: number;
  total_lessons: number;
  prev_lesson: LessonNav | null;
  next_lesson: LessonNav | null;
  course_outline: ChapterOut[];
}

export interface LessonQuizItem {
  id?: string;
  qid?: string;
  question?: string;
  q?: string;
  options?: string[];
  answer?: string | number;
  explain?: string;
}

/**
 * 课程详情中的 progress 使用后端 `app__schemas__course__CourseProgressOut`：
 * completed_lessons 为**完成数量（整数）**，与 `/api/progress/courses/{id}` 的
 * `completed_lessons: string[]` 语义不同，务必区分。
 */
export interface CourseDetailProgress {
  course_id: string;
  percent: number;
  completed_lessons: number;
  total_lessons: number;
  last_lesson_id: string | null;
}

export interface CourseDetail {
  course: CourseBrief;
  chapters: ChapterOut[];
  progress: CourseDetailProgress | null;
}

/** 对齐后端 LessonCompleteOut。 */
export interface CompleteLessonResult {
  progress: LearningProgressOut;
  xp_earned: number;
  level_up: boolean;
  /** 后端返回成就 code 列表（非对象）。 */
  unlocked_achievements: string[];
}

/* ------------------------------ 题目与判题 ------------------------------ */

export interface TestCaseOut {
  id: string;
  input: string;
  expected_output: string;
  comparison: string;
  is_sample: boolean;
  is_hidden: boolean;
  order_index: number;
}

export interface ProblemBrief {
  id: string;
  slug: string;
  title: string;
  problem_type: ProblemType;
  difficulty: Difficulty;
  category: string;
  acceptance_rate: number;
  submission_count: number;
  tags?: string[];
  my_status?: SubmissionStatus | null;
}

export interface ProblemDetail {
  problem: ProblemBrief & {
    statement_md: string;
    input_format: string | null;
    output_format: string | null;
    time_limit_ms: number;
    memory_limit_mb: number;
    hints_md: string | null;
  };
  sample_cases: TestCaseOut[];
  tags: string[];
  my_status: SubmissionStatus | null;
  my_last_submission_id: string | null;
}

export interface ProblemFilters {
  types: { value: string; label: string; count: number }[];
  difficulties: { value: string; label: string; count: number }[];
  categories: { value: string; label: string; count: number }[];
  tags: { value: string; label: string; count: number }[];
}

export interface SubmissionCaseResult {
  test_case_id: string;
  passed: boolean;
  time_ms: number;
  memory_kb: number;
  actual_output: string | null;
  expected_output?: string | null;
  diff: string | null;
}

export interface SubmissionOut {
  id: string;
  user_id: string;
  problem_id: string;
  language: string;
  status: SubmissionStatus;
  score: number;
  passed_cases: number;
  total_cases: number;
  time_ms: number;
  memory_kb: number;
  error_type: string | null;
  error_message: string | null;
  runner: RunnerKind;
  code: string;
  created_at: string;
  results: SubmissionCaseResult[];
}

export interface SubmissionBrief {
  id: string;
  problem_id: string;
  problem_title?: string;
  status: SubmissionStatus;
  score: number;
  passed_cases: number;
  total_cases: number;
  time_ms: number;
  memory_kb: number;
  runner: RunnerKind;
  created_at: string;
}

export interface SubmissionStatusPoll {
  status: SubmissionStatus;
  passed_cases: number;
  total_cases: number;
}

/* ------------------------------ 执行与编辑器 ------------------------------ */

export interface RunFile {
  path: string;
  content: string;
}

export interface RunRequestPayload {
  files: RunFile[];
  entry?: string;
  stdin?: string;
  timeout_ms?: number;
  memory_limit_mb?: number;
}

export interface SandboxError {
  type: string | null;
  message: string | null;
  traceback: string | null;
  line: number | null;
}

export interface RunResponse {
  request_id: string;
  status: string;
  exit_code: number;
  stdout: string;
  stderr: string;
  truncated: boolean;
  time_ms: number;
  memory_kb: number;
  error: SandboxError | null;
  runner: RunnerKind;
  degraded: boolean;
}

export interface CodeHistoryBrief {
  id: string;
  context_type: string;
  context_id: string | null;
  file_path: string;
  label: string | null;
  version_no: number;
  created_at: string;
}

export interface CodeHistoryOut extends CodeHistoryBrief {
  code: string;
  source: string | null;
}

/* ------------------------------ 项目 ------------------------------ */

export interface ProjectBrief {
  id: string;
  slug: string;
  title: string;
  summary: string | null;
  level: number;
  category: string;
  difficulty: Difficulty;
  estimated_hours: number;
  cover_url: string | null;
  my_progress_percent?: number | null;
}

export interface ProjectFileOut {
  id: string;
  path: string;
  content: string;
  is_entry: boolean;
  order_index: number;
}

export interface ProjectStepOut {
  id: string;
  title: string;
  description_md: string | null;
  order_index: number;
}

export interface ProjectDetail {
  project: ProjectBrief & { requirement_md: string };
  files: ProjectFileOut[];
  steps: ProjectStepOut[];
  my: UserProjectOut | null;
}

export interface UserProjectOut {
  id: string;
  user_id: string;
  project_id: string;
  files_json: Record<string, string>;
  progress_percent: number;
  current_step: number;
  /** 已完成的步骤 id 列表。 */
  completed_steps: string[];
  submitted_at: string | null;
}

/* ------------------------------ AI ------------------------------ */

export interface AiConversationBrief {
  id: string;
  title: string;
  mode: AiMode;
  scene: AiScene;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface AiMessageOut {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant' | 'system';
  kind: AiMessageKind | string;
  content_md: string;
  created_at: string;
}

export interface AiConversationDetail {
  conversation: AiConversationBrief;
  messages: AiMessageOut[];
}

export interface AiChatPayload {
  conversation_id?: string;
  message: string;
  mode?: AiMode;
  scene?: AiScene;
  level?: AiHintLevel;
  context?: { type: string; id?: string; code?: string; error?: string } | null;
  stream?: boolean;
}

export interface ChatOut {
  conversation_id: string;
  message_id: string;
  role: string;
  kind: string;
  content_md: string;
  degraded: boolean;
  tokens_in: number;
  tokens_out: number;
  latency_ms: number;
  suggestions: string[];
}

export interface AiStatus {
  provider: string;
  model: string;
  degraded: boolean;
  remaining_quota: number;
  modes: AiMode[];
}

export interface ReviewIssue {
  severity: 'error' | 'warning' | 'info';
  line: number | null;
  title: string;
  suggestion: string;
}

export interface ReviewOut {
  score: number;
  summary_md: string;
  issues: ReviewIssue[];
  improved_code: string;
  degraded: boolean;
}

export interface ErrorAnalysisOut {
  error_type: string;
  cause: string;
  location: string | null;
  fix_steps: string[];
  minimal_example: string;
  related_topics: string[];
  degraded?: boolean;
}

/* ------------------------------ 进度与统计 ------------------------------ */

/** 对齐后端 CourseProgressItem（`/api/progress` 内）。 */
export interface CourseProgressItem {
  course_id: string;
  slug: string | null;
  stage_no: number;
  title: string;
  percent: number;
  completed_lessons: number;
  total_lessons: number;
  last_lesson_id: string | null;
}

/** 对齐后端 ProgressOverviewOut（`GET /api/progress`）。 */
export interface ProgressOverview {
  courses: CourseProgressItem[];
  completed_lessons: number;
  total_lessons: number;
  overall_percent: number;
  current_stage: number | null;
}

/** 对齐后端 LearningDashboardOut（`GET /api/progress/dashboard`）。 */
export interface LearningDashboardOut {
  today_minutes: number;
  week_minutes: number;
  streak_days: number;
  max_streak_days: number;
  level: number;
  xp: number;
  next_level_xp: number;
  completed_lessons: number;
  total_lessons: number;
  completed_courses: number;
  total_courses: number;
  overall_percent: number;
  solved_problems: number;
  submissions: number;
  projects_completed: number;
  projects_total: number;
  current_stage: number | null;
}

/** 对齐后端 LearningSessionOut。 */
export interface SessionOut {
  id: string;
  session_type: string;
  learning_mode: string;
  ref_id: string | null;
  started_at: string | null;
  ended_at: string | null;
  duration_seconds: number;
  xp_earned: number;
  actions_count: number;
}

/** 对齐后端 KnowledgeMasteryOut。 */
export interface KnowledgeMasteryOut {
  id: string | null;
  topic_id: string;
  name: string | null;
  mastery_score: number;
  mastery_level: MasteryLevel | string;
  practiced_count: number;
  correct_count: number;
  mistake_count: number;
  last_practiced_at: string | null;
  next_review_at: string | null;
}

/** 对齐后端 MasteryOverviewOut。 */
export interface MasteryOut {
  topics: KnowledgeMasteryOut[];
  weak_topics: KnowledgeMasteryOut[];
  average_score: number;
}

export interface HeatmapPoint {
  date: string;
  count: number;
  minutes: number;
}

/** 对齐后端 HeatmapOut。 */
export interface HeatmapOut {
  points: HeatmapPoint[];
  total_count: number;
  active_days: number;
  max_count: number;
}

/** 对齐后端 WeakTopicItem。 */
export interface WeakTopicItem {
  topic_id: string;
  name: string;
  score: number;
}

/** 对齐后端 StatisticsOverviewOut。 */
export interface StatisticsOverview {
  total_minutes: number;
  solved: number;
  submissions: number;
  accepted: number;
  acceptance_rate: number;
  streak_days: number;
  xp: number;
  level: number;
  rank_percentile: number;
  run_count: number;
  projects: number;
  courses: number;
  strongest_topic: WeakTopicItem | null;
  weakest_topic: WeakTopicItem | null;
}

export interface TrendPoint {
  date: string;
  value: number;
}

/** 对齐后端 TrendOut。 */
export interface TrendOut {
  metric: string;
  points: TrendPoint[];
  total: number;
}

export interface CategoryStat {
  category: string;
  solved: number;
  total: number;
  score: number;
}

export interface CategoryStatsOut {
  categories: CategoryStat[];
}

export interface ReportMetrics {
  minutes: number;
  lessons: number;
  submissions: number;
  accepted: number;
  acceptance_rate: number;
}

export interface RecommendationItem {
  type: string;
  id: string | null;
  title: string;
  reason: string;
}

/** 对齐后端 ReportOut。 */
export interface ReportOut {
  period: string;
  start_date: string | null;
  end_date: string | null;
  summary_md: string;
  highlights: string[];
  metrics: ReportMetrics;
  weak_topics: WeakTopicItem[];
  recommendations: RecommendationItem[];
  degraded: boolean;
}

/** 对齐后端 RankingOut。 */
export interface RankingOut {
  my_rank: number | null;
  total_users: number;
  percentile: number;
  xp: number;
}

/* ------------------------------ 游戏化 ------------------------------ */

export interface AchievementOut {
  id: string;
  code: string;
  name: string;
  description: string | null;
  icon: string | null;
  category: string;
  condition_json: unknown;
  xp_reward: number;
  badge_color: string;
  is_secret: boolean;
  order_index: number;
  unlocked: boolean;
  unlocked_at: string | null;
}

export interface UserAchievementOut {
  id: string;
  achievement_id: string;
  unlocked_at: string | null;
  seen: boolean;
  achievement: AchievementOut | null;
}

export interface BadgeWallCategory {
  category: string;
  total: number;
  unlocked: number;
}

export interface BadgeWallOut {
  total: number;
  unlocked: number;
  categories: BadgeWallCategory[];
  achievements: AchievementOut[];
}

/** 对齐后端 UserDailyTaskOut。 */
export interface DailyTaskOut {
  id: string;
  daily_task_id: string;
  date: string | null;
  progress: number;
  target: number;
  completed: boolean;
  completed_at: string | null;
  xp_reward: number;
  title: string;
  code: string;
}

/** 对齐后端 XPTransactionOut。 */
export interface XPTransactionOut {
  id: string;
  amount: number;
  reason: string;
  ref_type: string | null;
  ref_id: string | null;
  balance_after: number;
  created_at: string | null;
}

/* ------------------------------ 挑战 ------------------------------ */

/** 对齐后端 ChallengeBrief（无 status 字段，用 start_at/end_at/is_open 推导）。 */
export interface ChallengeBrief {
  id: string;
  slug: string;
  title: string;
  challenge_type: ChallengeType;
  difficulty: Difficulty;
  start_at: string | null;
  end_at: string | null;
  duration_minutes: number;
  xp_reward: number;
  participant_count: number;
  problem_count: number;
  is_open: boolean;
  my_status: UserChallengeStatus | null;
}

export interface ChallengeDetail {
  challenge: ChallengeBrief;
  description_md: string | null;
  rules_md: string | null;
  problems: ProblemBrief[];
  my: UserChallengeOut | null;
}

export interface UserChallengeOut {
  id: string;
  challenge_id: string;
  status: UserChallengeStatus;
  score: number;
  passed_cases: number;
  total_time_ms: number;
  rank: number | null;
  submitted_at: string | null;
}

export interface LeaderboardEntry {
  rank: number;
  display_name: string;
  score: number;
  total_time_ms: number;
}

export interface LeaderboardOut {
  entries: LeaderboardEntry[];
  total: number;
  updated_at: string | null;
}

/* ------------------------------ 通知 / 搜索 / 收藏 / 错题 ------------------------------ */

/** 对齐后端 NotificationOut（content_md / link_url / icon / read_at）。 */
export interface NotificationOut {
  id: string;
  type: NotificationType;
  title: string;
  content_md: string | null;
  link_url: string | null;
  icon: string | null;
  is_read: boolean;
  read_at: string | null;
  created_at: string | null;
}

/** 对齐后端 AnnouncementOut。 */
export interface AnnouncementOut {
  id: string;
  title: string;
  content_md: string;
  level: string;
  is_pinned: boolean;
  published_at: string | null;
  expires_at: string | null;
}

export interface SearchItem {
  id: string;
  title: string;
  subtitle: string;
  url: string;
  highlight: string;
}

export interface SearchGroup {
  type: string;
  label: string;
  items: SearchItem[];
}

/** 对齐后端 SearchOut。 */
export interface SearchOut {
  groups: SearchGroup[];
  total: number;
  keyword: string;
}

export interface BookmarkOut {
  id: string;
  kind: BookmarkKind;
  ref_id: string | null;
  title: string;
  code_snippet: string | null;
  collection: string | null;
  tags: string[];
  created_at: string;
}

export interface MistakeOut {
  id: string;
  problem_id: string | null;
  problem_title?: string | null;
  title: string;
  error_type: string | null;
  user_answer: string | null;
  note_md: string | null;
  resolved: boolean;
  review_count: number;
  next_review_at: string | null;
  created_at: string;
}

/* ------------------------------ 健康检查 ------------------------------ */

export interface HealthOut {
  status: string;
  version: string;
  env: string;
}

export interface DbStatus {
  ok: boolean;
  detail: string | null;
  flavor: string;
  target: string;
}

export interface CacheStatus {
  ok: boolean;
  detail: string | null;
  backend: string;
}

export interface QueueStatus {
  ok: boolean;
  detail: string | null;
  backend: string;
}

export interface RunnerStatus {
  ok: boolean;
  detail: string | null;
  mode: string;
}

export interface AiDepsStatus {
  ok: boolean;
  detail: string | null;
  provider: string;
  model: string;
  degraded: boolean;
}

/** 对齐后端 DepsHealthOut。 */
export interface HealthDepsOut {
  status: string;
  db: DbStatus;
  cache: CacheStatus;
  queue: QueueStatus;
  runner: RunnerStatus;
  ai: AiDepsStatus;
  degraded: boolean;
  version: string;
}

/* ------------------------------ Admin ------------------------------ */

/** 对齐后端 DashboardOut。 */
export interface AdminDashboardOut {
  users_total: number;
  active_today: number;
  submissions_today: number;
  acceptance_rate: number;
  ai_calls_today: number;
  error_rate: number;
  runner: string;
  db_flavor: string;
  cache_backend: string;
  extra: Record<string, unknown>;
}

/** 对齐后端 AdminUserBrief。 */
export interface AdminUserItem {
  id: string;
  email: string;
  username: string;
  display_name: string;
  role: UserRole;
  status: UserStatus;
  level: number;
  xp: number;
  login_count: number;
  created_at: string | null;
  last_login_at: string | null;
}

/** 对齐后端 CountOut。 */
export interface CountOut {
  count: number;
}

/** 对齐后端 MessageOut。 */
export interface MessageOut {
  message: string;
}

/** 对齐后端 AuditLogOut。 */
export interface AuditLogOut {
  id: string;
  actor_id: string | null;
  action: string;
  target_type: string | null;
  target_id: string | null;
  detail_json: unknown;
  ip: string | null;
  created_at: string | null;
}

/** 对齐后端 AIUsageLogOut。 */
export interface AIUsageLogOut {
  id: string;
  user_id: string | null;
  provider: string;
  model: string;
  scene: string | null;
  tokens_in: number;
  tokens_out: number;
  latency_ms: number;
  success: boolean;
  created_at: string | null;
}

/** 对齐后端 ErrorLogGroup。 */
export interface ErrorLogGroup {
  code: string;
  count: number;
  last_at: string | null;
  sample_message: string | null;
}
