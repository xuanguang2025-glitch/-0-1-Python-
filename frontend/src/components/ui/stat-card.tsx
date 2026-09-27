'use client';

import { cn } from '@/lib/utils';
import { Skeleton } from './skeleton';

export interface StatCardProps {
  label: string;
  value: React.ReactNode;
  hint?: string;
  icon?: React.ReactNode;
  tone?: 'default' | 'primary' | 'accent' | 'success' | 'warning' | 'danger';
  loading?: boolean;
  className?: string;
}

const TONES = {
  default: 'text-foreground',
  primary: 'text-primary',
  accent: 'text-accent',
  success: 'text-emerald-500',
  warning: 'text-amber-500',
  danger: 'text-rose-500',
} as const;

/** 指标卡：仪表盘 / 统计页统一使用。 */
export function StatCard({
  label,
  value,
  hint,
  icon,
  tone = 'default',
  loading = false,
  className,
}: StatCardProps): React.ReactElement {
  return (
    <div className={cn('rounded-lg border border-border bg-card p-4 transition-colors hover:border-primary/30', className)}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-[12px] text-muted-foreground">{label}</span>
        {icon ? <span className="text-muted-foreground">{icon}</span> : null}
      </div>
      {loading ? (
        <Skeleton className="mt-2.5 h-7 w-20" />
      ) : (
        <p className={cn('mt-1.5 text-[22px] font-semibold leading-none tracking-tight', TONES[tone])}>{value}</p>
      )}
      {hint ? <p className="mt-1.5 text-[11px] text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

/** 区块标题：页面内的分组标题。 */
export function SectionTitle({
  title,
  description,
  action,
  className,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}): React.ReactElement {
  return (
    <div className={cn('mb-4 flex flex-wrap items-end justify-between gap-3', className)}>
      <div className="space-y-1">
        <h2 className="text-[17px] font-semibold tracking-tight">{title}</h2>
        {description ? <p className="text-[13px] text-muted-foreground">{description}</p> : null}
      </div>
      {action}
    </div>
  );
}

/** 带圆点图例。 */
export function Dot({ tone = 'default', className }: { tone?: string; className?: string }): React.ReactElement {
  return <span className={cn('inline-block h-2 w-2 shrink-0 rounded-full bg-primary', tone, className)} />;
}
