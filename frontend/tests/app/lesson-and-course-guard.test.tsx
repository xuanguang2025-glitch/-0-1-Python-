// @vitest-environment jsdom
/**
 * `courses/[slug]/course-detail-view.tsx` 与 `lesson/[id]/lesson-view.tsx` —— 重复提交防护。
 *
 * 这两页是 **view 组件**（命名导出 + props），不是 page.tsx：
 * - `CourseDetailView({ slug })` → `courseApi.enroll()`
 * - `LessonView({ lessonId })`   → `lessonApi.quiz()` / `lessonApi.complete()`
 *
 * 三处原先都是纯 `useState`（`enrolling` / `completing` / `quizSubmitting`），
 * 只有 loading 效果、没有守卫语义；现已接入 `useSubmitGuard`
 * （性质验证见 `tests/hooks/useSubmitGuard.test.tsx`）。
 *
 * 连点一律用同步 `button.click()`，不用 `userEvent.click()` —— 后者每次都会 await
 * 并让 React 重渲染，第二击会被 DOM 的 disabled 挡掉，只能测到 disabled 属性、
 * 测不到守卫，是假绿。
 *
 * 错误路径用 `resolve(非2xx)` 而非 `reject`：真实链路里 fetch 正常 resolve，
 * 由 `lib/api` 的 parseResponse 构造 `ApiRequestError`。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act, fireEvent, waitFor } from '@testing-library/react';
import type { CompleteLessonResult, CourseDetail, LessonDetail, UserBrief } from '@/lib/types';

import { CourseDetailView } from '@/app/courses/[slug]/course-detail-view';
import { LessonView } from '@/app/lesson/[id]/lesson-view';
import { useAuthStore } from '@/store/auth';
import { err, mockFetchByPath, ok } from '../helpers/fetch-mock';

vi.mock('next/navigation', () => ({
  usePathname: () => '/courses',
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn(), prefetch: vi.fn(), refresh: vi.fn() }),
  redirect: vi.fn(),
}));

const USER: UserBrief = {
  id: 'u-1',
  email: 'tester@example.com',
  username: 'tester',
  display_name: '测试用户',
  role: 'user',
  level: 1,
  xp: 0,
};

const COURSE_DETAIL: CourseDetail = {
  course: {
    id: 'c-1',
    slug: 'stage-1',
    stage_no: 1,
    title: 'Python 基础',
    subtitle: null,
    level: 'beginner',
    icon: null,
    cover_url: null,
    estimated_hours: 8,
    lesson_count: 2,
    order_index: 1,
    is_published: true,
    progress_percent: 0,
  },
  chapters: [],
  // progress 为 null → 页面渲染「加入我的课程」按钮
  progress: null,
};

const PROGRESS = {
  id: 'lp-1',
  lesson_id: 'les-1',
  status: 'in_progress',
  progress_percent: 50,
  time_spent_seconds: 120,
  attempt_count: 1,
  started_at: '2026-09-26T00:00:00Z',
  completed_at: null,
  updated_at: null,
};

/** 带一道随堂练习的课时（quiz 提交按钮仅在 quiz 非空时渲染）。 */
const LESSON: LessonDetail = {
  id: 'les-1',
  chapter_id: 'ch-1',
  slug: 'lesson-1',
  title: '第一课：变量',
  summary: null,
  content_md: '# 变量',
  lesson_type: 'practice',
  difficulty: 'easy',
  estimated_minutes: 10,
  order_index: 1,
  xp_reward: 20,
  has_playground: false,
  starter_code: null,
  solution_code: null,
  quiz_json: [{ id: 'q1', qid: 'q1', question: '1 + 1 = ?', options: ['1', '2'], answer: '2' }],
  topics: [],
  prev: null,
  next: null,
  chapter_title: '第一章',
  chapter_index: 1,
  lesson_index: 1,
  total_lessons: 2,
  prev_lesson: null,
  next_lesson: null,
  progress: PROGRESS,
  course_id: 'c-1',
  course_title: 'Python 基础',
  course_slug: 'stage-1',
  course_outline: [],
};

