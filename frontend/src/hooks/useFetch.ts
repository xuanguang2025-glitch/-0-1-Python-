'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

export interface FetchResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  /** 手动重新拉取。 */
  refresh: () => void;
  /** 本地更新数据（乐观更新用）。 */
  setData: (value: T | null) => void;
}

export interface FetchOptions {
  /** false 时不自动发起请求（例如需要登录后才能调用）。 */
  enabled?: boolean;
  /** 后端不可用时的兜底数据，保证页面不白屏。 */
  fallback?: unknown;
}

/**
 * 轻量数据请求 Hook。
 * 设计目标：后端不可用时返回 null + error 文案，页面自行渲染空态，绝不抛错。
 *
 * @param fetcher 请求函数（返回值应已解包为 data）
 * @param deps 依赖数组，变化即重新请求
 */
export function useFetch<T>(fetcher: () => Promise<T>, deps: unknown[] = [], options: FetchOptions = {}): FetchResult<T> {
  const { enabled = true } = options;
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState<boolean>(enabled);
  const [error, setError] = useState<string | null>(null);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const load = useCallback(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    fetcherRef
      .current()
      .then((result) => {
        if (!mounted.current) return;
        setData(result ?? null);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (!mounted.current) return;
        setData(null);
        setError(err instanceof Error ? err.message : '数据加载失败');
        setLoading(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, ...deps]);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load]);

  return { data, loading, error, refresh: load, setData };
}

export interface AsyncActionResult<A extends unknown[], T> {
  run: (...args: A) => Promise<T | null>;
  loading: boolean;
  error: string | null;
}

/** 写操作 Hook：提交 / 保存等。返回 null 表示失败（错误已通过 error 暴露）。 */
export function useAsyncAction<A extends unknown[], T>(
  action: (...args: A) => Promise<T>,
  hooks?: { onSuccess?: (result: T) => void; onError?: (message: string) => void },
): AsyncActionResult<A, T> {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const actionRef = useRef(action);
  actionRef.current = action;
  const hooksRef = useRef(hooks);
  hooksRef.current = hooks;

  const run = useCallback(async (...args: A): Promise<T | null> => {
    setLoading(true);
    setError(null);
    try {
      const result = await actionRef.current(...args);
      hooksRef.current?.onSuccess?.(result);
      return result;
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '操作失败';
      setError(message);
      hooksRef.current?.onError?.(message);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  return { run, loading, error };
}
