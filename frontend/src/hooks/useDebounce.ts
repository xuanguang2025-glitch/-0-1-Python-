'use client';

import { useEffect, useRef, useState } from 'react';

/**
 * 值防抖：常用于搜索输入。
 * @param value 输入值
 * @param delay 延迟毫秒数，默认 300ms
 */
export function useDebounce<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState<T>(value);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);

  return debounced;
}

/**
 * 回调防抖：常用于编辑器自动保存。
 * 返回的回调函数引用稳定，可直接作为 props 传递。
 */
export function useDebouncedCallback<A extends unknown[]>(
  callback: (...args: A) => void,
  delay = 500,
): (...args: A) => void {
  const callbackRef = useRef(callback);
  callbackRef.current = callback;
  const timerRef = useRef<number | null>(null);

  useEffect(
    () => () => {
      if (timerRef.current) window.clearTimeout(timerRef.current);
    },
    [],
  );

  const stable = useRef((...args: A) => {
    if (timerRef.current) window.clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(() => {
      timerRef.current = null;
      callbackRef.current(...args);
    }, delay);
  }).current;

  return stable;
}
