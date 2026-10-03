/**
 * `src/lib/utils.ts` —— 纯格式化函数测试。
 * 重点覆盖各处 `null` / 非法入参的兜底分支（真实数据里 null 极常见）。
 */
import { describe, it, expect, vi } from 'vitest';

import {
  cn,
  formatCompact,
  formatDate,
  formatDuration,
  formatMemory,
  formatMinutes,
  formatPercent,
  formatRelativeTime,
  formatTime,
  initials,
  parseFilename,
  truncate,
} from '@/lib/utils';

/** 与 tests/setup.ts 保持一致的基准时刻。 */
const FIXED_NOW = new Date('2026-09-27T10:00:00Z');

describe('formatDuration', () => {
  it('用例23：3661 秒 → 含「1」与「小时」', () => {
    const text = formatDuration(3661);
    expect(text).toContain('1');
    expect(text).toContain('小时');
    expect(text).toContain('分');
  });

  it('秒 / 分钟 / 整小时三个量级', () => {
    expect(formatDuration(30)).toBe('30 秒');
    expect(formatDuration(120)).toBe('2 分钟');
    expect(formatDuration(3600)).toBe('1 小时');
  });

  it('非法入参兜底为 0 分钟', () => {
    expect(formatDuration(-1)).toBe('0 分钟');
    expect(formatDuration(Number.NaN)).toBe('0 分钟');
  });
});

describe('formatMemory', () => {
  it('用例22：1536 KB → 1.5 MB 量级', () => {
    expect(formatMemory(1536)).toBe('1.5 MB');
  });

  it('小于 1MB 保持 KB', () => {
    expect(formatMemory(512)).toBe('512 KB');
  });

  it('非正数与非法入参兜底', () => {
    expect(formatMemory(0)).toBe('0 KB');
    expect(formatMemory(-5)).toBe('0 KB');
    expect(formatMemory(Number.POSITIVE_INFINITY)).toBe('0 KB');
  });
});

describe('formatMinutes / formatTime / formatPercent / formatCompact', () => {
  it('分钟换算小时', () => {
    expect(formatMinutes(90)).toBe('1.5 小时');
    expect(formatMinutes(30)).toBe('30 分钟');
    expect(formatMinutes(0)).toBe('0 分钟');
  });

  it('毫秒换算秒', () => {
    expect(formatTime(250)).toBe('250 ms');
    expect(formatTime(1500)).toBe('1.50 s');
    expect(formatTime(-1)).toBe('—');
  });

  it('比率换算百分比', () => {
    expect(formatPercent(0.775)).toBe('77.5%');
    expect(formatPercent(0.5, 0)).toBe('50%');
  });

  it('大数字缩写', () => {
    expect(formatCompact(999)).toBe('999');
    expect(formatCompact(1200)).toBe('1.2k');
    expect(formatCompact(34000)).toBe('3.4w');
  });
});

describe('parseFilename', () => {
  it('用例24：从 Content-Disposition 解析文件名', () => {
    expect(parseFilename('attachment; filename="a.md"', 'fallback.md')).toBe('a.md');
  });

  it('header 为 null 时返回 fallback', () => {
    expect(parseFilename(null, 'fallback.md')).toBe('fallback.md');
  });

  it('无 filename 片段时返回 fallback', () => {
    expect(parseFilename('attachment', 'fallback.md')).toBe('fallback.md');
  });

  it('支持 RFC 5987 的 filename*=UTF-8 形式', () => {
    expect(parseFilename("attachment; filename*=UTF-8''%E6%B5%8B%E8%AF%95.md", 'x.md')).toBe('测试.md');
  });
});

describe('initials', () => {
  it('用例26：取前两个字符并大写（按实现，Python Lab → PY）', () => {
    expect(initials('Python Lab')).toBe('PY');
    expect(initials('ab')).toBe('AB');
  });

  it('null / 空串 / 纯空白不抛错，返回兜底 P', () => {
    expect(initials(null)).toBe('P');
    expect(initials(undefined)).toBe('P');
    expect(initials('')).toBe('P');
    expect(initials('   ')).toBe('P');
  });
});

describe('formatDate / formatRelativeTime', () => {
  it('用例25：因固定 Date，relativeTime 结果稳定', () => {
    // setup.ts 的 beforeAll 固定时钟，但 afterEach 的 useRealTimers 会还原，
    // 因此每个依赖「现在」的用例必须自行重新固定。
    vi.useFakeTimers({ toFake: ['Date', 'performance'] });
    vi.setSystemTime(FIXED_NOW);

    expect(formatRelativeTime('2026-09-27T09:00:00Z')).toBe('1 小时前');
    expect(formatRelativeTime('2026-09-27T09:59:30Z')).toBe('刚刚');
    expect(formatRelativeTime('2026-09-26T10:00:00Z')).toBe('1 天前');
  });

  it('未来时间带「后」', () => {
    vi.useFakeTimers({ toFake: ['Date', 'performance'] });
    vi.setSystemTime(FIXED_NOW);
    expect(formatRelativeTime('2026-09-27T11:00:00Z')).toBe('1 小时后');
  });

  it('日期格式化 YYYY-MM-DD', () => {
    vi.useFakeTimers({ toFake: ['Date', 'performance'] });
    vi.setSystemTime(FIXED_NOW);
    expect(formatDate('2026-09-27T10:00:00Z')).toBe('2026-09-27');
  });

  it('null 与非法日期兜底为 —', () => {
    expect(formatDate(null)).toBe('—');
    expect(formatDate('not-a-date')).toBe('—');
    expect(formatRelativeTime(null)).toBe('—');
    expect(formatRelativeTime('not-a-date')).toBe('—');
  });

  it('超过 30 天回落到具体日期', () => {
    vi.useFakeTimers({ toFake: ['Date', 'performance'] });
    vi.setSystemTime(FIXED_NOW);
    expect(formatRelativeTime('2026-01-01T10:00:00Z')).toBe('2026-01-01');
  });
});

describe('truncate / cn', () => {
  it('超长文本截断并补省略号', () => {
    expect(truncate('abcdef', 3)).toBe('abc…');
    expect(truncate('abc', 10)).toBe('abc');
  });

  it('cn 合并类名且后者覆盖前者', () => {
    expect(cn('p-2', 'p-4')).toBe('p-4');
    expect(cn('text-sm', 'font-bold')).toBe('text-sm font-bold');
  });
});
