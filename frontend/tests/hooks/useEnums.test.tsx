// @vitest-environment jsdom
/**
 * `src/hooks/useEnums.ts` —— 后端权威枚举字典的加载、缓存与降级。
 *
 * 该 hook 是「后端为唯一枚举来源、前端不再硬编码」这条约定的执行点，
 * 一旦回退逻辑或合并顺序出错，页面会静默渲染错误的筛选项。
 *
 * ## 测试隔离是本文件的核心难点
 * `useEnums.ts` 用了**模块级**可变状态（`cache` / `inflight`）做进程级缓存，
 * 在同一测试文件里会跨用例残留。因此每个用例必须：
 *   1. `vi.resetModules()` 清掉模块注册表
 *   2. `await import(...)` 动态导入，拿到全新模块实例（新的 cache / inflight）
 * 否则第二个用例会直接命中上一个用例留下的 cache，测不到真实请求路径。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import type { EnumDictionary } from '@/lib/types';

import { FALLBACK_ENUMS } from '@/hooks/useEnums';
import { ok } from '../helpers/fetch-mock';

/** 全新模块实例（隔离模块级 cache / inflight）。 */
async function freshModule(): Promise<typeof import('@/hooks/useEnums')> {
  vi.resetModules();
  return import('@/hooks/useEnums');
}

/** 统计 GET /health/enums 的请求数。 */
function enumRequests(fetchMock: { calls: { url: string }[] }): number {
  return fetchMock.calls.filter((c) => c.url.includes('/health/enums')).length;
}

beforeEach(() => {
  // setup.ts 的 afterEach 会 useRealTimers 还原 beforeAll 的假 Date，逐用例重设
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(new Date('2026-09-27T10:00:00Z'));
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('useEnums · loadEnums', () => {
  it('后端返回时合并进内置兜底字典（后端值优先）', async () => {
    const calls: string[] = [];
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        calls.push(String(url));
        return ok({ role: ['user', 'admin'], ai_mode: ['standard'] } as Partial<EnumDictionary>);
      }),
    );

    const { loadEnums } = await freshModule();
    const dict = await loadEnums();

    // 后端给的字段用后端值
    expect(dict.role).toEqual(['user', 'admin']);
    expect(dict.ai_mode).toEqual(['standard']);
    // 后端没给的字段回落到内置兜底（保证页面不会缺字段）
    expect(dict.difficulty).toEqual(FALLBACK_ENUMS.difficulty);
    expect(calls.filter((u) => u.includes('/health/enums'))).toHaveLength(1);
  });

  it('★ 后端不可用时回退内置字典，且不抛错（离线降级）', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('Failed to fetch');
      }),
    );

    const { loadEnums } = await freshModule();
    const dict = await loadEnums();

    // 关键：不能 reject —— 页面必须能在后端挂掉时继续渲染
    expect(dict).toBeDefined();
    expect(dict.role).toEqual(FALLBACK_ENUMS.role);
    expect(dict.problem_category.length).toBeGreaterThan(0);
  });

  it('★ 并发调用只发一次请求（inflight 去重）', async () => {
    const fetchMock = vi.fn(async () => ok({ role: ['user'] } as Partial<EnumDictionary>));
    vi.stubGlobal('fetch', fetchMock);

    const { loadEnums } = await freshModule();
    // 同一 tick 内并发 3 次
    const results = await Promise.all([loadEnums(), loadEnums(), loadEnums()]);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    // 三次拿到同一份结果
    expect(results[0]).toBe(results[1]);
    expect(results[1]).toBe(results[2]);
  });

  it('★ 二次调用命中进程级缓存，不再发请求', async () => {
    const fetchMock = vi.fn(async () => ok({ role: ['user'] } as Partial<EnumDictionary>));
    vi.stubGlobal('fetch', fetchMock);

    const { loadEnums } = await freshModule();
    await loadEnums();
    expect(fetchMock).toHaveBeenCalledTimes(1);

    // 第二次直接命中 cache
    await loadEnums();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('★ 失败降级【不写入缓存】：后续调用会重新请求（与头部注释表述不符，见下）', async () => {
    const fetchMock = vi.fn(async () => {
      throw new TypeError('Failed to fetch');
    });
    vi.stubGlobal('fetch', fetchMock);

    const { loadEnums } = await freshModule();
    const first = await loadEnums();
    const second = await loadEnums();

    // 实际行为：`useEnums.ts:92` 的 `.catch(() => FALLBACK_ENUMS)` 只**返回**兜底字典，
    // 没有 `cache = FALLBACK_ENUMS`；而 `cache` 只在 `.then()` 的成功路径里赋值。
    // 因此失败时 cache 仍为 null，第二次调用会重新发请求。
    expect(fetchMock).toHaveBeenCalledTimes(2);
    // 两次都安全降级，没有抛错
    expect(first.role).toEqual(FALLBACK_ENUMS.role);
    expect(second.role).toEqual(FALLBACK_ENUMS.role);

    // ⚠️ 已知不一致（待产品/架构确认，本次不改代码）：
    // 头部注释写「该 hook 会缓存一次请求结果（进程级）」，但失败路径并未缓存。
    // 两种行为各有取舍：
    //   - 现状（不缓存失败）：后端短暂抖动后恢复，下一次挂载能重新拉取 → 利于自愈，
    //     代价是后端长期不可用时每个组件挂载都会重试一次（首页并发挂载即多次请求）。
    //   - 缓存失败：彻底杜绝重试风暴，但后端恢复后进程内永远拿不到新枚举，
    //     只能等刷新页面。
    // 修法（若决定缓存失败）：在 `.catch` 里补 `cache = FALLBACK_ENUMS; return cache;`，
    // 本用例断言需同步翻转为 `toHaveBeenCalledTimes(1)`。
  });
});

