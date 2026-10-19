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
import { fireEvent, render, screen } from '@testing-library/react';

import { Alert, EmptyState, ErrorState } from '@/components/ui/alert';

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

describe('ErrorState · 接口失败必须立刻播报（安全红线）', () => {
  it('★ getByRole("alert") 能取到 ErrorState', () => {
    render(<ErrorState title="课程列表加载失败" description="后端返回 500。" onRetry={() => {}} />);
    expect(screen.getByRole('alert')).toBeTruthy();
  });

  it('★ role 落在最外层 DIV，且内部无嵌套 role', () => {
    render(<ErrorState title="题目加载失败" description="网络异常" onRetry={() => {}} />);
    const el = screen.getByRole('alert');
    expect(el.tagName).toBe('DIV');
    expect(el.querySelector('[role]')).toBeNull();
    // 播报依据是子树内容：标题与描述必须留在这条 live region 内
    expect(el.textContent).toContain('题目加载失败');
    expect(el.textContent).toContain('网络异常');
  });

  it('★ 不用 toHaveAccessibleName：role=alert 是 name-from-author-only，名称为空属正常', () => {
    render(<ErrorState title="课时加载失败" description="稍后重试" />);
    const el = screen.getByRole('alert');
    // 刻意不加 aria-label —— 加了反而偏离 live region 的播报机制
    expect(el.getAttribute('aria-label')).toBeNull();
    expect(el.getAttribute('aria-labelledby')).toBeNull();
    expect(el.getAttribute('aria-live')).toBeNull();
    expect(el.textContent).toContain('课时加载失败');
  });

  it('★ 真实调用形态：骨架屏 → 失败，错误提示插入后仍带 alert 语义', () => {
    // 复刻 admin/courses 的 `{loading && !data ? <Skeleton/> : error && !data ? <ErrorState/> : ...}`
    const { rerender } = render(<div data-testid="slot" aria-busy="true" />);
    expect(screen.queryByRole('alert')).toBeNull();

    rerender(
      <div>
        <ErrorState title="课程列表加载失败" description="后端健康检查接口暂不可用。" onRetry={() => {}} />
      </div>,
    );
    const el = screen.getByRole('alert');
    expect(el).toBeTruthy();
    expect(el.textContent).toContain('课程列表加载失败');
  });

  it('原有能力不受影响：默认文案 + onRetry 按钮仍可用', () => {
    let clicked = 0;
    render(<ErrorState onRetry={() => { clicked += 1; }} />);
    const el = screen.getByRole('alert');
    expect(el.textContent).toContain('数据暂时加载失败');
    fireEvent.click(screen.getByRole('button', { name: /重新加载/ }));
    expect(clicked).toBe(1);
  });

  it('★ EmptyState 刻意不加 live region role（空态是正常业务态，不是异常）', () => {
    render(<EmptyState title="暂无课程" description="点击「新建课程」创建第一个阶段。" />);
    // 「没有数据」是用户主动查询后的预期结果之一，不该被当异常打断播报
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.queryByRole('status')).toBeNull();
    // 但内容必须照常渲染、可被读屏读到
    expect(screen.getByText('暂无课程')).toBeTruthy();
  });

  it('★ ErrorState 与 EmptyState 同页共存时不串台', () => {
    render(
      <div>
        <ErrorState title="用户列表加载失败" description="接口异常" />
        <EmptyState title="暂无题目" />
      </div>,
    );
    const alerts = screen.getAllByRole('alert');
    expect(alerts).toHaveLength(1);
    expect(alerts[0].textContent).toContain('用户列表加载失败');
    expect(screen.getByText('暂无题目')).toBeTruthy();
  });
});
