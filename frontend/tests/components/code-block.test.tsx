// @vitest-environment jsdom
/**
 * `src/components/code/code-block.tsx` —— **安全红线**（docs/SECURITY.md §2.1）。
 *
 * `code-block.tsx:119` 是全站**唯一**的 `dangerouslySetInnerHTML`。
 * 它注入的是 `lib/highlight.ts` 的输出，一旦转义回退即成为可直接利用的 XSS。
 * 因此本文件的核心断言是：任何用户/后端提供的代码文本进入 DOM 后，
 * 都不能产生可执行的标签节点。
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { CodeBlock } from '@/components/code/code-block';

describe('CodeBlock · XSS 纵深防御（安全红线，docs/TESTING.md 用例30）', () => {
  it('<script> 被转义为文本，绝不产生 script 节点', () => {
    const { container } = render(<CodeBlock code={'<script>alert(1)</script>'} />);
    const injected = container.querySelector('code.flex-1') as HTMLElement;

    // ★ 红线断言：DOM 中不存在 script 元素
    expect(container.querySelector('script')).toBeNull();
    // ★ 红线断言：尖括号以转义形态出现（高亮器会把 < > 包进 tok-op，故不能断言连续子串）
    expect(injected.innerHTML).toContain('&lt;');
    expect(injected.innerHTML).toContain('&gt;');
    // ★ 红线断言：注入的 HTML 里不得出现裸的 <script
    expect(injected.innerHTML).not.toContain('<script');
    // 页面呈现的文本仍与原始代码一致（转义只发生在 HTML 层）
    expect(container.textContent).toContain('<script>alert(1)</script>');
  });

  it('& 必须先转义：不得出现 &amp;lt; 这类双重转义', () => {
    const { container } = render(<CodeBlock code={'a < b && c > d'} />);
    const injected = container.querySelector('code.flex-1') as HTMLElement;

    // 双重转义会让页面把 &lt; 当成字面量展示，属于高亮器的经典 bug
    expect(injected.innerHTML).not.toContain('&amp;lt;');
    expect(injected.innerHTML).not.toContain('&amp;amp;');
    expect(injected.innerHTML).toContain('&amp;&amp;');
  });

  it('img onerror 等事件注入属性同样被转义', () => {
    const { container } = render(<CodeBlock code={'<img src=x onerror=alert(1)>'} />);
    const injected = container.querySelector('code.flex-1') as HTMLElement;

    expect(container.querySelector('img')).toBeNull();
    expect(injected.innerHTML).toContain('&lt;');
    expect(injected.innerHTML).not.toContain('<img');
  });

  it('多次渲染同一恶意片段结果稳定（高亮器无状态残留）', () => {
    const first = render(<CodeBlock code={'<script>alert(1)</script>'} />);
    const html1 = first.container.innerHTML;
    first.unmount();

    const second = render(<CodeBlock code={'<script>alert(1)</script>'} />);
    expect(second.container.innerHTML).toBe(html1);
  });
});

describe('CodeBlock · 正常渲染与高亮', () => {
  it('Python 关键字被着色（tok-* class）', () => {
    const { container } = render(<CodeBlock code={'def add(a, b):\n    return a + b'} />);

    expect(container.querySelector('[class*="tok-"]')).not.toBeNull();
    expect(container.textContent).toContain('def');
  });

  it('默认展示代码原文，文件名作为标题', () => {
    render(<CodeBlock code={'print(1)'} filename="main.py" />);
    expect(screen.getByText('main.py')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '复制代码' })).toBeInTheDocument();
  });

  it('showLineNumbers 时逐行输出行号', () => {
    const { container } = render(<CodeBlock code={'a = 1\nb = 2'} showLineNumbers />);
    const lineNumbers = container.querySelector('code[aria-hidden]');
    expect(lineNumbers?.textContent).toBe('1\n2\n');
  });

  it('回调型按钮按 props 决定显隐', async () => {
    const onRun = vi.fn();
    const onFormat = vi.fn();
    const { rerender } = render(<CodeBlock code={'print(1)'} />);
    expect(screen.queryByRole('button', { name: '运行' })).toBeNull();
    expect(screen.queryByRole('button', { name: '格式化' })).toBeNull();

    rerender(<CodeBlock code={'print(1)'} onRun={onRun} onFormat={onFormat} />);
    await userEvent.click(screen.getByRole('button', { name: '运行' }));
    expect(onRun).toHaveBeenCalledTimes(1);

    await userEvent.click(screen.getByRole('button', { name: '格式化' }));
    expect(onFormat).toHaveBeenCalledTimes(1);
  });

  it('未知语言不会抛错（fallback 到默认高亮）', () => {
    expect(() => render(<CodeBlock code={'SELECT 1;'} language="sql" />)).not.toThrow();
  });
});
