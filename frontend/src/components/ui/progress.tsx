'use client';

import { cn } from '@/lib/utils';

export interface ProgressProps extends React.HTMLAttributes<HTMLDivElement> {
  value: number;
  max?: number;
  /** 进度条粗细。 */
  size?: 'sm' | 'md' | 'lg';
  /** 仅用百分比着色（默认主色）。 */
  tone?: 'primary' | 'success' | 'warning' | 'accent';
  /** 是否在右侧显示百分比文本。 */
  showValue?: boolean;
}

const TONES = {
  primary: 'bg-primary',
  success: 'bg-success',
  warning: 'bg-warning',
  accent: 'bg-accent',
} as const;

/** 进度条。 */
export function Progress({
  value,
  max = 100,
  size = 'md',
  tone = 'primary',
  showValue = false,
  className,
  ...props
}: ProgressProps): React.ReactElement {
  const safeMax = max > 0 ? max : 100;
  const percent = Math.min(100, Math.max(0, (value / safeMax) * 100));
  const heights = { sm: 'h-1', md: 'h-1.5', lg: 'h-2.5' } as const;

  return (
    <div className={cn('flex items-center gap-2', className)} {...props}>
      <div
        className={cn('w-full overflow-hidden rounded-full bg-muted', heights[size])}
        role="progressbar"
        aria-valuenow={Math.round(percent)}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className={cn('h-full rounded-full transition-[width] duration-500 ease-out', TONES[tone])}
          style={{ width: `${percent}%` }}
        />
      </div>
      {showValue ? (
        <span className="w-9 shrink-0 text-right text-[11px] font-medium text-muted-foreground">
          {Math.round(percent)}%
        </span>
      ) : null}
    </div>
  );
}

export interface RingProgressProps {
  value: number;
  size?: number;
  stroke?: number;
  label?: string;
  className?: string;
}

/** 环形进度（用于课程完成度 / 等级）。 */
export function RingProgress({ value, size = 72, stroke = 7, label, className }: RingProgressProps): React.ReactElement {
  const percent = Math.min(100, Math.max(0, value));
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (percent / 100) * circumference;

  return (
    <div className={cn('relative inline-flex items-center justify-center', className)}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={stroke}
          className="stroke-muted"
          fill="transparent"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={stroke}
          strokeLinecap="round"
          className="stroke-primary transition-[stroke-dashoffset] duration-700"
          fill="transparent"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <span className="absolute text-[13px] font-semibold">{label ?? `${Math.round(percent)}%`}</span>
    </div>
  );
}
