// @vitest-environment jsdom
/**
 * `src/store/auth.ts` —— L3 状态层的**补充**用例：令牌读取回退 + 订阅契约。
 *
 * ## 与 `tests/store/auth.test.ts` 的分工（避免重复覆盖）
 * 已有文件覆盖：login / register / logout / hydrate 主路径、401 → onSessionExpired、
 * 刷新成功后 onTokensRefreshed 落盘、refreshProfile / setUser / clearError。
 * 错误码映射表由 `tests/store/resolve-error-message.test.ts` 单独逐码断言。
 *
 * 本文件只补**已有文件没有覆盖**的分支，每条都对应源码里一处真实分支：
 * 1. `getRefreshToken` 的 **localStorage 回退**（`store.refreshToken ?? readLocal(...)`）：
 *    store 被清空但 localStorage 仍有 token 时（onSessionExpired 之外的场景：
 *    页面刷新后 store 内存态为空），api 层仍必须能拿到 token 完成静默续期。
 *    这是注入回调里唯一带 `??` 的分支，漏测就等于把「刷新页面静默续期」押在运气上。
 * 2. `logout()` 同样有 `get().refreshToken ?? readLocal(...)` 回退：store 空 +
 *    localStorage 有值时仍要通知后端吊销该 token，否则 refresh token 留在服务端有效。
 * 3. `persistTokens` 的 `tokens.user ?? state.user`：类型上 `TokenPair.user` 是必填，
 *    但后端偶发不返回时不能把已登录用户踢回未登录（防御分支）。
 * 4. `onTokensRefreshed` 只更新令牌、**不动 user**：刷新不应把用户踢下线。
 * 5. store 作为 **React hook 的订阅契约**：已有用例全部走 `getState()`，
 *    组件里的 selector 订阅与重渲染没有任何用例覆盖 —— 而这正是 zustand 的核心价值，
 *    也是「登录后导航栏不刷新」这类缺陷的唯一暴露点。
 * 6. `hydrate()` 期间的 `loading` 状态机（已有用例只断言结束态）。
 *
 * ## mock 策略
 * 与 `tests/store/auth.test.ts` 一致：**部分 mock** `@/lib/api`，只替换 `authApi`，
 * 保留真实的 `apiGet` / `configureApiClient`。原因见 `tests/app/challenges-page.test.tsx`
 * 头部：`store/auth.ts` 在**模块初始化时**就调 `configureApiClient`，整体 mock
 * `@/lib/api` 会在 import 阶段炸掉；fetch 层 mock 才能验证真实的 401 → 刷新链路。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';

const { authMocks } = vi.hoisted(() => ({
  authMocks: {
    login: vi.fn(),
    register: vi.fn(),
    refresh: vi.fn(),
    me: vi.fn(),
    logout: vi.fn(),
    changePassword: vi.fn(),
  },
}));

vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>();
  return { ...actual, authApi: { ...actual.authApi, ...authMocks } };
});

import { useAuthStore } from '@/store/auth';
import { apiGet, ApiRequestError } from '@/lib/api';
import { STORAGE_KEYS } from '@/lib/storage';
import { mockFetchByPath, ok, unauthorized } from '../helpers/fetch-mock';
import type { TokenPair, UserBrief } from '@/lib/types';

const REFRESH_KEY = `pythonlab:${STORAGE_KEYS.refreshToken}`;

function makeUser(overrides: Partial<UserBrief> = {}): UserBrief {
  return {
    id: 'u-1',
    email: 'k@example.com',
    username: 'kou',
    display_name: '寇豆码',
    role: 'user',
    level: 3,
    xp: 420,
    ...overrides,
  };
}

function makeTokens(overrides: Partial<TokenPair> = {}): TokenPair {
  return {
    access_token: 'access-1',
    refresh_token: 'refresh-1',
    token_type: 'bearer',
    expires_in: 900,
    user: makeUser(),
    ...overrides,
  };
}

/** 把 store 复位到「未登录 + 未 hydrate」的初始态（模块级单例，每个用例都要复位）。 */
function resetStore(): void {
  window.localStorage.clear();
  useAuthStore.setState({
    user: null,
    accessToken: null,
    refreshToken: null,
    hydrated: false,
    loading: false,
    error: null,
  });
}

