// @vitest-environment jsdom
/**
 * `src/components/ui/alert.tsx` —— 实时播报（live region）分级。
 *
 * 背景：全站 32 个文件在用 `Alert`，但外层 div 没有任何 live region 语义 ——
 * 屏幕阅读器把动态出现的提示当普通内容，用户提交后听不到「答对 2/3 题」或
 * 「账号或密码错误」。
 *
 * 本文件锁住两个决策：
 * 1. `role` 必须落在**最外层 div**（挂到内部元素读屏软件不会播报整条提示）；
 * 2. **只有 error 是 assertive**（`role="alert"`），success/warning/info 一律 polite
 *    （`role="status"`）。对 warning 尤其关键：随堂练习未通过的判题结果就是
 *    `passed ? 'success' : 'warning'`，用 assertive 会打断用户正等着的反馈。
 *
 * 断言一律走 `getByRole('alert') / getByRole('status')`——这查的是**可访问性树**，
 * 而不是「DOM 上有没有这个属性」，所以 role 挂错位置、写错值都会红。
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { Alert } from '@/components/ui/alert';

describe('Alert · 实时播报分级（安全红线）', () => {
  it('★ error → role="alert"（assertive，立即打断）', () => {
    render(<Alert variant="error" title="账号或密码错误" description="请检查后重试。" />);
    expect(screen.getByRole('alert')).toBeTruthy();
    // assertive 优先：不能同时被当成 status 查到
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('★ success → role="status"（polite，等空闲再播报）', () => {
    render(<Alert variant="success" title="答对 3 / 3 题" description="很棒，继续下一节吧！" />);
    expect(screen.getByRole('status')).toBeTruthy();
    // ★ 不能一律 assertive：success 绝不能是 alert
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('★ warning → role="status"，不是 alert（判题未过属结果反馈，不该打断）', () => {
    render(<Alert variant="warning" title="答对 2 / 3 题" description="回顾一下错题，再提交一次。" />);
    expect(screen.getByRole('status')).toBeTruthy();
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('★ info（默认 variant）→ role="status"', () => {
    render(<Alert title="这是一个提示" />);
    expect(screen.getByRole('status')).toBeTruthy();
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('★ role 落在最外层 div 上（挂到内部元素读屏不会播报整条）', () => {
    render(<Alert variant="error" title="外层断言" description="描述文本" action={<button type="button">重试</button>} />);
    const el = screen.getByRole('alert');

    // 外层容器本身是 div，且直接包着图标 span（原有结构未被动过）
    expect(el.tagName).toBe('DIV');
    expect(el.firstElementChild?.tagName).toBe('SPAN');
    // 内部不得再出现任何 role —— 避免「role 挂错层级」的半吊子实现
    expect(el.querySelector('[role]')).toBeNull();
    // 标题与描述都在这条 live region 内，播报时才念得全
    expect(el.textContent).toContain('外层断言');
    expect(el.textContent).toContain('描述文本');
  });

  it('★ 播报内容 = live region 子树文本（不依赖 accessible name）', () => {
    render(<Alert variant="success" title="保存成功" description="改动已写入服务器。" />);
    const status = screen.getByRole('status');

    // 说明：`role="alert"` / `role="status"` 在 ARIA 里都是 **name from author only**，
    // 可访问名称不会由内容推导出来（实测 toHaveAccessibleName 为空）。
    // live region 的播报依据是**子树内容**，所以该断言的是「标题与描述都在这条
    // live region 内」，而不是名称非空 —— 断言名称会把人引向错误的修法（去加 aria-label）。
    expect(status.getAttribute('aria-label')).toBeNull();
    expect(status.getAttribute('aria-labelledby')).toBeNull();
    expect(status.textContent).toContain('保存成功');
    expect(status.textContent).toContain('改动已写入服务器。');
  });

  it('不显式写 aria-live（role 已隐含，重复写属冗余且易与 role 冲突）', () => {
    const { unmount } = render(<Alert variant="error" title="隐含 assertive" />);
    const alertEl = screen.getByRole('alert');
    expect(alertEl.getAttribute('aria-live')).toBeNull();
    expect(alertEl.getAttribute('aria-atomic')).toBeNull();
    unmount();

    render(<Alert variant="success" title="隐含 polite" />);
    const statusEl = screen.getByRole('status');
    expect(statusEl.getAttribute('aria-live')).toBeNull();
    expect(statusEl.getAttribute('aria-atomic')).toBeNull();
  });

  it('★ 动态插入（提交后才出现）也带 role —— live region 语义对插入生效', () => {
    const { rerender } = render(<div data-testid="host" />);
    expect(screen.queryByRole('status')).toBeNull();

    rerender(
      <div data-testid="host">
        <Alert variant="success" title="判题完成" description="用时 120ms" />
      </div>,
    );
    const status = screen.getByRole('status');
    expect(status).toBeTruthy();
    expect(status.textContent).toContain('判题完成');
  });

  it('同页多个 Alert 各自带自己的 role，互不干扰', () => {
    render(
      <div>
        <Alert variant="error" title="登录失败" />
        <Alert variant="success" title="保存成功" />
        <Alert variant="warning" title="答对 2 / 3 题" />
      </div>,
    );
    expect(screen.getAllByRole('alert')).toHaveLength(1);
    expect(screen.getAllByRole('status')).toHaveLength(2);
  });

  it('原有渲染能力未受影响：children / action / description 都能正常渲染', () => {
    render(
      <Alert variant="info" title="带附加内容" description="描述" action={<button type="button">知道了</button>}>
        <p>children 节点</p>
      </Alert>,
    );
    const status = screen.getByRole('status');
    expect(status.textContent).toContain('带附加内容');
    expect(status.textContent).toContain('描述');
    expect(status.textContent).toContain('children 节点');
    expect(screen.getByRole('button', { name: '知道了' })).toBeTruthy();
  });
});
