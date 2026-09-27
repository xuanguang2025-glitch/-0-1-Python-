'use client';

import { useMemo, useState } from 'react';
import { Check, Code2, Copy, Download, Play, Wand2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { highlightCode } from '@/lib/highlight';
import { Button } from '@/components/ui/button';
import { Tooltip } from '@/components/ui/tooltip';

export interface CodeBlockProps {
  code: string;
  language?: string;
  /** 文件 / 代码块标题。 */
  filename?: string;
  /** 是否展示行号。 */
  showLineNumbers?: boolean;
  /** 运行按钮回调（不传则隐藏）。 */
  onRun?: () => void;
  /** 运行中状态。 */
  running?: boolean;
  /** 在编辑器中打开回调（不传则隐藏）。 */
  onOpenInEditor?: () => void;
  /** 格式化回调（不传则隐藏）。 */
  onFormat?: () => void;
  /** 可下载为文件。 */
  downloadName?: string;
  className?: string;
  maxHeight?: number | null;
}

/**
 * 代码块：语法高亮 + 复制 + 运行 + 在编辑器打开 + 格式化。
 * 高亮由 lib/highlight.ts 完成（输出已转义，可安全注入）。
 */
export function CodeBlock({
  code,
  language = 'python',
  filename,
  showLineNumbers = false,
  onRun,
  running = false,
  onOpenInEditor,
  onFormat,
  downloadName,
  className,
  maxHeight = 460,
}: CodeBlockProps): React.ReactElement {
  const [copied, setCopied] = useState(false);
  const html = useMemo(() => highlightCode(code, language), [code, language]);

  const copy = async (): Promise<void> => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  };

  const download = (): void => {
    const blob = new Blob([code], { type: 'text/x-python;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = downloadName ?? 'code.py';
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className={cn('group/code overflow-hidden rounded-lg border border-border bg-[hsl(var(--muted))]', className)}>
      <div className="flex items-center gap-2 border-b border-border px-3 py-1.5">
        <Code2 className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="font-mono text-[11px] text-muted-foreground">{filename ?? language}</span>
        <div className="ml-auto flex items-center gap-0.5">
          {onFormat ? (
            <Tooltip content="格式化代码">
              <Button variant="ghost" size="icon-sm" onClick={onFormat} aria-label="格式化">
                <Wand2 className="h-3.5 w-3.5" />
              </Button>
            </Tooltip>
          ) : null}
          {onOpenInEditor ? (
            <Tooltip content="在编辑器中打开">
              <Button variant="ghost" size="icon-sm" onClick={onOpenInEditor} aria-label="在编辑器中打开">
                <Code2 className="h-3.5 w-3.5" />
              </Button>
            </Tooltip>
          ) : null}
          {downloadName ? (
            <Tooltip content="下载">
              <Button variant="ghost" size="icon-sm" onClick={download} aria-label="下载代码">
                <Download className="h-3.5 w-3.5" />
              </Button>
            </Tooltip>
          ) : null}
          {onRun ? (
            <Button variant="ghost" size="sm" onClick={onRun} loading={running} className="h-6 px-2 text-[11px]">
              <Play className="h-3 w-3" />
              运行
            </Button>
          ) : null}
          <Tooltip content={copied ? '已复制' : '复制代码'}>
            <Button variant="ghost" size="icon-sm" onClick={() => void copy()} aria-label="复制代码">
              {copied ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
            </Button>
          </Tooltip>
        </div>
      </div>

      <div className="overflow-auto" style={maxHeight ? { maxHeight } : undefined}>
        <pre className="flex min-w-full p-3 text-[13px] leading-[1.65]">
          {showLineNumbers ? (
            <code className="select-none pr-3 text-right text-muted-foreground/60" aria-hidden>
              {code.split('\n').map((_, index) => `${index + 1}\n`).join('')}
            </code>
          ) : null}
          <code className="flex-1 font-mono" dangerouslySetInnerHTML={{ __html: html }} />
        </pre>
      </div>
    </div>
  );
}

export interface InlineCodeProps {
  children: React.ReactNode;
  className?: string;
}

/** 行内代码。 */
export function InlineCode({ children, className }: InlineCodeProps): React.ReactElement {
  return (
    <code
      className={cn(
        'rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[0.86em] text-foreground',
        className,
      )}
    >
      {children}
    </code>
  );
}