const COMPLETE_RESULT: CompleteLessonResult = {
  progress: { ...PROGRESS, completed_at: '2026-09-27T00:00:00Z', status: 'completed' },
  xp_earned: 20,
  level_up: false,
  unlocked_achievements: [],
};

/** 可控 deferred。 */
function deferred<T>(): { promise: Promise<T>; resolve: (v: T) => void } {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
}

type FetchMock = ReturnType<typeof mockFetchByPath>;

function login(): void {
  useAuthStore.setState({
    hydrated: true,
    accessToken: 'test-access-token',
    refreshToken: 'test-refresh-token',
    user: USER,
    loading: false,
    error: null,
  });
}

/** 课程详情页：enroll 走 gate。 */
function setupCourse(options: { enrollError?: Response } = {}) {
  const enrollGate = deferred<Response>();

  const fetchMock = mockFetchByPath({
    '/enroll': () => (options.enrollError ?? enrollGate.promise) as unknown as Response,
    '/courses': () => ok(COURSE_DETAIL),
  });

  login();
  render(<CourseDetailView slug="stage-1" />);
  return { fetchMock, enrollGate };
}

/** 课时页：complete / quiz 各自走 gate。 */
function setupLesson(options: { completeError?: Response; quizError?: Response; lesson?: LessonDetail } = {}) {
  const completeGate = deferred<Response>();
  const quizGate = deferred<Response>();

  const fetchMock = mockFetchByPath({
    '/complete': () => (options.completeError ?? completeGate.promise) as unknown as Response,
    '/quiz': () => (options.quizError ?? quizGate.promise) as unknown as Response,
    '/lessons/les-1': () => ok(options.lesson ?? LESSON),
  });

  login();
  render(<LessonView lessonId="les-1" />);
  return { fetchMock, completeGate, quizGate };
}

/** 按可见文案找按钮。 */
function buttonByText(text: string | RegExp): HTMLElement {
  const found = Array.from(document.querySelectorAll('button')).find((b) => {
    const t = (b.textContent ?? '').trim();
    return typeof text === 'string' ? t === text : text.test(t);
  });
  if (!found) throw new Error(`未找到按钮 ${String(text)}`);
  return found as HTMLElement;
}

/** 统计某路径 + method 的请求数。 */
function countCalls(fetchMock: FetchMock, path: string, method?: string): number {
  return fetchMock.calls.filter((c) => c.url.includes(path) && (!method || c.init?.method === method)).length;
}

/** 切到随堂练习 Tab。 */
async function openQuizTab(): Promise<void> {
  await act(async () => {
    screen.getByRole('tab', { name: /随堂练习/ }).click();
    await Promise.resolve();
  });
}

beforeEach(() => {
  // setup.ts 的 afterEach 会 useRealTimers 还原 beforeAll 的假 Date，逐用例重设
  // （markComplete 用 Date.now() 计算 time_spent）
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(new Date('2026-09-27T10:00:00Z'));
});

afterEach(() => {
  useAuthStore.setState({ accessToken: null, refreshToken: null, user: null, hydrated: false, loading: false, error: null });
  vi.restoreAllMocks();
});

describe('course-detail-view · enroll 重复提交防护', () => {
  it('★ enroll：pending 期间同步连点三次，只发出一次 POST', async () => {
    const { fetchMock, enrollGate } = setupCourse();
    await screen.findByRole('button', { name: /加入我的课程/ });

    const btn = buttonByText(/加入我的课程/);
    await act(async () => {
      btn.click();
      btn.click();
      btn.click();
      await Promise.resolve();
    });

    expect(countCalls(fetchMock, '/courses/c-1/enroll', 'POST')).toBe(1);
    enrollGate.resolve(ok({}));
    await enrollGate.promise;
  });

  it('enroll 失败后复位：按钮恢复可点，可再次报名', async () => {
    const { fetchMock } = setupCourse({ enrollError: err('SERVER_ERROR', '报名服务异常', 500) });
    await screen.findByRole('button', { name: /加入我的课程/ });

    await act(async () => {
      buttonByText(/加入我的课程/).click();
      await Promise.resolve();
    });
    expect(countCalls(fetchMock, '/courses/c-1/enroll', 'POST')).toBe(1);

    // 等待失败落地
    await waitFor(() => expect(buttonByText(/加入我的课程/)).not.toBeDisabled());

    await act(async () => {
      buttonByText(/加入我的课程/).click();
      await Promise.resolve();
    });
    expect(countCalls(fetchMock, '/courses/c-1/enroll', 'POST')).toBe(2);
  });
});

