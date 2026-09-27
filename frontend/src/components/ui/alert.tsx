'use client';

import { AlertTriangle, CheckCircle2, Info, RefreshCw, XCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from './button';

export type AlertVariant = 'info' | 'success' | 'warning' | 'error';

const STYLES: Record<AlertVariant, { wrap: string; icon: React.ReactNode }> = {
  info: { wrap: 'border-sky-500/30 bg-sky-500/8 text-sky-600 dark:text-sky-400', icon: <Info className="h-4 w-4" /> },
  success: {
    wrap: 'border-emerald-500/30 bg-emerald-500/8 text-emerald-600 dark:text-emerald-400',
    icon: <CheckCircle2 className="h-4 w-4" />,
  },
  warning: {
    wrap: 'border-amber-500/30 bg-amber-500/8 text-amber-600 dark:text-amber-400',
    icon: <AlertTriangle className="h-4 w-4" />,
  },
  error: {
    wrap: 'border-rose-500/30 bg-rose-500/8 text-rose-600 dark:text-rose-400',
    icon: <XCircle className="h-4 w-4" />,
  },
};

export interface AlertProps {
  variant?: AlertVariant;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
  children?: React.ReactNode;
}

/** 提示条。 */
export function Alert({ variant = 'info', title, description, action, className, children }: AlertProps): React.ReactElement {
  const style = STYLES[variant];
  return (
    <div className={cn('flex items-start gap-2.5 rounded-lg border p-3', style.wrap, className)}>
      <span className="mt-0.5 shrink-0">{style.icon}</span>
      <div className="min-w-0 flex-1 space-y-1">
        <p className="text-[13px] font-medium">{title}</p>
        {description ? <p className="text-[12px] leading-relaxed opacity-85">{description}</p> : null}
        {children}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}

export interface ErrorStateProps {
  title?: string;
  description?: string;
  onRetry?: () => void;
  className?: string;
}

/**
 * 接口失败占位：后端未就绪时页面统一渲染它，绝不白屏。
 */
export function ErrorState({
  title = '数据暂时加载失败',
  description = '后端服务可能尚未启动，稍后重试即可。',
  onRetry,
  className,
}: ErrorStateProps): React.ReactElement {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border bg-muted/25 px-6 py-10 text-center',
        className,
      )}
    >
      <AlertTriangle className="h-6 w-6 text-amber-500" />
      <div className="space-y-1">
        <p className="text-sm font-medium">{title}</p>
        <p className="text-[12px] text-muted-foreground">{description}</p>
      </div>
      {onRetry ? (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RefreshCw className="h-3.5 w-3.5" />
          重新加载
        </Button>
      ) : null}
    </div>
  );
}

export interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}

/** 空态占位。 */
export function EmptyState({ icon, title, description, action, className }: EmptyStateProps): React.ReactElement {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border px-6 py-12 text-center',
        className,
      )}
    >
      {icon ? <span className="text-muted-foreground">{icon}</span> : null}
      <div className="space-y-1">
        <p className="text-sm font-medium">{title}</p>
        {description ? <p className="mx-auto max-w-md text-[12px] text-muted-foreground">{description}</p> : null}
      </div>
      {action}
    </div>
  );
}
