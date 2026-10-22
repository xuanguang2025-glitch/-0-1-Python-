// @vitest-environment jsdom
/**
 * `src/app/problems/page.tsx` —— 题库列表页（331 行）。
 *
 * 覆盖重点：筛选参数是否正确进入请求 URL、分页、以及「随机挑题」的成功/失败两条路径
 * （失败必须给用户可见提示，不能静默）。
 *
 * ## 为什么用 fetch 层 mock 而不是部分 mock `@/lib/api`
 * `store/auth.ts` 在模块初始化就会调 `configureApiClient`，整体 mock `@/lib/api`
 * 会在 import 阶段炸掉；fetch 层 mock 让 `lib/api` 原样加载，更贴近真实链路。
 *
 * ## 断言按代码事实写，不按设计文档
 * - `DIFFICULTY_LABEL` 实为 easy='入门' / medium='简单' / hard='中等' / expert='困难'
 * - `formatPercent(0.5, 0)` 返回 `'50%'`（不是 `'50.0%'`）
 * - `apiGet` 的 query 序列化会**丢弃** undefined / null / 空字符串（`lib/api.ts:78`），
 *   所以「状态=all」时请求里不应出现 status 参数
 * - 题库列表已对未登录用户公开：登录态只影响「做题状态筛选」等个人能力（不再整页门禁）
 * - `setup.ts` 只 fake 了 Date/performance，`setTimeout` 是真实的，
 *   所以防抖测试用真实等待而非 `advanceTimersByTime`
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act, fireEvent, waitFor, within } from '@testing-library/react';
import type { ProblemBrief, TagOut, UserBrief } from '@/lib/types';

import ProblemsPage from '@/app/problems/page';
import { useAuthStore } from '@/store/auth';
import { useUiStore } from '@/store/ui';
import { err, mockFetchByPath, ok } from '../helpers/fetch-mock';

vi.mock('next/navigation', () => ({
  usePathname: () => '/problems',
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn(), prefetch: vi.fn(), refresh: vi.fn() }),
  redirect: vi.fn(),
}));

/** jsdom 的页面 origin（vitest.config 里固定为这个）。 */
const BASE_URL = 'http://localhost:3000';

const USER: UserBrief = {
  id: 'u-1',
  email: 'tester@example.com',
  username: 'tester',
  display_name: '测试用户',
  role: 'user',
  level: 1,
  xp: 0,
};

function makeProblem(id: string, title: string, overrides: Partial<ProblemBrief> = {}): ProblemBrief {
  return {
    id,
    slug: id,
    title,
    problem_type: 'algorithm',
    difficulty: 'easy',
    category: '数组',
    score: 10,
    xp_reward: 20,
    submission_count: 100,
    accepted_count: 50,
    acceptance_rate: 0.5,
    tags: [],
    my_status: null,
    ...overrides,
  };
}

const FILTERS = {
  types: [{ value: 'algorithm', label: '算法', count: 12 }],
  difficulties: [{ value: 'easy', label: '入门', count: 8 }],
  categories: [{ value: '数组', label: '数组', count: 5 }],
  tags: [] as TagOut[],
};

