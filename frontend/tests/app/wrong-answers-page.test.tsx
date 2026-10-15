// @vitest-environment jsdom
/**
 * `src/app/wrong-answers/page.tsx` —— 错题本页（211 行）。
 *
 * 覆盖：错题列表渲染、已掌握/待复习状态、标记掌握与删除操作、复习队列、空态与错误态。
 *
 * ## 为什么用 fetch 层 mock
 * `store/auth.ts` 在模块初始化就调 `configureApiClient`，整体 mock `@/lib/api`
 * 会在 import 阶段炸掉；fetch 层 mock 让 `lib/api` 原样加载，更贴近真实链路。
 *
 * ## 断言按代码事实
 * - `<Toaster />` 挂在 `app/providers.tsx`，**不在页面树内**，
 *   所以 toast 一律断言 `useUiStore.getState().toasts`，而不是 screen 文本
 * - 错误路径要 **resolve 非 2xx**（而不是 reject）：真实链路里 fetch 正常 resolve，
 *   由 `lib/api` 的 parseResponse 构造 `ApiRequestError`；reject 会把 Response 对象
 *   当 rejection reason，导致 `error instanceof Error` 为 false、页面走兜底文案
 * - `formatRelativeTime` 读被 setup.ts 固定的「现在」（2026-09-27T10:00:00Z）
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act, fireEvent, waitFor } from '@testing-library/react';
import type { MistakeOut, UserBrief } from '@/lib/types';

import WrongAnswersPage from '@/app/wrong-answers/page';
import { useAuthStore } from '@/store/auth';
import { useUiStore } from '@/store/ui';
import { err, mockFetchByPath, ok } from '../helpers/fetch-mock';

vi.mock('next/navigation', () => ({
  usePathname: () => '/wrong-answers',
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

/** setup.ts 固定的「现在」：2026-09-27T10:00:00Z */
const NOW = new Date('2026-09-27T10:00:00Z');

function makeMistake(id: string, title: string, overrides: Partial<MistakeOut> = {}): MistakeOut {
  return {
    id,
    problem_id: `prob-${id}`,
    submission_id: null,
    lesson_id: null,
    topic_id: null,
    title,
    question_snapshot_md: null,
    user_answer: null,
    correct_answer: null,
    error_type: 'SyntaxError',
    error_message: null,
    note_md: null,
    resolved: false,
    resolved_at: null,
    review_count: 0,
    next_review_at: null,
    // 昨天 → formatRelativeTime 应渲染为「1 天前」
    created_at: new Date(NOW.getTime() - 24 * 60 * 60 * 1000).toISOString(),
    updated_at: null,
    ...overrides,
  };
}

type Page = { items: MistakeOut[]; total: number; page: number; pages: number };
type FetchMock = ReturnType<typeof mockFetchByPath>;

interface SetupOptions {
  items?: MistakeOut[];
  queue?: MistakeOut[];
  total?: number;
  listError?: Response;
  resolveError?: Response;
  removeError?: Response;
}

/** 挂载页面。列表/队列即时返回；标记与删除走 gate 便于控制成功失败。 */
function setup(options: SetupOptions = {}) {
  const items = options.items ?? [makeMistake('m-1', '两数之和'), makeMistake('m-2', '反转链表', { resolved: true })];
  const queue = options.queue ?? [makeMistake('q-1', '递归斐波那契', { review_count: 2 })];
  const total = options.total ?? items.length;

  const resolveGate = { promise: Promise.resolve<Response>(ok(makeMistake('m-1', 'x'))) };
  const removeGate = { promise: Promise.resolve<Response>(ok(null)) };

  const fetchMock = mockFetchByPath({
    // 注册顺序即匹配顺序：具体路径排在 /mistakes 之前
    '/mistakes/review-queue': () => ok(queue),
    '/resolve': () => options.resolveError ?? (resolveGate.promise as unknown as Response),
    '/mistakes': () => {
      const last = fetchMock.calls[fetchMock.calls.length - 1];
      const method = last?.init?.method ?? 'GET';
      if (method === 'DELETE') return options.removeError ?? (removeGate.promise as unknown as Response);
      return options.listError ?? ok({ items, total, page: 1, pages: 1 } as Page);
    },
  });

  useAuthStore.setState({
    hydrated: true,
    accessToken: 'test-access-token',
    refreshToken: 'test-refresh-token',
    user: USER,
    loading: false,
    error: null,
  });

  render(<WrongAnswersPage />);
  return { fetchMock };
}

/** 可控 deferred：用于精确控制写请求何时返回。 */
function deferred<T>(): { promise: Promise<T>; resolve: (v: T) => void } {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
}

/** 置为已登录（连点用例各自建 mock，故抽出共用）。 */
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

