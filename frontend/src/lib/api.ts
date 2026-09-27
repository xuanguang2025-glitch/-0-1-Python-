/**
 * PYTHON LAB 统一请求客户端。
 *
 * 约定（对齐 docs/API.md §5）：
 * 1. 所有请求经本模块发出，组件内禁止直接 fetch；
 * 2. 响应统一为 { success, data, message, error }，成功返回解包后的 data，失败抛 ApiRequestError；
 * 3. 401 且 code ∈ (TOKEN_EXPIRED, UNAUTHORIZED) → 单飞刷新令牌并重试一次，仍失败则清空登录态；
 * 4. Token 由外部注入（避免与 store 形成循环依赖）：见 configureApiClient()。
 */

import type { Page, ApiResponse, QueryParams, TokenPair } from './types';

export const API_BASE: string = process.env.NEXT_PUBLIC_API_BASE_URL ?? '/api';

/* ------------------------------ 错误类型 ------------------------------ */

export class ApiRequestError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown;

  constructor(message: string, status: number, code: string, details?: unknown) {
    super(message);
    this.name = 'ApiRequestError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

/** 无需重试的认证类错误码。 */
const REFRESHABLE_CODES: readonly string[] = ['TOKEN_EXPIRED', 'UNAUTHORIZED'];

/* ------------------------------ 外部注入点 ------------------------------ */

interface ApiClientConfig {
  getAccessToken: () => string | null;
  getRefreshToken: () => string | null;
  onTokensRefreshed: (tokens: TokenPair) => void;
  onSessionExpired: () => void;
}

const config: ApiClientConfig = {
  getAccessToken: () => null,
  getRefreshToken: () => null,
  onTokensRefreshed: () => undefined,
  onSessionExpired: () => undefined,
};

/** 由 src/store/auth.ts 在模块初始化时调用，注入令牌读取与刷新回调。 */
export function configureApiClient(next: Partial<ApiClientConfig>): void {
  Object.assign(config, next);
}

/* ------------------------------ 请求核心 ------------------------------ */

export interface RequestOptions {
  /** 查询参数（undefined / null 自动忽略）。 */
  query?: QueryParams;
  /** 请求体，对象会被序列化为 JSON。 */
  body?: unknown;
  /** 是否携带 Authorization，默认 true。 */
  auth?: boolean;
  /** multipart 表单数据（此时不设置 Content-Type，交由浏览器生成 boundary）。 */
  formData?: FormData;
  /** 期望返回二进制流（导出场景）。 */
  blob?: boolean;
  signal?: AbortSignal;
  /** 内部使用：是否为 401 重试请求。 */
  _retried?: boolean;
}

function buildUrl(path: string, query?: QueryParams): string {
  const url = `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`;
  if (!query) return url;
  const search = new URLSearchParams();
  Object.entries(query).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return;
    search.append(key, String(value));
  });
  const qs = search.toString();
  return qs ? `${url}?${qs}` : url;
}

async function parseResponse<T>(res: Response): Promise<T> {
  if (res.status === 204) return null as unknown as T;

  const text = await res.text();
  let payload: ApiResponse<T> | null = null;
  try {
    payload = text ? (JSON.parse(text) as ApiResponse<T>) : null;
  } catch {
    payload = null;
  }

  // 非统一结构（例如后端直返文件流 / 纯文本）时，直接返回原始内容
  if (!payload || typeof payload !== 'object' || !('success' in payload)) {
    if (!res.ok) {
      throw new ApiRequestError(res.statusText || '请求失败', res.status, 'INTERNAL_ERROR', text.slice(0, 500));
    }
    return (payload as unknown as T) ?? (text as unknown as T);
  }

  if (!payload.success || res.status >= 400) {
    throw new ApiRequestError(
      payload.message || '请求失败',
      res.status,
      payload.error?.code ?? 'INTERNAL_ERROR',
      payload.error?.details,
    );
  }

  // data 可能为 null（例如登出接口）；Page 结构保证为对象
  return payload.data as T;
}

/** 单飞刷新：并发 401 请求共用同一个刷新 Promise。 */
let refreshPromise: Promise<TokenPair> | null = null;