describe('lesson-view · complete 重复提交防护', () => {
  it('★ complete：pending 期间同步连点三次，只发出一次 POST', async () => {
    const { fetchMock, completeGate } = setupLesson();
    await screen.findByRole('button', { name: /标记为已完成/ });

    const btn = buttonByText(/标记为已完成/);
    await act(async () => {
      btn.click();
      btn.click();
      btn.click();
      await Promise.resolve();
    });

    expect(countCalls(fetchMock, '/lessons/les-1/complete', 'POST')).toBe(1);
    completeGate.resolve(ok(COMPLETE_RESULT));
    await completeGate.promise;
  });

  it('complete 失败后复位：按钮恢复可点，可再次提交', async () => {
    const { fetchMock } = setupLesson({ completeError: err('SERVER_ERROR', '提交失败', 500) });
    await screen.findByRole('button', { name: /标记为已完成/ });

    await act(async () => {
      buttonByText(/标记为已完成/).click();
      await Promise.resolve();
    });
    expect(countCalls(fetchMock, '/lessons/les-1/complete', 'POST')).toBe(1);

    await waitFor(() => expect(buttonByText(/标记为已完成/)).not.toBeDisabled());

    await act(async () => {
      buttonByText(/标记为已完成/).click();
      await Promise.resolve();
    });
    expect(countCalls(fetchMock, '/lessons/les-1/complete', 'POST')).toBe(2);
  });
});

describe('lesson-view · quiz 重复提交防护', () => {
  it('★ quiz：pending 期间同步连点三次，只发出一次 POST', async () => {
    const { fetchMock, quizGate } = setupLesson();
    await screen.findByRole('tab', { name: /随堂练习/ });
    await openQuizTab();

    const btn = await screen.findByRole('button', { name: '提交答案' });
    await act(async () => {
      btn.click();
      btn.click();
      btn.click();
      await Promise.resolve();
    });

    expect(countCalls(fetchMock, '/lessons/les-1/quiz', 'POST')).toBe(1);
    quizGate.resolve(ok({ correct_count: 1, total: 1, passed: true, details: [] }));
    await quizGate.promise;
  });

  it('quiz 失败后复位：按钮恢复可点，可再次提交', async () => {
    const { fetchMock } = setupLesson({ quizError: err('VALIDATION', '答案格式错误', 422) });
    await screen.findByRole('tab', { name: /随堂练习/ });
    await openQuizTab();

    const btn = await screen.findByRole('button', { name: '提交答案' });
    await act(async () => {
      btn.click();
      await Promise.resolve();
    });
    expect(countCalls(fetchMock, '/lessons/les-1/quiz', 'POST')).toBe(1);

    await waitFor(() => expect(screen.getByRole('button', { name: '提交答案' })).not.toBeDisabled());

    await act(async () => {
      screen.getByRole('button', { name: '提交答案' }).click();
      await Promise.resolve();
    });
    expect(countCalls(fetchMock, '/lessons/les-1/quiz', 'POST')).toBe(2);
  });

  it('quiz 为空的课时不渲染提交按钮（守卫无入口，不会误触）', async () => {
    setupLesson({ lesson: { ...LESSON, quiz_json: [] } });
    await screen.findByRole('tab', { name: /随堂练习/ });
    await openQuizTab();

    expect(screen.queryByRole('button', { name: '提交答案' })).toBeNull();
  });
});
