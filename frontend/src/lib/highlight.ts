/**
 * 轻量 Python 语法高亮（无外部依赖、无 WASM）。
 * 仅做词法着色，输出 HTML 字符串前会完整转义，避免 XSS。
 * 复杂高亮（编辑器内）交由 Monaco 处理。
 */

const KEYWORDS = new Set([
  'and', 'as', 'assert', 'async', 'await', 'break', 'class', 'continue', 'def', 'del', 'elif', 'else', 'except',
  'finally', 'for', 'from', 'global', 'if', 'import', 'in', 'is', 'lambda', 'nonlocal', 'not', 'or', 'pass',
  'raise', 'return', 'try', 'while', 'with', 'yield', 'match', 'case', 'True', 'False', 'None',
]);

const BUILTINS = new Set([
  'abs', 'all', 'any', 'ascii', 'bin', 'bool', 'bytearray', 'bytes', 'callable', 'chr', 'classmethod', 'compile',
  'complex', 'delattr', 'dict', 'dir', 'divmod', 'enumerate', 'eval', 'exec', 'filter', 'float', 'format',
  'frozenset', 'getattr', 'globals', 'hasattr', 'hash', 'help', 'hex', 'id', 'input', 'int', 'isinstance',
  'issubclass', 'iter', 'len', 'list', 'locals', 'map', 'max', 'memoryview', 'min', 'next', 'object', 'oct',
  'open', 'ord', 'pow', 'print', 'property', 'range', 'repr', 'reversed', 'round', 'set', 'setattr', 'slice',
  'sorted', 'staticmethod', 'str', 'sum', 'super', 'tuple', 'type', 'vars', 'zip', 'self', 'cls',
]);

const TOKEN_RE =
  /(#[^\n]*)|("""[\s\S]*?"""|'''[\s\S]*?'''|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|(\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b)|([A-Za-z_][A-Za-z0-9_]*)|([+\-*/%=<>!&|^~@]+)/g;

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function wrap(className: string, text: string): string {
  return `<span class="${className}">${escapeHtml(text)}</span>`;
}

/** 把 Python 源码转换成带高亮 span 的 HTML 片段（已转义）。 */
export function highlightPython(code: string): string {
  let result = '';
  let lastIndex = 0;
  TOKEN_RE.lastIndex = 0;

  let match: RegExpExecArray | null = TOKEN_RE.exec(code);
  while (match !== null) {
    const [full, comment, str, num, ident, op] = match;
    result += escapeHtml(code.slice(lastIndex, match.index));
    lastIndex = match.index + full.length;

    if (comment !== undefined) {
      result += wrap('tok-comment', comment);
    } else if (str !== undefined) {
      result += wrap('tok-string', str);
    } else if (num !== undefined) {
      result += wrap('tok-number', num);
    } else if (ident !== undefined) {
      if (KEYWORDS.has(ident)) result += wrap('tok-keyword', ident);
      else if (BUILTINS.has(ident)) result += wrap('tok-builtin', ident);
      else if (/^\s*\(/.test(code.slice(lastIndex))) result += wrap('tok-func', ident);
      else result += escapeHtml(ident);
    } else if (op !== undefined) {
      result += wrap('tok-op', op);
    }

    match = TOKEN_RE.exec(code);
  }

  result += escapeHtml(code.slice(lastIndex));
  return result;
}

/** 按语言分发（目前仅 Python 有专门高亮，其余原样转义）。 */
export function highlightCode(code: string, language = 'python'): string {
  if (language === 'python' || language === 'py') return highlightPython(code);
  return escapeHtml(code);
}
