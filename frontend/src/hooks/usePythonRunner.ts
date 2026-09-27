'use client';

import { useCallback, useState } from 'react';
import { pythonApi } from '@/lib/api';
import { useAuthStore } from '@/store/auth';
import type { RunFile, RunResponse } from '@/lib/types';

export interface UsePythonRunnerResult {
  result: RunResponse | null;
  running: boolean;
  error: string | null;
  run: (files: RunFile[], options?: { entry?: string; stdin?: string; timeoutMs?: number }) => Promise<RunResponse | null>;
  reset: () => void;
  setResult: (value: RunResponse | null) => void;
}

/**
 * 代码执行 Hook：封装 /api/python/run。
 * 未登录或后端不可用时返回友好错误文案，不会抛出异常。
 */
export function usePythonRunner(): UsePythonRunnerResult {
  const [result, setResult] = useState<RunResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isAuthenticated = useAuthStore((state) => Boolean(state.accessToken));

  const run = useCallback<UsePythonRunnerResult['run']>(
    async (files, options) => {
      if (!isAuthenticated) {
        setError('运行代码需要先登录，请登录后重试。');
        return null;
      }
      setRunning(true);
      setError(null);
      try {
        const response = await pythonApi.run({
          files,
          entry: options?.entry,
          stdin: options?.stdin,
          timeout_ms: options?.timeoutMs ?? 5000,
        });
        setResult(response);
        return response;
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : '运行失败';
        setError(message || '运行服务暂时不可用，请稍后再试。');
        return null;
      } finally {
        setRunning(false);
      }
    },
    [isAuthenticated],
  );

  const reset = useCallback(() => {
    setResult(null);
    setError(null);
  }, []);

  return { result, running, error, run, reset, setResult };
}