/** 最近一次错题列表请求的 URL。 */
function lastListUrl(fetchMock: FetchMock): URL {
  const calls = fetchMock.calls.filter(
    (c) => c.url.includes('/mistakes') && !c.url.includes('/review-queue') && !c.url.includes('/resolve'),
  );
  return new URL(calls[calls.length - 1]!.url, BASE_URL);
}

/**
 * 找到某条错题所在卡片里的按钮。
 * 同时匹配可见文案与 aria-label —— 「删除错题」是纯图标按钮，只有 aria-label。
 */
function buttonInMistake(title: string, label: string | RegExp): HTMLElement {
  const cardTitle = screen.getByText(title);
  const card = cardTitle.closest('div.p-4') as HTMLElement;
  const buttons = Array.from(card.querySelectorAll('button'));
  const matches = (b: HTMLElement, l: string | RegExp): boolean => {
    const text = b.textContent ?? '';
    const aria = b.getAttribute('aria-label') ?? '';
    return typeof l === 'string' ? text === l || aria === l : l.test(text) || l.test(aria);
  };
  const found = buttons.find((b) => matches(b as HTMLElement, label));
  if (!found) throw new Error(`未找到「${title}」卡片里的按钮 ${String(label)}`);
  return found as HTMLElement;
}

/**
 * 复习队列里的按钮（队列行是 div.p-3，不是错题卡片的 div.p-4，故单独查找）。
 * 队列按钮文案唯一，可直接全文档搜索。
 */
function queueButton(label: string): HTMLElement {
  const found = Array.from(document.querySelectorAll('button')).find((b) => b.textContent === label);
  if (!found) throw new Error(`未找到复习队列里的按钮 ${label}`);
  return found as HTMLElement;
}

beforeEach(() => {
  useUiStore.setState({ toasts: [] });
  // setup.ts 的 afterEach 里有 vi.useRealTimers()，会把 beforeAll 设的假 Date 还原掉，
  // 于是第 2 个用例起 Date.now() 变回真实时间、相对时间文案随之漂移。
  // 因此每个用例都要重新 fake Date 并对齐到同一基准时刻。
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(NOW);
});

afterEach(() => {
  useAuthStore.setState({ accessToken: null, refreshToken: null, user: null, hydrated: false, loading: false, error: null });
  vi.restoreAllMocks();
});

describe('wrong-answers · 列表渲染与统计', () => {
  it('渲染错题标题、状态徽章与统计数字', async () => {
    setup();

    expect(await screen.findByText('两数之和')).toBeTruthy();
    expect(screen.getByText('反转链表')).toBeTruthy();
    // 「待复习」既是错题卡片的 Badge 文案、也是统计卡的 label，会出现多次
    expect(screen.getAllByText('待复习').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('已掌握').length).toBeGreaterThanOrEqual(1);
    // 统计卡标题
    expect(screen.getByText('错题总数')).toBeTruthy();
    // 「今日复习队列」既是 StatCard label 又是卡片标题，会出现两次
    expect(screen.getAllByText('今日复习队列').length).toBeGreaterThanOrEqual(1);
  });

  it('error_type 以 Badge 形式展示', async () => {
    setup();
    await screen.findByText('两数之和');

    // error_type 默认 'SyntaxError'
    expect(screen.getAllByText('SyntaxError').length).toBeGreaterThanOrEqual(1);
  });

  it('收录时间用相对时间渲染（formatRelativeTime）', async () => {
    setup();
    await screen.findByText('两数之和');

    // created_at 是「现在 - 24h」→ formatRelativeTime 应得「1 天前」。
    // 注意该文案被 JSX 插值拆成多个文本节点（"收录于 " / "1 天前" / " · 复习 " ...），
    // 所以不能直接用 getByText，要取包含「收录于」的 <p> 再看 textContent。
    const meta = Array.from(document.querySelectorAll('p')).find((el) => el.textContent?.includes('收录于'));
    expect(meta).toBeTruthy();
    expect(meta!.textContent).toContain('1 天前');
  });

  it('note_md 存在时才渲染备注', async () => {
    setup({ items: [makeMistake('m-1', '带备注的题', { note_md: '这里是我的思路笔记' })] });
    await screen.findByText('带备注的题');

    expect(screen.getByText('这里是我的思路笔记')).toBeTruthy();
  });
});

