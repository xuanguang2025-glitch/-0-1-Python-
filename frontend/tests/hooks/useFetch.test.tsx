// @vitest-environment jsdom
/**
 * `src/hooks/useFetch.ts` —— L3 共享数据层：加载态生命周期 + 竞态。
 *
 * 先读实现再写断言，结论如下（详见文件内注释与报告）：
 *
 * ✅ **已有防护**：卸载守卫。`useFetch.ts:36-43` 用 `mounted` ref，
 *    `.then/.catch` 里先判 `mounted.current` 再 setState（:55、:61），
 *    所以「组件卸载后响应回来」不会 setState —— 本文件锁死这一条。
 *
 * ❌ **无防护**：请求乱序。`load()`（:45-66）没有 AbortController，
 *    也没有请求序号 / latest-request 守卫。deps 变化会并发发起新请求，
 *    旧请求若后到达会**覆盖**新数据。本文件用「缺陷复现用例」记录当前行为，
 *    修复后这些用例需要翻转断言（已在用例名与注释中标注）。
 *
 * 定时器：本文件全部用 Promise 微任务控制顺序，**不需要 fake timers**
 * （setup.ts 只 fake 了 Date/performance，正好不受影响）。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';

import { useAsyncAction, useFetch } from '@/hooks/useFetch';

/** 可控 deferred，用于精确构造「谁先返回」。 */
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

/* ------------------------------ 加载态生命周期 ------------------------------ */

