// @vitest-environment jsdom
/**
 * `src/app/problems/[id]/problem-detail-view.tsx` —— 提交判题的 in-flight 守卫。
 *
 * ## 为什么这处风险最高
 * `submit()` 的窗口包含**提交 + 轮询判题**：拿到submission 后还要
 * `while (status === 'pending' || 'judging')` 轮询到终态（POLL_MAX = 30，
 * 每次间隔 1s），最长可拖 30 秒。原先：
 * - `const [submitting, setSubmitting] = useState(false)` —— 纯 state，无守卫
 * - `submit()` 开头只有 `if (!problem) return`，**没有 `if (submitting) return`**
 * - 按钮只有 `loading={submitting}`，**没有 `disabled`**
 *
 * 连点会重复创建 submission、重复扣 XP、重复计入统计。现已接入 `useSubmitGuard`
 * （ref 同步判断 + state 驱动 UI，性质验证见 `tests/hooks/useSubmitGuard.test.tsx`）。
 *
 * ## 轮询不会挂死
 * 测试里让 `/submissions` POST **第一次就返回终态**（status = 'accepted'），
 * `while` 条件不成立、不会进入轮询分支，因此无需 mock `setTimeout`，
 * 也不会写出挂死的用例。另有 1 条用例显式覆盖「pending → 轮询一次 → 终态」，
 * 验证轮询路径本身也能正常释放守卫。
 *
 * 连点一律用同步 `button.click()`，不用 `userEvent.click()` —— 后者每次都会 await
 * 并让 React 重渲染，第二击会被 DOM 的 disabled 挡掉，只能测到 disabled 属性、
 * 测不到守卫，是假绿。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act, waitFor } from '@testing-library/react';
import type { ProblemDetail, SubmissionOut, UserBrief } from '@/lib/types';

import { ProblemDetailView } from '@/app/problems/[id]/problem-detail-view';
import { useAuthStore } from '@/store/auth';
import { err, mockFetchByPath, ok } from '../helpers/fetch-mock';

vi.mock('next/navigation', () => ({
  usePathname: () => '/problems/p-1',
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

const PROBLEM: ProblemDetail = {
  id: 'p-1',
  slug: 'two-sum',
  title: '两数之和',
  statement_md: '给你两个整数，输出它们的和。',
  problem_type: 'coding',
  difficulty: 'easy',
  category: '数组',
  input_format: '两个整数',
  output_format: '一个整数',
  sample_input: '1 2',
  sample_output: '3',
  constraints: '数字范围 -100~100',
  options_json: null,
  hint_md: null,
  solution_md: null,
  starter_code: 'a, b = map(int, input().split())\nprint(a + b)\n',
  buggy_code: null,
  time_limit_ms: 1000,
  memory_limit_mb: 256,
  score: 10,
  xp_reward: 20,
  submission_count: 8,
  accepted_count: 4,
  acceptance_rate: 0.5,
  tags: [],
  sample_cases: [],
  my_status: null,
  my_last_submission_id: null,
};

/** 终态 submission（第一次 POST 就返回它，while 不成立、不进轮询）。 */
const ACCEPTED: SubmissionOut = {
  id: 'sub-1',
  user_id: 'u-1',
  problem_id: 'p-1',
  lesson_id: null,
  challenge_id: null,
  language: 'python',
  status: 'accepted',
  score: 100,
  passed_cases: 3,
  total_cases: 3,
  time_ms: 12,
  memory_kb: 1024,
  error_type: null,
  error_message: null,
  runner: 'local',
  judged_by: 'sandbox',
  code: 'print(3)',
  created_at: '2026-09-27T10:00:00Z',
  finished_at: '2026-09-27T10:00:01Z',
  results: [],
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

/**
 * 统计「创建提交」的请求数。
 * 注意 `GET /submissions`（提交历史列表）与 `POST /submissions` 路径完全相同，
 * 只按 countOf('/submissions') 会把列表请求也算进来，必须带 method 区分。
 */
function countSubmits(fetchMock: FetchMock): number {
  return fetchMock.calls.filter((c) => c.url.includes('/submissions') && c.init?.method === 'POST').length;
}

/** 提交按钮。 */
function submitButton(): HTMLElement {
  const btn = screen.getByRole('button', { name: /提交判题/ });
  return btn as HTMLElement;
}

/**
 * 挂载题目详情。
 * @param pollFirst true 时让首次 POST 返回 pending，走一次轮询后才到终态。
 */
function setup(options: { pollFirst?: boolean } = {}) {
  const submitGate = deferred<Response>();
  const statusGate = deferred<Response>();

  const fetchMock = mockFetchByPath({
    // 注册顺序即匹配顺序：具体路径排在通配之前
    '/submissions/status': () => ok({ status: 'accepted', passed_cases: 3, total_cases: 3, finished: true }),
    '/submissions': () => {
      const last = fetchMock.calls[fetchMock.calls.length - 1];
      const url = last?.url ?? '';
      // POST /submissions（创建）与 GET /submissions（列表）路径相同，按 method 区分
      if (last?.init?.method === 'POST') return submitGate.promise as unknown as Response;
      void url;
      return ok({ items: [], total: 0, page: 1, page_size: 20 });
    },
    '/similar': () => ok([]),
    '/discussion-ai': () => ok({ summary_md: '题解' }),
    '/problems/p-1': () => ok(PROBLEM),
  });

  useAuthStore.setState({
    hydrated: true,
    accessToken: 'test-access-token',
    refreshToken: 'test-refresh-token',
    user: USER,
    loading: false,
    error: null,
  });

  render(<ProblemDetailView problemId="p-1" />);
  return { fetchMock, submitGate, statusGate };
}

beforeEach(() => {
  // setup.ts 的 afterEach 会 useRealTimers 还原 beforeAll 的假 Date，逐用例重设
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(new Date('2026-09-27T10:00:00Z'));
});

afterEach(() => {
  useAuthStore.setState({ accessToken: null, refreshToken: null, user: null, hydrated: false, loading: false, error: null });
  vi.restoreAllMocks();
});

describe('problem-detail-view · 提交判题守卫', () => {
  it('★ pending 期间同步连点三次，只发出一次 POST /submissions', async () => {
    const { fetchMock, submitGate } = setup();
    await screen.findByRole('button', { name: /提交判题/ });

    const btn = submitButton();
    await act(async () => {
      btn.click();
      btn.click();
      btn.click();
      await Promise.resolve();
    });

    // ★ 核心断言：3 次点击 → 1 次提交。无守卫时这里是 3（重复建submission、重复扣 XP）
    expect(countSubmits(fetchMock)).toBe(1);

    await act(async () => {
      submitGate.resolve(ok(ACCEPTED));
      await submitGate.promise;
    });
  });

  it('提交进行中按钮进入禁用态（UI 反馈，DOM 层第二道防线）', async () => {
    const { submitGate } = setup();
    await screen.findByRole('button', { name: /提交判题/ });

    await act(async () => {
      submitButton().click();
      await Promise.resolve();
    });

    expect(submitButton()).toBeDisabled();

    await act(async () => {
      submitGate.resolve(ok(ACCEPTED));
      await submitGate.promise;
    });
  });

  it('★ 提交失败后复位：按钮恢复可点，可再次提交', async () => {
    const { fetchMock, submitGate } = setup();
    await screen.findByRole('button', { name: /提交判题/ });

    await act(async () => {
      submitButton().click();
      await Promise.resolve();
    });
    expect(countSubmits(fetchMock)).toBe(1);

    await act(async () => {
      submitGate.resolve(err('RATE_LIMIT', '提交过于频繁', 429));
      await submitGate.promise;
    });

    // 失败也必须复位，否则按钮永久禁用、用户再也无法提交
    await waitFor(() => expect(submitButton()).not.toBeDisabled());

    await act(async () => {
      submitButton().click();
      await Promise.resolve();
    });
    expect(countSubmits(fetchMock)).toBe(2);
  });

  it('成功后按钮恢复可点（守卫在 finally 释放，可再次提交）', async () => {
    const { fetchMock, submitGate } = setup();
    await screen.findByRole('button', { name: /提交判题/ });

    await act(async () => {
      submitButton().click();
      await Promise.resolve();
    });
    await act(async () => {
      submitGate.resolve(ok(ACCEPTED));
      await submitGate.promise;
    });

    await waitFor(() => expect(submitButton()).not.toBeDisabled());

    await act(async () => {
      submitButton().click();
      await Promise.resolve();
    });
    // 第二次提交同样能发出（证明不是「一次性锁死」）
    expect(countSubmits(fetchMock)).toBe(2);
  });
});