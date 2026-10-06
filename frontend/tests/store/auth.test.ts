// @vitest-environment jsdom
/**
 * `src/store/auth.ts` —— L3 状态层：登录态流转 + 令牌持久化。
 *
 * 关键点（也是最容易回归的地方）：
 * 1. **Access Token 只在内存、Refresh Token 落 localStorage**（`pythonlab:auth.refresh_token`），
 *    刷新页面靠 `hydrate()` 用 refresh token 换回来；
 * 2. 模块初始化时通过 `configureApiClient` 注入令牌回调，
 *    所以本文件用**部分 mock**：只替换 `authApi`，保留真实的 `apiGet` / `configureApiClient`，
 *    这样才能验证「401 → onSessionExpired」这条真实链路；
 * 3. `useAuthStore` 是模块级单例，每个用例必须显式复位。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';

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

// 部分 mock：保留 apiGet / configureApiClient 等真实实现，只替换 authApi 的方法
vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>();
  return { ...actual, authApi: { ...actual.authApi, ...authMocks } };
});

import { useAuthStore, resolveErrorMessage } from '@/store/auth';
import { apiGet, ApiRequestError } from '@/lib/api';
import { STORAGE_KEYS } from '@/lib/storage';
import { mockFetchByPath, ok, unauthorized } from '../helpers/fetch-mock';
import type { TokenPair, UserBrief, UserMe } from '@/lib/types';

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

function makeMe(overrides: Partial<UserMe> = {}): UserMe {
  return {
    id: 'u-1',
    email: 'k@example.com',
    username: 'kou',
    role: 'user',
    status: 'active',
    is_verified: true,
    xp: 420,
    level: 3,
    streak_days: 7,
    max_streak_days: 7,
    login_count: 12,
    created_at: '2026-09-01T00:00:00',
    last_login_at: '2026-10-01T00:00:00',
    profile: {
      display_name: '寇豆码',
      avatar_url: null,
      bio: null,
      theme_preference: 'dark',
      ai_mode: 'standard',
      learning_mode: 'system',
    },
    ...overrides,
  };
}

/** 把 store 复位到「未登录 + 未 hydrate」的初始态。 */
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

beforeEach(() => {
  Object.values(authMocks).forEach((fn) => fn.mockReset());
  resetStore();
});

describe('auth store · login', () => {
  it('成功：返回 true，令牌落 store，refresh token 持久化', async () => {
    authMocks.login.mockResolvedValue(makeTokens());

    const okLogin = await useAuthStore.getState().login('kou', 'Passw0rd!');

    expect(okLogin).toBe(true);
    const s = useAuthStore.getState();
    expect(s.accessToken).toBe('access-1');
    expect(s.refreshToken).toBe('refresh-1');
    expect(s.user?.username).toBe('kou');
    expect(s.loading).toBe(false);
    expect(s.error).toBeNull();
    // refresh token 必须落 localStorage，access token 绝不能落盘
    expect(window.localStorage.getItem(REFRESH_KEY)).toBe('"refresh-1"');
    expect(window.localStorage.getItem(REFRESH_KEY)).not.toContain('access-1');
  });

  it('失败：INVALID_CREDENTIALS 映射为中文，返回 false 且不落任何令牌', async () => {
    authMocks.login.mockRejectedValue(new ApiRequestError('raw', 401, 'INVALID_CREDENTIALS'));

    const okLogin = await useAuthStore.getState().login('kou', 'wrong');

    expect(okLogin).toBe(false);
    const s = useAuthStore.getState();
    expect(s.error).toBe('账号或密码错误');
    expect(s.loading).toBe(false);
    expect(s.accessToken).toBeNull();
    expect(s.refreshToken).toBeNull();
    expect(window.localStorage.getItem(REFRESH_KEY)).toBeNull();
  });

  it('失败：未知码透传后端 message', async () => {
    authMocks.login.mockRejectedValue(new ApiRequestError('验证码错误', 400, 'SOME_NEW_CODE'));

    await useAuthStore.getState().login('kou', 'x');

    expect(useAuthStore.getState().error).toBe('验证码错误');
  });

  it('再次登录会先清空上一次的 error', async () => {
    authMocks.login.mockRejectedValueOnce(new ApiRequestError('e', 400, 'RATE_LIMITED'));
    await useAuthStore.getState().login('kou', 'x');
    expect(useAuthStore.getState().error).toBe('操作过于频繁，请稍后再试');

    authMocks.login.mockResolvedValueOnce(makeTokens());
    await useAuthStore.getState().login('kou', 'Passw0rd!');

    expect(useAuthStore.getState().error).toBeNull();
  });
});

