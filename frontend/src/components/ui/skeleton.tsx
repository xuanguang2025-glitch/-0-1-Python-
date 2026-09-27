'use client';

import { cn } from '@/lib/utils';

export interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {}

/** 骨架屏占位块。 */
export function Skeleton({ className, ...props }: SkeletonProps): React.ReactElement {
  return <div className={cn('animate-pulse-soft rounded-md bg-muted', className)} {...props} />;
}

/** 卡片骨架：列表加载时使用，避免布局跳动。 */
export function CardSkeleton({ lines = 3, className }: { lines?: number; className?: string }): React.ReactElement {
  return (
    <div className={cn('rounded-lg border border-border bg-card p-5', className)}>
      <Skeleton className="mb-3 h-4 w-1/3" />
      <div className="space-y-2">
        {Array.from({ length: lines }).map((_, index) => (
          <Skeleton key={index} className="h-3 w-full" style={{ width: `${92 - index * 12}%` }} />
        ))}
      </div>
    </div>
  );
}

/** 统计卡片骨架。 */
export function StatSkeleton(): React.ReactElement {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <Skeleton className="mb-2 h-3 w-16" />
      <Skeleton className="h-7 w-24" />
    </div>
  );
}

/** 行 skeleton。 */
export function RowSkeleton({ rows = 5 }: { rows?: number }): React.ReactElement {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, index) => (
        <Skeleton key={index} className="h-11 w-full" />
      ))}
    </div>
  );
}
