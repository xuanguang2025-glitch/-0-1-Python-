// @vitest-environment jsdom
/**
 * `src/app/settings/page.tsx` —— 账号安全相关操作的重复提交防护。
 *
 * 该页原有 `savingPrefs` / `changingPassword` / `deleting` 三个**纯 state** 标记，
 * 只做 UI 展示、没有任何守卫判断：同一 tick 内连点会发出多个请求。
 * 其中 `deleteAccount` 重复提交会真的重复注销账号（软删除 + 登出），
 * 是数据正确性问题，风险最高，故本文件以它为核心。
 *
 * 连点一律用同步 `button.click()`，不用 `userEvent.click()` —— 后者每次都会 await
 * 并让 React 重渲染，第二击会被 DOM 的 disabled 挡掉，只能测到 disabled 属性，
 * 测不到守卫，是假绿。
 */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import type { UserBrief } from '@/lib/types';

import SettingsPage from '@/app/settings/page';
import { useAuthStore } from '@/store/auth';
import { err, mockFetchByPath, ok } from '../helpers/fetch-mock';

vi.mock('next/navigation', () => ({
  usePathname: () => '/settings',
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn(), prefetch: vi.fn(), refresh: vi.fn() }),
  redirect: vi.fn(),
}));

// next-themes 的 useTheme 需要主题上下文，测试里直接 mock 掉
vi.mock('next-themes', () => ({
  useTheme: () => ({ theme: 'dark', setTheme: vi.fn() }),
  ThemeProvider: ({ children }: { children: React.ReactNode }) => children,
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

const PROFILE = {
  id: 'u-1',
  email: 'tester@example.com',
  username: 'tester',
  display_name: '测试用户',
  role: 'user',
  level: 1,
  xp: 0,
  ai_mode: 'standard',
  learning_mode: 'system',
  weekly_goal_minutes: 300,
  theme_preference: 'dark',
  public_profile: true,
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

/** 统计某个路径 + method 的请求数（读和写路径有重叠，必须带上 method 才能区分）。 */
function countCalls(fetchMock: { calls: { url: string; init?: RequestInit }[] }, path: string, method?: string): number {
  return fetchMock.calls.filter((c) => c.url.includes(path) && (!method || c.init?.method === method)).length;
}

function setup() {
  useAuthStore.setState({
    hydrated: true,
    accessToken: 'test-access-token',
    refreshToken: 'test-refresh-token',
    user: USER,
    loading: false,
    error: null,
  });

  const deleteGate = deferred<Response>();
  const prefsGate = deferred<Response>();

  const fetchMock = mockFetchByPath({
    // 注册顺序即匹配顺序：具体路径必须排在泛化的 /users/me 之前
    '/users/me/preferences': () => prefsGate.promise as unknown as Response,
    '/users/me/profile': () => ok(PROFILE),
    '/users/me': () => deleteGate.promise as unknown as Response,
    '/auth/logout': () => ok({ success: true }),
  });

  render(<SettingsPage />);
  return { fetchMock, deleteGate, prefsGate };
}

/** 打开注销确认弹窗并返回「确认注销」按钮。 */
async function openDeleteDialog(): Promise<HTMLElement> {
  const openBtn = await screen.findByRole('button', { name: /注销/ });
  await act(async () => {
    openBtn.click();
    await Promise.resolve();
  });
  return screen.findByRole('button', { name: '确认注销' });
}

afterEach(() => {
  useAuthStore.setState({ accessToken: null, refreshToken: null, user: null, hydrated: false, loading: false, error: null });
});

describe('settings · 注销账号重复提交（最高优先级）', () => {
  it('★ deleteAccount：pending 期间同步连点三次，只发出一次 DELETE', async () => {
    const { fetchMock } = setup();
    const confirmBtn = await openDeleteDialog();

    await act(async () => {
      confirmBtn.click();
      confirmBtn.click();
      confirmBtn.click();
      await Promise.resolve();
    });

    // ★ 核心断言：3 次点击 → 1 次 DELETE。无守卫时这里是 3（会真的重复注销）。
    expect(countCalls(fetchMock, '/users/me', 'DELETE')).toBe(1);
  });

  it('注销失败后复位：按钮恢复可点，可再次尝试', async () => {
    const { fetchMock, deleteGate } = setup();
    const confirmBtn = await openDeleteDialog();

    await act(async () => {
      confirmBtn.click();
      await Promise.resolve();
    });
    expect(countCalls(fetchMock, '/users/me', 'DELETE')).toBe(1);

    // 密码错误导致注销失败
    await act(async () => {
      deleteGate.reject(err('BAD_PASSWORD', '密码错误', 400));
      await deleteGate.promise.catch(() => undefined);
    });

    // 复位 → 可再次点击（不复位则按钮永久禁用，用户被卡死）
    const retry = await screen.findByRole('button', { name: '确认注销' });
    expect(retry).not.toBeDisabled();

    await act(async () => {
      retry.click();
      await Promise.resolve();
    });
    expect(countCalls(fetchMock, '/users/me', 'DELETE')).toBe(2);
  });

  it('注销进行中，取消按钮同时禁用', async () => {
    setup();
    const confirmBtn = await openDeleteDialog();

    await act(async () => {
      confirmBtn.click();
      await Promise.resolve();
    });

    expect(screen.getByRole('button', { name: '取消' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '确认注销' })).toBeDisabled();
  });
});

describe('settings · 偏好与密码重复提交', () => {
  it('★ savePreferences：pending 期间连点两次只保存一次', async () => {
    const { fetchMock } = setup();
    const saveBtn = await screen.findByRole('button', { name: '保存偏好' });

    await act(async () => {
      saveBtn.click();
      saveBtn.click();
      await Promise.resolve();
    });

    expect(countCalls(fetchMock, '/users/me/preferences', 'PATCH')).toBe(1);
  });

  it('savePreferences 失败后复位，可再次保存', async () => {
    const { fetchMock, prefsGate } = setup();
    const saveBtn = await screen.findByRole('button', { name: '保存偏好' });

    await act(async () => {
      saveBtn.click();
      await Promise.resolve();
    });
    expect(countCalls(fetchMock, '/users/me/preferences', 'PATCH')).toBe(1);

    await act(async () => {
      prefsGate.reject(err('VALIDATION', '参数不合法', 422));
      await prefsGate.promise.catch(() => undefined);
    });

    const retry = await screen.findByRole('button', { name: '保存偏好' });
    expect(retry).not.toBeDisabled();

    await act(async () => {
      retry.click();
      await Promise.resolve();
    });
    expect(countCalls(fetchMock, '/users/me/preferences', 'PATCH')).toBe(2);
  });

  it('保存偏好与注销互不阻塞（key 隔离）', async () => {
    const { fetchMock } = setup();

    const saveBtn = await screen.findByRole('button', { name: '保存偏好' });
    await act(async () => {
      saveBtn.click();
      await Promise.resolve();
    });
    expect(countCalls(fetchMock, '/users/me/preferences', 'PATCH')).toBe(1);

    // 保存进行中，注销按钮仍可点
    const openBtn = screen.getByRole('button', { name: /注销/ });
    expect(openBtn).not.toBeDisabled();
    await act(async () => {
      openBtn.click();
      await Promise.resolve();
    });

    const confirmBtn = await screen.findByRole('button', { name: '确认注销' });
    expect(confirmBtn).not.toBeDisabled();
    await act(async () => {
      confirmBtn.click();
      await Promise.resolve();
    });

    expect(countCalls(fetchMock, '/users/me', 'DELETE')).toBe(1);
  });

  it('changePassword 有前置校验：不满足条件不发请求', async () => {
    const { fetchMock } = setup();
    const btn = await screen.findByRole('button', { name: '修改密码' });

    // 未填任何密码 → 应被前置校验拦下，不发请求
    await act(async () => {
      btn.click();
      await Promise.resolve();
    });

    expect(fetchMock.countOf('/auth/change-password')).toBe(0);
  });
});