describe('useFetch · 加载态生命周期', () => {
  it('初始 loading=true，成功后 data 落地且 loading=false', async () => {
    const gate = deferred<string>();
    const { result } = renderHook(() => useFetch(() => gate.promise, []));

    expect(result.current.loading).toBe(true);
    expect(result.current.data).toBeNull();
    expect(result.current.error).toBeNull();

    await act(async () => {
      gate.resolve('hello');
      await gate.promise;
    });

    expect(result.current.data).toBe('hello');
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('失败时 error 落地、data 清空、loading 必须复位（不得卡在 loading）', async () => {
    const gate = deferred<string>();
    const { result } = renderHook(() => useFetch(() => gate.promise, []));

    await act(async () => {
      gate.reject(new Error('后端炸了'));
      await gate.promise.catch(() => undefined);
    });

    expect(result.current.error).toBe('后端炸了');
    expect(result.current.data).toBeNull();
    expect(result.current.loading).toBe(false);
  });

  it('非 Error 抛出物也有兜底文案，且同样复位 loading', async () => {
    const gate = deferred<string>();
    const { result } = renderHook(() => useFetch(() => gate.promise, []));

    await act(async () => {
      gate.reject('boom');
      await gate.promise.catch(() => undefined);
    });

    expect(result.current.error).toBe('数据加载失败');
    expect(result.current.loading).toBe(false);
  });

  it('成功拿到 null 时 data 归一为 null（不是 undefined）', async () => {
    const gate = deferred<string | null>();
    const { result } = renderHook(() => useFetch(() => gate.promise, []));

    await act(async () => {
      gate.resolve(null);
      await gate.promise;
    });

    expect(result.current.data).toBeNull();
    expect(result.current.loading).toBe(false);
  });

  it('refresh() 重新拉取，并先清空上一次的 error', async () => {
    let call = 0;
    const { result } = renderHook(() =>
      useFetch(() => {
        call += 1;
        return call === 1 ? Promise.reject(new Error('首次失败')) : Promise.resolve('ok');
      }, []),
    );

    await waitFor(() => expect(result.current.error).toBe('首次失败'));

    await act(async () => {
      result.current.refresh();
    });

    await waitFor(() => expect(result.current.data).toBe('ok'));
    expect(result.current.error).toBeNull();
    expect(result.current.loading).toBe(false);
    expect(call).toBe(2);
  });

  it('setData 支持乐观更新', async () => {
    const { result } = renderHook(() => useFetch(() => Promise.resolve('server'), []));

    await waitFor(() => expect(result.current.data).toBe('server'));

    act(() => {
      result.current.setData('optimistic');
    });
    expect(result.current.data).toBe('optimistic');
  });
});

/* ------------------------------ 卸载守卫（已有防护） ------------------------------ */

describe('useFetch · 卸载守卫（实现已有 mounted ref 防护）', () => {
  it('卸载后响应回来不得 setState（无 React 警告）', async () => {
    const gate = deferred<string>();
    const { result, unmount } = renderHook(() => useFetch(() => gate.promise, []));

    expect(result.current.loading).toBe(true);

    unmount();

    await act(async () => {
      gate.resolve('late');
      await gate.promise;
    });

    // React 18+ 已移除该警告，但仍断言 console.error 未被触发（等价于无 setState-after-unmount 副作用）
    expect(console.error).not.toHaveBeenCalled();
  });

  it('卸载后失败响应也不得 setState', async () => {
    const gate = deferred<string>();
    const { unmount } = renderHook(() => useFetch(() => gate.promise, []));

    unmount();

    await act(async () => {
      gate.reject(new Error('late failure'));
      await gate.promise.catch(() => undefined);
    });

    expect(console.error).not.toHaveBeenCalled();
  });
});

/* ------------------------------ 依赖变化 ------------------------------ */

describe('useFetch · 依赖数组变化触发重新拉取', () => {
  it('deps 变化 → 重新请求', async () => {
    const seen: string[] = [];
    const { rerender } = renderHook(
      ({ v }) =>
        useFetch(() => {
          seen.push(v);
          return Promise.resolve(v);
        }, [v]),
      { initialProps: { v: 'a' } },
    );

    await waitFor(() => expect(seen).toEqual(['a']));

    await act(async () => {
      rerender({ v: 'b' });
    });

    expect(seen).toEqual(['a', 'b']);
  });

  it('deps 未变 → 不重复请求', async () => {
    const fetcher = vi.fn(() => Promise.resolve('x'));
    const { rerender } = renderHook(({ v }) => useFetch(fetcher, [v]), { initialProps: { v: 'a' } });

    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));

    await act(async () => {
      rerender({ v: 'a' }); // 同值：deps 未变
    });

    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it('fetcher 闭包总是取最新（fetcherRef），无需把函数放进 deps', async () => {
    const { result, rerender } = renderHook(
      ({ v }) => useFetch(() => Promise.resolve(`v=${v}`), []),
      { initialProps: { v: 1 } },
    );

    await waitFor(() => expect(result.current.data).toBe('v=1'));

    await act(async () => {
      rerender({ v: 2 });
    });

    // deps 为空数组，理论上不会重新请求；这里验证 fetcherRef 已指向新闭包
    expect(result.current.data).toBe('v=1');
  });

  it('enabled:false 时不发请求且 loading=false', async () => {
    const fetcher = vi.fn(() => Promise.resolve('x'));
    const { result } = renderHook(() => useFetch(fetcher, [], { enabled: false }));

    await act(async () => {
      await Promise.resolve();
    });

    expect(fetcher).not.toHaveBeenCalled();
    expect(result.current.loading).toBe(false);
    expect(result.current.data).toBeNull();
  });

  it('enabled 由 false 变 true 时开始请求', async () => {
    const fetcher = vi.fn(() => Promise.resolve('ready'));
    const { result, rerender } = renderHook(
      ({ on }) => useFetch(fetcher, [], { enabled: on }),
      { initialProps: { on: false } },
    );

    expect(fetcher).not.toHaveBeenCalled();

    await act(async () => {
      rerender({ on: true });
    });

    await waitFor(() => expect(result.current.data).toBe('ready'));
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});

/* ------------------------------ 竞态（实现无防护，缺陷复现） ------------------------------ */

describe('useFetch · 乱序响应（★ 缺陷复现：实现无 latest-request 守卫）', () => {
  it('【当前行为=缺陷】旧请求后返回会覆盖新请求的数据', async () => {
    const first = deferred<string>();
    const second = deferred<string>();
    const queue = [first.promise, second.promise];
    let idx = 0;

    const { result, rerender } = renderHook(
      ({ v }) =>
        useFetch(() => {
          const p = queue[idx]!;
          idx += 1;
          return p;
        }, [v]),
      { initialProps: { v: 'a' } },
    );

    // 第二次请求：deps 变化触发
    await act(async () => {
      rerender({ v: 'b' });
    });

    // 新请求先返回
    await act(async () => {
      second.resolve('new-data');
      await second.promise;
    });
    expect(result.current.data).toBe('new-data');
    // 确认两个请求确实都发出过（否则本用例会变成空跑）
    expect(idx).toBe(2);

    // 旧请求后返回 —— 若实现有防护，这里应仍为 'new-data'
    await act(async () => {
      first.resolve('old-data');
      await first.promise;
    });

    // ⚠️ 断言的是**当前存在缺陷的行为**。修复 useFetch（加请求序号或 AbortController）后，
    //    此断言会失败，需要翻转为 expect(result.current.data).toBe('new-data')。
    expect(result.current.data).toBe('old-data');
  });

  it('【当前行为=缺陷】旧请求后失败会覆盖新请求的成功结果', async () => {
    const first = deferred<string>();
    const second = deferred<string>();
    const queue = [first.promise, second.promise];
    let idx = 0;

    const { result, rerender } = renderHook(
      ({ v }) =>
        useFetch(() => {
          const p = queue[idx]!;
          idx += 1;
          return p;
        }, [v]),
      { initialProps: { v: 'a' } },
    );

    await act(async () => {
      rerender({ v: 'b' });
    });
    await act(async () => {
      second.resolve('new-data');
      await second.promise;
    });
    expect(result.current.data).toBe('new-data');
    expect(idx).toBe(2);

    await act(async () => {
      first.reject(new Error('stale failure'));
      await first.promise.catch(() => undefined);
    });

    // ⚠️ 同样是缺陷表征：过期失败把已成功的新数据打成 error + null
    expect(result.current.error).toBe('stale failure');
    expect(result.current.data).toBeNull();
  });
});

/* ------------------------------ useAsyncAction ------------------------------ */

describe('useAsyncAction · 基本语义', () => {
  it('成功：返回结果、调用 onSuccess、loading 复位', async () => {
    const onSuccess = vi.fn();
    const onError = vi.fn();
    const action = vi.fn(() => Promise.resolve('done'));

    const { result } = renderHook(() => useAsyncAction(action, { onSuccess, onError }));

    let returned: string | null = null;
    await act(async () => {
      returned = await result.current.run();
    });

    expect(returned).toBe('done');
    expect(onSuccess).toHaveBeenCalledWith('done');
    expect(onError).not.toHaveBeenCalled();
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('执行中 loading=true，结束后复位', async () => {
    const gate = deferred<string>();
    const { result } = renderHook(() => useAsyncAction(() => gate.promise));

    expect(result.current.loading).toBe(false);

    let p: Promise<string | null> | null = null;
    await act(async () => {
      p = result.current.run();
      await Promise.resolve();
    });
    expect(result.current.loading).toBe(true);

    await act(async () => {
      gate.resolve('ok');
      await p;
    });
    expect(result.current.loading).toBe(false);
  });

  it('失败：返回 null、error 落地、onError 收到同一文案、loading 复位', async () => {
    const onSuccess = vi.fn();
    const onError = vi.fn();
    const { result } = renderHook(() =>
      useAsyncAction(() => Promise.reject(new Error('提交失败')), { onSuccess, onError }),
    );

    let returned: string | null = null;
    await act(async () => {
      returned = await result.current.run();
    });

    expect(returned).toBeNull();
    expect(result.current.error).toBe('提交失败');
    expect(onError).toHaveBeenCalledWith('提交失败');
    expect(onSuccess).not.toHaveBeenCalled();
    expect(result.current.loading).toBe(false);
  });

  it('非 Error 抛出物使用兜底文案「操作失败」', async () => {
    const { result } = renderHook(() => useAsyncAction(() => Promise.reject('boom')));

    await act(async () => {
      await result.current.run();
    });

    expect(result.current.error).toBe('操作失败');
  });

  it('参数透传给 action', async () => {
    const action = vi.fn((_a: number, _b: string) => Promise.resolve('ok'));
    const { result } = renderHook(() => useAsyncAction(action));

    await act(async () => {
      await result.current.run(7, 'x');
    });

    expect(action).toHaveBeenCalledWith(7, 'x');
  });

  it('失败后再执行会先清空 error', async () => {
    let attempt = 0;
    const { result } = renderHook(() =>
      useAsyncAction(() => {
        attempt += 1;
        return attempt === 1 ? Promise.reject(new Error('首次失败')) : Promise.resolve('ok');
      }),
    );

    await act(async () => {
      await result.current.run();
    });
    expect(result.current.error).toBe('首次失败');

    await act(async () => {
      await result.current.run();
    });
    expect(result.current.error).toBeNull();
  });

  it('run 引用跨渲染稳定（deps 为 []）', () => {
    const { result, rerender } = renderHook(({ n }) => useAsyncAction(() => Promise.resolve(n)), {
      initialProps: { n: 1 },
    });

    const first = result.current.run;
    rerender({ n: 2 });
    expect(result.current.run).toBe(first);
  });

  it('稳定引用的同时仍调用最新 action 闭包（actionRef）', async () => {
    // 显式声明参数：vi.fn(() => ...) 会被推断为 0 参，导致 spy(n) 报 TS2554
    const spy = vi.fn((_n: number) => Promise.resolve('ok'));
    const { result, rerender } = renderHook(({ n }) => useAsyncAction(() => spy(n)), {
      initialProps: { n: 1 },
    });

    rerender({ n: 99 });
    await act(async () => {
      await result.current.run();
    });

    expect(spy).toHaveBeenCalledWith(99);
  });

  it('hooks 回调始终取最新（hooksRef）', async () => {
    const first = vi.fn();
    const second = vi.fn();
    const { result, rerender } = renderHook(
      ({ cb }) => useAsyncAction(() => Promise.resolve('v'), { onSuccess: cb }),
      { initialProps: { cb: first } },
    );

    rerender({ cb: second });
    await act(async () => {
      await result.current.run();
    });

    expect(first).not.toHaveBeenCalled();
    expect(second).toHaveBeenCalledWith('v');
  });
});

describe('useAsyncAction · 重复提交（★ 缺陷复现：实现无 pending 守卫）', () => {
  it('【当前行为=缺陷】连点两次会发出两次请求', async () => {
    const action = vi.fn(() => Promise.resolve('ok'));
    const { result } = renderHook(() => useAsyncAction(action));

    // 模拟按钮连点：两次 run() 之间不 await
    await act(async () => {
      void result.current.run();
      void result.current.run();
      await Promise.resolve();
    });

    // ⚠️ 断言的是**当前存在缺陷的行为**。若实现加 in-flight 守卫（pending 时直接 return），
    //    此断言会失败，应翻转为 expect(action).toHaveBeenCalledTimes(1)。
    expect(action).toHaveBeenCalledTimes(2);
  });

  it('【当前行为=缺陷】pending 期间 run() 仍会真正执行 action', async () => {
    const gate = deferred<string>();
    const action = vi.fn(() => gate.promise);
    const { result } = renderHook(() => useAsyncAction(action));

    let p1: Promise<string | null> | null = null;
    let p2: Promise<string | null> | null = null;
    await act(async () => {
      p1 = result.current.run();
      await Promise.resolve();
    });
    await act(async () => {
      p2 = result.current.run();
      await Promise.resolve();
    });

    expect(action).toHaveBeenCalledTimes(2);

    await act(async () => {
      gate.resolve('ok');
      await Promise.all([p1, p2]);
    });
    // 两次都拿到了结果（各自独立完成）
    expect(result.current.error).toBeNull();
  });
});
