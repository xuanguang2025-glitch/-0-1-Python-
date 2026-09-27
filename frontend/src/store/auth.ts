'use client';

/**
 * 认证状态仓库。
 * - Access Token 仅保存在内存（刷新页面后由 Refresh Token 换取）
 * - Refresh Token 保存在 localStorage
 */

import { create } from 'zustand';
import { authApi, configureApiClient } from '@/lib/api';
import { STORAGE_KEYS, readLocal, removeLocal, writeLocal } from '@/lib/storage';
import type { TokenPair, UserBrief, UserMe } from '@/lib/types';

export interface AuthState {
  user: UserBrief | null;
  accessToken: string | null;
  refreshToken: string | null;
  /** 会话恢复是否已完成，避免未登录闪烁。 */
  hydrated: boolean;
  loading: boolean;
  error: string | null;

  hydrate: () => Promise<void>;
  login: (account: string, password: string) => Promise<boolean>;
  register: (payload: { email: string; username: string; password: string }) => Promise<boolean>;
  logout: () => Promise<void>;
  refreshProfile: () => Promise<void>;
  setUser: (user: UserBrief | null) => void;
  clearError: () => void;
}

function persistTokens(state: AuthState, tokens: TokenPair): Partial<AuthState> {
  writeLocal(STORAGE_KEYS.refreshToken, tokens.refresh_token);
  return {
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token,
    user: tokens.user ?? state.user,
  };
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  accessToken: null,
  refreshToken: null,
  hydrated: false,
  loading: false,
  error: null,

  async hydrate() {
    if (get().hydrated) return;
    if (typeof window === 'undefined') {
      set({ hydrated: true });
      return;
    }
    const stored = readLocal<string | null>(STORAGE_KEYS.refreshToken, null);
    if (!stored) {
      set({ hydrated: true });
      return;
    }
    set({ loading: true });
    try {
      const tokens = await authApi.refresh(stored);
      writeLocal(STORAGE_KEYS.refreshToken, tokens.refresh_token);
      let user: UserBrief = tokens.user;
      try {
        const me: UserMe = await authApi.me();
        user = { ...tokens.user, ...mapMeToBrief(me) };
      } catch {
        /* me 失败时用 token 内的用户信息兜底 */
      }
      set({ accessToken: tokens.access_token, refreshToken: tokens.refresh_token, user, hydrated: true, loading: false });
    } catch {
      removeLocal(STORAGE_KEYS.refreshToken);
      set({ accessToken: null, refreshToken: null, user: null, hydrated: true, loading: false });
    }
  },

  async login(account, password) {
    set({ loading: true, error: null });
    try {
      const tokens = await authApi.login({ account, password });
      set({ ...persistTokens(get(), tokens), loading: false, error: null });
      return true;
    } catch (error) {
      set({ error: resolveErrorMessage(error, '登录失败，请检查账号或密码'), loading: false });
      return false;
    }
  },

  async register(payload) {
    set({ loading: true, error: null });
    try {
      const tokens = await authApi.register(payload);
      set({ ...persistTokens(get(), tokens), loading: false, error: null });
      return true;
    } catch (error) {
      set({ error: resolveErrorMessage(error, '注册失败，请稍后再试'), loading: false });
      return false;
    }
  },

  async logout() {
    const refresh = get().refreshToken ?? readLocal<string | null>(STORAGE_KEYS.refreshToken, null);
    try {
      if (refresh) await authApi.logout(refresh);
    } catch {
      /* 忽略登出接口错误，本地会话仍要清理 */
    }
    removeLocal(STORAGE_KEYS.refreshToken);
    set({ user: null, accessToken: null, refreshToken: null, error: null });
  },

  async refreshProfile() {
    try {
      const me = await authApi.me();
      set({ user: mapMeToBrief(me) });
    } catch {
      /* 静默失败：不影响当前页面 */
    }
  },

  setUser(user) {
    set({ user });
  },

  clearError() {
    set({ error: null });
  },
}));

function mapMeToBrief(me: UserMe): UserBrief {
  return {
    id: me.id,
    email: me.email,
    username: me.username,
    display_name: me.profile?.display_name ?? me.username,
    role: me.role,
    level: me.level,
    xp: me.xp,
  };
}

/** 把后端错误码映射为对用户友好的中文提示。 */
export function resolveErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error) {
    const code = (error as { code?: string }).code;
    if (code === 'INVALID_CREDENTIALS') return '账号或密码错误';
    if (code === 'EMAIL_EXISTS') return '该邮箱已被注册';
    if (code === 'USERNAME_EXISTS') return '该用户名已被占用';
    if (code === 'WEAK_PASSWORD') return '密码强度不足，至少 8 位并包含字母和数字';
    if (code === 'VALIDATION_ERROR') return '请检查表单填写是否完整';
    if (code === 'RATE_LIMITED') return '操作过于频繁，请稍后再试';
    if (code === 'ACCOUNT_SUSPENDED') return '账号已被禁用，请联系管理员';
    if (error.message) return error.message;
  }
  return fallback;
}

// 注入令牌读取与刷新回调（本模块 → api.ts 单向依赖，无循环引用）
configureApiClient({
  getAccessToken: () => useAuthStore.getState().accessToken,
  getRefreshToken: () =>
    useAuthStore.getState().refreshToken ??
    (typeof window === 'undefined' ? null : readLocal<string | null>(STORAGE_KEYS.refreshToken, null)),
  onTokensRefreshed: (tokens: TokenPair) => {
    writeLocal(STORAGE_KEYS.refreshToken, tokens.refresh_token);
    useAuthStore.setState({ accessToken: tokens.access_token, refreshToken: tokens.refresh_token });
  },
  onSessionExpired: () => {
    removeLocal(STORAGE_KEYS.refreshToken);
    useAuthStore.setState({ user: null, accessToken: null, refreshToken: null });
  },
});