/** 读取 mock 到的刷新请求体（验证「用哪个 token 去续期」）。 */
function refreshBodyOf(calls: { url: string; init?: RequestInit }[]): { refresh_token?: string } {
  const call = calls.find((c) => c.url.includes('/auth/refresh'));
  if (!call?.init?.body) throw new Error('未捕获到 /auth/refresh 请求');
  return JSON.parse(String(call.init.body)) as { refresh_token?: string };
}

beforeEach(() => {
  Object.values(authMocks).forEach((fn) => fn.mockReset());
  resetStore();
});

describe('auth store · getRefreshToken 的 localStorage 回退', () => {
  it('store 内存态为空但 localStorage 有 token：刷新请求用 localStorage 里的值', async () => {
    // 页面刷新后的真实状态：内存 store 全空，只有 refresh token 落盘
    window.localStorage.setItem(REFRESH_KEY, JSON.stringify('refresh-from-storage'));
    useAuthStore.setState({ accessToken: 'stale' });

    const { calls } = mockFetchByPath({
      '/auth/refresh': () => ok(makeTokens({ access_token: 'access-2', refresh_token: 'refresh-2' })),
      '/users/me/overview': () => unauthorized(),
    });

    await expect(apiGet('/users/me/overview')).rejects.toBeInstanceOf(ApiRequestError);

    // 关键断言：走的是 `store.refreshToken ?? readLocal(...)` 的右半边
    expect(refreshBodyOf(calls)).toEqual({ refresh_token: 'refresh-from-storage' });
    // 续期成功后新令牌同时进 store 与 localStorage
    expect(useAuthStore.getState().accessToken).toBe('access-2');
    expect(window.localStorage.getItem(REFRESH_KEY)).toBe('"refresh-2"');
  });

  it('store 有值时优先用 store（不回落到过期的 localStorage）', async () => {
    useAuthStore.setState({ accessToken: 'stale', refreshToken: 'refresh-from-store' });
    window.localStorage.setItem(REFRESH_KEY, JSON.stringify('refresh-from-storage'));

    const { calls } = mockFetchByPath({
      '/auth/refresh': () => ok(makeTokens({ access_token: 'access-3', refresh_token: 'refresh-3' })),
      '/users/me/overview': () => unauthorized(),
    });

    await expect(apiGet('/users/me/overview')).rejects.toBeInstanceOf(ApiRequestError);

    expect(refreshBodyOf(calls)).toEqual({ refresh_token: 'refresh-from-store' });
  });

  it('两处都没有 token：根本不发刷新请求，直接判定会话过期', async () => {
    // 不写 localStorage、store 也为空 —— 这是「确实未登录」，不应产生任何刷新流量
    useAuthStore.setState({ accessToken: 'stale' });

    const { calls } = mockFetchByPath({ '/users/me/overview': () => unauthorized() });

    await expect(apiGet('/users/me/overview')).rejects.toBeInstanceOf(ApiRequestError);

    expect(calls.some((c) => c.url.includes('/auth/refresh'))).toBe(false);
    expect(useAuthStore.getState().accessToken).toBeNull();
  });
});

describe('auth store · logout 的 refresh token 回退', () => {
  it('store 为空但 localStorage 有值：仍调后端吊销该 token', async () => {
    window.localStorage.setItem(REFRESH_KEY, JSON.stringify('refresh-orphan'));
    authMocks.logout.mockResolvedValue(null);

    await useAuthStore.getState().logout();

    // 不吊销等于 token 仍可在服务端换新 access token
    expect(authMocks.logout).toHaveBeenCalledWith('refresh-orphan');
    expect(window.localStorage.getItem(REFRESH_KEY)).toBeNull();
  });
});

