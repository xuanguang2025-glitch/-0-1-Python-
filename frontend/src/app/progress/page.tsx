'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';
import { BookOpen, Flame, Layers, Target, TrendingUp, Zap } from 'lucide-react';
import { courseApi, progressApi } from '@/lib/api';
import { cn, formatPercent } from '@/lib/utils';
import { useFetch } from '@/hooks/useFetch';
import { useToaster } from '@/hooks/useToast';
import { AuthGate } from '@/components/common/auth-gate';
import { PageContainer } from '@/components/layout/page-container';
import { EmptyState } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress, RingProgress } from '@/components/ui/progress';
import { Select } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { SectionTitle, StatCard } from '@/components/ui/stat-card';
import { Heatmap } from '@/components/stats/heatmap';
import { MasteryRadarChart } from '@/components/stats/charts';

const MODE_OPTIONS = [
  { value: 'system', label: '系统学习（按路线图）' },
  { value: 'free', label: '自由学习' },
  { value: 'drill', label: '专项刷题' },
  { value: 'project', label: '项目驱动' },
  { value: 'challenge', label: '挑战模式' },
  { value: 'exam', label: '考试模式' },
  { value: 'ai', label: 'AI 陪练' },
];

/** 学习进度：整体完成度 + 阶段进度 + 知识点掌握 + 热力图。 */
function ProgressContent(): React.ReactElement {
  const toaster = useToaster();
  const [learningMode, setLearningMode] = useState('system');

  const overview = useFetch(() => progressApi.overview(), []);
  const mastery = useFetch(() => progressApi.mastery(), []);
  const heatmap = useFetch(() => progressApi.heatmap(180), []);
  const courses = useFetch(() => courseApi.list({ page: 1, page_size: 100 }), []);

  const radarData = useMemo(
    () =>
      (mastery.data?.topics ?? [])
        .slice(0, 8)
        .map((topic) => {
          const label = topic.name ?? topic.topic_id;
          return { name: label.length > 6 ? `${label.slice(0, 6)}…` : label, score: topic.mastery_score };
        }),
    [mastery.data],
  );

  const changeMode = async (value: string): Promise<void> => {
    setLearningMode(value);
    try {
      await progressApi.setMode(value);
      toaster.success('学习模式已切换');
    } catch {
      toaster.error('切换失败', '稍后再试');
    }
  };

  const overall = overview.data?.overall_percent ?? 0;

  return (
    <PageContainer
      title="我的养成"
      description="看看自己走到哪一步了：完成度、知识点掌握、学习热力。"
      actions={
        <Button size="sm" variant="outline" asChild>
          <Link href="/statistics">
            <TrendingUp className="h-3.5 w-3.5" />
            详细统计
          </Link>
        </Button>
      }
    >
      <div className="space-y-6">
        <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
          <Card>
            <CardContent className="flex flex-col items-center gap-3 pt-6">
              <RingProgress value={overall} size={116} label={`${Math.round(overall)}%`} />
              <p className="text-[13px] font-medium">整体完成度</p>
              <p className="text-[12px] text-muted-foreground">
                已完成 {overview.data?.completed_lessons ?? 0} / {overview.data?.total_lessons ?? 0} 课时
              </p>
              <Badge variant="secondary" className="gap-1">
                <Layers className="h-3 w-3" />
                当前阶段 STAGE {overview.data?.current_stage ?? 1}
              </Badge>
            </CardContent>
          </Card>

          <div className="grid gap-3 sm:grid-cols-2">
            <StatCard
              label="已完成课时"
              value={overview.data?.completed_lessons ?? 0}
              icon={<BookOpen className="h-3.5 w-3.5" />}
              tone="success"
              loading={overview.loading && !overview.data}
            />
            <StatCard
              label="当前阶段"
              value={`STAGE ${overview.data?.current_stage ?? 1}`}
              hint="按路线图顺序推进"
              icon={<Layers className="h-3.5 w-3.5" />}
              tone="primary"
              loading={overview.loading && !overview.data}
            />
            <StatCard
              label="薄弱知识点"
              value={mastery.data?.weak_topics.length ?? 0}
              hint="掌握度低于 60% 的知识点"
              icon={<Target className="h-3.5 w-3.5" />}
              tone="warning"
              loading={mastery.loading && !mastery.data}
            />
            <Card className="sm:col-span-2">
              <CardHeader className="pb-2">
                <CardTitle>学习模式</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-wrap items-center gap-3">
                <div className="w-52">
                  <Select value={learningMode} options={MODE_OPTIONS} onChange={(event) => void changeMode(event.target.value)} />
                </div>
                <p className="text-[12px] text-muted-foreground">学习模式会影响推荐策略与练习侧重。</p>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* 阶段进度 */}
        <div>
          <SectionTitle title="阶段完成情况" description="18 阶段的逐项进度。" />
          {courses.loading && !courses.data ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, index) => (
                <Skeleton key={index} className="h-12 w-full" />
              ))}
            </div>
          ) : courses.data && courses.data.items.length > 0 ? (
            <div className="space-y-2">
              {courses.data.items.map((course) => (
                <Link
                  key={course.id}
                  href={`/courses/${course.slug}`}
                  className="flex items-center gap-3 rounded-lg border border-border bg-card p-3 transition-colors hover:border-primary/40"
                >
                  <span
                    className={cn(
                      'flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-[12px] font-bold',
                      (course.progress_percent ?? 0) >= 100
                        ? 'bg-emerald-500/12 text-emerald-500'
                        : 'bg-primary/12 text-primary',
                    )}
                  >
                    {course.stage_no}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13px] font-medium">{course.title}</p>
                    <Progress value={course.progress_percent ?? 0} size="sm" className="mt-1.5" />
                  </div>
                  <span className="shrink-0 text-[12px] text-muted-foreground">{Math.round(course.progress_percent ?? 0)}%</span>
                </Link>
              ))}
            </div>
          ) : (
            <EmptyState title="暂无阶段数据" description="后端课程进度接口暂时不可用。" />
          )}
        </div>

        {/* 掌握度 + 热力图 */}
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle>知识点掌握度</CardTitle>
              <Badge variant="outline">Top 8</Badge>
            </CardHeader>
            <CardContent>
              {mastery.loading && !mastery.data ? (
                <Skeleton className="h-[260px] w-full" />
              ) : radarData.length >= 3 ? (
                <MasteryRadarChart data={radarData} />
              ) : (
                <EmptyState
                  title="掌握度数据不足"
                  description="完成随堂练习与题目后，这里会绘制知识点雷达图。"
                  className="border-0 py-8"
                />
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle className="flex items-center gap-1.5">
                <Flame className="h-4 w-4 text-amber-500" />
                学习热力图
              </CardTitle>
              <Badge variant="secondary">近 180 天</Badge>
            </CardHeader>
            <CardContent className="space-y-3">
              {heatmap.loading && !heatmap.data ? (
                <Skeleton className="h-[150px] w-full" />
              ) : (
                <Heatmap points={heatmap.data?.points ?? []} days={180} />
              )}
              <p className="text-[11px] text-muted-foreground">
                共 {heatmap.data?.points.filter((point) => point.count > 0).length ?? 0} 个活跃日 · 累计{' '}
                {heatmap.data?.points.reduce((sum, point) => sum + point.minutes, 0) ?? 0} 分钟
              </p>
            </CardContent>
          </Card>
        </div>

        {/* 薄弱知识点 */}
        <div>
          <SectionTitle
            title="需要巩固的知识点"
            description="掌握度较低的知识点，建议优先复习。"
            action={
              <Button size="sm" variant="outline" asChild>
                <Link href="/wrong-answers">
                  <Zap className="h-3.5 w-3.5" />
                  去错题本
                </Link>
              </Button>
            }
          />
          {mastery.data && mastery.data.weak_topics.length > 0 ? (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {mastery.data.weak_topics.map((topic) => (
                <Card key={topic.topic_id} className="p-4">
                  <div className="flex items-center justify-between gap-2">
                    <p className="truncate text-[13px] font-medium">{topic.name}</p>
                    <Badge variant="warning">{formatPercent(topic.mastery_score / 100, 0)}</Badge>
                  </div>
                  <Progress value={topic.mastery_score} size="sm" className="mt-2.5" tone="warning" />
                  <p className="mt-2 text-[11px] text-muted-foreground">已练习 {topic.practiced_count} 次</p>
                </Card>
              ))}
            </div>
          ) : (
            <EmptyState
              icon={<Target className="h-6 w-6" />}
              title="暂时没有薄弱知识点"
              description="继续保持！做更多题能让掌握度画像更准确。"
              action={
                <Button size="sm" asChild>
                  <Link href="/problems">去刷题</Link>
                </Button>
              }
            />
          )}
        </div>
      </div>
    </PageContainer>
  );
}

export default function ProgressPage(): React.ReactElement {
  return (
    <AuthGate title="登录后查看学习进度" description="完成度、掌握度与热力图都基于你的学习记录生成。">
      <ProgressContent />
    </AuthGate>
  );
}