/** 可控 deferred。 */
function deferred<T>(): { promise: Promise<T>; resolve: (v: T) => void; reject: (e: unknown) => void } {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

type ListQuery = { items: ProblemBrief[]; total: number; page: number; pages: number };
type FetchMock = ReturnType<typeof mockFetchByPath>;

interface SetupOptions {
  items?: ProblemBrief[];
  pages?: number;
  total?: number;
  /** 非空则列表请求直接返回该错误响应（用于错误态用例）。 */
  listError?: Response;
}

/** 挂载页面。列表默认即时返回，只有 random 走 gate 便于控制成功/失败。 */
function setup(options: SetupOptions = {}) {
  const items = options.items ?? [makeProblem('p-1', '两数之和'), makeProblem('p-2', '反转链表')];
  const pages = options.pages ?? 1;
  const total = options.total ?? items.length;

  const randomGate = deferred<Response>();

  const fetchMock = mockFetchByPath({
    // 注册顺序即匹配顺序：具体路径必须排在 /problems 之前
    '/problems/filters': () => ok(FILTERS),
    '/problems/random': () => randomGate.promise as unknown as Response,
    '/problems': () =>
      options.listError ?? ok({ items, total, page: 1, pages } as ListQuery),
  });

  useAuthStore.setState({
    hydrated: true,
    accessToken: 'test-access-token',
    refreshToken: 'test-refresh-token',
    user: USER,
    loading: false,
    error: null,
  });

  render(<ProblemsPage />);
  return { fetchMock, randomGate, items };
}

/** 最近一次列表请求的 URL（排除 filters / random）。 */
function lastListUrl(fetchMock: FetchMock): URL {
  const calls = fetchMock.calls.filter(
    (c) => c.url.includes('/problems') && !c.url.includes('/filters') && !c.url.includes('/random'),
  );
  // 实际请求是相对路径（/api/problems?...），new URL 需要 base
  return new URL(calls[calls.length - 1]!.url, BASE_URL);
}

beforeEach(() => {
  // toast 存在全局 store 里，逐用例清空避免互相污染
  useUiStore.setState({ toasts: [] });
  // 成功路径会写 window.location.href，jsdom 未实现导航，这里替换成可写对象
  Object.defineProperty(window, 'location', {
    configurable: true,
    writable: true,
    value: { ...window.location, href: 'http://localhost:3000/problems' },
  });
});

afterEach(() => {
  useAuthStore.setState({ accessToken: null, refreshToken: null, user: null, hydrated: false, loading: false, error: null });
  vi.restoreAllMocks();
});

describe('problems · 列表渲染', () => {
  it('渲染题目标题、难度、题型与通过率（按代码事实断言）', async () => {
    setup();

    const title = await screen.findByText('两数之和');
    // 用 within 限定到该题所在行：难度文案在 Select 选项与移动端/桌面两处Badge 里都会出现
    const row = title.closest('div.grid') as HTMLElement;
    // DIFFICULTY_LABEL.easy 实为「入门」（不是「简单」）
    // 注意：难度/题型在同一行会渲染两次（移动端 lg:hidden 版 + 桌面端版），
    // CSS 隐藏但都在 DOM 里，所以用 getAllByText 断言「至少出现一次」。
    expect(within(row).getAllByText('入门').length).toBeGreaterThanOrEqual(1);
    // PROBLEM_TYPE_LABEL.algorithm 实为「算法题」（不是「算法」）
    expect(within(row).getAllByText('算法题').length).toBeGreaterThanOrEqual(1);
    // formatPercent(0.5, 0) → '50%'（通过率只渲染一次）
    expect(within(row).getByText('50%')).toBeTruthy();
  });

  it('已通过（accepted）的题目显示对勾而非序号', async () => {
    setup({
      items: [makeProblem('p-1', '已做的题', { my_status: 'accepted' }), makeProblem('p-2', '没做的题')],
      total: 2,
    });

    expect(await screen.findByText('已做的题')).toBeTruthy();
    expect(screen.getByText('没做的题')).toBeTruthy();
    // 未通过的第 2 题显示序号（(page-1)*PAGE_SIZE + index + 1 = 2）
    expect(screen.getByText('2')).toBeTruthy();
    // 已通过的题不再显示序号 1
    expect(screen.queryByText('1')).toBeNull();
  });

  it('列表加载失败 → 渲染 ErrorState 且文案来自后端错误信息', async () => {
    setup({ listError: err('SERVER_ERROR', '服务异常', 500) });

    expect(await screen.findByText('题库加载失败')).toBeTruthy();
    expect(screen.getByText('服务异常')).toBeTruthy();
    expect(screen.getByRole('button', { name: /重试|重新加载/ })).toBeTruthy();
  });

  it('空列表 → 渲染空态而非报错', async () => {
    setup({ items: [], total: 0 });

    expect(await screen.findByText('没有符合条件的题目')).toBeTruthy();
  });
});

describe('problems · 筛选参数进入请求', () => {
  it('初始请求携带默认筛选（status=all 不应出现 status 参数）', async () => {
    const { fetchMock } = setup();
    await screen.findByText('两数之和');

    const url = lastListUrl(fetchMock);
    expect(url.searchParams.get('sort')).toBe('-created_at');
    expect(url.searchParams.get('page')).toBe('1');
    expect(url.searchParams.get('page_size')).toBe('20');
    // 空值参数会被 api 层丢弃
    expect(url.searchParams.get('status')).toBeNull();
    expect(url.searchParams.get('keyword')).toBeNull();
    expect(url.searchParams.get('difficulty')).toBeNull();
  });

  it('切换难度 → 请求带上 difficulty 且页码重置为 1', async () => {
    const { fetchMock } = setup({ pages: 3, total: 60 });
    await screen.findByText('两数之和');

    // 先翻到第 2 页
    await act(async () => {
      screen.getByRole('button', { name: /下一页/ }).click();
      await Promise.resolve();
    });
    await waitFor(() => expect(lastListUrl(fetchMock).searchParams.get('page')).toBe('2'));

    // 再改难度：应重置回第 1 页
    const difficultySelect = screen.getAllByRole('combobox')[0] as HTMLSelectElement;
    await act(async () => {
      fireEvent.change(difficultySelect, { target: { value: 'easy' } });
      await Promise.resolve();
    });

    await waitFor(() => {
      const url = lastListUrl(fetchMock);
      expect(url.searchParams.get('difficulty')).toBe('easy');
      expect(url.searchParams.get('page')).toBe('1');
    });
  });

  it('状态切到「未解决」→ 请求带 status=unsolved', async () => {
    const { fetchMock } = setup();
    await screen.findByText('两数之和');

    // 顺序：难度 / 分类 / 题型 / 状态 / 排序
    const statusSelect = screen.getAllByRole('combobox')[3] as HTMLSelectElement;
    await act(async () => {
      fireEvent.change(statusSelect, { target: { value: 'unsolved' } });
      await Promise.resolve();
    });

    await waitFor(() => expect(lastListUrl(fetchMock).searchParams.get('status')).toBe('unsolved'));
  });

  it('切换排序 → 请求带 sort', async () => {
    const { fetchMock } = setup();
    await screen.findByText('两数之和');

    const sortSelect = screen.getAllByRole('combobox')[4] as HTMLSelectElement;
    await act(async () => {
      fireEvent.change(sortSelect, { target: { value: 'difficulty' } });
      await Promise.resolve();
    });

    await waitFor(() => expect(lastListUrl(fetchMock).searchParams.get('sort')).toBe('difficulty'));
  });

  it('输入关键词 → 防抖 300ms 后请求带 keyword', async () => {
    const { fetchMock } = setup();
    await screen.findByText('两数之和');

    await act(async () => {
      fireEvent.change(screen.getByPlaceholderText('搜索题目名称或关键词'), { target: { value: '链表' } });
      await Promise.resolve();
    });

    // 防抖窗口内不应重新请求
    expect(lastListUrl(fetchMock).searchParams.get('keyword')).toBeNull();

    // 真实等待越过 300ms 防抖（setup.ts 只 fake 了 Date/performance）
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 350));
      await Promise.resolve();
    });

    await waitFor(() => expect(lastListUrl(fetchMock).searchParams.get('keyword')).toBe('链表'));
  });

  it('「重置」清空所有筛选并回到第一页', async () => {
    const { fetchMock } = setup({ pages: 3, total: 60 });
    await screen.findByText('两数之和');

    await act(async () => {
      fireEvent.change(screen.getAllByRole('combobox')[0] as HTMLSelectElement, { target: { value: 'easy' } });
      await Promise.resolve();
    });
    await waitFor(() => expect(lastListUrl(fetchMock).searchParams.get('difficulty')).toBe('easy'));

    await act(async () => {
      screen.getByRole('button', { name: /重置/ }).click();
      await Promise.resolve();
    });

    await waitFor(() => {
      const url = lastListUrl(fetchMock);
      expect(url.searchParams.get('difficulty')).toBeNull();
      expect(url.searchParams.get('page')).toBe('1');
    });
  });
});

