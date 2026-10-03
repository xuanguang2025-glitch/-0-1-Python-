/**
 * `src/lib/format.ts` —— 代码格式化与错误行号提取。
 */
import { describe, it, expect } from 'vitest';

import { countLines, extractErrorLine, formatCode, formatPython } from '@/lib/format';

describe('extractErrorLine', () => {
  it('用例20：从 traceback 提取行号', () => {
    expect(extractErrorLine('  File "main.py", line 3')).toBe(3);
    expect(extractErrorLine('Traceback:\n  File "x.py", line 42, in <module>\nZeroDivisionError')).toBe(42);
  });

  it('无匹配返回 null', () => {
    expect(extractErrorLine('no line info here')).toBeNull();
  });

  it('null / undefined / 空串返回 null', () => {
    expect(extractErrorLine(null)).toBeNull();
    expect(extractErrorLine(undefined)).toBeNull();
    expect(extractErrorLine('')).toBeNull();
  });

  it('取第一个匹配的行号', () => {
    expect(extractErrorLine('line 5\nline 9')).toBe(5);
  });
});

describe('formatPython', () => {
  it('Tab 展开为 4 空格', () => {
    expect(formatPython('if x:\n\tprint(1)')).toContain('    print(1)');
  });

  it('去掉行尾空白', () => {
    expect(formatPython('x = 1   \ny = 2')).toBe('x = 1\ny = 2\n');
  });

  it('压缩连续空行为单个空行', () => {
    const formatted = formatPython('a = 1\n\n\n\nb = 2');
    expect(formatted).toBe('a = 1\n\nb = 2\n');
  });

  it('保证末尾恰有一个换行', () => {
    expect(formatPython('x = 1')).toBe('x = 1\n');
    expect(formatPython('x = 1\n\n\n')).toBe('x = 1\n');
  });

  it('保留缩进层级语义（不破坏代码结构）', () => {
    const code = 'def f():\n    if True:\n        return 1';
    expect(formatPython(code)).toBe(`${code}\n`);
  });

  it('不破坏字符串字面量内的内容', () => {
    const code = 's = "line1\nline2"';
    expect(formatPython(code)).toContain('"line1');
    expect(formatPython(code)).toContain('line2"');
  });

  it('统一 CRLF 为 LF', () => {
    expect(formatPython('a = 1\r\nb = 2')).toBe('a = 1\nb = 2\n');
  });
});

describe('formatCode', () => {
  it('python / py 走完整 Python 格式化', () => {
    expect(formatCode('if x:\n\tpass', 'python')).toContain('    pass');
    expect(formatCode('if x:\n\tpass', 'py')).toContain('    pass');
  });

  it('其它语言仅做最小整理（去行尾空白 + 末尾换行）', () => {
    expect(formatCode('let a = 1   \nlet b = 2', 'javascript')).toBe('let a = 1\nlet b = 2\n');
  });
});

describe('countLines', () => {
  it('统计行数（含空行）', () => {
    expect(countLines('a\nb\nc')).toBe(3);
    expect(countLines('a\n\nb')).toBe(3);
  });

  it('空串返回 0', () => {
    expect(countLines('')).toBe(0);
  });
});
