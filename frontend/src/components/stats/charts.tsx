'use client';

import dynamic from 'next/dynamic';
import { cn } from '@/lib/utils';
import { Skeleton } from '@/components/ui/skeleton';

function ChartSkeleton({ height = 220 }: { height?: number }): React.ReactElement {
  return (
    <div className="w-full space-y-2" style={{ height }}>
      <Skeleton className="h-4 w-24" />
      <Skeleton className="h-[calc(100%-1.5rem)] w-full" />
    </div>
  );
}

/**
 * 图表统一走 ssr:false 动态加载：
 * recharts 依赖 DOM 测量，服务端渲染会产生 hydration 警告且无意义。
 */
export const TrendLineChart = dynamic(() => import('./charts-inner').then((m) => m.TrendLineChart), {
  ssr: false,
  loading: () => <ChartSkeleton height={240} />,
});

export const WeeklyBarChart = dynamic(() => import('./charts-inner').then((m) => m.WeeklyBarChart), {
  ssr: false,
  loading: () => <ChartSkeleton height={220} />,
});

export const MasteryRadarChart = dynamic(() => import('./charts-inner').then((m) => m.MasteryRadarChart), {
  ssr: false,
  loading: () => <ChartSkeleton height={260} />,
});

export const CategoryBarChart = dynamic(() => import('./charts-inner').then((m) => m.CategoryBarChart), {
  ssr: false,
  loading: () => <ChartSkeleton height={260} />,
});

export const ActivityAreaChart = dynamic(() => import('./charts-inner').then((m) => m.ActivityAreaChart), {
  ssr: false,
  loading: () => <ChartSkeleton height={200} />,
});

/** 空数据占位（图表容器尺寸保持一致，避免布局跳动）。 */
export function ChartEmpty({ height = 220, hint = '暂无数据' }: { height?: number; hint?: string }): React.ReactElement {
  return (
    <div
      className={cn('flex items-center justify-center rounded-lg border border-dashed border-border text-[12px] text-muted-foreground')}
      style={{ height }}
    >
      {hint}
    </div>
  );
}
