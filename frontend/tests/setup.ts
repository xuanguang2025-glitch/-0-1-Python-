import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach, beforeAll, vi } from 'vitest';

/** 固定时区与基准时刻，避免 formatRelativeTime 断言随时钟漂移。 */
const FIXED_NOW = new Date('2026-09-27T10:00:00Z');

beforeAll(() => {
  // 固定为 UTC：CI 与本机时区不同会导致日期格式化断言飘红
  process.env.TZ = 'UTC';
  // 统一「现在」：所有依赖当前时间的函数都读它
  // 注意只 fake Date + performance；全量 fake 会让 testing-library 的 waitFor 挂死
  vi.useFakeTimers({ toFake: ['Date', 'performance'] });
  vi.setSystemTime(FIXED_NOW);
});

afterEach(() => {
  cleanup(); // 卸载 React 树
  vi.clearAllTimers();
  vi.useRealTimers();
});
