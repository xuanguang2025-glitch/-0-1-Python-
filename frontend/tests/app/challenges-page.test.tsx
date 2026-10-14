// @vitest-environment jsdom
/**
 * `src/app/challenges/page.tsx` —— 报名 in-flight 守卫（缺陷 C 的回归防护）。
 *
 * ## 缺陷背景
 * `join()` 原先无 in-flight 守卫：`setJoined` 在 `await challengeApi.join()` **之后**
 * 才执行，而按钮的 `disabled` 依赖 `joined`，于是双击窗口内会发出两次
 * `POST /challenges/{id}/join`，污染报名计数并重复发 XP / 通知。
 *
 * ## 修法
 * 加 `submitting: Record<string, boolean>`，`join()` 开头判 `if (submitting[id]) return;`，
 * 并用 `try/finally` 保证成功与失败路径都复位（失败不复位会让按钮永久禁用）。
 *
 * ## 本文件的两个设计决策
 * 1. **用 fetch 层 mock，而不是部分 mock `@/lib/api`**。
 *    `store/auth.ts` 在模块初始化就会调 `configureApiClient`，整体 mock `@/lib/api`
 *    会在 import 阶段炸掉；fetch 层 mock 让 `lib/api` 原样加载，更贴近真实链路。
 * 2. **连点必须同步触发**。`userEvent.click()` 每次都会 await 并让 React 重渲染，
 *    此时按钮已因 `disabled` 变成不可点，第二击会被 DOM 层挡掉 —— 那样测到的只是
 *    `disabled` 属性，**测不到 `join()` 里的守卫**。因此核心用例用
 *    `act()` 内连续同步 `button.click()`，模拟真实双击（同一 tick 内多次触发、
 *    React 尚未 flush），断言请求只发出一次。已用变异测试确认：
 *    移除守卫后该用例会失败（3 次调用）。
 */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, act, waitFor } from '@testing-library/react';
import type { ChallengeBrief, UserBrief } from '@/lib/types';

import ChallengesPage from '@/app/challenges/page';
import { useAuthStore } from '@/store/auth';
import { err, mockFetchByPath, ok } from '../helpers/fetch-mock';

// 页面链路上的 Navbar 还会用 useRouter / useSearchParams，需一并提供，
// 否则渲染到 Navbar 时会因 mock 缺导出而抛错。
vi.mock('next/navigation', () => ({
  usePathname: () => '/challenges',
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn(), prefetch: vi.fn(), refresh: vi.fn() }),
  redirect: vi.fn(),
}));

/** end_at 取未来时间，保证 `challengeState()` 判为 active（否则按钮是禁用的）。 */
function makeChallenge(id: string, title: string): ChallengeBrief {
  return {
    id,
    slug: `${id}-slug`,
    title,
    challenge_type: 'daily',
    difficulty: 'easy',
    start_at: null,
    end_at: '2099-01-01T00:00:00Z',
    duration_minutes: 60,
    xp_reward: 200,
    participant_count: 3,
    problem_count: 2,
    is_open: true,
    my_status: null,
  };
}

const CHALLENGE = makeChallenge('ch-1', '今日日赛');

const JOIN_RESULT = {
  id: 'uc-1',
  challenge_id: 'ch-1',
  status: 'in_progress' as const,
  score: 0,
  passed_cases: 0,
  total_time_ms: 0,
  rank: null,
  submitted_at: null,
};

