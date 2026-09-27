'use client';

import Link from 'next/link';
import { useMemo } from 'react';
import {
  ArrowRight,
  BookOpen,
  CalendarCheck,
  CheckCircle2,
  Clock,
  Code2,
  Flame,
  FolderKanban,
  ListChecks,
  Sparkles,
  Target,
  TrendingUp,
  Trophy,
  Zap,
} from 'lucide-react';
import { achievementApi, progressApi, projectApi, statisticsApi, userApi } from '@/lib/api';
import { levelName, nextLevelXp } from '@/lib/constants';
import { cn, formatMinutes } from '@/lib/utils';
import { useFetch } from '@/hooks/useFetch';
import { useAuth } from '@/hooks/useAuth';
import { AuthGate } from '@/components/common/auth-gate';
import { PageContainer } from '@/components/layout/page-container';
import { Alert, EmptyState } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress, RingProgress } from '@/components/ui/progress';
import { SectionTitle, StatCard } from '@/components/ui/stat-card';
import { Skeleton } from '@/components/ui/skeleton';
import { WeeklyBarChart } from '@/components/stats/charts';

/** 学习看板：核心指标 + 本周趋势 + 今日任务 + 推荐。 */
function DashboardContent(): React.ReactElement {
  const { user } = useAuth();

  const overview = useFetch(() => userApi.overview(), []);
  const progress = useFetch(() => progressApi.overview(), []);
  const weekly = useFetch(() => statisticsApi.trend(7, 'minutes'), []);
  const tasks = useFetch(() => achievementApi.dailyTasks(), []);
  const projects = useFetch(() => projectApi.list({ page: 1, page_size: 1 }), []);
  const recommend = useFetch(() => statisticsApi.report('week'), []);

  const weeklyPoints = useMemo(() => weekly.data?.points ?? [], [weekly.data]);
  const weeklyMinutes = weeklyPoints.reduce((sum, point) => sum + point.value, 0);
  const weeklyGoal = 300;
  const goalPercent = Math.min(100, Math.round((weeklyMinutes / weeklyGoal) * 100));

  const xp = overview.data?.xp ?? user?.xp ?? 0;
  const level = overview.data?.level ?? user?.level ?? 1;
  const nextXp = overview.data?.next_level_xp ?? nextLevelXp(level);
  const levelPercent = nextXp > 0 ? Math.min(100, Math.round((xp / nextXp) * 100)) : 0;
  const completedTasks = tasks.data?.filter((task) => task.completed).length ?? 0;

  const apiDown = !overview.loading && Boolean(overview.error);

  return (
    <PageContainer
      title={`你好，${user?.display_name ?? user?.username ?? 'Python 学习者'}`}
      description="今天也来写点代码吧。下面是你的学习概况。"
      actions={
        <>
          <Button variant="outline" size="sm" asChild>
            <Link href="/learn">
              <BookOpen className="h-3.5 w-3.5" />
              继续学习
            </Link>
          </Button>
          <Button size="sm" asChild>
            <Link href="/editor">
              <Code2 className="h-3.5 w-3.5" />
              打开编辑器
            </Link>
          </Button>
        </>
      }
    >
      <div className="space-y-6">
        {apiDown ? (
          <Alert
            variant="warning"
            title="部分数据暂时无法获取"
            description="可能是后端服务尚未启动或网络波动，页面其余内容仍可正常使用。"
          />
        ) : null}

        {/* 核心指标 */}
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            label="今日学习时间"
            value={formatMinutes(overview.data?.today_minutes ?? 0)}
            hint="累计专注学习时长"
            icon={<Clock className="h-3.5 w-3.5" />}
            tone="primary"
            loading={overview.loading && !overview.data}
          />
          <StatCard
            label="连续学习天数"
            value={`${overview.data?.streak_days ?? 0} 天`}
            hint="保持连续，别断签"
            icon={<Flame className="h-3.5 w-3.5" />}
            tone="warning"
            loading={overview.loading && !overview.data}
          />
          <StatCard
            label="本周学习时长"
            value={formatMinutes(weeklyMinutes)}
            hint={`目标 ${weeklyGoal} 分钟 · 完成 ${goalPercent}%`}
            icon={<TrendingUp className="h-3.5 w-3.5" />}
            loading={weekly.loading && !weekly.data}
          />
          <StatCard
            label="课程完成度"
            value={`${progress.data?.overall_percent ?? 0}%`}
            hint={`已完成 ${progress.data?.completed_lessons ?? 0}/${progress.data?.total_lessons ?? 0} 课时`}
            icon={<Target className="h-3.5 w-3.5" />}
            tone="success"
            loading={progress.loading && !progress.data}
          />
          <StatCard
            label="已解决题目"
            value={overview.data?.solved_problems ?? 0}
            hint="AC 通过的题目数"
            icon={<ListChecks className="h-3.5 w-3.5" />}
            loading={overview.loading && !overview.data}
          />
          <StatCard
            label="项目实战"
            value={projects.data?.total ?? 0}
            hint="可参与的项目数量"
            icon={<FolderKanban className="h-3.5 w-3.5" />}
            loading={projects.loading && !projects.data}
          />
          <StatCard
            label="Python 等级"
            value={`Lv.${level}`}
            hint={levelName(level)}
            icon={<Trophy className="h-3.5 w-3.5" />}
            tone="accent"
            loading={overview.loading && !overview.data}
          />
          <StatCard
            label="经验值 XP"
            value={xp}
            hint={`距下一级还需 ${Math.max(0, nextXp - xp)} XP`}
            icon={<Zap className="h-3.5 w-3.5" />}
            tone="primary"
            loading={overview.loading && !overview.data}
          />
        </div>

        <div className="grid gap-5 lg:grid-cols-[1.4fr_1fr]">
          {/* 本周趋势 */}
          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle>本周学习时长</CardTitle>
              <Badge variant="secondary">近 7 天</Badge>
            </CardHeader>
            <CardContent>
              {weekly.loading && !weekly.data ? (
                <Skeleton className="h-[220px] w-full" />
              ) : weeklyPoints.length ? (
                <WeeklyBarChart points={weeklyPoints} />
              ) : (
                <EmptyState
                  title="本周还没有学习记录"
                  description="完成一节课或运行一次代码，就会记录在这里。"
                  action={
                    <Button size="sm" asChild>
                      <Link href="/learn">开始学习</Link>
                    </Button>
                  }
                  className="border-0 py-10"
                />
              )}
            </CardContent>
          </Card>

          {/* 等级进度 */}
          <Card>
            <CardHeader>
              <CardTitle>等级进度</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center gap-4">
                <RingProgress value={levelPercent} label={`Lv.${level}`} size={84} />
                <div className="min-w-0 space-y-1">
                  <p className="text-[14px] font-semibold">{levelName(level)}</p>
                  <p className="text-[12px] text-muted-foreground">
                    {xp} / {nextXp} XP
                  </p>
                  <Progress value={levelPercent} size="sm" />
                </div>
              </div>

              <div className="space-y-2 rounded-lg border border-border bg-muted/25 p-3">
                <p className="flex items-center gap-1.5 text-[12px] font-medium">
                  <Sparkles className="h-3.5 w-3.5 text-accent" />
                  本周学习目标
                </p>
                <Progress value={goalPercent} size="md" showValue tone={goalPercent >= 100 ? 'success' : 'primary'} />
                <p className="text-[11px] text-muted-foreground">
                  {weeklyMinutes} / {weeklyGoal} 分钟
                </p>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="grid gap-5 lg:grid-cols-2">
          {/* 今日任务 */}
          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle>今日任务</CardTitle>
              <Badge variant={completedTasks > 0 ? 'success' : 'secondary'}>
                {completedTasks}/{tasks.data?.length ?? 0}
              </Badge>
            </CardHeader>
            <CardContent className="space-y-2.5">
              {tasks.loading && !tasks.data ? (
                <>
                  <Skeleton className="h-12 w-full" />
                  <Skeleton className="h-12 w-full" />
                </>
              ) : tasks.data && tasks.data.length > 0 ? (
                tasks.data.map((task) => (
                  <div key={task.id} className="flex items-center gap-3 rounded-lg border border-border p-3">
                    <span
                      className={cn(
                        'flex h-7 w-7 shrink-0 items-center justify-center rounded-full',
                        task.completed ? 'bg-success/15 text-success' : 'bg-muted text-muted-foreground',
                      )}
                    >
                      {task.completed ? <CheckCircle2 className="h-3.5 w-3.5" /> : <CalendarCheck className="h-3.5 w-3.5" />}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[13px] font-medium">{task.title}</p>
                      <div className="mt-1.5">
                        <Progress value={task.progress} max={task.target} size="sm" />
                      </div>
                    </div>
                    <span className="shrink-0 text-[11px] text-muted-foreground">+{task.xp_reward} XP</span>
                  </div>
                ))
              ) : (
                <EmptyState
                  title="今日暂无任务"
                  description="任务通常在学习后自动生成，先完成一节课试试。"
                  className="border-0 py-8"
                />
              )}
            </CardContent>
          </Card>

          {/* 学习建议 */}
          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle>本周学习建议</CardTitle>
              <Badge variant="outline">AI 生成</Badge>
            </CardHeader>
            <CardContent className="space-y-3">
              {recommend.loading && !recommend.data ? (
                <Skeleton className="h-32 w-full" />
              ) : recommend.data ? (
                <>
                  <p className="text-[12.5px] leading-relaxed text-muted-foreground">
                    {recommend.data.summary_md.slice(0, 180) || '暂无学习总结。'}
                  </p>
                  {recommend.data.highlights.length > 0 ? (
                    <ul className="space-y-1.5">
                      {recommend.data.highlights.slice(0, 3).map((item) => (
                        <li key={item} className="flex items-start gap-2 text-[12.5px] text-muted-foreground">
                          <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" />
                          {item}
                        </li>
                      ))}
                    </ul>
                  ) : null}
                  {recommend.data.weak_topics.length > 0 ? (
                    <div className="flex flex-wrap gap-1.5 pt-1">
                      <span className="text-[11px] text-muted-foreground">建议巩固：</span>
                      {recommend.data.weak_topics.slice(0, 4).map((topic) => (
                        <Badge key={topic.topic_id} variant="warning">
                          {topic.name}
                        </Badge>
                      ))}
                    </div>
                  ) : null}
                </>
              ) : (
                <EmptyState
                  title="还没有足够的学习数据"
                  description="积累几天的学习记录后，这里会给出针对性的建议。"
                  className="border-0 py-8"
                />
              )}
              <Button variant="outline" size="sm" className="w-full" asChild>
                <Link href="/statistics">
                  查看完整统计
                  <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* 阶段进度 */}
        <div>
          <SectionTitle
            title="阶段进度"
            description="按 18 阶段路线图查看你的完成情况。"
            action={
              <Button variant="ghost" size="sm" asChild>
                <Link href="/learn">
                  全部课程
                  <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </Button>
            }
          />
          {progress.loading && !progress.data ? (
            <div className="space-y-2">
              {Array.from({ length: 4 }).map((_, index) => (
                <Skeleton key={index} className="h-14 w-full" />
              ))}
            </div>
          ) : progress.data && progress.data.courses.length > 0 ? (
            <div className="grid gap-3 sm:grid-cols-2">
              {progress.data.courses.slice(0, 6).map((course) => (
                <Link
                  key={course.course_id}
                  href={`/courses/${course.slug}`}
                  className="flex items-center gap-3 rounded-lg border border-border bg-card p-3 transition-colors hover:border-primary/40"
                >
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-primary/12 text-[12px] font-bold text-primary">
                    {course.stage_no}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13px] font-medium">{course.title}</p>
                    <div className="mt-1.5">
                      <Progress value={course.percent} size="sm" showValue />
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <EmptyState
              title="还没有开始任何课程"
              description="从阶段 1 开始，18 步走完 Python 主干知识。"
              action={
                <Button size="sm" asChild>
                  <Link href="/courses">浏览课程</Link>
                </Button>
              }
            />
          )}
        </div>
      </div>
    </PageContainer>
  );
}

export default function DashboardPage(): React.ReactElement {
  return (
    <AuthGate title="登录后查看学习看板" description="学习看板会汇总你的时长、进度、等级与今日任务。">
      <DashboardContent />
    </AuthGate>
  );
}
