// @vitest-environment jsdom
/**
 * `src/app/lesson/[id]/lesson-view.tsx` —— 随堂练习 radio 组的 a11y。
 *
 * 背景：上一轮 `Field` 组件加了 label↔控件自动关联，但**随堂练习的 radio 不在 Field 里**，
 * 单控件的 label 关联本来就成立（`<label>` 包裹 `<input type="radio">` 是 HTML 规范写法）。
 * 真正缺的是**组级语义**：同一题多个选项构成一个 radio 组，整组却没有可访问名称，
 * 屏幕阅读器无法播报「第 3 题，共 4 个选项」，也无法把选项归属到题目。
 *
 * 本文件锁住的修复：选项容器加 `role="radiogroup"` + `aria-labelledby` 指向题干。
 * 分组互斥仍由原生 `name={qid}` 保证（同名 radio 天然互斥），语义层只是补「这组是谁」。
 *
 * 渲染方式沿用 `tests/app/lesson-and-course-guard.test.tsx`：view 组件 + fetch mock。
 * 交互用同步 `fireEvent.click`。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react';
import type { LessonDetail, UserBrief } from '@/lib/types';

import { LessonView } from '@/app/lesson/[id]/lesson-view';
import { useAuthStore } from '@/store/auth';
import { mockFetchByPath, ok } from '../helpers/fetch-mock';

vi.mock('next/navigation', () => ({
  usePathname: () => '/lesson/les-1',
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn(), prefetch: vi.fn(), refresh: vi.fn() }),
  redirect: vi.fn(),
}));

const USER: UserBrief = {
  id: 'u-1',
  email: 'tester@example.com',
  username: 'tester',
  display_name: '测试用户',
  role: 'user',
  level: 1,
  xp: 0,
};

const PROGRESS = {
  id: 'lp-1',
  lesson_id: 'les-1',
  status: 'in_progress',
  progress_percent: 50,
  time_spent_seconds: 120,
  attempt_count: 1,
  started_at: '2026-10-01T00:00:00Z',
  completed_at: null,
  updated_at: null,
};

/** 两道题、选项数不同 —— 用于验证「组」是按题目隔离的，而不是整页一个大组。 */
const LESSON: LessonDetail = {
  id: 'les-1',
  chapter_id: 'ch-1',
  slug: 'lesson-1',
  title: '第一课：变量',
  summary: null,
  content_md: '# 变量',
  lesson_type: 'practice',
  difficulty: 'easy',
  estimated_minutes: 10,
  order_index: 1,
  xp_reward: 20,
  has_playground: false,
  starter_code: null,
  solution_code: null,
  quiz_json: [
    { id: 'q1', qid: 'q1', question: '1 + 1 = ?', options: ['1', '2', '3'], answer: '2' },
    { id: 'q2', qid: 'q2', question: 'Python 里打印用哪个函数？', options: ['print', 'echo'], answer: 'print' },
  ],
  topics: [],
  prev: null,
  next: null,
  chapter_title: '第一章',
  chapter_index: 1,
  lesson_index: 1,
  total_lessons: 2,
  prev_lesson: null,
  next_lesson: null,
  progress: PROGRESS,
  course_id: 'c-1',
  course_title: 'Python 基础',
  course_slug: 'stage-1',
  course_outline: [],
};

beforeEach(() => {
  useAuthStore.setState({
    hydrated: true,
    accessToken: 'test-access-token',
    refreshToken: 'test-refresh-token',
    user: USER,
    loading: false,
    error: null,
  });
  mockFetchByPath({
    '/notifications': () => ok({ items: [], total: 0, page: 1, page_size: 5, pages: 0 }),
    '/complete': () => ok({}),
    '/quiz': () => ok({ correct_count: 0, total: 2, passed: false, details: [] }),
    '/lessons/les-1': () => ok(LESSON),
  });
});

/**
 * 渲染并切到「随堂练习」Tab。
 *
 * 随堂练习位于 Radix `TabsContent value="quiz"` 内，**未激活的 Tab 不挂载内容**，
 * 所以必须先点开 Tab 才能拿到 radio —— 这一步与 tests/app/lesson-and-course-guard.test.tsx
 * 的既有做法一致（那里用它来触发 quiz 提交）。
 *
 * 用同步原生 `.click()`：Radix Tabs Trigger 靠 click 事件切换，
 * `fireEvent.click` 额外包一层 act 也可，但原生 click 与既有测试同构、更好对照。
 */
async function renderLesson(): Promise<void> {
  render(<LessonView lessonId="les-1" />);
  const tab = await screen.findByRole('tab', { name: /随堂练习/ });
  tab.click();
  await waitFor(() => expect(screen.getAllByRole('radio').length).toBeGreaterThan(0));
}

