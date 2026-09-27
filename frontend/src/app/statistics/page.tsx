'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';
import { Award, BarChart3, CheckCircle2, Clock, FileText, Flame, Target, TrendingUp, Trophy, Zap } from 'lucide-react';
import { statisticsApi } from '@/lib/api';
import { formatMinutes, formatPercent } from '@/lib/utils';
import { useFetch } from '@/hooks/useFetch';
import { AuthGate } from '@/components/common/auth-gate';
import { Markdown } from '@/components/markdown';
import { PageContainer } from '@/components/layout/page-container';
import { Alert, EmptyState } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { SectionTitle, StatCard } from '@/components/ui/stat-card';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ActivityAreaChart, CategoryBarChart, ChartEmpty, TrendLineChart } from '@/components/stats/charts';
import { Heatmap } from '@/components/stats/heatmap';

/** 后端 /api/statistics/trend 的 metric 仅支持 submissions | accepted | minutes。 */
const METRIC_OPTIONS = [
  { value: 'submissions', label: '提交次数' },
  { value: 'accepted', label: '通过次数' },
  { value: 'minutes', label: '学习时长' },
];

/** 统计分析：总览 + 趋势 + 分类 + 热力图 + 报告 + 排名。 */
function StatisticsContent(): React.ReactElement {
  const [days, setDays] = useState(30);
  const [metric, setMetric] = useState('submissions');
  const [period, setPeriod] = useState<'week' | 'month'>('week');

  const overview = useFetch(() => statisticsApi.overview(), []);
  const trend = useFetch(() => statisticsApi.trend(days, metric), [days, metric]);
  const categories = useFetch(() => statisticsApi.categories(), []);
  const heatmap = useFetch(() => statisticsApi.heatmap(180), []);
  const report = useFetch(() => statisticsApi.report(period), [period]);
  const ranking = useFetch(() => statisticsApi.ranking(), []);

  const categoryData = useMemo(
    () =>
      (categories.data?.categories ?? []).slice(0, 8).map((item) => ({
        name: item.category,
        value: item.total > 0 ? Math.round((item.solved / item.total) * 100) : item.score,
      })),
    [categories.data],
  );

  const trendPoints = trend.data?.points ?? [];

  return (
    <PageContainer
      title="统计分析"
      description="用数据看清学习节奏：趋势、分类正确率、热力图与周报。"
      actions={
        <>
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              window.open('/api/statistics/export?type=report&format=md', '_blank');
            }}
          >
            <FileText className="h-3.5 w-3.5" />
            导出 Markdown
          </Button>
          {/* 后端不提供 PDF，按约定改走浏览器打印（可另存为 PDF）。 */}
          <Button size="sm" variant="ghost" onClick={() => window.print()}>
            <FileText className="h-3.5 w-3.5" />
            导出 PDF
          </Button>
        </>
      }
    >
      <div className="space-y-6">
        {/* 总览 */}
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            label="累计学习时长"
            value={formatMinutes(overview.data?.total_minutes ?? 0)}
            icon={<Clock className="h-3.5 w-3.5" />}
            tone="primary"
            loading={overview.loading && !overview.data}
          />
          <StatCard
            label="解题数量"
            value={overview.data?.solved ?? 0}
            hint={`共 ${overview.data?.submissions ?? 0} 次提交`}
            icon={<CheckCircle2 className="h-3.5 w-3.5" />}
            tone="success"
            loading={overview.loading && !overview.data}
          />
          <StatCard
            label="通过率"
            value={formatPercent(overview.data?.acceptance_rate ?? 0, 1)}
            hint="提交中 AC 的比例"
            icon={<Target className="h-3.5 w-3.5" />}
            loading={overview.loading && !overview.data}
          />
          <StatCard
            label="连续学习"
            value={`${overview.data?.streak_days ?? 0} 天`}
            icon={<Flame className="h-3.5 w-3.5" />}
            tone="warning"
            loading={overview.loading && !overview.data}
          />
          <StatCard
            label="当前等级"
            value={`Lv.${overview.data?.level ?? 1}`}
            icon={<Trophy className="h-3.5 w-3.5" />}
            tone="accent"
            loading={overview.loading && !overview.data}
          />
          <StatCard
            label="经验值"
            value={overview.data?.xp ?? 0}
            icon={<Zap className="h-3.5 w-3.5" />}
            loading={overview.loading && !overview.data}
          />
          <StatCard
            label="我的排名"
            value={
              ranking.data
                ? `第 ${ranking.data.my_rank} / ${ranking.data.total_users}`
                : '—'
            }
            hint="仅显示名次，不暴露他人信息"
            icon={<Award className="h-3.5 w-3.5" />}
            loading={ranking.loading && !ranking.data}
          />
          <StatCard
            label="击败比例"
            value={formatPercent((ranking.data?.percentile ?? 0) / 100, 0)}
            hint="超过同平台学习者"
            icon={<TrendingUp className="h-3.5 w-3.5" />}
            tone="success"
            loading={ranking.loading && !ranking.data}
          />
        </div>

        {/* 趋势 */}
        <Card>
          <CardHeader className="flex-row flex-wrap items-center justify-between gap-3">
            <CardTitle className="flex items-center gap-1.5">
              <BarChart3 className="h-4 w-4 text-primary" />
              学习趋势
            </CardTitle>
            <div className="flex items-center gap-2">
              <div className="w-32">
                <Select
                  controlSize="sm"
                  value={metric}
                  options={METRIC_OPTIONS}
                  onChange={(event) => setMetric(event.target.value)}
                />
              </div>
              <Tabs value={String(days)} onValueChange={(value) => setDays(Number(value))}>
                <TabsList>
                  <TabsTrigger value="7">7 天</TabsTrigger>
                  <TabsTrigger value="30">30 天</TabsTrigger>
                  <TabsTrigger value="90">90 天</TabsTrigger>
                </TabsList>
              </Tabs>
            </div>
          </CardHeader>
          <CardContent>
            {trend.loading && !trend.data ? (
              <Skeleton className="h-[240px] w-full" />
            ) : trendPoints.length > 0 ? (
              <TrendLineChart points={trendPoints} dataKeyLabel={METRIC_OPTIONS.find((o) => o.value === metric)?.label ?? '数值'} />
            ) : (
              <ChartEmpty height={240} hint="这段时间还没有记录，先去学一节课吧" />
            )}
          </CardContent>
        </Card>

        {/* 分类 + 热力图 */}
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle>分类正确率</CardTitle>
              <Badge variant="outline">按题型 / 分类</Badge>
            </CardHeader>
            <CardContent>
              {categories.loading && !categories.data ? (
                <Skeleton className="h-[260px] w-full" />
              ) : categoryData.length > 0 ? (
                <CategoryBarChart data={categoryData} />
              ) : (
                <ChartEmpty height={260} hint="还没有分类统计数据" />
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle>活跃度趋势</CardTitle>
              <Badge variant="secondary">近 180 天</Badge>
            </CardHeader>
            <CardContent className="space-y-4">
              {heatmap.loading && !heatmap.data ? (
                <Skeleton className="h-[200px] w-full" />
              ) : (
                <>
                  <Heatmap points={heatmap.data?.points ?? []} days={180} />
                  <ActivityAreaChart
                    points={(heatmap.data?.points ?? []).slice(-60).map((point) => ({ date: point.date, value: point.count }))}
                    height={160}
                  />
                </>
              )}
            </CardContent>
          </Card>
        </div>

        {/* 周报 */}
        <div>
          <SectionTitle
            title="学习报告"
            description="AI 汇总的阶段性总结与下一步建议。"
            action={
              <Tabs value={period} onValueChange={(value) => setPeriod(value as 'week' | 'month')}>
                <TabsList>
                  <TabsTrigger value="week">本周</TabsTrigger>
                  <TabsTrigger value="month">本月</TabsTrigger>
                </TabsList>
              </Tabs>
            }
          />
          <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
            <Card>
              <CardContent className="pt-5">
                {report.loading && !report.data ? (
                  <Skeleton className="h-40 w-full" />
                ) : report.data ? (
                  <div className="space-y-3">
                    <p className="text-[11px] text-muted-foreground">
                      {report.data.start_date ?? '—'} ~ {report.data.end_date ?? '—'}
                    </p>
                    <Markdown content={report.data.summary_md} />
                    {report.data.highlights.length > 0 ? (
                      <div className="flex flex-wrap gap-1.5">
                        {report.data.highlights.map((item) => (
                          <Badge key={item} variant="success">
                            {item}
                          </Badge>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ) : (
                  <EmptyState
                    title="暂无报告"
                    description="产生一些学习记录后，AI 会为你生成周报。"
                    className="border-0 py-8"
                  />
                )}
              </CardContent>
            </Card>

            <div className="space-y-4">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle>关键指标</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 text-[12.5px]">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">学习时长</span>
                    <span>{report.data?.metrics.minutes ?? 0} 分钟</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">完成课时</span>
                    <span>{report.data?.metrics.lessons ?? 0}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">提交次数</span>
                    <span>{report.data?.metrics.submissions ?? 0}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">通过次数</span>
                    <span>{report.data?.metrics.accepted ?? 0}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">通过率</span>
                    <span>{formatPercent(report.data?.metrics.acceptance_rate ?? 0, 1)}</span>
                  </div>
                </CardContent>
              </Card>

              {report.data?.recommendations && report.data.recommendations.length > 0 ? (
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle>下一步建议</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {report.data.recommendations.slice(0, 4).map((item) => (
                      <Link
                        key={`${item.type}-${item.id}`}
                        href={item.type === 'problem' ? `/problems/${item.id}` : '/learn'}
                        className="block rounded-md border border-border p-2.5 transition-colors hover:bg-muted/50"
                      >
                        <p className="text-[12.5px] font-medium">{item.title}</p>
                        <p className="mt-0.5 text-[11.5px] text-muted-foreground">{item.reason}</p>
                      </Link>
                    ))}
                  </CardContent>
                </Card>
              ) : (
                <Alert variant="info" title="暂无个性化建议" description="继续积累学习数据，建议会越来越准。" />
              )}
            </div>
          </div>
        </div>
      </div>
    </PageContainer>
  );
}

export default function StatisticsPage(): React.ReactElement {
  return (
    <AuthGate title="登录后查看统计分析" description="趋势图、分类正确率与学习报告都基于你的学习数据。">
      <StatisticsContent />
    </AuthGate>
  );
}