describe('useEnums · useEnums hook', () => {
  it('初始返回内置兜底字典，挂载后替换为后端字典', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ok({ role: ['user', 'custom-role'] } as Partial<EnumDictionary>)),
    );

    const { useEnums } = await freshModule();
    const { result } = renderHook(() => useEnums());

    // 首帧就是可用的兜底字典，页面不会白屏
    expect(result.current.role).toEqual(FALLBACK_ENUMS.role);

    await waitFor(() => expect(result.current.role).toEqual(['user', 'custom-role']));
  });

  it('后端失败时保持内置兜底字典（hook 不崩、不返回 undefined）', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('Failed to fetch');
      }),
    );

    const { useEnums } = await freshModule();
    const { result } = renderHook(() => useEnums());

    await waitFor(() => expect(result.current).toBeDefined());
    expect(result.current.role).toEqual(FALLBACK_ENUMS.role);
  });
});

describe('useEnums · 内置兜底字典的完整性', () => {
  it('FALLBACK_ENUMS 覆盖页面实际用到的关键枚举', () => {
    // 这些枚举在前端多处被直接索引；缺一个就会渲染出 undefined 选项
    const required = [
      'role',
      'user_status',
      'difficulty',
      'lesson_type',
      'problem_type',
      'submission_status',
      'bookmark_kind',
      'ai_mode',
      'notification_type',
      'theme_preference',
    ];
    for (const key of required) {
      expect(FALLBACK_ENUMS[key as keyof EnumDictionary], `缺少枚举 ${key}`).toBeDefined();
      expect(Array.isArray(FALLBACK_ENUMS[key as keyof EnumDictionary])).toBe(true);
    }
  });

  it('枚举值与 lib/types.ts 的联合类型一致（抽查几组）', () => {
    // 与 types.ts 中已定义的联合类型逐项对齐，防止兜底字典里混入已废弃的值
    expect(FALLBACK_ENUMS.difficulty).toEqual(['easy', 'medium', 'hard', 'expert']);
    expect(FALLBACK_ENUMS.lesson_type).toEqual(['concept', 'practice', 'quiz', 'project']);
    expect(FALLBACK_ENUMS.ai_mode).toEqual(['beginner', 'standard', 'advanced']);
    expect(FALLBACK_ENUMS.theme_preference).toEqual(['light', 'dark', 'system']);
  });

  it('所有枚举数组均非空（空数组会让对应筛选器渲染成空白下拉）', () => {
    for (const [key, values] of Object.entries(FALLBACK_ENUMS)) {
      expect(Array.isArray(values), `${key} 不是数组`).toBe(true);
      expect(values.length, `${key} 是空数组`).toBeGreaterThan(0);
    }
  });
});