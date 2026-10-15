// @vitest-environment jsdom
/**
 * `src/app/bookmarks/page.tsx` 与 `src/app/notifications/page.tsx` —— 重复提交防护。
 *
 * 这两页原先**完全没有 in-flight 守卫**：`bookmarkApi.create()` 连点会重复收藏，
 * `bookmarkApi.remove()` / `notificationApi.remove()` 连点会重复删除，
 * `notificationApi.read()` / `readAll()` 连点会重复打标记。现已接入 `useSubmitGuard`
 * （ref 同步判断 + state 驱动 UI，性质验证见 `tests/hooks/useSubmitGuard.test.tsx`）。
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
import type { BookmarkOut, NotificationOut, UserBrief } from '@/lib/types';

import BookmarksPage from '@/app/bookmarks/page';
import NotificationsPage from '@/app/notifications/page';
import { useAuthStore } from '@/store/auth';
import { err, mockFetchByPath, ok } from '../helpers/fetch-mock';

vi.mock('next/navigation', () => ({
  usePathname: () => '/bookmarks',
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

const BOOKMARK: BookmarkOut = {
  id: 'b-1',
  kind: 'problem',
  ref_id: 'p-1',
  title: '两数之和',
  description: null,
  code_snippet: null,
  language: '',
  collection: '',
  tags: [],
  created_at: '2026-09-20T00:00:00Z',
};

const NOTIFICATION: NotificationOut = {
  id: 'n-1',
  type: 'system',
  title: '欢迎加入',
  content_md: null,
  link_url: null,
  icon: null,
  is_read: false,
  read_at: null,
  created_at: '2026-09-20T00:00:00Z',
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

/** 书签页：写操作走 gate 便于控制成功/失败。 */
function setupBookmarks(options: { createError?: Response; removeError?: Response } = {}) {
  const createGate = deferred<Response>();
  const removeGate = deferred<Response>();

  const fetchMock = mockFetchByPath({
    '/bookmarks/collections': () => ok([]),
    '/bookmarks': () => {
      const last = fetchMock.calls[fetchMock.calls.length - 1];
      const method = last?.init?.method ?? 'GET';
      if (method === 'POST') return (options.createError ?? createGate.promise) as unknown as Response;
      if (method === 'DELETE') return (options.removeError ?? removeGate.promise) as unknown as Response;
      return ok({ items: [BOOKMARK], total: 1, page: 1, pages: 1 });
    },
  });

  login();
  render(<BookmarksPage />);
  return { fetchMock, createGate, removeGate };
}

/** 通知页：写操作走 gate。 */
function setupNotifications(options: { readError?: Response; removeError?: Response } = {}) {
  const readGate = deferred<Response>();
  const readAllGate = deferred<Response>();
  const removeGate = deferred<Response>();

  const fetchMock = mockFetchByPath({
    '/notifications/unread-count': () => ok({ count: 1 }),
    '/notifications/announcements': () => ok([]),
    '/notifications/read-all': () => (options.readError ?? readAllGate.promise) as unknown as Response,
    '/notifications': () => {
      const last = fetchMock.calls[fetchMock.calls.length - 1];
      const url = last?.url ?? '';
      if (url.includes('/read')) return (options.readError ?? readGate.promise) as unknown as Response;
      return ok({ items: [NOTIFICATION], total: 1, page: 1, pages: 1 });
    },
  });

  login();
  render(<NotificationsPage />);
  return { fetchMock, readGate, readAllGate, removeGate };
}

/** 统计某路径 + method 的请求数。 */
function countCalls(fetchMock: FetchMock, path: string, method?: string): number {
  return fetchMock.calls.filter((c) => c.url.includes(path) && (!method || c.init?.method === method)).length;
}

/** 找到 aria-label 或文案匹配的按钮。 */
function buttonByLabel(label: string | RegExp): HTMLElement {
  const found = Array.from(document.querySelectorAll('button')).find((b) => {
    const text = b.textContent ?? '';
    const aria = b.getAttribute('aria-label') ?? '';
    return typeof label === 'string' ? text.trim() === label || aria === label : label.test(text) || label.test(aria);
  });
  if (!found) throw new Error(`未找到按钮 ${String(label)}`);
  return found as HTMLElement;
}

beforeEach(() => {
  // setup.ts 的 afterEach 会 useRealTimers，把 beforeAll 的假 Date 还原掉，逐用例重设
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(new Date('2026-09-27T10:00:00Z'));
});

afterEach(() => {
  useAuthStore.setState({ accessToken: null, refreshToken: null, user: null, hydrated: false, loading: false, error: null });
  vi.restoreAllMocks();
});