describe('wrong-answers · 复习队列', () => {
  it('渲染队列条目与复习信息', async () => {
    setup({ queue: [makeMistake('q-1', '递归斐波那契', { review_count: 3 })] });

    expect(await screen.findByText('递归斐波那契')).toBeTruthy();
    // 队列行展示「已复习 N 次」
    expect(screen.getByText(/已复习 3 次/)).toBeTruthy();
  });

  it('队列为空 → 渲染空态', async () => {
    setup({ queue: [] });

    expect(await screen.findByText('今日没有需要复习的错题')).toBeTruthy();
  });

  it('「我掌握了」调用 resolve 接口并给出成功提示', async () => {
    const { fetchMock } = setup();
    await screen.findByText('递归斐波那契');

    await act(async () => {
      queueButton('我掌握了').click();
      await Promise.resolve();
    });

    await waitFor(() => expect(fetchMock.countOf('/resolve')).toBe(1));
    const resolveCall = fetchMock.calls.find((c) => c.url.includes('/resolve'))!;
    expect(resolveCall.url).toContain('/mistakes/q-1/resolve');
    expect(resolveCall.init?.method).toBe('POST');
    await waitFor(() =>
      expect(useUiStore.getState().toasts.some((t) => t.title === '已标记为掌握')).toBe(true),
    );
  });
});

describe('wrong-answers · 标记掌握 / 恢复待复习', () => {
  it('未掌握的错题显示「标记掌握」，点击后调用 resolve(resolved=true)', async () => {
    const { fetchMock } = setup();
    await screen.findByText('两数之和');

    await act(async () => {
      buttonInMistake('两数之和', '标记掌握').click();
      await Promise.resolve();
    });

    await waitFor(() => expect(fetchMock.countOf('/resolve')).toBe(1));
    const body = JSON.parse(String(fetchMock.calls.find((c) => c.url.includes('/resolve'))!.init?.body ?? '{}'));
    expect(body.resolved).toBe(true);
  });

  it('已掌握的错题显示「恢复待复习」，点击后调用 resolve(resolved=false)', async () => {
    const { fetchMock } = setup();
    await screen.findByText('反转链表');

    await act(async () => {
      buttonInMistake('反转链表', '恢复待复习').click();
      await Promise.resolve();
    });

    await waitFor(() => expect(fetchMock.countOf('/resolve')).toBe(1));
    const body = JSON.parse(String(fetchMock.calls.find((c) => c.url.includes('/resolve'))!.init?.body ?? '{}'));
    expect(body.resolved).toBe(false);
    await waitFor(() =>
      expect(useUiStore.getState().toasts.some((t) => t.title === '已加入复习队列')).toBe(true),
    );
  });

  it('★ 失败 → 必须给用户可见提示（后端文案透传），不能静默', async () => {
    setup({ resolveError: err('NOT_FOUND', '错题不存在', 404) });
    await screen.findByText('两数之和');

    await act(async () => {
      buttonInMistake('两数之和', '标记掌握').click();
      await Promise.resolve();
    });

    await waitFor(() => {
      const toasts = useUiStore.getState().toasts;
      expect(toasts.some((t) => t.title === '操作失败')).toBe(true);
      // description 来自后端 message，说明用户能看到具体原因
      expect(toasts.some((t) => t.title === '操作失败' && t.description === '错题不存在')).toBe(true);
    });
  });
});

describe('wrong-answers · 删除错题', () => {
  it('点击删除调用 DELETE 接口并提示成功', async () => {
    const { fetchMock } = setup();
    await screen.findByText('两数之和');

    await act(async () => {
      buttonInMistake('两数之和', /删除错题/).click();
      await Promise.resolve();
    });

    await waitFor(() => expect(fetchMock.countOf('/mistakes/m-1')).toBe(1));
    const deleteCall = fetchMock.calls.find((c) => c.init?.method === 'DELETE')!;
    expect(deleteCall.url).toContain('/mistakes/m-1');
    await waitFor(() => expect(useUiStore.getState().toasts.some((t) => t.title === '已删除')).toBe(true));
  });

  it('删除失败 → 给出「删除失败」提示', async () => {
    const { fetchMock } = setup({ removeError: err('FORBIDDEN', '无权删除', 403) });
    await screen.findByText('两数之和');

    await act(async () => {
      buttonInMistake('两数之和', /删除错题/).click();
      await Promise.resolve();
    });

    await waitFor(() => {
      const toasts = useUiStore.getState().toasts;
      expect(toasts.some((t) => t.title === '删除失败')).toBe(true);
      expect(toasts.some((t) => t.title === '删除失败' && t.description === '无权删除')).toBe(true);
    });
    // 失败不应发出第二次请求
    expect(fetchMock.countOf('/mistakes/m-1')).toBe(1);
  });
});

