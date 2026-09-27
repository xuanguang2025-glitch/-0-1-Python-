/**
 * 极简 Python 代码格式化器（无外部依赖）。
 * 仅做确定性、安全的整理：Tab → 4 空格、去行尾空白、压缩连续空行、保证末尾换行。
 * 不做 AST 级重排，避免破坏语义。
 */
export function formatPython(code: string): string {
  const lines = code.replace(/\r\n?/g, '\n').split('\n');
  const out: string[] = [];
  let blankRun = 0;

  for (const raw of lines) {
    let line = raw.replace(/\t/g, '    ').replace(/[ \t]+$/g, '');
    // 去掉行尾多余的逗号/空格混排前的空白重复
    line = line.replace(/ {2,}(?=[^\s#])/g, (match) => (match.length >= 4 ? match : ' '));

    if (line.trim() === '') {
      blankRun += 1;
      if (blankRun > 1) continue;
      out.push('');
      continue;
    }
    blankRun = 0;
    out.push(line);
  }

  return `${out.join('\n').replace(/\n+$/, '')}\n`;
}

/** 其它语言仅做最小整理（去行尾空白 + 末尾换行）。 */
export function formatCode(code: string, language = 'python'): string {
  if (language !== 'python' && language !== 'py') {
    return `${code.replace(/\r\n?/g, '\n').replace(/[ \t]+$/gm, '').replace(/\n+$/, '')}\n`;
  }
  return formatPython(code);
}

/** 粗略统计代码行数（含空行）。 */
export function countLines(code: string): number {
  if (!code) return 0;
  return code.split('\n').length;
}

/** 从错误输出中提取出错行号（用于定位编辑器）。 */
export function extractErrorLine(stderr: string | null | undefined): number | null {
  if (!stderr) return null;
  const match = /line (\d+)/.exec(stderr);
  return match ? Number(match[1]) : null;
}