describe('auth store · register', () => {
  it('成功：与 login 走同一套令牌落盘逻辑', async () => {
    authMocks.register.mockResolvedValue(makeTokens({ access_token: 'access-new', refresh_token: 'refresh-new' }));

    const okReg = await useAuthStore
      .getState()
      .register({ email: 'k@example.com', username: 'kou', password: 'Passw0rd!' });

    expect(okReg).toBe(true);
    expect(useAuthStore.getState().accessToken).toBe('access-new');
    expect(window.localStorage.getItem(REFRESH_KEY)).toBe('"refresh-new"');
  });

  it('失败：USERNAME_EXISTS 映射为中文', async () => {
    authMocks.register.mockRejectedValue(new ApiRequestError('raw', 409, 'USERNAME_EXISTS'));

    const okReg = await useAuthStore
      .getState()
      .register({ email: 'k@example.com', username: 'taken', password: 'Passw0rd!' });

    expect(okReg).toBe(false);
    expect(useAuthStore.getState().error).toBe('该用户名已被占用');
    expect(window.localStorage.getItem(REFRESH_KEY)).toBeNull();
  });
});

describe('auth store · logout', () => {
  it('带 refresh token 时先调后端登出，再清空 store 与 localStorage', async () => {
    authMocks.logout.mockResolvedValue(null);
    authMocks.login.mockResolvedValue(makeTokens());
    await useAuthStore.getState().login('kou', 'Passw0rd!');

    await useAuthStore.getState().logout();

    expect(authMocks.logout).toHaveBeenCalledWith('refresh-1');
    const s = useAuthStore.getState();
    expect(s.user).toBeNull();
    expect(s.accessToken).toBeNull();
    expect(s.refreshToken).toBeNull();
    expect(window.localStorage.getItem(REFRESH_KEY)).toBeNull();
  });

  it('后端登出报错也必须清本地会话（不得卡在登录态）', async () => {
    authMocks.login.mockResolvedValue(makeTokens());
    await useAuthStore.getState().login('kou', 'Passw0rd!');
    authMocks.logout.mockRejectedValue(new Error('network down'));

    await useAuthStore.getState().logout();

    expect(useAuthStore.getState().accessToken).toBeNull();
    expect(window.localStorage.getItem(REFRESH_KEY)).toBeNull();
  });

  it('无 refresh token 时不调后端接口', async () => {
    await useAuthStore.getState().logout();
    expect(authMocks.logout).not.toHaveBeenCalled();
  });
});

describe('auth store · hydrate（刷新页面恢复登录态）', () => {
  it('无本地 refresh token：直接标记 hydrated，不发任何请求', async () => {
    await useAuthStore.getState().hydrate();

    expect(authMocks.refresh).not.toHaveBeenCalled();
    expect(authMocks.me).not.toHaveBeenCalled();
    expect(useAuthStore.getState().hydrated).toBe(true);
    expect(useAuthStore.getState().accessToken).toBeNull();
  });

  it('有本地 refresh token：换取新令牌并用 /auth/me 补齐用户资料', async () => {
    window.localStorage.setItem(REFRESH_KEY, JSON.stringify('refresh-stored'));
    authMocks.refresh.mockResolvedValue(makeTokens({ access_token: 'access-2', refresh_token: 'refresh-2' }));
    authMocks.me.mockResolvedValue(makeMe({ level: 9, xp: 9999 }));

    await useAuthStore.getState().hydrate();

    expect(authMocks.refresh).toHaveBeenCalledWith('refresh-stored');
    const s = useAuthStore.getState();
    expect(s.accessToken).toBe('access-2');
    expect(s.hydrated).toBe(true);
    expect(s.loading).toBe(false);
    // /auth/me 的 level/xp 覆盖 token 内的旧值
    expect(s.user?.level).toBe(9);
    expect(s.user?.xp).toBe(9999);
    // refresh token 轮换后要覆盖旧值
    expect(window.localStorage.getItem(REFRESH_KEY)).toBe('"refresh-2"');
  });

  it('/auth/me 失败时用 token 内用户兜底，仍标记 hydrated（优雅降级）', async () => {
    window.localStorage.setItem(REFRESH_KEY, JSON.stringify('refresh-stored'));
    authMocks.refresh.mockResolvedValue(makeTokens());
    authMocks.me.mockRejectedValue(new Error('me 500'));

    await useAuthStore.getState().hydrate();

    const s = useAuthStore.getState();
    expect(s.hydrated).toBe(true);
    expect(s.accessToken).toBe('access-1');
    expect(s.user?.username).toBe('kou');
  });

  it('刷新失败：清除本地 token 并标记 hydrated（不得卡在骨架屏）', async () => {
    window.localStorage.setItem(REFRESH_KEY, JSON.stringify('refresh-expired'));
    authMocks.refresh.mockRejectedValue(new Error('401'));

    await useAuthStore.getState().hydrate();

    const s = useAuthStore.getState();
    expect(s.hydrated).toBe(true);
    expect(s.accessToken).toBeNull();
    expect(s.user).toBeNull();
    expect(window.localStorage.getItem(REFRESH_KEY)).toBeNull();
  });

  it('幂等：已 hydrate 后再调用不发请求', async () => {
    authMocks.login.mockResolvedValue(makeTokens());
    await useAuthStore.getState().login('kou', 'Passw0rd!');
    useAuthStore.setState({ hydrated: true });

    await useAuthStore.getState().hydrate();

    expect(authMocks.refresh).not.toHaveBeenCalled();
  });
});

