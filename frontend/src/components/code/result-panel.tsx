'use client';

import { AlertTriangle, CheckCircle2, Clock, Cpu, Play, Terminal, XCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatMemory, formatTime } from '@/lib/utils';
import type { RunResponse } from '@/lib/types';
import { Badge } from '@/components/ui/badge';
import { EmptyState } from '@/components/ui/alert';

export interface ResultPanelProps {
  /** 运行结果；null 表示尚未运行。 */
  result: RunResponse | null;
  running?: boolean;
  error?: string | null;
  className?: string;
  /** 空态文案。 */
  emptyHint?: string;
}

/** 运行结果面板：状态、stdout、stderr、耗时、内存、降级提示。 */
export function ResultPanel({
  result,
  running = false,
  error = null,
  className,
  emptyHint = '点击「运行」执行代码，结果会显示在这里',
}: ResultPanelProps): React.ReactElement {
  if (running) {
    return (
      <div className={cn('flex h-full flex-col items-center justify-center gap-2 text-muted-foreground', className)}>
        <Play className="h-5 w-5 animate-pulse-soft" />
        <p className="text-[13px]">正在运行…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className={cn('flex h-full flex-col items-center justify-center gap-2 px-4 text-center', className)}>
        <XCircle className="h-5 w-5 text-rose-500" />
        <p className="text-[13px] font-medium text-rose-500">运行失败</p>
        <p className="max-w-sm text-[12px] text-muted-foreground">{error}</p>
      </div>
    );
  }

  if (!result) {
    return (
      <div className={className}>
        <EmptyState icon={<Terminal className="h-5 w-5" />} title="暂无运行结果" description={emptyHint} className="border-0 py-10" />
      </div>
    );
  }

  const ok = result.status === 'success' && result.exit_code === 0;

  return (
    <div className={cn('flex h-full flex-col', className)}>
      <div className="flex flex-wrap items-center gap-2 border-b border-border px-3 py-2">
        <Badge variant={ok ? 'success' : 'danger'} className="gap-1">
          {ok ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
          {ok ? '运行成功' : result.status === 'timeout' ? '超时' : '运行出错'}
        </Badge>
        <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
          <Clock className="h-3 w-3" />
          {formatTime(result.time_ms)}
        </span>
        <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
          <Cpu className="h-3 w-3" />
          {formatMemory(result.memory_kb)}
        </span>
        <span className="ml-auto flex items-center gap-1.5">
          {result.degraded ? <Badge variant="warning">本地降级运行</Badge> : <Badge variant="secondary">sandbox</Badge>}
          <Badge variant="outline">exit {result.exit_code}</Badge>
        </span>
      </div>

      <div className="scroll-area flex-1 space-y-3 p-3">
        <section>
          <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">标准输出</p>
          <pre className="code-surface max-h-64 overflow-auto whitespace-pre-wrap p-3">
            {result.stdout || <span className="text-muted-foreground">（无输出）</span>}
          </pre>
        </section>

        {result.stderr ? (
          <section>
            <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">标准错误</p>
            <pre className="code-surface max-h-64 overflow-auto whitespace-pre-wrap border-rose-500/30 p-3 text-rose-500">
              {result.stderr}
            </pre>
          </section>
        ) : null}

        {result.error ? (
          <section className="rounded-lg border border-amber-500/30 bg-amber-500/8 p-3">
            <p className="flex items-center gap-1.5 text-[12px] font-medium text-amber-500">
              <AlertTriangle className="h-3.5 w-3.5" />
              {result.error.type ?? '运行异常'}
              {result.error.line ? `（第 ${result.error.line} 行）` : ''}
            </p>
            {result.error.message ? (
              <p className="mt-1 text-[12px] text-muted-foreground">{result.error.message}</p>
            ) : null}
            {result.error.traceback ? (
              <pre className="code-surface mt-2 max-h-40 overflow-auto p-2 text-[12px]">{result.error.traceback}</pre>
            ) : null}
          </section>
        ) : null}

        {result.truncated ? (
          <p className="text-[11px] text-amber-500">输出过长已被截断，仅显示前 64KB。</p>
        ) : null}
      </div>
    </div>
  );
}