async function tryRefreshToken(): Promise<TokenPair | null> {
  const refreshToken = config.getRefreshToken();
  if (!refreshToken) return null;

  if (!refreshPromise) {
    refreshPromise = (async () => {
      const res = await fetch(buildUrl('/auth/refresh'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      const tokens = await parseResponse<TokenPair>(res);
      config.onTokensRefreshed(tokens);
      return tokens;
    })().finally(() => {
      refreshPromise = null;
    });
  }
  try {
    return await refreshPromise;
  } catch {
    return null;
  }
}

async function rawRequest<T>(
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE',
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { query, body, auth = true, formData, blob, signal, _retried = false } = options;

  const headers: Record<string, string> = { Accept: 'application/json' };
  const token = auth ? config.getAccessToken() : null;
  if (token) headers.Authorization = `Bearer ${token}`;

  let payload: BodyInit | undefined;
  if (formData) {
    payload = formData;
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    payload = JSON.stringify(body);
  }

  const res = await fetch(buildUrl(path, query), { method, headers, body: payload, signal, cache: 'no-store' });

  if (res.status === 401 && auth && !_retried) {
    const { code } = (await peekError(res)) ?? { code: 'UNAUTHORIZED' };
    if (REFRESHABLE_CODES.includes(code)) {
      const tokens = await tryRefreshToken();
      if (tokens) {
        return rawRequest<T>(method, path, { ...options, _retried: true });
      }
      config.onSessionExpired();
      throw new ApiRequestError('登录已过期，请重新登录', 401, code);
    }
  }

  if (blob) {
    if (!res.ok) throw new ApiRequestError('导出失败', res.status, 'INTERNAL_ERROR');
    return (await res.blob()) as unknown as T;
  }
  return parseResponse<T>(res);
}

/** 读取错误码但不消费 body（通过 clone 方式避免影响后续解析）。 */
async function peekError(res: Response): Promise<{ code: string } | null> {
  try {
    const cloned = res.clone();
    const payload = (await cloned.json()) as ApiResponse<unknown>;
    return { code: payload?.error?.code ?? 'UNAUTHORIZED' };
  } catch {
    return null;
  }
}

/* ------------------------------ 快捷方法 ------------------------------ */

export const apiGet = <T>(path: string, query?: QueryParams, options?: RequestOptions): Promise<T> =>
  rawRequest<T>('GET', path, { ...options, query });

export const apiPost = <T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> =>
  rawRequest<T>('POST', path, { ...options, body });

export const apiPut = <T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> =>
  rawRequest<T>('PUT', path, { ...options, body });

export const apiPatch = <T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> =>
  rawRequest<T>('PATCH', path, { ...options, body });

export const apiDelete = <T>(path: string, options?: RequestOptions): Promise<T> =>
  rawRequest<T>('DELETE', path, options);

/* ------------------------------ 资源接口 ------------------------------ */

export const authApi = {
  register: (payload: { email: string; username: string; password: string }) =>
    apiPost<TokenPair>('/auth/register', payload, { auth: false }),
  login: (payload: { account: string; password: string }) =>
    apiPost<TokenPair>('/auth/login', payload, { auth: false }),
  refresh: (refresh_token: string) => apiPost<TokenPair>('/auth/refresh', { refresh_token }, { auth: false }),
  logout: (refresh_token?: string) => apiPost<null>('/auth/logout', { refresh_token }),
  me: () => apiGet<import('./types').UserMe>('/auth/me'),
  changePassword: (old_password: string, new_password: string) =>
    apiPost<null>('/auth/change-password', { old_password, new_password }),
};

export const userApi = {
  profile: () => apiGet<import('./types').ProfileOut>('/users/me/profile'),
  updateProfile: (payload: Partial<import('./types').ProfileOut>) =>
    apiPatch<import('./types').ProfileOut>('/users/me/profile', payload),
  preferences: (payload: Record<string, unknown>) =>
    apiPatch<import('./types').ProfileOut>('/users/me/preferences', payload),
  overview: () => apiGet<import('./types').UserOverview>('/users/me/overview'),
  publicInfo: (id: string) => apiGet<import('./types').PublicUserOut>(`/users/${id}/public`),
  /** 上传头像（multipart/form-data）。 */
  uploadAvatar: (file: File) => {
    const form = new FormData();
    form.append('file', file);
    return apiPost<{ avatar_url: string | null }>('/users/me/avatar', undefined, { formData: form });
  },
  /** 注销账号（软删除），需要重新输入密码。 */
  deleteAccount: (password: string) => apiDelete<null>('/users/me', { body: { password } }),
  /** 导出学习数据（返回 Blob，由调用方负责下载）。 */
  exportData: (format: 'json' | 'zip' = 'json') =>
    apiGet<Blob>('/users/me/export', { format }, { blob: true }),
};

export const courseApi = {
  list: (query?: QueryParams) => apiGet<Page<import('./types').CourseBrief>>('/courses', query),
  stages: () => apiGet<import('./types').StageOut[]>('/courses/stages'),
  detail: (slug: string) => apiGet<import('./types').CourseDetail>(`/courses/${slug}`),
  enroll: (id: string) => apiPost<Record<string, unknown>>(`/courses/${id}/enroll`),
  chapters: (slug: string) => apiGet<import('./types').ChapterOut[]>(`/courses/${slug}/chapters`),
  lessons: (slug: string) => apiGet<import('./types').LessonBrief[]>(`/courses/${slug}/lessons`),
  lesson: (slug: string, lessonId: string) =>
    apiGet<import('./types').LessonDetail>(`/courses/${slug}/lessons/${lessonId}`),
};

export const lessonApi = {
  detail: (id: string) => apiGet<import('./types').LessonDetail>(`/lessons/${id}`),
  progress: (id: string, payload: { progress_percent: number; time_spent_seconds?: number; code_snapshot?: string }) =>
    apiPost<import('./types').LearningProgressOut>(`/lessons/${id}/progress`, payload),
  complete: (id: string, time_spent_seconds?: number) =>
    apiPost<import('./types').CompleteLessonResult>(`/lessons/${id}/complete`, { time_spent_seconds }),
  quiz: (id: string, answers: { qid: string; value: string }[]) =>
    apiPost<{ correct_count: number; total: number; passed: boolean; details: unknown[] }>(`/lessons/${id}/quiz`, {
      answers,
    }),
  topics: (id: string) => apiGet<import('./types').TopicOut[]>(`/lessons/${id}/topics`),
};

export const problemApi = {
  list: (query?: QueryParams) => apiGet<Page<import('./types').ProblemBrief>>('/problems', query),
  filters: () => apiGet<import('./types').ProblemFilters>('/problems/filters'),
  random: (query?: QueryParams) => apiGet<import('./types').ProblemBrief>('/problems/random', query),
  recommend: (limit = 10) => apiGet<import('./types').ProblemBrief[]>('/problems/recommend', { limit }),
  detail: (id: string) => apiGet<import('./types').ProblemDetail>(`/problems/${id}`),
  similar: (id: string, limit = 5) => apiGet<import('./types').ProblemBrief[]>(`/problems/${id}/similar`, { limit }),
  discussionAi: (id: string) => apiGet<{ summary_md: string }>(`/problems/${id}/discussion-ai`),
};

export const submissionApi = {
  submit: (payload: { problem_id: string; code: string; lesson_id?: string; language?: string }) =>
    apiPost<import('./types').SubmissionOut>('/submissions', payload),
  list: (query?: QueryParams) => apiGet<Page<import('./types').SubmissionBrief>>('/submissions', query),
  detail: (id: string) => apiGet<import('./types').SubmissionOut>(`/submissions/${id}`),
  results: (id: string) => apiGet<import('./types').SubmissionCaseResult[]>(`/submissions/${id}/results`),
  status: (id: string) => apiGet<import('./types').SubmissionStatusPoll>(`/submissions/${id}/status`),
};

export const pythonApi = {
  run: (payload: import('./types').RunRequestPayload) =>
    apiPost<import('./types').RunResponse>('/python/run', payload),
};

export const projectApi = {
  list: (query?: QueryParams) => apiGet<Page<import('./types').ProjectBrief>>('/projects', query),
  detail: (id: string) => apiGet<import('./types').ProjectDetail>(`/projects/${id}`),
  start: (id: string) => apiPost<import('./types').UserProjectOut>(`/projects/${id}/start`),
  mine: (id: string) => apiGet<import('./types').UserProjectOut>(`/projects/${id}/my`),
  saveFiles: (id: string, files: Record<string, string>) =>
    apiPut<import('./types').UserProjectOut>(`/projects/${id}/files`, { files }),
  run: (id: string, payload: { entry?: string; stdin?: string }) =>
    apiPost<import('./types').RunResponse>(`/projects/${id}/run`, payload),
  submit: (id: string, notes_md?: string) =>
    apiPost<{ user_project: import('./types').UserProjectOut; xp_earned: number; unlocked_achievements: unknown[] }>(
      `/projects/${id}/submit`,
      { notes_md },
    ),
};

export const editorApi = {
  saveSnapshot: (payload: {
    context_type: string;
    context_id?: string;
    file_path: string;
    code: string;
    label?: string;
    source?: string;
  }) => apiPost<import('./types').CodeHistoryOut>('/editor/save-snapshot', payload),
  history: (query?: QueryParams) => apiGet<Page<import('./types').CodeHistoryBrief>>('/editor/history', query),
  historyDetail: (id: string) => apiGet<import('./types').CodeHistoryOut>(`/editor/history/${id}`),
  restore: (id: string) => apiPost<import('./types').CodeHistoryOut>(`/editor/history/${id}/restore`),
  compare: (left_id: string, right_id: string) =>
    apiPost<{ diff_text: string; hunks: unknown[] }>('/editor/compare', { left_id, right_id }),
  remove: (id: string) => apiDelete<null>(`/editor/history/${id}`),
};

export const aiApi = {
  status: () => apiGet<import('./types').AiStatus>('/ai/status'),
  chat: (payload: import('./types').AiChatPayload) => apiPost<import('./types').ChatOut>('/ai/chat', payload),
  review: (payload: { code: string; language?: string; context_type?: string; context_id?: string; focus?: string }) =>
    apiPost<import('./types').ReviewOut>('/ai/review', payload),
  analyzeError: (payload: { code: string; error_message: string; traceback?: string; problem_id?: string }) =>
    apiPost<import('./types').ErrorAnalysisOut>('/ai/analyze-error', payload),
  conversations: (query?: QueryParams) =>
    apiGet<Page<import('./types').AiConversationBrief>>('/ai/conversations', query),
  createConversation: (payload: {
    title?: string;
    mode?: string;
    scene?: string;
    context_type?: string;
    context_id?: string;
  }) => apiPost<import('./types').AiConversationBrief>('/ai/conversations', payload),
  conversation: (id: string) => apiGet<import('./types').AiConversationDetail>(`/ai/conversations/${id}`),
  deleteConversation: (id: string) => apiDelete<null>(`/ai/conversations/${id}`),
  archiveConversation: (id: string, is_archived: boolean) =>
    apiPost<import('./types').AiConversationBrief>(`/ai/conversations/${id}/archive`, { is_archived }),
};

export const progressApi = {
  /** GET /api/progress —— ProgressOverviewOut（课程进度概览）。 */
  overview: () => apiGet<import('./types').ProgressOverview>('/progress'),
  /** GET /api/progress/dashboard —— LearningDashboardOut（学习看板）。 */
  dashboard: () => apiGet<import('./types').LearningDashboardOut>('/progress/dashboard'),
  /** GET /api/progress/courses/{id} —— completed_lessons 为 **id 列表**。 */
  course: (id: string) =>
    apiGet<{ course_id: string; percent: number; completed_lessons: string[]; last_lesson_id: string | null }>(
      `/progress/courses/${id}`,
    ),
  mastery: (parent_topic_id?: string) => apiGet<import('./types').MasteryOut>('/progress/mastery', { parent_topic_id }),
  masteryTopic: (topic_id: string) => apiGet<import('./types').KnowledgeMasteryOut>(`/progress/mastery/${topic_id}`),
  updateMastery: (topic_id: string, correct: boolean) =>
    apiPost<Record<string, unknown>>(`/progress/mastery/${topic_id}`, { correct }),
  heatmap: (days = 180) => apiGet<import('./types').HeatmapOut>('/progress/heatmap', { days }),
  setMode: (learning_mode: string) => apiPut<{ learning_mode: string }>('/progress/mode', { learning_mode }),
  startSession: (payload: { session_type: string; learning_mode?: string; ref_id?: string }) =>
    apiPost<import('./types').SessionOut>('/progress/sessions', payload),
  heartbeat: (id: string, payload: { seconds?: number; actions?: number; xp_earned?: number }) =>
    apiPost<import('./types').SessionOut>(`/progress/sessions/${id}/heartbeat`, payload),
  endSession: (id: string, payload: { duration_seconds?: number; actions_count?: number }) =>
    apiPost<import('./types').SessionOut>(`/progress/sessions/${id}/end`, payload),
};

export const statisticsApi = {
  overview: () => apiGet<import('./types').StatisticsOverview>('/statistics/overview'),
  trend: (days = 30, metric = 'submissions') => apiGet<import('./types').TrendOut>('/statistics/trend', { days, metric }),
  categories: () => apiGet<import('./types').CategoryStatsOut>('/statistics/categories'),
  heatmap: (days = 180) => apiGet<import('./types').HeatmapOut>('/statistics/heatmap', { days }),
  report: (period: 'week' | 'month' = 'week') => apiGet<import('./types').ReportOut>('/statistics/report', { period }),
  ranking: () => apiGet<import('./types').RankingOut>('/statistics/ranking'),
  /** GET /api/statistics/export —— type ∈ report|submissions|code，format ∈ md|csv|json。返回 Blob。 */
  exportData: (type: 'report' | 'submissions' | 'code' = 'report', format: 'md' | 'csv' | 'json' = 'md') =>
    apiGet<Blob>('/statistics/export', { type, format }, { blob: true }),
};

export const achievementApi = {
  list: (category?: string) => apiGet<import('./types').AchievementOut[]>('/achievements', { category }),
  /** GET /api/achievements/badge-wall —— 成就墙（分类统计 + 全部成就）。 */
  badgeWall: () => apiGet<import('./types').BadgeWallOut>('/achievements/badge-wall'),
  mine: (query?: QueryParams) => apiGet<Page<import('./types').UserAchievementOut>>('/achievements/mine', query),
  dailyTasks: (date?: string) => apiGet<import('./types').DailyTaskOut[]>('/achievements/daily-tasks', { date }),
  checkTask: (id: string) =>
    apiPost<{ progress: number; target: number; completed: boolean; xp_earned: number }>(
      `/achievements/daily-tasks/${id}/check`,
    ),
  xp: (query?: QueryParams) => apiGet<Page<import('./types').XPTransactionOut>>('/achievements/xp', query),
  markSeen: (id: string) => apiPost<null>(`/achievements/${id}/seen`),
};

export const challengeApi = {
  list: (query?: QueryParams) => apiGet<Page<import('./types').ChallengeBrief>>('/challenges', query),
  detail: (id: string) => apiGet<import('./types').ChallengeDetail>(`/challenges/${id}`),
  join: (id: string) => apiPost<import('./types').UserChallengeOut>(`/challenges/${id}/join`),
  problems: (id: string) => apiGet<import('./types').ProblemBrief[]>(`/challenges/${id}/problems`),
  submit: (id: string, solutions: Record<string, string>) =>
    apiPost<import('./types').UserChallengeOut>(`/challenges/${id}/submit`, { solutions }),
  leaderboard: (id: string, limit = 100) =>
    apiGet<import('./types').LeaderboardOut>(`/challenges/${id}/leaderboard`, { limit }),
  mine: (query?: QueryParams) => apiGet<Page<import('./types').UserChallengeOut>>('/challenges/my', query),
};

export const notificationApi = {
  list: (query?: QueryParams) => apiGet<Page<import('./types').NotificationOut>>('/notifications', query),
  unreadCount: () => apiGet<import('./types').CountOut>('/notifications/unread-count'),
  read: (id: string) => apiPost<import('./types').NotificationOut>(`/notifications/${id}/read`),
  readAll: (type?: string) => apiPost<{ updated: number }>('/notifications/read-all', { type }),
  remove: (id: string) => apiDelete<null>(`/notifications/${id}`),
  announcements: (limit = 5) => apiGet<import('./types').AnnouncementOut[]>('/notifications/announcements', { limit }),
  announcement: (id: string) => apiGet<import('./types').AnnouncementOut>(`/notifications/announcements/${id}`),
};

export const searchApi = {
  search: (q: string, types?: string, limit = 5) => apiGet<import('./types').SearchOut>('/search', { q, types, limit }),
  suggest: (q: string) =>
    apiGet<{ suggestions: { text: string; type: string; url: string }[] }>('/search/suggest', { q }),
};

export const bookmarkApi = {
  list: (query?: QueryParams) => apiGet<Page<import('./types').BookmarkOut>>('/bookmarks', query),
  create: (payload: Partial<import('./types').BookmarkOut>) =>
    apiPost<import('./types').BookmarkOut>('/bookmarks', payload),
  update: (id: string, payload: Partial<import('./types').BookmarkOut>) =>
    apiPatch<import('./types').BookmarkOut>(`/bookmarks/${id}`, payload),
  remove: (id: string) => apiDelete<null>(`/bookmarks/${id}`),
  collections: () => apiGet<{ collections: { name: string; count: number }[] }>('/bookmarks/collections'),
};

export const mistakeApi = {
  list: (query?: QueryParams) => apiGet<Page<import('./types').MistakeOut>>('/mistakes', query),
  create: (payload: Partial<import('./types').MistakeOut>) => apiPost<import('./types').MistakeOut>('/mistakes', payload),
  reviewQueue: (limit = 10) => apiGet<import('./types').MistakeOut[]>('/mistakes/review-queue', { limit }),
  detail: (id: string) => apiGet<import('./types').MistakeOut>(`/mistakes/${id}`),
  update: (id: string, payload: Partial<import('./types').MistakeOut>) =>
    apiPatch<import('./types').MistakeOut>(`/mistakes/${id}`, payload),
  resolve: (id: string, resolved: boolean) => apiPost<import('./types').MistakeOut>(`/mistakes/${id}/resolve`, { resolved }),
  remove: (id: string) => apiDelete<null>(`/mistakes/${id}`),
};

export const adminApi = {
  dashboard: () => apiGet<import('./types').AdminDashboardOut>('/admin/dashboard'),

  users: (query?: QueryParams) => apiGet<Page<import('./types').AdminUserItem>>('/admin/users', query),
  createUser: (payload: Record<string, unknown>) => apiPost<import('./types').AdminUserItem>('/admin/users', payload),
  updateUser: (id: string, payload: Record<string, unknown>) =>
    apiPatch<import('./types').AdminUserItem>(`/admin/users/${id}`, payload),
  deleteUser: (id: string) => apiDelete<null>(`/admin/users/${id}`),
  resetUserPassword: (id: string, new_password: string) =>
    apiPost<null>(`/admin/users/${id}/reset-password`, { new_password }),

  courses: (query?: QueryParams) => apiGet<Page<import('./types').CourseBrief>>('/admin/courses', query),
  createCourse: (payload: Record<string, unknown>) => apiPost<import('./types').CourseBrief>('/admin/courses', payload),
  updateCourse: (id: string, payload: Record<string, unknown>) =>
    apiPatch<import('./types').CourseBrief>(`/admin/courses/${id}`, payload),
  deleteCourse: (id: string) => apiDelete<null>(`/admin/courses/${id}`),

  problems: (query?: QueryParams) => apiGet<Page<import('./types').ProblemBrief>>('/admin/problems', query),
  createProblem: (payload: Record<string, unknown>) => apiPost<import('./types').ProblemBrief>('/admin/problems', payload),
  updateProblem: (id: string, payload: Record<string, unknown>) =>
    apiPatch<import('./types').ProblemBrief>(`/admin/problems/${id}`, payload),
  deleteProblem: (id: string) => apiDelete<null>(`/admin/problems/${id}`),

  projects: (query?: QueryParams) => apiGet<Page<import('./types').ProjectBrief>>('/admin/projects', query),
  createProject: (payload: Record<string, unknown>) => apiPost<import('./types').ProjectBrief>('/admin/projects', payload),
  updateProject: (id: string, payload: Record<string, unknown>) =>
    apiPatch<import('./types').ProjectBrief>(`/admin/projects/${id}`, payload),
  deleteProject: (id: string) => apiDelete<null>(`/admin/projects/${id}`),

  logsAudit: (query?: QueryParams) => apiGet<Page<import('./types').AuditLogOut>>('/admin/logs/audit', query),
  logsAiUsage: (query?: QueryParams) => apiGet<Page<import('./types').AIUsageLogOut>>('/admin/logs/ai-usage', query),
  /** 后端返回 ErrorLogGroup[]（非分页）。 */
  logsErrors: (query?: QueryParams) => apiGet<import('./types').ErrorLogGroup[]>('/admin/logs/errors', query),
  rejudge: (payload: { problem_id?: string; limit?: number }) =>
    apiPost<Record<string, unknown>>('/admin/maintenance/rejudge', payload),
};

export const healthApi = {
  health: () => apiGet<import('./types').HealthOut>('/health', undefined, { auth: false }),
  deps: () => apiGet<import('./types').HealthDepsOut>('/health/deps', undefined, { auth: false }),
  /** GET /api/health/enums —— 后端权威枚举字典，前端不再硬编码。 */
  enums: () => apiGet<import('./types').EnumDictionary>('/health/enums', undefined, { auth: false }),
};

/** 把可能失败的接口调用降级为 null，保证后端不可用时页面不白屏。 */
export async function safeCall<T>(fn: () => Promise<T>, fallback: T): Promise<T> {
  try {
    return await fn();
  } catch {
    return fallback;
  }
}
