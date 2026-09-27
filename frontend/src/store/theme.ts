'use client';

/**
 * 主题仓库：浅色 / 深色 / 跟随系统。
 * 实际 DOM class 由 next-themes 注入，本仓库负责保存用户偏好并在切换后同步 Monaco 主题。
 */

import { create } from 'zustand';
import { readLocal, writeLocal } from '@/lib/storage';

export type ThemeMode = 'light' | 'dark' | 'system';

export interface ThemeState {
  mode: ThemeMode;
  /** 解析后的实际主题（供 Monaco 等需要明确 light/dark 的组件使用）。 */
  resolved: 'light' | 'dark';
  setMode: (mode: ThemeMode) => void;
  setResolved: (resolved: 'light' | 'dark') => void;
  hydrate: () => void;
}

export const useThemeStore = create<ThemeState>((set, get) => ({
  mode: 'dark',
  resolved: 'dark',

  setMode(mode) {
    writeLocal('ui.theme', mode);
    set({ mode, resolved: mode === 'system' ? get().resolved : mode });
  },

  setResolved(resolved) {
    set({ resolved });
  },

  hydrate() {
    const stored = readLocal<ThemeMode | null>('ui.theme', null);
    if (!stored) return;
    set({ mode: stored, resolved: stored === 'system' ? get().resolved : stored });
  },
}));

/** Monaco 主题名（需与 monaco 主题注册保持一致）。 */
export function monacoThemeOf(resolved: 'light' | 'dark'): string {
  return resolved === 'dark' ? 'python-dark' : 'python-light';
}
