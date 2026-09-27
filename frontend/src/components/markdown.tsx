'use client';

import Link from 'next/link';
import ReactMarkdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { cn } from '@/lib/utils';
import { CodeBlock } from '@/components/code/code-block';

export interface MarkdownProps {
  content: string;
  className?: string;
  /** 代码块的「在编辑器打开」回调。 */
  onOpenInEditor?: (code: string, language: string) => void;
  /** 代码块的「运行」回调。 */
  onRunCode?: (code: string, language: string) => void;
}

/**
 * Markdown 渲染：课程正文 / AI 回复 / 报告统一使用。
 * 代码块自动替换为带复制、运行能力的 CodeBlock。
 */
export function Markdown({ content, className, onOpenInEditor, onRunCode }: MarkdownProps): React.ReactElement {
  const components: Components = {
    pre: ({ children }) => <>{children}</>,
    code: ({ className: codeClass, children }) => {
      const language = /language-([\w+-]+)/.exec(codeClass ?? '')?.[1] ?? '';
      const text = String(children).replace(/\n$/, '');
      const isBlock = Boolean(language) || text.includes('\n');
      if (isBlock) {
        return (
          <CodeBlock
            code={text}
            language={language || 'python'}
            className="my-3"
            onOpenInEditor={onOpenInEditor ? () => onOpenInEditor(text, language || 'python') : undefined}
            onRun={onRunCode ? () => onRunCode(text, language || 'python') : undefined}
          />
        );
      }
      return (
        <code className="rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[0.86em]">{children}</code>
      );
    },
    a: ({ href, children }) => {
      const target = href ?? '#';
      const internal = target.startsWith('/');
      if (internal) {
        return (
          <Link href={target} className="text-primary underline underline-offset-2">
            {children}
          </Link>
        );
      }
      return (
        <a href={target} target="_blank" rel="noreferrer noopener" className="text-primary underline underline-offset-2">
          {children}
        </a>
      );
    },
    table: ({ children }) => (
      <div className="my-3 overflow-x-auto">
        <table>{children}</table>
      </div>
    ),
  };

  return (
    <div className={cn('prose-lab', className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content || ''}
      </ReactMarkdown>
    </div>
  );
}
