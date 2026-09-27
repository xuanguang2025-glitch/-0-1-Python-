'use client';

import { useEffect, useState } from 'react';
import { useAuthStore } from '@/store/auth';
import { useRouter } from 'next/navigation';
import type { UserBrief } from '@/lib/types';

export interface UseAuthResult {
  user: UserBrief | null;
  isAuthenticated: boolean;
  isAdmin: boolean;
  hydrated: boolean;
  loading: boolean;
  error: string | null;
  login: (account: string, password: string) => Promise<boolean>;
  register: (payload: { email: string; username: string; password: string }) => Promise<boolean>;
  logout: () => Promise<void>;
  /** 重新拉取 /auth/me，同步最新的用户信息。 */
  refreshProfile: () => Promise<void>;
  clearError: () => void;
}

/**
 * 认证 Hook：负责会话恢复（页面刷新时用 Refresh Token 换取 Access Token）。
 */
export function useAuth(): UseAuthResult {
  const user = useAuthStore((state) => state.user);
  const accessToken = useAuthStore((state) => state.accessToken);
  const hydrated = useAuthStore((state) => state.hydrated);
  const loading = useAuthStore((state) => state.loading);
  const error = useAuthStore((state) => state.error);
  const hydrate = useAuthStore((state) => state.hydrate);

  useEffect(() => {
    void hydrate();
  }, [hydrate]);

  return {
    user,
    isAuthenticated: Boolean(accessToken && user),
    isAdmin: Boolean(user && (user.role === 'admin' || user.role === 'superadmin')),
    hydrated,
    loading,
    error,
    login: useAuthStore((state) => state.login),
    register: useAuthStore((state) => state.register),
    logout: useAuthStore((state) => state.logout),
    refreshProfile: useAuthStore((state) => state.refreshProfile),
    clearError: useAuthStore((state) => state.clearError),
  };
}

/** 需要登录才能访问的页面：未登录跳转登录页并携带回跳地址。 */
export function useRequireAuth(returnTo?: string): UseAuthResult {
  const auth = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!auth.hydrated) return;
    if (auth.isAuthenticated) return;
    const target = returnTo ?? (typeof window !== 'undefined' ? window.location.pathname + window.location.search : '/dashboard');
    router.replace(`/login?redirect=${encodeURIComponent(target)}`);
  }, [auth.hydrated, auth.isAuthenticated, returnTo, router]);

  return auth;
}
