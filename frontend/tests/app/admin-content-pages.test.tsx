// @vitest-environment jsdom
/**
 * `src/app/admin/{courses,problems,projects}/page.tsx` —— 管理端重复提交防护（轻量版）。
 *
 * 这三页的 `submit()` 原先只有一个纯 state 标记 `saving`（无守卫判断），
 * `remove()` 则**完全没有任何守卫**。现已统一接入 `useSubmitGuard`
 * （详细的性质验证见 `tests/hooks/useSubmitGuard.test.tsx`，本文件只做页面级接线验证）。
 *
 * 连点一律用同步 `button.click()`，不用 `userEvent.click()` —— 后者每次都会 await
 * 并让 React 重渲染，第二击会被 DOM 的 disabled 挡掉，只能测到 disabled 属性，
 * 测不到守卫，是假绿。
 */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, act, fireEvent } from '@testing-library/react';
import type { CourseBrief, ProblemBrief, ProjectBrief } from '@/lib/types';

import AdminCoursesPage from '@/app/admin/courses/page';
import AdminProblemsPage from '@/app/admin/problems/page';
import AdminProjectsPage from '@/app/admin/projects/page';
import { mockFetchByPath, ok, err } from '../helpers/fetch-mock';

vi.mock('next/navigation', () => ({
  usePathname: () => '/admin',
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn(), prefetch: vi.fn(), refresh: vi.fn() }),
  redirect: vi.fn(),
}));

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

const COURSE: CourseBrief = {
  id: 'c-1',
  slug: 'stage-1',
  stage_no: 1,
  title: 'Python 基础',
  subtitle: null,
  level: 'beginner',
  icon: null,
  cover_url: null,
  estimated_hours: 8,
  lesson_count: 3,
  order_index: 1,
  is_published: true,
  progress_percent: 0,
};

const PROBLEM: ProblemBrief = {
  id: 'p-1',
  slug: 'two-sum',
  title: '两数之和',
  problem_type: 'algorithm',
  difficulty: 'easy',
  category: '数组',
  score: 10,
  xp_reward: 20,
  submission_count: 10,
  accepted_count: 5,
  acceptance_rate: 0.5,
  tags: [],
  my_status: null,
};

const PROJECT: ProjectBrief = {
  id: 'pr-1',
  slug: 'todo-cli',
  title: '命令行待办',
  summary: null,
  level: 1,
  category: 'cli',
  difficulty: 'easy',
  estimated_hours: 4,
  xp_reward: 50,
  order_index: 1,
  cover_url: null,
  my_status: null,
  progress_percent: 0,
};

type Page = { items: unknown[]; total: number; page: number; pages: number };

/**
 * 打开新建弹窗并填好必填项（slug + title）。
 *
 * 这三页的 `Field` 都没传 `htmlFor`，label 与 input 未关联，不能用 getByLabelText；
 * 而 slug / title 恰好是弹窗里的前两个文本输入框，按顺序取即可。
 * 不填的话会被 `submit()` 的前置校验拦下，请求根本不会发出（测不到守卫）。
 */
async function openCreateDialogAndFill(buttonName: RegExp): Promise<HTMLElement> {
  const newBtn = await screen.findByRole('button', { name: buttonName });
  await act(async () => {
    newBtn.click();
    await Promise.resolve();
  });

  const dialog = await screen.findByRole('dialog');
  const inputs = Array.from(dialog.querySelectorAll('input')).filter(
    (el) => (el as HTMLInputElement).type !== 'number',
  ) as HTMLInputElement[];

  await act(async () => {
    fireEvent.change(inputs[0]!, { target: { value: 'test-slug' } });
    fireEvent.change(inputs[1]!, { target: { value: '测试标题' } });
    await Promise.resolve();
  });

  return screen.getByRole('button', { name: /创建|保存/ });
}