describe('problems · 分页', () => {
  it('首页时「上一页」禁用，「下一页」可用', async () => {
    setup({ pages: 3, total: 60, items: [makeProblem('p-1', '题一')] });
    await screen.findByText('题一');

    expect(screen.getByRole('button', { name: /上一页/ })).toBeDisabled();
    expect(screen.getByRole('button', { name: /下一页/ })).not.toBeDisabled();
    expect(screen.getByText(/第 1 \/ 3 页/)).toBeTruthy();
  });

  it('点「下一页」→ 请求 page=2', async () => {
    const { fetchMock } = setup({ pages: 3, total: 60, items: [makeProblem('p-1', '题一')] });
    await screen.findByText('题一');

    await act(async () => {
      screen.getByRole('button', { name: /下一页/ }).click();
      await Promise.resolve();
    });

    await waitFor(() => expect(lastListUrl(fetchMock).searchParams.get('page')).toBe('2'));
    expect(screen.getByRole('button', { name: /上一页/ })).not.toBeDisabled();
  });

  it('只有一页时不渲染分页条', async () => {
    setup({ pages: 1, items: [makeProblem('p-1', '题一')] });
    await screen.findByText('题一');

    expect(screen.queryByRole('button', { name: /下一页/ })).toBeNull();
  });
});

