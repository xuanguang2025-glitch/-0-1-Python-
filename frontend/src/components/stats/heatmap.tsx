'use client';

import { useMemo } from 'react';
import { cn } from '@/lib/utils';

export interface HeatmapProps {
  points: { date: string; count: number; minutes?: number }[];
  /** 展示最近多少天。 */
  days?: number;
  className?: string;
}

const LEVELS = [
  'bg-muted',
  'bg-primary/25',
  'bg-primary/45',
  'bg-primary/70',
  'bg-primary',
];

function levelOf(count: number, max: number): number {
  if (count <= 0) return 0;
  if (max <= 1) return 4;
  const ratio = count / max;
  if (ratio <= 0.25) return 1;
  if (ratio <= 0.5) return 2;
  if (ratio <= 0.75) return 3;
  return 4;
}

/** 学习热力图：按周排列的方格日历（纯 CSS，无依赖）。 */
export function Heatmap({ points, days = 180, className }: HeatmapProps): React.ReactElement {
  const { weeks, maxCount, monthLabels } = useMemo(() => {
    const map = new Map(points.map((point) => [point.date, point]));
    const today = new Date();
    const cells: { date: string; count: number; minutes: number }[] = [];
    for (let index = days - 1; index >= 0; index -= 1) {
      const date = new Date(today);
      date.setDate(today.getDate() - index);
      const key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
      const found = map.get(key);
      cells.push({ date: key, count: found?.count ?? 0, minutes: found?.minutes ?? 0 });
    }

    // 按周分组（以周一为一周起点）
    const grouped: typeof cells[] = [];
    let current: typeof cells = [];
    cells.forEach((cell) => {
      const weekday = new Date(`${cell.date}T00:00:00`).getDay();
      if (weekday === 1 && current.length > 0) {
        grouped.push(current);
        current = [];
      }
      current.push(cell);
    });
    if (current.length > 0) grouped.push(current);

    const labels = grouped.map((week) => {
      const first = new Date(`${week[0].date}T00:00:00`);
      return first.getDate() <= 7 ? `${first.getMonth() + 1}月` : '';
    });

    const max = Math.max(1, ...cells.map((cell) => cell.count));
    return { weeks: grouped, maxCount: max, monthLabels: labels };
  }, [points, days]);

  return (
    <div className={cn('space-y-2', className)}>
      <div className="overflow-x-auto pb-1">
        <div className="inline-flex flex-col gap-1">
          <div className="flex gap-[3px] pl-7">
            {monthLabels.map((label, index) => (
              <span key={index} className="w-[13px] text-[9px] text-muted-foreground">
                {label}
              </span>
            ))}
          </div>
          <div className="flex gap-[3px]">
            <div className="mr-1 flex w-6 flex-col justify-between text-[9px] text-muted-foreground">
              <span>一</span>
              <span>三</span>
              <span>五</span>
              <span>日</span>
            </div>
            {weeks.map((week, weekIndex) => (
              <div key={weekIndex} className="flex flex-col gap-[3px]">
                {Array.from({ length: 7 }).map((_, dayIndex) => {
                  const cell = week[dayIndex];
                  if (!cell) return <span key={dayIndex} className="h-[13px] w-[13px]" />;
                  const level = levelOf(cell.count, maxCount);
                  return (
                    <span
                      key={cell.date}
                      title={`${cell.date} · ${cell.count} 次活动${cell.minutes ? ` · ${cell.minutes} 分钟` : ''}`}
                      className={cn('h-[13px] w-[13px] rounded-[3px] transition-colors', LEVELS[level])}
                    />
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
        <span>少</span>
        {LEVELS.map((level) => (
          <span key={level} className={cn('h-[10px] w-[10px] rounded-[2px]', level)} />
        ))}
        <span>多</span>
      </div>
    </div>
  );
}