describe('auth store · 令牌缺失时的用户兜底', () => {
  it('login 返回体没有 user：保留登录前已有的 user，不踢回未登录', async () => {
    useAuthStore.setState({ user: makeUser({ username: 'old-user', display_name: '老用户' }) });
    // 类型上 user 必填，但后端偶发缺失时不能把已登录用户清空（persistTokens 的 ?? 分支）
    const tokensWithoutUser = {
      access_token: 'access-x',
      refresh_token: 'refresh-x',
      token_type: 'bearer',
      expires_in: 900,
    } as unknown as TokenPair;
    authMocks.login.mockResolvedValue(tokensWithoutUser);

    await useAuthStore.getState().login('kou', 'Passw0rd!');

    const s = useAuthStore.getState();
    expect(s.accessToken).toBe('access-x');
    expect(s.user?.username).toBe('old-user');
    // 令牌照常落盘
    expect(window.localStorage.getItem(REFRESH_KEY)).toBe('"refresh-x"');
  });

  it('onTokensRefreshed 只更新令牌，不清空 user（刷新不应把用户踢下线）', async () => {
    useAuthStore.setState({ user: makeUser({ username: 'keep-me' }), accessToken: 'stale', refreshToken: 'refresh-1' });

    const { calls } = mockFetchByPath({
      '/auth/refresh': () => ok(makeTokens({ access_token: 'access-n', refresh_token: 'refresh-n' })),
      '/users/me/overview': () => unauthorized(),
    });

    await expect(apiGet('/users/me/overview')).rejects.toBeInstanceOf(ApiRequestError);

    const s = useAuthStore.getState();
    expect(s.accessToken).toBe('access-n');
    // 用户资料必须原样保留 —— 注入回调里没有 setState({ user: null })
    expect(s.user?.username).toBe('keep-me');
    expect(s.user?.display_name).toBe('寇豆码');
    expect(calls.length).toBeGreaterThan(0);
  });
});

describe('auth store · hydrate 的 loading 状态机', () => {
  it('换取令牌期间 loading=true，结束后复位', async () => {
    window.localStorage.setItem(REFRESH_KEY, JSON.stringify('refresh-1'));
    let releaseRefresh: (value: TokenPair) => void = () => undefined;
    authMocks.refresh.mockImplementation(
      () =>
        new Promise<TokenPair>((resolve) => {
          releaseRefresh = resolve;
        }),
    );

    const pending = useAuthStore.getState().hydrate();

    // 请求在途：必须处于 loading，UI 据此显示骨架屏
    expect(useAuthStore.getState().loading).toBe(true);
    expect(useAuthStore.getState().hydrated).toBe(false);

    releaseRefresh(makeTokens());
    await pending;

    const s = useAuthStore.getState();
    expect(s.loading).toBe(false);
    expect(s.hydrated).toBe(true);
  });
});

/** 订阅 store 的探针组件：验证 selector 订阅与重渲染契约。 */
function AuthProbe() {
  const accessToken = useAuthStore((s) => s.accessToken);
  const username = useAuthStore((s) => s.user?.username ?? 'anonymous');
  const error = useAuthStore((s) => s.error);
  return (
    <div>
      <span data-testid="token">{accessToken ?? 'none'}</span>
      <span data-testid="user">{username}</span>
      <span data-testid="error">{error ?? 'no-error'}</span>
    </div>
  );
}

describe('auth store · 作为 React hook 的订阅契约', () => {
  it('login / logout 触发 selector 重渲染（组件拿到的是最新值）', async () => {
    authMocks.login.mockResolvedValue(makeTokens());
    authMocks.logout.mockResolvedValue(null);

    render(<AuthProbe />);
    expect(screen.getByTestId('token')).toHaveTextContent('none');
    expect(screen.getByTestId('user')).toHaveTextContent('anonymous');

    await act(async () => {
      await useAuthStore.getState().login('kou', 'Passw0rd!');
    });

    // 登录后必须重渲染 —— 不重渲染就是「登录成功但界面仍是未登录」
    expect(screen.getByTestId('token')).toHaveTextContent('access-1');
    expect(screen.getByTestId('user')).toHaveTextContent('kou');

    await act(async () => {
      await useAuthStore.getState().logout();
    });

    expect(screen.getByTestId('token')).toHaveTextContent('none');
    expect(screen.getByTestId('user')).toHaveTextContent('anonymous');
  });

  it('登录失败只驱动 error 字段变化，token/user 视图保持不变', async () => {
    authMocks.login.mockRejectedValue(new ApiRequestError('raw', 401, 'INVALID_CREDENTIALS'));

    render(<AuthProbe />);

    await act(async () => {
      await useAuthStore.getState().login('kou', 'wrong');
    });

    expect(screen.getByTestId('error')).toHaveTextContent('账号或密码错误');
    expect(screen.getByTestId('token')).toHaveTextContent('none');
    expect(screen.getByTestId('user')).toHaveTextContent('anonymous');
  });
});