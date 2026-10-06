// @vitest-environment jsdom
/**
 * `src/hooks/usePythonRunner.ts` —— L3 Hook 状态机（docs/TESTING.md §4.5）。
 *
 * 关注点：
 * 1. 成功路径：result.stdout 透传、running 终态为 false；
 * 2. 失败路径：error 非空、result 保持 null（**不得残留上次结果**）；
 * 3. reset() 同时清空 result 与 error；
 * 4. 未登录短路：不打后端、直接给中文提示。
 *
 * 只 mock `pythonApi.run`（`vi.mock` + `importOriginal` 保留其余导出），
 * 因为 `store/auth.ts` 在模块初始化时就会调用 `configureApiClient`，
 * 若整体替换 `@/lib/api` 会在导入阶段抛错。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';

const { runMock } = vi.hoisted(() => ({ runMock: vi.fn() }));

vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>();
  return { ...actual, pythonApi: { run: runMock } };
});

import { usePythonRunner } from '@/hooks/usePythonRunner';
import { useAuthStore } from '@/store/auth';
import type { RunResponse } from '@/lib/types';

/** 构造一个合法的 RunResponse（字段与后端 python_runner 契约一致）。 */
function makeResult(overrides: Partial<RunResponse> = {}): RunResponse {
  return {
    request_id: 'req-1',
    status: 'success',
    exit_code: 0,
    stdout: 'hello\n',
    stderr: '',
    truncated: false,
    time_ms: 12,
    memory_kb: 2048,
    error: null,
    error_type: null,
    runner: 'local',
    degraded: false,
    ...overrides,
  };
}

/** 可控的延迟 promise，用于观察中间态 running === true。 */
function deferred<T>(): { promise: Promise<T>; resolve: (value: T) => void; reject: (reason: unknown) => void } {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

beforeEach(() => {
  runMock.mockReset();
  // 已登录：usePythonRunner 以 accessToken 判定是否放行。
  // 只在 beforeEach 复位 —— 放到 afterEach 会在 cleanup 之前触发订阅更新，
  // 产生 "not wrapped in act(...)" 噪声警告。
  useAuthStore.setState({ accessToken: 'test-access-token', refreshToken: 'test-refresh-token' });
});

describe('usePythonRunner · 成功路径（用例27）', () => {
  it('run() 成功后 result.stdout 正确透传，running 终为 false', async () => {
    runMock.mockResolvedValue(makeResult({ stdout: 'Python LAB\n' }));

    const { result } = renderHook(() => usePythonRunner());
    expect(result.current.result).toBeNull();
    expect(result.current.running).toBe(false);

    // 用对象承接返回值：TS 不会跟踪闭包里的局部变量赋值，直接用 let 会被收窄成 never
    const box: { value: RunResponse | null } = { value: null };
    await act(async () => {
      box.value = await result.current.run([{ path: 'main.py', content: 'print("Python LAB")' }]);
    });

    expect(box.value?.stdout).toBe('Python LAB\n');
    expect(result.current.result?.stdout).toBe('Python LAB\n');
    expect(result.current.running).toBe(false);
    expect(result.current.error).toBeNull();
    expect(runMock).toHaveBeenCalledTimes(1);
  });

  it('promise 未 settle 前 running 为 true（中间态）', async () => {
    const gate = deferred<RunResponse>();
    runMock.mockReturnValue(gate.promise);

    const { result } = renderHook(() => usePythonRunner());

    let pending: Promise<RunResponse | null> | null = null;
    await act(async () => {
      pending = result.current.run([{ path: 'main.py', content: 'pass' }]);
      await Promise.resolve();
    });
    expect(result.current.running).toBe(true);

    await act(async () => {
      gate.resolve(makeResult());
      await pending;
    });
    expect(result.current.running).toBe(false);
  });

  it('请求体携带 files / entry / 默认 timeout_ms=5000', async () => {
    runMock.mockResolvedValue(makeResult());
    const { result } = renderHook(() => usePythonRunner());

    await act(async () => {
      await result.current.run([{ path: 'main.py', content: 'pass' }], { entry: 'main.py', stdin: '1\n' });
    });

    expect(runMock).toHaveBeenCalledWith({
      files: [{ path: 'main.py', content: 'pass' }],
      entry: 'main.py',
      stdin: '1\n',
      timeout_ms: 5000,
    });
  });

  it('显式传入 timeoutMs 时覆盖默认值', async () => {
    runMock.mockResolvedValue(makeResult());
    const { result } = renderHook(() => usePythonRunner());

    await act(async () => {
      await result.current.run([{ path: 'main.py', content: 'pass' }], { timeoutMs: 1500 });
    });

    expect(runMock.mock.calls[0]![0]).toMatchObject({ timeout_ms: 1500 });
  });
});

describe('usePythonRunner · 失败路径（用例28）', () => {
  it('pythonApi.run reject → error 非空，result 为 null', async () => {
    runMock.mockRejectedValue(new Error('运行服务暂时不可用'));

    const { result } = renderHook(() => usePythonRunner());
    const box: { value: RunResponse | null } = { value: makeResult() };
    await act(async () => {
      box.value = await result.current.run([{ path: 'main.py', content: 'pass' }]);
    });

    expect(box.value).toBeNull();
    expect(result.current.result).toBeNull();
    expect(result.current.error).toBe('运行服务暂时不可用');
    expect(result.current.running).toBe(false);
  });

  it('非 Error 抛出物也给出兜底文案（不抛给调用方）', async () => {
    runMock.mockRejectedValue('boom');

    const { result } = renderHook(() => usePythonRunner());
    await act(async () => {
      await result.current.run([{ path: 'main.py', content: 'pass' }]);
    });

    expect(result.current.error).toBeTruthy();
    expect(result.current.result).toBeNull();
  });

  it('失败不会残留上一次的 result', async () => {
    runMock.mockResolvedValueOnce(makeResult({ stdout: 'first\n' }));
    const { result } = renderHook(() => usePythonRunner());

    await act(async () => {
      await result.current.run([{ path: 'main.py', content: 'pass' }]);
    });
    expect(result.current.result?.stdout).toBe('first\n');

    runMock.mockRejectedValueOnce(new Error('第二次失败'));
    await act(async () => {
      await result.current.run([{ path: 'main.py', content: 'pass' }]);
    });
    expect(result.current.error).toBe('第二次失败');
  });
});

describe('usePythonRunner · reset（用例29）', () => {
  it('reset() 同时清空 result 与 error', async () => {
    runMock.mockRejectedValueOnce(new Error('先失败一次'));
    const { result } = renderHook(() => usePythonRunner());

    await act(async () => {
      await result.current.run([{ path: 'main.py', content: 'pass' }]);
    });
    expect(result.current.error).toBeTruthy();

    act(() => {
      result.current.reset();
    });

    expect(result.current.result).toBeNull();
    expect(result.current.error).toBeNull();
    expect(result.current.running).toBe(false);
  });
});

describe('usePythonRunner · 未登录短路', () => {
  it('无 accessToken 时不发请求，返回中文提示', async () => {
    useAuthStore.setState({ accessToken: null });
    const { result } = renderHook(() => usePythonRunner());

    const box: { value: RunResponse | null } = { value: makeResult() };
    await act(async () => {
      box.value = await result.current.run([{ path: 'main.py', content: 'pass' }]);
    });

    expect(runMock).not.toHaveBeenCalled();
    expect(box.value).toBeNull();
    expect(result.current.error).toContain('登录');
    expect(result.current.running).toBe(false);
  });
});
