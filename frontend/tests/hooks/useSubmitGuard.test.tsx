// @vitest-environment jsdom
/**
 * `src/hooks/useSubmitGuard.ts` —— 提交守卫单测。
 *
 * 本 hook 是 admin/users、ai-tutor、settings、admin courses/problems/projects
 * 共用的重复提交防线。**最重要的一条性质**是：`begin()` 的判断基于 ref，
 * 同步可见 —— 因此同一 tick 内的重复调用也会被拦下。
 * 若退化成纯 state 判断，下面第一条用例就会失败（返回 true 而不是 false）。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';

import { useSubmitGuard } from '@/hooks/useSubmitGuard';

/** 可控 deferred。 */
function deferred<T>(): { promise: Promise<T>; resolve: (v: T) => void; reject: (e: unknown) => void } {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

beforeEach(() => {
  vi.spyOn(console, 'error').mockImplementation(() => undefined);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('useSubmitGuard · ref 同步性（核心性质）', () => {
  it('同一 tick 内连续 begin 同一 key，只有第一次返回 true', () => {
    const { result } = renderHook(() => useSubmitGuard());

    // 不经过任何 await / act flush，模拟连点：三次调用看到的是同一份 ref
    expect(result.current.begin('save')).toBe(true);
    expect(result.current.begin('save')).toBe(false);
    expect(result.current.begin('save')).toBe(false);
  });

  it('★ 纯 state 实现会在此失败：无 flush 时 begin 仍能拦住重复调用', () => {
    const { result } = renderHook(() => useSubmitGuard());

    let results: boolean[] = [];
    act(() => {
      results = [result.current.begin('x'), result.current.begin('x'), result.current.begin('x')];
    });

    // 第一次放行，后两次被拦 —— 证明判断不依赖重渲染
    expect(results).toEqual([true, false, false]);
  });
});

describe('useSubmitGuard · key 隔离', () => {
  it('不同 key 互不阻塞', () => {
    const { result } = renderHook(() => useSubmitGuard());

    expect(result.current.begin('create')).toBe(true);
    expect(result.current.begin('u-1:role')).toBe(true);
    expect(result.current.begin('u-2:role')).toBe(true);
    // 相同 key 仍被拦
    expect(result.current.begin('create')).toBe(false);
  });

  it('submitting 表反映所有进行中的 key', () => {
    const { result } = renderHook(() => useSubmitGuard());

    act(() => {
      result.current.begin('a');
      result.current.begin('b');
    });

    expect(result.current.submitting).toEqual({ a: true, b: true });
  });
});

describe('useSubmitGuard · 生命周期复位', () => {
  it('end 后同一 key 可再次 begin', () => {
    const { result } = renderHook(() => useSubmitGuard());

    act(() => {
      result.current.begin('save');
    });
    act(() => {
      result.current.end('save');
    });
    expect(result.current.submitting).toEqual({});

    expect(result.current.begin('save')).toBe(true);
  });

  it('end 是幂等的：重复 end 不报错也不产生多余状态变化', () => {
    const { result } = renderHook(() => useSubmitGuard());

    act(() => {
      result.current.begin('save');
    });
    act(() => {
      result.current.end('save');
      result.current.end('save');
      result.current.end('save');
    });

    expect(result.current.submitting).toEqual({});
    expect(console.error).not.toHaveBeenCalled();
  });

  it('只 end 自己那个 key，不影响其它进行中的操作', () => {
    const { result } = renderHook(() => useSubmitGuard());

    act(() => {
      result.current.begin('a');
      result.current.begin('b');
    });
    act(() => {
      result.current.end('a');
    });

    expect(result.current.submitting).toEqual({ b: true });
  });
});

describe('useSubmitGuard · 与真实异步流程配合', () => {
  it('请求 pending 期间拦住重复调用，完成后放行', async () => {
    const gate = deferred<string>();
    const { result } = renderHook(() => useSubmitGuard());

    let firstReturn: string | null = null;
    let secondReturn: string | null = null;

    await act(async () => {
      // 模拟页面写法：begin 失败就直接 return
      const run = async (): Promise<void> => {
        if (!result.current.begin('save')) return;
        try {
          firstReturn = await gate.promise;
        } finally {
          result.current.end('save');
        }
      };
      void run();
      // 同一 tick 内第二次进入，应被拦下且不执行 finally
      if (result.current.begin('save')) {
        try {
          secondReturn = await gate.promise;
        } finally {
          result.current.end('save');
        }
      }
    });

    expect(firstReturn).toBeNull(); // 尚未 resolve
    expect(secondReturn).toBeNull(); // 被拦下，从未执行

    await act(async () => {
      gate.resolve('done');
      await gate.promise;
    });

    expect(firstReturn).toBe('done');
    expect(result.current.submitting).toEqual({});
  });

  it('失败路径同样复位（finally 由调用方保证）', async () => {
    const gate = deferred<string>();
    const { result } = renderHook(() => useSubmitGuard());

    let settled = false;
    const run = async (): Promise<void> => {
      if (!result.current.begin('save')) return;
      try {
        await gate.promise;
      } catch {
        /* 吞掉，模拟页面的 toaster.error */
      } finally {
        result.current.end('save');
        settled = true;
      }
    };

    // 用 void 启动而不是在 act 内直接 await，否则 act 会一直等到超时
    await act(async () => {
      void run();
      await Promise.resolve();
    });
    expect(settled).toBe(false);

    await act(async () => {
      gate.reject(new Error('boom'));
      await gate.promise.catch(() => undefined);
    });

    expect(settled).toBe(true);
    expect(result.current.submitting).toEqual({});
    // 失败也复位 → 可以再次提交
    expect(result.current.begin('save')).toBe(true);
  });

  it('卸载后进行中的请求结束时不再 setState（无 React 警告）', async () => {
    const gate = deferred<string>();
    const { result, unmount } = renderHook(() => useSubmitGuard());

    const run = async (): Promise<void> => {
      if (!result.current.begin('save')) return;
      try {
        await gate.promise;
      } catch {
        /* ignore */
      } finally {
        result.current.end('save');
      }
    };

    await act(async () => {
      void run();
      await Promise.resolve();
    });

    unmount();

    await act(async () => {
      gate.resolve('late');
      await gate.promise;
    });

    // 卸载后 end 不再 setState；React 18 该场景本就静默，此处防未来行为漂移
    expect(console.error).not.toHaveBeenCalled();
  });
});