/** 统计某个路径 + method 的请求数。 */
function countCalls(
  fetchMock: { calls: { url: string; init?: RequestInit }[] },
  path: string,
  method?: string,
): number {
  return fetchMock.calls.filter((c) => c.url.includes(path) && (!method || c.init?.method === method)).length;
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('admin/courses · 重复提交防护', () => {
  it('★ submit：pending 期间同步连点三次，只发出一次创建请求', async () => {
    const createGate = deferred<Response>();
    const fetchMock = mockFetchByPath({
      '/admin/courses': () => {
        const last = fetchMock.calls[fetchMock.calls.length - 1];
        if (last?.init?.method === 'POST') return createGate.promise as unknown as Response;
        return ok({ items: [COURSE], total: 1, page: 1, pages: 1 } as Page);
      },
    });

    render(<AdminCoursesPage />);

    // 打开新建弹窗并填好必填项
    const submitBtn = await openCreateDialogAndFill(/新建课程/);
    await act(async () => {
      submitBtn.click();
      submitBtn.click();
      submitBtn.click();
      await Promise.resolve();
    });

    // ★ 核心断言：3 次点击 → 1 次 POST。无守卫时这里是 3。
    expect(countCalls(fetchMock, '/admin/courses', 'POST')).toBe(1);
  });

  it('remove：pending 期间同步连点两次，只发出一次删除请求', async () => {
    const deleteGate = deferred<Response>();
    const fetchMock = mockFetchByPath({
      '/admin/courses': () => {
        const last = fetchMock.calls[fetchMock.calls.length - 1];
        if (last?.init?.method === 'DELETE') return deleteGate.promise as unknown as Response;
        return ok({ items: [COURSE], total: 1, page: 1, pages: 1 } as Page);
      },
    });

    render(<AdminCoursesPage />);

    // 点第一行的删除按钮打开确认框
    const delBtn = await screen.findByRole('button', { name: '删除课程' });
    await act(async () => {
      delBtn.click();
      await Promise.resolve();
    });

    const confirmBtn = await screen.findByRole('button', { name: '确认删除' });
    await act(async () => {
      confirmBtn.click();
      confirmBtn.click();
      await Promise.resolve();
    });

    expect(countCalls(fetchMock, '/admin/courses/c-1', 'DELETE')).toBe(1);
  });

  it('删除失败后复位：可再次尝试', async () => {
    const deleteGate = deferred<Response>();
    const fetchMock = mockFetchByPath({
      '/admin/courses': () => {
        const last = fetchMock.calls[fetchMock.calls.length - 1];
        if (last?.init?.method === 'DELETE') return deleteGate.promise as unknown as Response;
        return ok({ items: [COURSE], total: 1, page: 1, pages: 1 } as Page);
      },
    });

    render(<AdminCoursesPage />);
    const delBtn = await screen.findByRole('button', { name: '删除课程' });
    await act(async () => {
      delBtn.click();
      await Promise.resolve();
    });
    const confirmBtn = await screen.findByRole('button', { name: '确认删除' });

    await act(async () => {
      confirmBtn.click();
      await Promise.resolve();
    });
    expect(countCalls(fetchMock, '/admin/courses/c-1', 'DELETE')).toBe(1);

    await act(async () => {
      deleteGate.resolve(err('CONFLICT', '课程下还有题目', 409));
      await deleteGate.promise;
    });

    const retry = await screen.findByRole('button', { name: '确认删除' });
    expect(retry).not.toBeDisabled();

    await act(async () => {
      retry.click();
      await Promise.resolve();
    });
    expect(countCalls(fetchMock, '/admin/courses/c-1', 'DELETE')).toBe(2);
  });
});

describe('admin/problems · 重复提交防护', () => {
  it('★ submit：pending 期间同步连点三次，只发出一次创建请求', async () => {
    const createGate = deferred<Response>();
    const fetchMock = mockFetchByPath({
      '/admin/problems': () => {
        const last = fetchMock.calls[fetchMock.calls.length - 1];
        if (last?.init?.method === 'POST') return createGate.promise as unknown as Response;
        return ok({ items: [PROBLEM], total: 1, page: 1, pages: 1 } as Page);
      },
    });

    render(<AdminProblemsPage />);

    const submitBtn = await openCreateDialogAndFill(/新建题目/);
    await act(async () => {
      submitBtn.click();
      submitBtn.click();
      submitBtn.click();
      await Promise.resolve();
    });

    expect(countCalls(fetchMock, '/admin/problems', 'POST')).toBe(1);
  });

  it('remove：pending 期间同步连点两次，只发出一次删除请求', async () => {
    const deleteGate = deferred<Response>();
    const fetchMock = mockFetchByPath({
      '/admin/problems': () => {
        const last = fetchMock.calls[fetchMock.calls.length - 1];
        if (last?.init?.method === 'DELETE') return deleteGate.promise as unknown as Response;
        return ok({ items: [PROBLEM], total: 1, page: 1, pages: 1 } as Page);
      },
    });

    render(<AdminProblemsPage />);
    const delBtn = await screen.findByRole('button', { name: '删除题目' });
    await act(async () => {
      delBtn.click();
      await Promise.resolve();
    });

    const confirmBtn = await screen.findByRole('button', { name: '确认删除' });
    await act(async () => {
      confirmBtn.click();
      confirmBtn.click();
      await Promise.resolve();
    });

    expect(countCalls(fetchMock, '/admin/problems/p-1', 'DELETE')).toBe(1);
  });
});

describe('admin/projects · 重复提交防护', () => {
  it('★ submit：pending 期间同步连点三次，只发出一次创建请求', async () => {
    const createGate = deferred<Response>();
    const fetchMock = mockFetchByPath({
      '/admin/projects': () => {
        const last = fetchMock.calls[fetchMock.calls.length - 1];
        if (last?.init?.method === 'POST') return createGate.promise as unknown as Response;
        return ok({ items: [PROJECT], total: 1, page: 1, pages: 1 } as Page);
      },
    });

    render(<AdminProjectsPage />);

    const submitBtn = await openCreateDialogAndFill(/新建项目/);
    await act(async () => {
      submitBtn.click();
      submitBtn.click();
      submitBtn.click();
      await Promise.resolve();
    });

    expect(countCalls(fetchMock, '/admin/projects', 'POST')).toBe(1);
  });

  it('remove：pending 期间同步连点两次，只发出一次删除请求', async () => {
    const deleteGate = deferred<Response>();
    const fetchMock = mockFetchByPath({
      '/admin/projects': () => {
        const last = fetchMock.calls[fetchMock.calls.length - 1];
        if (last?.init?.method === 'DELETE') return deleteGate.promise as unknown as Response;
        return ok({ items: [PROJECT], total: 1, page: 1, pages: 1 } as Page);
      },
    });

    render(<AdminProjectsPage />);
    const delBtn = await screen.findByRole('button', { name: '删除项目' });
    await act(async () => {
      delBtn.click();
      await Promise.resolve();
    });

    const confirmBtn = await screen.findByRole('button', { name: '确认删除' });
    await act(async () => {
      confirmBtn.click();
      confirmBtn.click();
      await Promise.resolve();
    });

    expect(countCalls(fetchMock, '/admin/projects/pr-1', 'DELETE')).toBe(1);
  });
});
