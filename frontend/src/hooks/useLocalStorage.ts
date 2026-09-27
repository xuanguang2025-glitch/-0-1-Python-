'use client';

import { useCallback, useEffect, useState } from 'react';
import { readLocal, writeLocal } from '@/lib/storage';

/**
 * localStorage 持久化（SSR 安全）。
 * @param key 键名（自动加统一前缀）
 * @param initialValue 初始值
 */
export function useLocalStorage<T>(key: string, initialValue: T): [T, (value: T | ((prev: T) => T)) => void, () => void] {
  const [stored, setStored] = useState<T>(initialValue);

  // 首次挂载时读取本地值，避免 SSR 与首屏不一致
  useEffect(() => {
    setStored(readLocal<T>(key, initialValue));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const setValue = useCallback(
    (value: T | ((prev: T) => T)) => {
      setStored((prev) => {
        const next = typeof value === 'function' ? (value as (p: T) => T)(prev) : value;
        writeLocal(key, next);
        return next;
      });
    },
    [key],
  );

  const clear = useCallback(() => {
    setStored(initialValue);
    writeLocal(key, initialValue);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return [stored, setValue, clear];
}
