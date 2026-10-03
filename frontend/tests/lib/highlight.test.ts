/**
 * `src/lib/highlight.ts` —— 安全红线测试。
 *
 * 本模块是全站唯一 `dangerouslySetInnerHTML`（code-block.tsx:119）的数据源，
 * 任何漏转义都会变成存储型 XSS。红线见 docs/SECURITY.md §2.1。
 */
import { describe, it, expect } from 'vitest';

import { highlightCode, highlightPython } from '@/lib/highlight';

/** 去掉高亮 span 并还原 HTML 实体，用于验证「渲染结果 == 原始代码」。 */
function decodeEntities(html: string): string {
  return html
    .replace(/<[^>]+>/g, '')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&amp;/g, '&');
}

describe('highlight · 安全红线：HTML 转义', () => {
  it('用例1：<script> 标签必须被完全转义，不得残留裸 <', () => {
    const html = highlightCode('<script>alert(1)</script>');
    // 安全断言：除高亮器自己产出的 <span> 外，不得有任何裸标签
    expect(html).not.toMatch(/<(?!\/?span)/i);
    expect(html).not.toContain('<script');
    // 转义确实发生了：还原实体后应能拿回原始 payload
    expect(decodeEntities(html)).toBe('<script>alert(1)</script>');
  });

  it('用例2：字符串字面量里的 onerror 是数据，不得变成属性', () => {
    const html = highlightCode("s = '<img src=x onerror=alert(1)>'");
    expect(html).not.toMatch(/<img/i);
    expect(html).toContain('&lt;img');
    // onerror 只能作为 span 内的文本出现，不能出现在标签属性位置
    expect(html).not.toMatch(/<span[^>]*onerror/i);
  });

  it('用例3：比较运算符 < 被转义，and 仍带 keyword class', () => {
    const html = highlightCode('x = "a" and 1 < 2');
    expect(html).toContain('&lt;'); // 裸 < 已转义（可能包在 tok-op span 内）
    expect(html).toMatch(/<span class="tok-keyword">and<\/span>/);
    expect(decodeEntities(html)).toBe('x = "a" and 1 < 2');
  });

  it('用例4：javascript: 协议不得产生任何 href/src 属性', () => {
    const html = highlightCode('javascript:alert(1)');
    expect(html).not.toMatch(/href=/i);
    expect(html).not.toMatch(/src=/i);
    // 高亮器只允许输出 class 属性
    const tags = html.match(/<[a-z]+[^>]*>/gi) ?? [];
    for (const tag of tags) {
      expect(tag).not.toMatch(/="[^"]*"[^>]*="[^"]*"/); // 不允许多属性
    }
  });

  it('用例5：& 必须先转义，不能出现 &amp;lt; 式双重错误', () => {
    const html = highlightCode('a & b');
    expect(html).toContain('&amp;');
    expect(html).not.toContain('&amp;lt;');
    expect(html).not.toContain('&amp;amp;');
  });

  it('用例6：空串与纯符号不抛错', () => {
    expect(() => highlightCode('')).not.toThrow();
    expect(highlightCode('')).toBe('');
    expect(() => highlightCode('!!!')).not.toThrow();
    expect(highlightCode('!!!')).toContain('!!!');
  });

  it('用例7：非 Python 语言走整体转义分支，不产生高亮 span', () => {
    const html = highlightCode('<b>x</b>', 'javascript');
    expect(html).not.toMatch(/<span/i);
    expect(html).toContain('&lt;b&gt;');
  });
});

describe('highlight · 正则状态安全', () => {
  it('用例8：幂等性 —— 连续两次调用结果必须完全一致', () => {
    // TOKEN_RE 是模块级带 g 标志的正则，lastIndex 是共享可变状态。
    // 若某分支忘记重置，跨调用会漏 token 或错位——这是本文件最可能的隐藏 bug。
    const samples = [
      'def f(x):\n    return x + 1',
      's = "a" and 1 < 2',
      "# 注释\nprint('hi')",
      'a & b',
      '<script>alert(1)</script>',
    ];
    for (const sample of samples) {
      const first = highlightPython(sample);
      const second = highlightPython(sample);
      expect(second).toBe(first);
      // 第三次用于捕捉「两次后才失衡」的边界
      expect(highlightPython(sample)).toBe(first);
    }
  });

  it('幂等性：交替调用不同代码不应互相污染', () => {
    const a = 'def a():\n    pass';
    const b = 'x = 1 < 2 and 3 > 2';
    const firstA = highlightPython(a);
    highlightPython(b);
    expect(highlightPython(a)).toBe(firstA);
  });
});

describe('highlight · 常规高亮行为', () => {
  it('关键字 / 字符串 / 数字 / 注释各自带上正确 class', () => {
    const html = highlightPython('def f():\n    # note\n    s = "x"\n    return 42');
    expect(html).toContain('tok-keyword');
    expect(html).toContain('tok-comment');
    expect(html).toContain('tok-string');
    expect(html).toContain('tok-number');
  });

  it('保留原始文本内容（去掉标签后应等于输入）', () => {
    const code = 'def add(a, b):\n    return a + b';
    const stripped = highlightPython(code)
      .replace(/<[^>]+>/g, '')
      .replace(/&lt;/g, '<')
      .replace(/&gt;/g, '>')
      .replace(/&quot;/g, '"')
      .replace(/&#39;/g, "'")
      .replace(/&amp;/g, '&');
    expect(stripped).toBe(code);
  });
});
