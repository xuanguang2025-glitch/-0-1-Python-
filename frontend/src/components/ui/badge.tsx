'use client';

import { cn } from '@/lib/utils';

export type BadgeVariant = 'default' | 'secondary' | 'outline' | 'success' | 'warning' | 'danger' | 'info' | 'accent';

const VARIANTS: Record<BadgeVariant, string> = {
  default: 'border-primary/25 bg-primary/12 text-primary',
  secondary: 'border-border bg-muted text-muted-foreground',
  outline: 'border-border bg-transparent text-foreground',
  success: 'border-emerald-500/25 bg-emerald-500/12 text-emerald-500',
  warning: 'border-amber-500/25 bg-amber-500/12 text-amber-500',
  danger: 'border-rose-500/25 bg-rose-500/12 text-rose-500',
  info: 'border-sky-500/25 bg-sky-500/12 text-sky-500',
  accent: 'border-accent/40 bg-accent/15 text-accent',
};

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
}

/** 状态标记徽章。 */
export function Badge({ className, variant = 'default', ...props }: BadgeProps): React.ReactElement {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium leading-tight',
        VARIANTS[variant],
        className,
      )}
      {...props}
    />
  );
}