describe('problems · 随机挑题', () => {
  it('成功 → 请求 /problems/random 并跳转到该题详情', async () => {
    const { fetchMock, randomGate } = setup();
    await screen.findByText('两数之和');

    await act(async () => {
      randomGate.resolve(ok(makeProblem('p-random', '随机到的题')));
      await randomGate.promise;
    });
    await act(async () => {
      screen.getAllByRole('button', { name: /随机一题/ })[0]!.click();
      await randomGate.promise;
    });

    expect(fetchMock.countOf('/problems/random')).toBe(1);
    expect(window.location.href).toBe('/problems/p-random');
  });

  it('★ 失败 → 必须给用户可见提示，且不跳转', async () => {
    const { fetchMock, randomGate } = setup();
    await screen.findByText('两数之和');

    await act(async () => {
      screen.getAllByRole('button', { name: /随机一题/ })[0]!.click();
      await Promise.resolve();
    });
    // 用 resolve 返回非 2xx（而非 reject）：真实链路里 fetch 正常 resolve，
    // 由 lib/api 的 parseResponse 构造 ApiRequestError，reject 会把 Response 对象
    // 当作 rejection reason，导致页面走「请稍后再试」兜底而非后端文案。
    await act(async () => {
      randomGate.resolve(err('NO_PROBLEM', '当前筛选下没有可用题目', 404));
      await randomGate.promise;
    });

    // 用户可见提示：<Toaster /> 挂在 providers 上、不在页面树内，
    // 因此直接断言 store 里的 toast（这才是用户最终看到的内容）
    const toasts = useUiStore.getState().toasts;
    expect(toasts.some((t) => t.title === '随机挑题失败')).toBe(true);
    expect(toasts.some((t) => t.title === '随机挑题失败' && t.description === '当前筛选下没有可用题目')).toBe(true);
    // 失败时不应跳转
    expect(window.location.href).not.toContain('/problems/p-');
    expect(fetchMock.countOf('/problems/random')).toBe(1);
  });

  it('状态为「未解决」时携带 exclude_solved=true', async () => {
    const { fetchMock, randomGate } = setup();
    await screen.findByText('两数之和');

    await act(async () => {
      fireEvent.change(screen.getAllByRole('combobox')[3] as HTMLSelectElement, { target: { value: 'unsolved' } });
      await Promise.resolve();
    });

    await act(async () => {
      randomGate.resolve(ok(makeProblem('p-random', '随机到的题')));
      await randomGate.promise;
    });
    await act(async () => {
      screen.getAllByRole('button', { name: /随机一题/ })[0]!.click();
      await randomGate.promise;
    });

    const randomUrl = new URL(
      fetchMock.calls.filter((c) => c.url.includes('/problems/random')).pop()!.url,
      BASE_URL,
    );
    expect(randomUrl.searchParams.get('exclude_solved')).toBe('true');
  });

  it('空态里的「随机一题」同样可用', async () => {
    const { fetchMock, randomGate } = setup({ items: [], total: 0 });
    await screen.findByText('没有符合条件的题目');

    await act(async () => {
      randomGate.resolve(ok(makeProblem('p-random', '随机到的题')));
      await randomGate.promise;
    });
    await act(async () => {
      // 「随机一题」有两个（PageContainer actions + 空态 action），取第一个
      screen.getAllByRole('button', { name: /随机一题/ })[0]!.click();
      await randomGate.promise;
    });

    expect(fetchMock.countOf('/problems/random')).toBe(1);
  });
});

