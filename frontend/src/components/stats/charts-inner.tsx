'use client';

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { cn } from '@/lib/utils';

/** 统一坐标轴样式，避免各图表重复配置。 */
const AXIS = {
  stroke: 'hsl(var(--muted-foreground))',
  fontSize: 11,
  tickLine: false,
  axisLine: false,
} as const;

const GRID_STROKE = 'hsl(var(--border))';

const TOOLTIP_STYLE = {
  contentStyle: {
    background: 'hsl(var(--popover))',
    border: '1px solid hsl(var(--border))',
    borderRadius: 8,
    fontSize: 12,
    color: 'hsl(var(--popover-foreground))',
  },
  labelStyle: { color: 'hsl(var(--muted-foreground))', fontSize: 11 },
} as const;

export interface TrendPoint {
  date: string;
  value: number;
}

/** 学习趋势折线图（提交数 / 学习时长）。 */
export function TrendLineChart({
  points,
  height = 240,
  className,
  dataKeyLabel = '数值',
}: {
  points: TrendPoint[];
  height?: number;
  className?: string;
  dataKeyLabel?: string;
}): React.ReactElement {
  const data = points.map((point) => ({ ...point, label: point.date.slice(5) }));
  return (
    <div className={cn('w-full', className)} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
          <CartesianGrid stroke={GRID_STROKE} strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="label" {...AXIS} />
          <YAxis {...AXIS} allowDecimals={false} />
          <Tooltip {...TOOLTIP_STYLE} formatter={(value: unknown) => [String(value), dataKeyLabel] as [string, string]} />
          <Line
            type="monotone"
            dataKey="value"
            stroke="#3776AB"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, fill: '#FFD43B', stroke: '#3776AB' }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

/** 近 7 天学习时长柱状图。 */
export function WeeklyBarChart({
  points,
  height = 220,
  className,
}: {
  points: TrendPoint[];
  height?: number;
  className?: string;
}): React.ReactElement {
  const data = points.map((point) => ({ ...point, label: point.date.slice(5) }));
  return (
    <div className={cn('w-full', className)} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
          <CartesianGrid stroke={GRID_STROKE} strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="label" {...AXIS} />
          <YAxis {...AXIS} allowDecimals={false} />
          <Tooltip {...TOOLTIP_STYLE} formatter={(value: unknown) => [`${value} 分钟`, '学习时长'] as [string, string]} />
          <Bar dataKey="value" fill="#3776AB" radius={[4, 4, 0, 0]} maxBarSize={28} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** 知识点掌握度雷达图。 */
export function MasteryRadarChart({
  data,
  height = 260,
  className,
}: {
  data: { name: string; score: number }[];
  height?: number;
  className?: string;
}): React.ReactElement {
  return (
    <div className={cn('w-full', className)} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data} outerRadius="72%">
          <PolarGrid stroke={GRID_STROKE} />
          <PolarAngleAxis dataKey="name" tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }} />
          <Radar dataKey="score" stroke="#3776AB" fill="#3776AB" fillOpacity={0.32} />
          <Tooltip {...TOOLTIP_STYLE} formatter={(value: unknown) => [`${value} 分`, '掌握度'] as [string, string]} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** 分类正确率横向条图。 */
export function CategoryBarChart({
  data,
  height = 260,
  className,
}: {
  data: { name: string; value: number }[];
  height?: number;
  className?: string;
}): React.ReactElement {
  return (
    <div className={cn('w-full', className)} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, bottom: 0, left: 24 }}>
          <CartesianGrid stroke={GRID_STROKE} strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" {...AXIS} domain={[0, 100]} />
          <YAxis type="category" dataKey="name" width={78} {...AXIS} />
          <Tooltip {...TOOLTIP_STYLE} formatter={(value: unknown) => [`${value}%`, '正确率'] as [string, string]} />
          <Bar dataKey="value" radius={[0, 4, 4, 0]} maxBarSize={18}>
            {data.map((entry, index) => (
              <Cell key={entry.name} fill={index % 2 === 0 ? '#3776AB' : '#FFD43B'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** 学习热力趋势（180 天面积图）。 */
export function ActivityAreaChart({
  points,
  height = 200,
  className,
}: {
  points: TrendPoint[];
  height?: number;
  className?: string;
}): React.ReactElement {
  const data = points.map((point) => ({ ...point, label: point.date.slice(5) }));
  return (
    <div className={cn('w-full', className)} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
          <defs>
            <linearGradient id="activityFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#3776AB" stopOpacity={0.45} />
              <stop offset="100%" stopColor="#3776AB" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={GRID_STROKE} strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="label" {...AXIS} minTickGap={24} />
          <YAxis {...AXIS} allowDecimals={false} />
          <Tooltip {...TOOLTIP_STYLE} formatter={(value: unknown) => [String(value), '活动次数'] as [string, string]} />
          <Area type="monotone" dataKey="value" stroke="#3776AB" strokeWidth={2} fill="url(#activityFill)" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
