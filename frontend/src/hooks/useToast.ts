'use client';

import { useCallback } from 'react';
import { useUiStore, type ToastVariant } from '@/store/ui';

export interface ToastOptions {
  title: string;
  description?: string;
  variant?: ToastVariant;
  duration?: number;
}

/**
 * Toast Hook：基于 zustand 的轻量提示。
 * @example const toast = useToast(); toast({ title: '保存成功', variant: 'success' });
 */
export function useToast(): (options: ToastOptions) => string {
  const notify = useUiStore((state) => state.notify);
  return useCallback((options: ToastOptions) => notify(options), [notify]);
}

/** 便捷包装：直接拿到 success / error 两个常用方法。 */
export function useToaster() {
  const notify = useUiStore((state) => state.notify);
  return {
    toast: (options: ToastOptions) => notify(options),
    success: (title: string, description?: string) => notify({ title, description, variant: 'success' }),
    error: (title: string, description?: string) => notify({ title, description, variant: 'error' }),
    info: (title: string, description?: string) => notify({ title, description, variant: 'info' }),
  };
}
