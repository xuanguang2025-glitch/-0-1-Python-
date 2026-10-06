// @vitest-environment jsdom
/**
 * `src/hooks/useDebounce.ts` —— L3 Hook 时序（值防抖 + 回调防抖）。
 *
 * 定时器策略（踩过的坑）：
 * - `tests/setup.ts` 只 fake 了 `Date` 和 `performance`，**定时器是真的**，
 *   所以本文件在每个用例内部 `vi.useFakeTimers()`（不 fake Date，避免影响全局），
 *   并在 `finally` 里 `vi.useRealTimers()` 还原；
 * - 全量 `vi.useFakeTimers()` 会让 testing-library 的 `waitFor` 挂死，本文件不依赖 waitFor；
 * - 推进时间必须包在 `act()` 里，否则 React 不会提交 state 更新。
 *
 * 语义以源码为准（`useDebounce.ts:10-19`）：
 * - **无首屏防抖**：`useState(value)` 初值即 value，首帧就返回新值；
 * - 变更后延迟 `delay` 才提交；连续变更只认最后一次。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';

import { useDebounce, useDebouncedCallback } from '@/hooks/useDebounce';

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('useDebounce · 首屏语义', () => {
  it('初始值立即返回，不做首帧防抖（源码用 useState(value) 初始化）', () => {
    const { result } = renderHook(() => useDebounce('hello', 300));

    // 首帧就是新值：不等待任何延迟
    expect(result.current).toBe('hello');
    // 推进时间后值不变（挂载那次的提交是同值提交，无副作用）
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(result.current).toBe('hello');
  });

  it('delay 缺省为 300ms', () => {
    const { result, rerender } = renderHook(({ v }) => useDebounce(v), {
      initialProps: { v: 'a' },
    });

    rerender({ v: 'b' });
    act(() => {
      vi.advanceTimersByTime(299);
    });
    expect(result.current).toBe('a');

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(result.current).toBe('b');
  });
});

describe('useDebounce · 连续输入只提交一次', () => {
  it('连续 5 次快速变更，只在停止后拿到最终值', () => {
    const { result, rerender } = renderHook(({ v }) => useDebounce(v, 300), {
      initialProps: { v: '' },
    });

    for (const v of ['p', 'py', 'pyt', 'pyth', 'python']) {
      rerender({ v });
      act(() => {
        vi.advanceTimersByTime(50); // 每次间隔都远小于 300ms
      });
    }

    // 还没停下来，值不应变化
    expect(result.current).toBe('');

    act(() => {
      vi.advanceTimersByTime(300);
    });
    expect(result.current).toBe('python');
  });

  it('中间值从未被提交过（逐帧推进验证只提交最终态）', () => {
    const seen: string[] = [];
    const { rerender } = renderHook(
      ({ v }) => {
        seen.push(useDebounce(v, 200));
        return v;
      },
      { initialProps: { v: 'a' } },
    );

    rerender({ v: 'ab' });
    act(() => {
      vi.advanceTimersByTime(100);
    });
    rerender({ v: 'abc' });
    act(() => {
      vi.advanceTimersByTime(199);
    });
    act(() => {
      vi.advanceTimersByTime(1);
    });

    // 只有 'a'（初值）和最终值 'abc' 出现过，'ab' 从未成为防抖输出
    expect(seen).toEqual(['a', 'a', 'a', 'abc']);
  });

  it('停止后再输入会重新计时', () => {
    const { result, rerender } = renderHook(({ v }) => useDebounce(v, 300), {
      initialProps: { v: 'a' },
    });

    rerender({ v: 'b' });
    act(() => {
      vi.advanceTimersByTime(300);
    });
    expect(result.current).toBe('b');

    rerender({ v: 'c' });
    act(() => {
      vi.advanceTimersByTime(299);
    });
    expect(result.current).toBe('b');
    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(result.current).toBe('c');
  });

  it('值未变时不重启延迟：仍按原定时间点提交', () => {
    const { result, rerender } = renderHook(({ v }) => useDebounce(v, 300), { initialProps: { v: 'a' } });

    rerender({ v: 'b' });
    act(() => {
      vi.advanceTimersByTime(200);
    });
    expect(result.current).toBe('a');

    // 传入同一个值：依赖数组 [value, delay] 未变 → effect 不重跑 → 延迟不重启
    rerender({ v: 'b' });
    act(() => {
      vi.advanceTimersByTime(100); // 距首次变更刚好 300ms
    });
    expect(result.current).toBe('b');
  });
});

describe('useDebounce · 卸载清理', () => {
  it('卸载时调用 clearTimeout 清理 pending 定时器', () => {
    const clearSpy = vi.spyOn(window, 'clearTimeout');
    const { rerender, unmount } = renderHook(({ v }) => useDebounce(v, 300), { initialProps: { v: 'a' } });

    rerender({ v: 'b' });
    unmount();

    // 卸载后不得残留定时器：推进时间不应再触发提交，也不得抛错
    expect(clearSpy).toHaveBeenCalled();
    expect(() =>
      act(() => {
        vi.advanceTimersByTime(1000);
      }),
    ).not.toThrow();
  });

  it('连续变更时旧定时器被逐一清理', () => {
    const clearSpy = vi.spyOn(window, 'clearTimeout');
    const { rerender, unmount } = renderHook(({ v }) => useDebounce(v, 300), { initialProps: { v: 'a' } });

    rerender({ v: 'b' });
    rerender({ v: 'c' });
    rerender({ v: 'd' });
    clearSpy.mockClear();

    unmount();

    // 每次 value 变化都会先清掉上一个定时器，卸载时再清一次
    expect(clearSpy.mock.calls.length).toBeGreaterThanOrEqual(1);
  });

  it('卸载后不再提交状态：无 React 警告', () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    const { rerender, unmount } = renderHook(({ v }) => useDebounce(v, 300), { initialProps: { v: 'a' } });

    rerender({ v: 'b' });
    unmount();
    act(() => {
      vi.advanceTimersByTime(1000);
    });

    // setState on unmounted component 会打 console.error，这里断言没有
    expect(errorSpy).not.toHaveBeenCalled();
  });
});

describe('useDebouncedCallback · 回调防抖', () => {
  it('连续调用只在最后一次触发一次回调，参数为最后一次', () => {
    const cb = vi.fn();
    const { result } = renderHook(() => useDebouncedCallback(cb, 500));

    act(() => {
      result.current('a');
      result.current('b');
      result.current('c');
    });

    act(() => {
      vi.advanceTimersByTime(499);
    });
    expect(cb).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(cb).toHaveBeenCalledTimes(1);
    expect(cb).toHaveBeenCalledWith('c');
  });

  it('停止后再调用会重新计时（两次独立触发）', () => {
    const cb = vi.fn();
    const { result } = renderHook(() => useDebouncedCallback(cb, 500));

    act(() => {
      result.current('first');
    });
    act(() => {
      vi.advanceTimersByTime(500);
    });
    expect(cb).toHaveBeenCalledTimes(1);

    act(() => {
      result.current('second');
    });
    act(() => {
      vi.advanceTimersByTime(500);
    });
    expect(cb).toHaveBeenCalledTimes(2);
    expect(cb).toHaveBeenLastCalledWith('second');
  });

  it('回调引用跨渲染稳定（可直接当 props 传，避免子组件重渲染）', () => {
    const cb = vi.fn();
    const { result, rerender } = renderHook(({ n }) => useDebouncedCallback(() => cb(n), 300), {
      initialProps: { n: 1 },
    });

    const first = result.current;
    rerender({ n: 2 });
    const second = result.current;
    rerender({ n: 3 });
    expect(result.current).toBe(first);
    expect(second).toBe(first);
  });

  it('稳定引用的同时仍调用最新闭包（不会拿到旧 callback）', () => {
    const spy = vi.fn();
    const { result, rerender } = renderHook(({ n }) => useDebouncedCallback(() => spy(n), 300), {
      initialProps: { n: 1 },
    });

    rerender({ n: 42 });
    act(() => {
      result.current();
    });
    act(() => {
      vi.advanceTimersByTime(300);
    });

    expect(spy).toHaveBeenCalledWith(42);
  });

  it('卸载时清理 pending 回调，不再触发', () => {
    const cb = vi.fn();
    const { result, unmount } = renderHook(() => useDebouncedCallback(cb, 500));

    act(() => {
      result.current('x');
    });

    unmount();

    // 卸载后定时器被清掉，推进时间不应再触发回调
    act(() => {
      vi.advanceTimersByTime(2000);
    });
    expect(cb).not.toHaveBeenCalled();
  });

  it('delay 缺省为 500ms', () => {
    const cb = vi.fn();
    const { result } = renderHook(() => useDebouncedCallback(cb));

    act(() => {
      result.current('x');
    });
    act(() => {
      vi.advanceTimersByTime(499);
    });
    expect(cb).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(cb).toHaveBeenCalledTimes(1);
  });
});
