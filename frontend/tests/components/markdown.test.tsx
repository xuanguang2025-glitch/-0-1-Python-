// @vitest-environment jsdom
/**
 * `src/components/markdown.tsx` —— 正文渲染安全 + GFM 支持。
 *
 * 安全断言（docs/TESTING.md 用例31）：本组件**未启用 rehype-raw**，
 * 因此课程正文 / AI 回复里的原始 HTML 不会被解析成真实元素。
 * 一旦有人为了「让正文支持 HTML」加上 rehype-raw，这条断言会立刻变红。
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { Markdown } from '@/components/markdown';

describe('Markdown · 原始 HTML 不渲染（安全断言，用例31）', () => {
  it('<img onerror> 不会变成真实 img 元素', () => {
    const { container } = render(<Markdown content={'<img src=x onerror=alert(1)>'} />);

    // ★ 红线断言：未启用 rehype-raw，容器内不得出现 img
    expect(container.querySelector('img')).toBeNull();
  });

  it('<script> 不会变成真实 script 元素', () => {
    const { container } = render(<Markdown content={'<script>alert(1)</script>'} />);
    expect(container.querySelector('script')).toBeNull();
  });

  it('<iframe> 与 javascript: 伪协议链接不产生可执行节点', () => {
    const { container } = render(<Markdown content={'<iframe src="//evil.example"></iframe>'} />);
    expect(container.querySelector('iframe')).toBeNull();

    const link = render(<Markdown content={'[点我](javascript:alert(1))'} />);
    const anchors = Array.from(link.container.querySelectorAll('a'));
    // react-markdown 会把危险协议过滤掉，href 不得原样保留 javascript:
    anchors.forEach((a) => {
      expect(a.getAttribute('href') ?? '').not.toMatch(/^javascript:/i);
    });
  });

  it('HTML 实体被当作纯文本展示（不二次解析）', () => {
    const { container } = render(<Markdown content={'<b>not bold</b>'} />);
    expect(container.querySelector('b')).toBeNull();
  });
});

describe('Markdown · GFM 渲染（用例32）', () => {
  it('**粗体** 生成 strong 元素', () => {
    const { container } = render(<Markdown content={'**粗体**'} />);

    const strong = container.querySelector('strong');
    expect(strong).not.toBeNull();
    expect(strong?.textContent).toBe('粗体');
  });

  it('GFM 表格被渲染为 table（remark-gfm 生效）', () => {
    const { container } = render(<Markdown content={'| 名称 | 说明 |\n| --- | --- |\n| for | 循环 |'} />);

    expect(container.querySelector('table')).not.toBeNull();
    expect(container.querySelectorAll('th')).toHaveLength(2);
    expect(container.textContent).toContain('for');
  });

  it('GFM 删除线与任务列表', () => {
    const { container } = render(<Markdown content={'~~废弃~~\n\n- [x] 已完成\n- [ ] 待办'} />);
    expect(container.querySelector('del')).not.toBeNull();
    expect(container.querySelectorAll('input[type="checkbox"]')).toHaveLength(2);
  });

  it('内联代码不渲染成 CodeBlock 组件', () => {
    render(<Markdown content={'使用 `print()` 打印'} />);
    // 内联 code 没有复制按钮，块级才有
    expect(screen.queryByRole('button', { name: '复制代码' })).toBeNull();
  });
});

describe('Markdown · 代码块与链接', () => {
  it('围栏代码块替换为 CodeBlock（含复制按钮）', () => {
    render(<Markdown content={'```python\nprint("hi")\n```'} />);
    // 围栏代码块走 CodeBlock；未传 onRunCode 时不渲染「运行」按钮
    expect(screen.getByRole('button', { name: '复制代码' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '运行' })).toBeNull();
    expect(screen.getByText('python')).toBeInTheDocument();
  });

  it('onRunCode 回调收到代码与语言', async () => {
    const onRunCode = vi.fn();
    render(<Markdown content={'```python\nprint(1)\n```'} onRunCode={onRunCode} />);

    await userEvent.click(screen.getByRole('button', { name: '运行' }));
    expect(onRunCode).toHaveBeenCalledWith('print(1)', 'python');
  });

  it('站内链接走 next/link、外链带 rel=noopener', () => {
    const { container } = render(<Markdown content={'[站内](/courses)\n\n[外链](https://docs.python.org)'} />);
    const anchors = Array.from(container.querySelectorAll('a'));

    expect(anchors[0]?.getAttribute('href')).toBe('/courses');
    expect(anchors[1]?.getAttribute('target')).toBe('_blank');
    expect(anchors[1]?.getAttribute('rel')).toContain('noopener');
  });

  it('空内容不抛错且不白屏', () => {
    const { container } = render(<Markdown content={''} />);
    expect(container.textContent).toBe('');
  });
});