describe('problems · 公开列表（未登录）', () => {
  it('★ 未登录仍能看到题目列表，登录引导降级为页内提示条', async () => {
    useAuthStore.setState({ hydrated: true, accessToken: null, refreshToken: null, user: null, loading: false, error: null });
    const fetchMock = mockFetchByPath({
      '/problems/filters': () => ok(FILTERS),
      '/problems': () => ok({ items: [makeProblem('p-1', '两数之和')], total: 1, page: 1, pages: 1 } as ListQuery),
    });

    render(<ProblemsPage />);

    // 核心行为锁：列表本体对未登录用户可见（不再被 AuthGate 整页替换）
    expect(await screen.findByText('两数之和')).toBeTruthy();
    // 原 AuthGate 的文案与按钮迁到页内提示条
    expect(screen.getByText('题目列表公开可见，登录后可以记录做题状态、提交判题并保存错题。')).toBeTruthy();
    expect(screen.getByRole('link', { name: '登录' })).toBeTruthy();
    expect(screen.getByRole('link', { name: '注册新账号' })).toBeTruthy();
    expect(fetchMock.countOf('/problems/filters')).toBe(1);
  });

  it('未登录时不渲染「做题状态」筛选（个人能力），其余筛选与做题入口保留', async () => {
    useAuthStore.setState({ hydrated: true, accessToken: null, refreshToken: null, user: null, loading: false, error: null });
    mockFetchByPath({
      '/problems/filters': () => ok(FILTERS),
      '/problems': () => ok({ items: [makeProblem('p-1', '两数之和')], total: 1, page: 1, pages: 1 } as ListQuery),
    });

    render(<ProblemsPage />);
    await screen.findByText('两数之和');

    // 已登录是 5 个（难度/分类/题型/状态/排序），未登录去掉「状态」后剩 4 个
    expect(screen.getAllByRole('combobox')).toHaveLength(4);
    // 关键词与「去做题」入口仍可用
    expect(screen.getByPlaceholderText('搜索题目名称或关键词')).toBeTruthy();
    expect(screen.getAllByRole('link', { name: '去做题' }).length).toBeGreaterThanOrEqual(1);
  });

  it('未登录时状态参数不可能被发出（无入口），默认请求不含 status', async () => {
    useAuthStore.setState({ hydrated: true, accessToken: null, refreshToken: null, user: null, loading: false, error: null });
    const fetchMock = mockFetchByPath({
      '/problems/filters': () => ok(FILTERS),
      '/problems': () => ok({ items: [makeProblem('p-1', '两数之和')], total: 1, page: 1, pages: 1 } as ListQuery),
    });

    render(<ProblemsPage />);
    await screen.findByText('两数之和');

    const url = new URL(
      fetchMock.calls.filter((c) => c.url.includes('/problems') && !c.url.includes('/filters')).pop()!.url,
      BASE_URL,
    );
    expect(url.searchParams.get('status')).toBeNull();
  });
});