describe('lesson-view · 随堂练习 radio 组 a11y（安全红线）', () => {
  it('★ radio 组有 role=radiogroup，且可访问名称能取到（非空、等于题干）', async () => {
    await renderLesson();

    const groups = screen.getAllByRole('radiogroup');
    // 两道题 → 两个独立的组，而不是整页一个大组
    expect(groups).toHaveLength(2);

    // 关键：不是只断言属性存在，而是断言「可访问名称真的算得出来」
    const nameA = groups[0].getAttribute('aria-labelledby');
    expect(nameA).toBeTruthy();
    const labelEl = document.getElementById(nameA as string);
    expect(labelEl).not.toBeNull();
    expect(labelEl?.textContent?.trim()).toBe('1. 1 + 1 = ?');

    // testing-library 的 name 过滤走 dom-accessibility-api，等于浏览器层真实计算
    const named = screen.getByRole('radiogroup', { name: /1 \+ 1 = \?/ });
    expect(named).toBe(groups[0]);
    expect(named).toHaveAccessibleName('1. 1 + 1 = ?');
  });

  it('★ 两个组的可访问名称各自指向自己的题干（不串台）', async () => {
    await renderLesson();

    const byName1 = screen.getByRole('radiogroup', { name: /1 \+ 1 = \?/ });
    const byName2 = screen.getByRole('radiogroup', { name: /Python 里打印用哪个函数/ });

    expect(byName1).not.toBe(byName2);
    expect(byName1).toHaveAccessibleName('1. 1 + 1 = ?');
    expect(byName2).toHaveAccessibleName('2. Python 里打印用哪个函数？');

    // 题干所在元素不得同时被两组引用
    const id1 = byName1.getAttribute('aria-labelledby');
    const id2 = byName2.getAttribute('aria-labelledby');
    expect(id1).not.toBe(id2);
  });

  it('★ 组内 radio 数量与选项数一致，且 name 相同（原生互斥分组）', async () => {
    await renderLesson();

    const g1 = screen.getByRole('radiogroup', { name: /1 \+ 1 = \?/ });
    const radios1 = within(g1).getAllByRole('radio');
    expect(radios1).toHaveLength(3);
    // 同一组内 name 一致 → 浏览器原生互斥
    expect(new Set(radios1.map((r) => r.getAttribute('name'))).size).toBe(1);

    const g2 = screen.getByRole('radiogroup', { name: /Python 里打印用哪个函数/ });
    const radios2 = within(g2).getAllByRole('radio');
    expect(radios2).toHaveLength(2);

    // 不同题必须不同组，否则两题会互相取消选中
    const name1 = radios1[0].getAttribute('name');
    const name2 = radios2[0].getAttribute('name');
    expect(name1).not.toBe(name2);
  });

  it('★ 选中某选项后：该项 checked，其余 unchecked；组级 checked 查询唯一命中', async () => {
    await renderLesson();
    const g1 = screen.getByRole('radiogroup', { name: /1 \+ 1 = \?/ });

    // 初始全不选
    within(g1).getAllByRole('radio').forEach((r) => expect((r as HTMLInputElement).checked).toBe(false));
    expect(within(g1).queryAllByRole('radio', { checked: true })).toHaveLength(0);

    const target = within(g1).getByRole('radio', { name: '2' });
    fireEvent.click(target);

    // 受控状态已更新
    await waitFor(() => expect((target as HTMLInputElement).checked).toBe(true));
    const checked = within(g1).getAllByRole('radio').filter((r) => (r as HTMLInputElement).checked);
    expect(checked).toHaveLength(1);
    expect((checked[0] as HTMLInputElement).value).toBe('2');
    // aria 层面的可访问选中态也只有一个（原生 radio 由 checked 映射）
    expect(within(g1).getAllByRole('radio', { checked: true })).toHaveLength(1);
  });

  it('★ 改选另一项：原项自动取消（单选互斥未被破坏）', async () => {
    await renderLesson();
    const g1 = screen.getByRole('radiogroup', { name: /1 \+ 1 = \?/ });

    fireEvent.click(within(g1).getByRole('radio', { name: '2' }));
    await waitFor(() => expect((within(g1).getByRole('radio', { name: '2' }) as HTMLInputElement).checked).toBe(true));

    fireEvent.click(within(g1).getByRole('radio', { name: '3' }));
    await waitFor(() => expect((within(g1).getByRole('radio', { name: '3' }) as HTMLInputElement).checked).toBe(true));
    expect((within(g1).getByRole('radio', { name: '2' }) as HTMLInputElement).checked).toBe(false);
    expect(within(g1).getAllByRole('radio', { checked: true })).toHaveLength(1);
  });

  it('★ 两题各自独立：选第 1 题不影响第 2 题的选中态', async () => {
    await renderLesson();
    const g1 = screen.getByRole('radiogroup', { name: /1 \+ 1 = \?/ });
    const g2 = screen.getByRole('radiogroup', { name: /Python 里打印用哪个函数/ });

    fireEvent.click(within(g1).getByRole('radio', { name: '2' }));
    await waitFor(() => expect(within(g1).getAllByRole('radio', { checked: true })).toHaveLength(1));
    // 用 query*：断言「没有」时零匹配应返回 []，而 getAllByRole 零匹配会直接抛错
    expect(within(g2).queryAllByRole('radio', { checked: true })).toHaveLength(0);

    fireEvent.click(within(g2).getByRole('radio', { name: 'print' }));
    await waitFor(() => expect(within(g2).getAllByRole('radio', { checked: true })).toHaveLength(1));
    expect(within(g1).getAllByRole('radio', { checked: true })).toHaveLength(1);
  });

  it('★ label 包裹语义保留：点击选项文字仍能选中（未被改成 htmlFor 分离写法）', async () => {
    await renderLesson();
    const g1 = screen.getByRole('radiogroup', { name: /1 \+ 1 = \?/ });

    // input 的祖先就是 label（包裹写法），而不是靠 htmlFor 关联
    const radio = within(g1).getByRole('radio', { name: '3' }) as HTMLInputElement;
    const wrappingLabel = radio.closest('label');
    expect(wrappingLabel).not.toBeNull();
    expect(radio.getAttribute('id')).toBeNull();
    expect(wrappingLabel?.getAttribute('for')).toBeNull();

    // 点击 label 上的文字节点 → 转发为点击控件
    fireEvent.click(wrappingLabel as HTMLElement);
    await waitFor(() => expect(radio.checked).toBe(true));
  });
});
