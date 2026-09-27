'use client';

/**
 * UI 状态仓库：Toast 队列、侧边栏折叠、命令面板开关。
 * 主题由 next-themes 管理，这里仅保存用户显式选择的模式以便服务端渲染前取用。
 */

import { create } from 'zustand';

export type ToastVariant = 'default' | 'success' | 'error' | 'warning' | 'info';

export interface ToastItem {
  id: string;
  title: string;
  description?: string;
  variant: ToastVariant;
  duration: number;
}

export interface UiState {
  toasts: ToastItem[];
  sidebarCollapsed: boolean;
  commandOpen: boolean;
  notify: (payload: { title: string; description?: string; variant?: ToastVariant; duration?: number }) => string;
  dismiss: (id: string) => void;
  toggleSidebar: () => void;
  setCommandOpen: (open: boolean) => void;
}

let toastSeq = 0;

export const useUiStore = create<UiState>((set, get) => ({
  toasts: [],
  sidebarCollapsed: false,
  commandOpen: false,

  notify({ title, description, variant = 'default', duration = 3200 }) {
    toastSeq += 1;
    const id = `toast-${toastSeq}`;
    set({ toasts: [...get().toasts, { id, title, description, variant, duration }] });
    if (typeof window !== 'undefined' && duration > 0) {
      window.setTimeout(() => {
        get().dismiss(id);
      }, duration);
    }
    return id;
  },

  dismiss(id) {
    set({ toasts: get().toasts.filter((toast) => toast.id !== id) });
  },

  toggleSidebar() {
    set({ sidebarCollapsed: !get().sidebarCollapsed });
  },

  setCommandOpen(open) {
    set({ commandOpen: open });
  },
}));