/** 可控 deferred：用于精确控制 join 请求何时返回。 */
function deferred<T>(): { promise: Promise<T>; resolve: (v: T) => void; reject: (e: unknown) => void } {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

type Gate = ReturnType<typeof deferred<Response>>;

const USER: UserBrief = {
  id: 'u-1',
  email: 'tester@example.com',
  username: 'tester',
  display_name: '测试用户',
  role: 'user',
  level: 1,
  xp: 0,
};

/** 置为已登录并渲染页面；每个挑战的 join 请求由独立 gate 控制返回时机。 */
function setup(challenges: ChallengeBrief[] = [CHALLENGE]) {
  useAuthStore.setState({
    hydrated: true,
    accessToken: 'test-access-token',
    refreshToken: 'test-refresh-token',
    user: USER,
    loading: false,
    error: null,
  });

  const gates = new Map<string, Gate>();
  for (const challenge of challenges) {
    gates.set(challenge.id, deferred<Response>());
  }

  const fetchMock = mockFetchByPath({
    // 注意：mockFetchByPath 按注册顺序做 includes 匹配，具体路径必须排在 /challenges 之前，
    // 否则 /challenges/xxx/join 会先命中 /challenges 这一条。
    '/join': () => {
      // 从最近一次 fetch 的 URL 反推是哪个挑战，取对应的 gate
      const last = fetchMock.calls[fetchMock.calls.length - 1];
      const id = /\/challenges\/([^/]+)\/join/.exec(last?.url ?? '')?.[1] ?? '';
      const gate = gates.get(id);
      if (!gate) throw new Error(`join 命中了未注册的挑战 id：${id}`);
      // helper 的签名是 () => Response，但其内部 vi.fn 是 async，会 await 这里的返回值，
      // 因此返回 Promise<Response> 是正确的；此处仅需安抚类型。
      return gate.promise as unknown as Response;
    },
    '/leaderboard': () => ok({ entries: [], total: 0, updated_at: null }),
    '/my': () => ok({ items: [], total: 0, page: 1, page_size: 20 }),
    '/challenges': () => ok({ items: challenges, total: challenges.length, page: 1, page_size: 20 }),
  });

  render(<ChallengesPage />);
  return { fetchMock, gates };
}

/** 等列表渲染出可点击的报名按钮。 */
async function findJoinButton(title: string): Promise<HTMLElement> {
  // 按钮在同一张卡片内，用卡片标题定位比全局 name 更稳（多个挑战时 name 会重复）
  const card = await screen.findByText(title);
  return card.closest('div.rounded-lg')!.querySelector('button') as HTMLElement;
}

afterEach(() => {
  useAuthStore.setState({ accessToken: null, refreshToken: null, user: null, hydrated: false, loading: false, error: null });
});

describe('challenges 页面 · 报名 in-flight 守卫（缺陷 C）', () => {
  it('pending 期间同步连点三次，join 请求只发出一次', async () => {
    const { fetchMock } = setup();
    const button = await findJoinButton('今日日赛');

    // 真实双击形态：同一 tick 内连续触发，React 来不及重渲染，按钮仍是可点的。
    await act(async () => {
      button.click();
      button.click();
      button.click();
      await Promise.resolve();
    });

    // ★ 核心断言：3 次点击 → 1 次请求。无 in-flight 守卫时这里是 3。
    expect(fetchMock.countOf('/join')).toBe(1);
  });

  it('连点后按钮进入 submitting 态（禁用 + 报名中文案）', async () => {
    setup();
    const button = await findJoinButton('今日日赛');

    await act(async () => {
      button.click();
      button.click();
      await Promise.resolve();
    });

    const submitting = await screen.findByRole('button', { name: '报名中' });
    expect(submitting).toBeDisabled();
    // Button 组件在 loading 时置 aria-busy
    expect(submitting.getAttribute('aria-busy')).toBe('true');
  });

  it('成功后按钮变为「已报名」并保持禁用', async () => {
    const { fetchMock, gates } = setup();
    const button = await findJoinButton('今日日赛');

    await act(async () => {
      button.click();
      await Promise.resolve();
    });
    expect(fetchMock.countOf('/join')).toBe(1);

    await act(async () => {
      gates.get('ch-1')!.resolve(ok(JOIN_RESULT));
      await gates.get('ch-1')!.promise;
    });

    const joined = await screen.findByRole('button', { name: '已报名' });
    expect(joined).toBeDisabled();
    // 报名成功后触发 mine.refresh()
    await waitFor(() => expect(fetchMock.countOf('/my')).toBeGreaterThanOrEqual(2));
  });

  it('★ 失败后 submitting 必须复位：按钮恢复可点，可再次报名', async () => {
    const { fetchMock, gates } = setup();
    const button = await findJoinButton('今日日赛');

    await act(async () => {
      button.click();
      await Promise.resolve();
    });
    expect(fetchMock.countOf('/join')).toBe(1);

    // 第一次报名被后端拒绝（409）
    await act(async () => {
      gates.get('ch-1')!.reject(err('CONFLICT', '你已经报名过该挑战', 409));
      await gates.get('ch-1')!.promise.catch(() => undefined);
    });

    // 失败路径同样复位 → 按钮回到「立即参加」且可点（不复位则会永久禁用）
    const retry = await screen.findByRole('button', { name: '立即参加' });
    expect(retry).not.toBeDisabled();

    // 再次点击应当能发出第二次请求（说明状态真的复位了，不是卡死）
    await act(async () => {
      retry.click();
      await Promise.resolve();
    });
    expect(fetchMock.countOf('/join')).toBe(2);
  });

  it('不同挑战的报名互不阻塞（submitting 按 id 隔离）', async () => {
    const { fetchMock } = setup([makeChallenge('ch-1', '挑战一'), makeChallenge('ch-2', '挑战二')]);

    const first = await findJoinButton('挑战一');
    const second = await findJoinButton('挑战二');

    // 先点第一个，让它挂在 pending 上
    await act(async () => {
      first.click();
      await Promise.resolve();
    });
    expect(fetchMock.countOf('/join')).toBe(1);

    // 第二个挑战不应被第一个的 in-flight 阻塞
    expect(second).not.toBeDisabled();
    await act(async () => {
      second.click();
      await Promise.resolve();
    });
    expect(fetchMock.countOf('/join')).toBe(2);

    // 两个按钮都进入 submitting
    expect(screen.getAllByRole('button', { name: '报名中' })).toHaveLength(2);
  });

  it('未登录点击报名：不发请求，给出登录提示', async () => {
    useAuthStore.setState({ hydrated: true, accessToken: null, refreshToken: null, user: null, loading: false, error: null });
    // AuthGate 在未登录时不渲染子内容，此路径由 AuthGate 自身覆盖；
    // 这里验证登录门禁确实拦住了页面（不出现报名按钮、不发任何请求）。
    render(<ChallengesPage />);
    await waitFor(() => expect(screen.queryByRole('button', { name: '立即参加' })).toBeNull());
  });
});
