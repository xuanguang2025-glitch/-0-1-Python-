// @vitest-environment jsdom
/**
 * `src/app/admin/users/page.tsx` —— 管理端重复提交防护。
 *
 * 该页面原有 5 个写操作，其中 `changeRole` / `toggleStatus` / `removeUser` /
 * `resetPassword` **完全没有任何 in-flight 守卫**，`create` 只有一个纯 state 标记
 * （同一 tick 连点依然会穿帮，因为闭包读到的是旧值）。
 * 现已统一接入 `useSubmitGuard`（ref 做同步判断 + state 驱动 UI）。
 *
 * 连点一律用同步 `button.click()` / `fireEvent`，不用 `userEvent.click()`：
 * 后者每次都会 await 并让 React 重渲染，第二击会被 DOM 的 disabled 挡掉，
 * 那样只能测到 disabled 属性、测不到守卫，是假绿。
 */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, act, waitFor, fireEvent } from '@testing-library/react';
import type { AdminUserItem, UserRole, UserStatus } from '@/lib/types';

import AdminUsersPage from '@/app/admin/users/page';
import { mockFetchByPath, ok, err } from '../helpers/fetch-mock';

vi.mock('next/navigation', () => ({
  usePathname: () => '/admin/users',
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn(), prefetch: vi.fn(), refresh: vi.fn() }),
  redirect: vi.fn(),
}));

function makeUser(id: string, username: string, role: UserRole = 'user', status: UserStatus = 'active'): AdminUserItem {
  return {
    id,
    email: `${username}@example.com`,
    username,
    display_name: username,
    role,
    status,
    level: 1,
    xp: 0,
    login_count: 3,
    created_at: '2026-01-01T00:00:00Z',
    last_login_at: '2026-02-01T00:00:00Z',
  };
}

const USER_A = makeUser('u-1', 'alice');
const USER_B = makeUser('u-2', 'bob', 'admin');

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

/** 每个用户每个操作各一个 gate，便于精确控制返回时机。 */
function setup(users: AdminUserItem[] = [USER_A, USER_B]) {
  const gates = new Map<string, ReturnType<typeof deferred<Response>>>();
  const key = (url: string): string => {
    // /users/{id} →  {id}:update ；/users → create 列表
    const m = /\/users\/([^/?]+)/.exec(url);
    return m ? `${m[1]}:update` : 'list';
  };

  const fetchMock = mockFetchByPath({
    '/users': () => {
      const last = fetchMock.calls[fetchMock.calls.length - 1];
      const k = key(last?.url ?? '');
      if (k === 'list') return ok({ items: users, total: users.length, page: 1, pages: 1 });
      let gate = gates.get(k);
      if (!gate) {
        gate = deferred<Response>();
        gates.set(k, gate);
      }
      return gate.promise as unknown as Response;
    },
  });

  render(<AdminUsersPage />);
  return { fetchMock, gates };
}

/** 等表格渲染出指定用户的状态按钮（禁用/恢复）。 */
async function findStatusButton(username: string): Promise<HTMLElement> {
  const row = await screen.findByText(`@${username}`);
  const cell = row.closest('tr') as HTMLElement;
  const buttons = Array.from(cell.querySelectorAll('button'));
  const target = buttons.find((b) => b.textContent === '禁用' || b.textContent === '恢复');
  if (!target) throw new Error(`未找到 ${username} 的状态按钮`);
  return target as HTMLElement;
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('admin/users · 重复提交防护', () => {
  it('★ toggleStatus：pending 期间同步连点三次，只发出一次请求', async () => {
    const { fetchMock, gates } = setup();
    const button = await findStatusButton('alice');

    await act(async () => {
      button.click();
      button.click();
      button.click();
      await Promise.resolve();
    });

    expect(fetchMock.countOf('/users/u-1')).toBe(1);
    expect(gates.has('u-1:update')).toBe(true);
  });

  it('★ changeRole：pending 期间连续切换三次，只发出一次请求', async () => {
    const { fetchMock } = setup();
    // 等列表渲染
    await screen.findByText('@alice');

    const selects = screen.getAllByRole('combobox');
    const aliceSelect = selects[0] as HTMLSelectElement;

    await act(async () => {
      // 连续触发三次 change，前两次应被守卫拦下
      fireEvent.change(aliceSelect, { target: { value: 'admin' } });
      fireEvent.change(aliceSelect, { target: { value: 'superadmin' } });
      fireEvent.change(aliceSelect, { target: { value: 'user' } });
      await Promise.resolve();
    });

    expect(fetchMock.countOf('/users/u-1')).toBe(1);
  });

  it('toggleStatus 失败后复位：按钮恢复可点，可再次操作', async () => {
    const { fetchMock, gates } = setup();
    const button = await findStatusButton('alice');

    await act(async () => {
      button.click();
      await Promise.resolve();
    });
    expect(fetchMock.countOf('/users/u-1')).toBe(1);

    // 后端拒绝
    await act(async () => {
      gates.get('u-1:update')!.reject(err('FORBIDDEN', '不能禁用超级管理员', 403));
      await gates.get('u-1:update')!.promise.catch(() => undefined);
    });

    const retry = await findStatusButton('alice');
    expect(retry).not.toBeDisabled();

    await act(async () => {
      retry.click();
      await Promise.resolve();
    });
    expect(fetchMock.countOf('/users/u-1')).toBe(2);
  });

  it('不同用户的操作互不阻塞（key 按 id 隔离）', async () => {
    const { fetchMock } = setup();
    const aliceBtn = await findStatusButton('alice');
    const bobBtn = await findStatusButton('bob');

    await act(async () => {
      aliceBtn.click();
      await Promise.resolve();
    });
    expect(fetchMock.countOf('/users/u-1')).toBe(1);

    // bob 的操作不应被 alice 的 in-flight 阻塞
    expect(bobBtn).not.toBeDisabled();
    await act(async () => {
      bobBtn.click();
      await Promise.resolve();
    });
    expect(fetchMock.countOf('/users/u-2')).toBe(1);
  });

  it('toggleStatus 进行中按钮进入禁用态（UI 反馈）', async () => {
    setup();
    const button = await findStatusButton('alice');

    await act(async () => {
      button.click();
      await Promise.resolve();
    });

    const disabled = await findStatusButton('alice');
    expect(disabled).toBeDisabled();
  });
});