describe('bookmarks · 重复提交防护', () => {
  it('★ create：pending 期间同步连点三次，只发出一次 POST', async () => {
    const { fetchMock, createGate } = setupBookmarks();

    // 打开新建弹窗并填标题（title 必填，否则前置校验会拦下）
    await act(async () => {
      buttonByLabel(/新建收藏|添加收藏/).click();
      await Promise.resolve();
    });
    const dialog = await screen.findByRole('dialog');
    const input = dialog.querySelector('input') as HTMLInputElement;
    await act(async () => {
      fireEvent.change(input, { target: { value: '我的收藏' } });
      await Promise.resolve();
    });

    const saveBtn = buttonByLabel('保存');
    await act(async () => {
      saveBtn.click();
      saveBtn.click();
      saveBtn.click();
      await Promise.resolve();
    });

    expect(countCalls(fetchMock, '/bookmarks', 'POST')).toBe(1);
    createGate.resolve(ok(BOOKMARK));
    await createGate.promise;
  });

  it('★ remove：pending 期间同步连点两次，只发出一次 DELETE', async () => {
    const { fetchMock, removeGate } = setupBookmarks();
    await screen.findByText('两数之和');

    const removeBtn = buttonByLabel('移除收藏');
    await act(async () => {
      removeBtn.click();
      removeBtn.click();
      await Promise.resolve();
    });

    expect(countCalls(fetchMock, '/bookmarks/b-1', 'DELETE')).toBe(1);
    removeGate.resolve(ok(null));
    await removeGate.promise;
  });

  it('remove 失败后复位：按钮恢复可点，可再次移除', async () => {
    const { fetchMock, removeGate } = setupBookmarks({ removeError: err('FORBIDDEN', '无权删除', 403) });
    await screen.findByText('两数之和');

    await act(async () => {
      buttonByLabel('移除收藏').click();
      await Promise.resolve();
    });
    expect(countCalls(fetchMock, '/bookmarks/b-1', 'DELETE')).toBe(1);

    await act(async () => {
      removeGate.resolve(err('FORBIDDEN', '无权删除', 403));
      await removeGate.promise;
    });

    const retry = buttonByLabel('移除收藏');
    expect(retry).not.toBeDisabled();

    await act(async () => {
      retry.click();
      await Promise.resolve();
    });
    expect(countCalls(fetchMock, '/bookmarks/b-1', 'DELETE')).toBe(2);
  });
});

describe('notifications · 重复提交防护', () => {
  it('★ markRead：pending 期间同步连点三次，只发出一次 read 请求', async () => {
    const { fetchMock, readGate } = setupNotifications();
    await screen.findByText('欢迎加入');

    const readBtn = buttonByLabel('标为已读');
    await act(async () => {
      readBtn.click();
      readBtn.click();
      readBtn.click();
      await Promise.resolve();
    });

    expect(countCalls(fetchMock, '/notifications/n-1/read', 'POST')).toBe(1);
    readGate.resolve(ok(NOTIFICATION));
    await readGate.promise;
  });

  it('★ markAllRead：pending 期间同步连点三次，只发出一次 read-all', async () => {
    const { fetchMock, readAllGate } = setupNotifications();
    await screen.findByText('欢迎加入');

    const allBtn = buttonByLabel(/全部标为已读/);
    await act(async () => {
      allBtn.click();
      allBtn.click();
      allBtn.click();
      await Promise.resolve();
    });

    expect(countCalls(fetchMock, '/notifications/read-all', 'POST')).toBe(1);
    readAllGate.resolve(ok({ updated: 3 }));
    await readAllGate.promise;
  });

  it('markAllRead 失败后复位：按钮恢复可点', async () => {
    const { fetchMock, readAllGate } = setupNotifications();
    await screen.findByText('欢迎加入');

    await act(async () => {
      buttonByLabel(/全部标为已读/).click();
      await Promise.resolve();
    });
    expect(countCalls(fetchMock, '/notifications/read-all', 'POST')).toBe(1);

    await act(async () => {
      readAllGate.resolve(err('SERVER_ERROR', '服务异常', 500));
      await readAllGate.promise;
    });

    expect(buttonByLabel(/全部标为已读/)).not.toBeDisabled();
  });

  it('★ remove：pending 期间同步连点两次，只发出一次 DELETE', async () => {
    const { fetchMock } = setupNotifications();
    await screen.findByText('欢迎加入');

    const removeBtn = buttonByLabel('删除通知');
    await act(async () => {
      removeBtn.click();
      removeBtn.click();
      await Promise.resolve();
    });

    expect(countCalls(fetchMock, '/notifications/n-1', 'DELETE')).toBe(1);
  });

  it('不同通知的操作互不阻塞（key 按 id 隔离）', async () => {
    const second = { ...NOTIFICATION, id: 'n-2', title: '成就解锁' };
    const gates = new Map<string, ReturnType<typeof deferred<Response>>>();
    const fetchMock = mockFetchByPath({
      '/notifications/unread-count': () => ok({ count: 2 }),
      '/notifications/announcements': () => ok([]),
      '/notifications/read-all': () => ok({ updated: 2 }),
      '/notifications': () => {
        const last = fetchMock.calls[fetchMock.calls.length - 1];
        const url = last?.url ?? '';
        if (url.includes('/read')) {
          const id = /\/notifications\/([^/]+)\/read/.exec(url)?.[1] ?? '';
          let gate = gates.get(id);
          if (!gate) {
            gate = deferred<Response>();
            gates.set(id, gate);
          }
          return gate.promise as unknown as Response;
        }
        return ok({ items: [NOTIFICATION, second], total: 2, page: 1, pages: 1 });
      },
    });

    login();
    render(<NotificationsPage />);
    await screen.findByText('欢迎加入');

    const buttons = Array.from(document.querySelectorAll('button')).filter((b) => b.textContent?.trim() === '标为已读');
    expect(buttons).toHaveLength(2);

    await act(async () => {
      (buttons[0] as HTMLElement).click();
      await Promise.resolve();
    });
    // 第二条不应被第一条的 in-flight 阻塞
    const stillEnabled = Array.from(document.querySelectorAll('button')).filter(
      (b) => b.textContent?.trim() === '标为已读' && !(b as HTMLButtonElement).disabled,
    );
    expect(stillEnabled.length).toBeGreaterThanOrEqual(1);

    await act(async () => {
      (stillEnabled[0] as HTMLElement).click();
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(countCalls(fetchMock, '/notifications/n-1/read', 'POST')).toBe(1);
      expect(countCalls(fetchMock, '/notifications/n-2/read', 'POST')).toBe(1);
    });
  });
});