describe('wrong-answers · 筛选与状态分支', () => {
  it('切到「待复习」→ 请求带 resolved=false', async () => {
    const { fetchMock } = setup();
    await screen.findByText('两数之和');

    await act(async () => {
      fireEvent.change(screen.getByRole('combobox'), { target: { value: 'false' } });
      await Promise.resolve();
    });

    await waitFor(() => expect(lastListUrl(fetchMock).searchParams.get('resolved')).toBe('false'));
  });

  it('切到「已掌握」→ 请求带 resolved=true', async () => {
    const { fetchMock } = setup();
    await screen.findByText('两数之和');

    await act(async () => {
      fireEvent.change(screen.getByRole('combobox'), { target: { value: 'true' } });
      await Promise.resolve();
    });

    await waitFor(() => expect(lastListUrl(fetchMock).searchParams.get('resolved')).toBe('true'));
  });

  it('错题列表为空 → 渲染空态并给出「去刷题」入口', async () => {
    setup({ items: [], total: 0 });
    await screen.findByText('没有符合条件的题目').catch(() => undefined);

    expect(await screen.findByText('错题本还是空的')).toBeTruthy();
    expect(screen.getByText('去刷题')).toBeTruthy();
  });

  it('列表加载失败 → 渲染 ErrorState 且带后端错误文案', async () => {
    setup({ listError: err('SERVER_ERROR', '错题服务异常', 500) });

    expect(await screen.findByText('错题加载失败')).toBeTruthy();
    expect(screen.getByText('错题服务异常')).toBeTruthy();
    expect(screen.getByRole('button', { name: /重试|重新加载/ })).toBeTruthy();
  });
});

describe('wrong-answers · 重复提交防护（连点）', () => {
  it('★ 标记掌握：pending 期间同步连点三次，只发出一次 resolve 请求', async () => {
    const resolveGate = deferred<Response>();
    const fetchMock = mockFetchByPath({
      '/mistakes/review-queue': () => ok([]),
      '/resolve': () => resolveGate.promise as unknown as Response,
      '/mistakes': () => ok({ items: [makeMistake('m-1', '两数之和')], total: 1, page: 1, pages: 1 } as Page),
    });
    login();
    render(<WrongAnswersPage />);
    await screen.findByText('两数之和');

    await act(async () => {
      const btn = buttonInMistake('两数之和', '标记掌握');
      btn.click();
      btn.click();
      btn.click();
      await Promise.resolve();
    });

    expect(fetchMock.countOf('/resolve')).toBe(1);
    await act(async () => {
      resolveGate.resolve(ok(makeMistake('m-1', '两数之和', { resolved: true })));
      await resolveGate.promise;
    });
  });

  it('★ 删除错题：pending 期间同步连点两次，只发出一次 DELETE', async () => {
    const removeGate = deferred<Response>();
    const fetchMock = mockFetchByPath({
      '/mistakes/review-queue': () => ok([]),
      '/mistakes': () => {
        const last = fetchMock.calls[fetchMock.calls.length - 1];
        if (last?.init?.method === 'DELETE') return removeGate.promise as unknown as Response;
        return ok({ items: [makeMistake('m-1', '两数之和')], total: 1, page: 1, pages: 1 } as Page);
      },
    });
    login();
    render(<WrongAnswersPage />);
    await screen.findByText('两数之和');

    await act(async () => {
      const btn = buttonInMistake('两数之和', /删除错题/);
      btn.click();
      btn.click();
      await Promise.resolve();
    });

    expect(fetchMock.countOf('/mistakes/m-1')).toBe(1);
    await act(async () => {
      removeGate.resolve(ok(null));
      await removeGate.promise;
    });
  });

  it('标记失败后复位：可再次提交（守卫必须释放）', async () => {
    const resolveGate = deferred<Response>();
    const fetchMock = mockFetchByPath({
      '/mistakes/review-queue': () => ok([]),
      '/resolve': () => resolveGate.promise as unknown as Response,
      '/mistakes': () => ok({ items: [makeMistake('m-1', '两数之和')], total: 1, page: 1, pages: 1 } as Page),
    });
    login();
    render(<WrongAnswersPage />);
    await screen.findByText('两数之和');

    await act(async () => {
      buttonInMistake('两数之和', '标记掌握').click();
      await Promise.resolve();
    });
    expect(fetchMock.countOf('/resolve')).toBe(1);

    await act(async () => {
      resolveGate.resolve(err('NOT_FOUND', '错题不存在', 404));
      await resolveGate.promise;
    });

    const retry = buttonInMistake('两数之和', '标记掌握');
    expect(retry).not.toBeDisabled();

    await act(async () => {
      retry.click();
      await Promise.resolve();
    });
    expect(fetchMock.countOf('/resolve')).toBe(2);
  });
});

describe('wrong-answers · 未登录门禁', () => {
  it('未登录时展示登录引导而非错题内容', async () => {
    useAuthStore.setState({ hydrated: true, accessToken: null, refreshToken: null, user: null, loading: false, error: null });
    mockFetchByPath({
      '/mistakes/review-queue': () => ok([]),
      '/mistakes': () => ok({ items: [], total: 0, page: 1, pages: 1 } as Page),
    });

    render(<WrongAnswersPage />);

    expect(await screen.findByText('登录后查看错题本')).toBeTruthy();
    expect(screen.queryByText('错题本还是空的')).toBeNull();
  });
});
