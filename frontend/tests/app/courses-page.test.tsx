// @vitest-environment jsdom
/**
 * `src/app/courses/page.tsx` —— 课程列表页。
 *
 * 覆盖重点：**列表公开化**后的登录态降级（本轮核心行为锁）。
 * - 未登录：课程卡可见、进度区显示「登录后记录进度」引导、页内提示条出现；
 * - 已登录：有进度数据时渲染进度条，不出现登录引导。
 *
 * ## 断言按代码事实写
 * - 课程卡进度区：`isAuthenticated && typeof progress_percent === 'number'` 才渲染
 *   `<Progress role="progressbar">`；未登录固定渲染文案「登录后记录进度」。
 * - `PageContainer` 自身不渲染任何登录链接，因此「登录」链接唯一来自提示条。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import type { CourseBrief } from '@/lib/types';

import CoursesPage from '@/app/courses/page';
import { useAuthStore } from '@/store/auth';
import { useUiStore } from '@/store/ui';
import { mockFetchByPath, ok } from '../helpers/fetch-mock';

vi.mock('next/navigation', () => ({
  usePathname: () => '/courses',
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn(), prefetch: vi.fn(), refresh: vi.fn() }),
  redirect: vi.fn(),
}));

const USER = {
  id: 'u-1',
  email: 'tester@example.com',
  username: 'tester',
  display_name: '测试用户',
  role: 'user' as const,
  level: 1,
  xp: 0,
};

type ListQuery = { items: CourseBrief[]; total: number; page: number; pages: number };

function makeCourse(slug: string, title: string, overrides: Partial<CourseBrief> = {}): CourseBrief {
  return {
    id: slug,
    slug,
    stage_no: 1,
    title,
    subtitle: `${title} 简介`,
    level: 'beginner',
    icon: null,
    cover_url: null,
    estimated_hours: 6,
    lesson_count: 9,
    order_index: 1,
    is_published: true,
    progress_percent: 0,
    ...overrides,
  };
}

const COURSES: CourseBrief[] = [
  makeCourse('stage-01-python-basics', '阶段 1 · Python 基础'),
  makeCourse('stage-02-control-flow', '阶段 2 · 流程控制'),
];

function setup(options: { items?: CourseBrief[]; authenticated?: boolean; pages?: number } = {}) {
  const items = options.items ?? COURSES;
  const authenticated = options.authenticated ?? false;

  const fetchMock = mockFetchByPath({
    '/courses': () => ok({ items, total: items.length, page: 1, pages: options.pages ?? 1 } as ListQuery),
  });

  useAuthStore.setState(
    authenticated
      ? { hydrated: true, accessToken: 'test-access-token', refreshToken: 'test-refresh-token', user: USER, loading: false, error: null }
      : { hydrated: true, accessToken: null, refreshToken: null, user: null, loading: false, error: null },
  );

  render(<CoursesPage />);
  return { fetchMock };
}

beforeEach(() => {
  useUiStore.setState({ toasts: [] });
});

afterEach(() => {
  useAuthStore.setState({ accessToken: null, refreshToken: null, user: null, hydrated: false, loading: false, error: null });
  vi.restoreAllMocks();
});

describe('courses · 公开列表（未登录）', () => {
  it('★ 未登录能看到课程列表，进度区降级为「登录后记录进度」引导', async () => {
    setup();

    expect(await screen.findByText('阶段 1 · Python 基础')).toBeTruthy();
    expect(screen.getByText('阶段 2 · 流程控制')).toBeTruthy();

    // 每张课程卡的进度区都显示登录引导（而不是空进度条或死按钮）
    expect(screen.getAllByText('登录后记录进度')).toHaveLength(COURSES.length);
    // 未登录不渲染任何进度条
    expect(screen.queryByRole('progressbar')).toBeNull();
    // 详情入口仍可用
    expect(screen.getAllByRole('link', { name: '查看阶段内容' })).toHaveLength(COURSES.length);
  });

  it('★ 未登录渲染页内登录提示条（原 AuthGate 文案与按钮迁到页内）', async () => {
    setup();
    await screen.findByText('阶段 1 · Python 基础');

    expect(screen.getByText('课程列表对所有人开放，登录后还能看到每个阶段的完成度。')).toBeTruthy();
    expect(screen.getByRole('link', { name: '登录' })).toBeTruthy();
    expect(screen.getByRole('link', { name: '注册新账号' })).toBeTruthy();
    // PageContainer 不含登录链接，提示条只出现一次
    expect(screen.getAllByRole('link', { name: '登录' })).toHaveLength(1);
  });

  it('未登录仍可使用关键词筛选（客户端过滤，300ms 防抖后生效）', async () => {
    setup();
    await screen.findByText('阶段 1 · Python 基础');

    await act(async () => {
      fireEvent.change(screen.getByPlaceholderText('按标题筛选'), { target: { value: '流程控制' } });
      // setup.ts 只 fake 了 Date/performance，setTimeout 是真实的 → 真实等待越过防抖窗口
      await new Promise((resolve) => setTimeout(resolve, 350));
      await Promise.resolve();
    });

    expect(screen.getByText('阶段 2 · 流程控制')).toBeTruthy();
    expect(screen.queryByText('阶段 1 · Python 基础')).toBeNull();
  });

  it('未登录时列表请求仍正常发出（后端 OptionalUser）', async () => {
    const { fetchMock } = setup();
    await screen.findByText('阶段 1 · Python 基础');

    expect(fetchMock.countOf('/courses')).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/共 2 个阶段/)).toBeTruthy();
  });
});

describe('courses · 已登录', () => {
  it('有进度数据 → 渲染进度条，且不出现登录引导', async () => {
    setup({
      authenticated: true,
      items: [makeCourse('stage-01-python-basics', '阶段 1 · Python 基础', { progress_percent: 60 })],
    });
    await screen.findByText('阶段 1 · Python 基础');

    const bar = screen.getByRole('progressbar');
    expect(bar.getAttribute('aria-valuenow')).toBe('60');
    expect(screen.queryByText('登录后记录进度')).toBeNull();
    expect(screen.queryByRole('link', { name: '登录' })).toBeNull();
  });

  it('无进度数据 → 不渲染进度条也不渲染引导（保持既有行为）', async () => {
    setup({
      authenticated: true,
      items: [makeCourse('stage-01-python-basics', '阶段 1 · Python 基础', { progress_percent: undefined as unknown as number })],
    });
    await screen.findByText('阶段 1 · Python 基础');

    expect(screen.queryByRole('progressbar')).toBeNull();
    expect(screen.queryByText('登录后记录进度')).toBeNull();
  });
});
