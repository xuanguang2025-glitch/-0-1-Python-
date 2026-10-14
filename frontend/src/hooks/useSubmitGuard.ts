'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * 提交守卫：按 key 记录 in-flight 状态，防止重复提交。
 *
 * ## 为什么必须用 ref 而不是纯 state
 * 页面里的提交函数是**当前 render 的闭包**。若只用 `useState` 做守卫，
 * 同一 tick 内的连续点击调用的是同一个闭包，读到的 state 仍是旧值（`false`），
 * `setSubmitting(true)` 只是排队等重渲染 —— 守卫在第二次调用时尚未生效，
 * 于是连点依然会发出多个请求。
 * `useRef` 的读写是同步的，第二次调用能立刻看到「已在进行中」。
 *
 * 因此本 hook 内部维护 ref（做判断）+ state（驱动 UI），两者存同一份数据的
 * 不同快照，始终以「创建新对象」的方式更新，不原地修改。
 */
export interface SubmitGuard {
  /**
   * 标记操作开始。返回 false 表示该 key 已在进行中，**调用方必须直接 return**。
   *
   * @param key 操作标识，建议 `'save'` 或 `` `${id}:delete` `` 这类「资源 + 操作」
   *            组合，使同一页面多个按钮的 in-flight 状态互不阻塞。
   */
  begin: (key: string) => boolean;
  /** 标记操作结束。放在 `finally` 里，保证成功与失败路径都复位。 */
  end: (key: string) => void;
  /** 响应式 in-flight 表，供按钮的 `disabled` / `loading` 使用。 */
  submitting: Record<string, boolean>;
}

/** 生成一份提交守卫。同一组件可复用一个实例管理多个操作。 */
export function useSubmitGuard(): SubmitGuard {
  const mountedRef = useRef(true);
  const inFlightRef = useRef<Record<string, boolean>>({});
  const [submitting, setSubmitting] = useState<Record<string, boolean>>({});

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const begin = useCallback((key: string): boolean => {
    // ref 同步读：同一 tick 的重复调用在此被拦下
    if (inFlightRef.current[key]) return false;
    const next = { ...inFlightRef.current, [key]: true };
    inFlightRef.current = next;
    setSubmitting(next);
    return true;
  }, []);

  const end = useCallback((key: string): void => {
    // 幂等：重复 end 不会产生多余渲染
    if (!inFlightRef.current[key]) return;
    const next = { ...inFlightRef.current };
    delete next[key];
    inFlightRef.current = next;
    // 卸载后不再 setState，避免 React 警告
    if (mountedRef.current) setSubmitting(next);
  }, []);

  return { begin, end, submitting };
}