describe('auth store · configureApiClient 注入的回调（真实 401 链路）', () => {
  it('无 refresh token 的 401 → onSessionExpired 清空登录态与本地 token', async () => {
    useAuthStore.setState({ accessToken: 'stale', user: makeUser() });
    mockFetchByPath({ '/users/me/overview': () => unauthorized() });

    await expect(apiGet('/users/me/overview')).rejects.toBeInstanceOf(ApiRequestError);

    const s = useAuthStore.getState();
    expect(s.accessToken).toBeNull();
    expect(s.user).toBeNull();
    expect(window.localStorage.getItem(REFRESH_KEY)).toBeNull();
  });

  it('刷新成功 → onTokensRefreshed 把新令牌写进 store 与 localStorage', async () => {
    useAuthStore.setState({ accessToken: 'stale', refreshToken: 'refresh-stored' });
    mockFetchByPath({
      '/auth/refresh': () => ok({ access_token: 'access-new', refresh_token: 'refresh-new' }),
      // 首次 401 触发刷新；重试仍 401，函数最终以 ApiRequestError 结束
      '/users/me/overview': () => unauthorized(),
    });

    await expect(apiGet('/users/me/overview')).rejects.toBeInstanceOf(ApiRequestError);

    // 注入的 onTokensRefreshed 必须在真实链路上把新令牌落到 store + localStorage
    const after = useAuthStore.getState();
    expect(after.accessToken).toBe('access-new');
    expect(after.refreshToken).toBe('refresh-new');
    expect(window.localStorage.getItem(REFRESH_KEY)).toBe('"refresh-new"');
  });
});

describe('auth store · refreshProfile / setUser / clearError', () => {
  it('refreshProfile 用 /auth/me 覆盖 user', async () => {
    useAuthStore.setState({ user: makeUser({ level: 1, xp: 0 }) });
    authMocks.me.mockResolvedValue(makeMe({ level: 7, xp: 5000, profile: { ...makeMe().profile!, display_name: '新昵称' } }));

    await useAuthStore.getState().refreshProfile();

    const u = useAuthStore.getState().user;
    expect(u?.level).toBe(7);
    expect(u?.display_name).toBe('新昵称');
  });

  it('refreshProfile 静默失败：user 保持不变且不抛错', async () => {
    useAuthStore.setState({ user: makeUser() });
    authMocks.me.mockRejectedValue(new Error('500'));

    await expect(useAuthStore.getState().refreshProfile()).resolves.toBeUndefined();

    expect(useAuthStore.getState().user?.username).toBe('kou');
  });

  it('setUser 与 clearError 生效', () => {
    useAuthStore.setState({ user: makeUser() });
    useAuthStore.getState().setUser(null);
    expect(useAuthStore.getState().user).toBeNull();

    useAuthStore.setState({ error: 'boom' });
    useAuthStore.getState().clearError();
    expect(useAuthStore.getState().error).toBeNull();
  });
});

describe('auth store · resolveErrorMessage 复用', () => {
  it('store 直接复用该函数（非重复实现）', () => {
    expect(resolveErrorMessage(new ApiRequestError('x', 400, 'WEAK_PASSWORD'), 'fb')).toBe(
      '密码强度不足，至少 8 位并包含字母和数字',
    );
  });
});
