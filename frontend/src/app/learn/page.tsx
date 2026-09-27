'use client';

import Link from 'next/link';
import { useMemo } from 'react';
import {
  ArrowRight,
  BookMarked,
  BookOpen,
  CheckCircle2,
  Clock,
  Flame,
  GraduationCap,
  ListChecks,
  PlayCircle,
  Sparkles,
  Target,
} from 'lucide-react';
import { courseApi, problemApi, progressApi, statisticsApi } from '@/lib/api';
import { STAGE_GROUP_LABEL } from '@/lib/constants';
import { cn, formatMinutes } from '@/lib/utils';
import { useFetch } from '@/hooks/useFetch';
import { useAuth } from '@/hooks/useAuth';
import { AuthGate } from '@/components/common/auth-gate';
import { PageContainer } from '@/components/layout/page-container';
import { EmptyState } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress, RingProgress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import { SectionTitle, StatCard } from '@/components/ui/stat-card';

/** 我的学习：继续学习入口 + 阶段进度 + 推荐练习。 */
function LearnContent(): React.ReactElement {
  const { user } = useAuth();

  const progress = useFetch(() => progressApi.overview(), []);
  const courses = useFetch(() => courseApi.list({ page: 1, page_size: 100 }), []);
  const recommend = useFetch(() => problemApi.recommend(6), []);
  const stats = useFetch(() => statisticsApi.overview(), []);

  const started = useMemo(() => {
    const list = courses.data?.items ?? [];
    return list
      .filter((course) => (course.progress_percent ?? 0) > 0)
      .sort((a, b) => (b.progress_percent ?? 0) - (a.progress_percent ?? 0));
  }, [courses.data]);

  const currentCourse = started[0] ?? courses.data?.items?.[0] ?? null;
  const overall = progress.data?.overall_percent ?? 0;

  return (
    <PageContainer
      title="我的学习"
      description={`继续你的 Python 之旅，${user?.display_name ?? user?.username ?? '同学'}。`}
      actions={
        <Button size="sm" asChild>
          <Link href="/editor">
            打开编辑器
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </Button>
      }
    >
      <div className="space-y-6">
        {/* 概览 */}
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            label="整体完成度"
            value={`${overall}%`}
            icon={<Target className="h-3.5 w-3.5" />}
            tone="primary"
            loading={progress.loading && !progress.data}
          />
          <StatCard
            label="已完成课时"
            value={`${progress.data?.completed_lessons ?? 0}`}
            hint={`共 ${progress.data?.total_lessons ?? 0} 课时`}
            icon={<CheckCircle2 className="h-3.5 w-3.5" />}
            tone="success"
            loading={progress.loading && !progress.data}
          />
          <StatCard
            label="当前阶段"
            value={`STAGE ${progress.data?.current_stage ?? 1}`}
            hint="按路线图顺序推进"
            icon={<GraduationCap className="h-3.5 w-3.5" />}
            loading={progress.loading && !progress.data}
          />
          <StatCard
            label="连续学习天数"
            value={`${stats.data?.streak_days ?? 0} 天`}
            hint="保持每日学习习惯"
            icon={<Flame className="h-3.5 w-3.5" />}
            tone="warning"
            loading={stats.loading && !stats.data}
          />
        </div>

        {/* 继续学习 */}
        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>继续学习</CardTitle>
            <Badge variant="accent" className="gap-1">
              <Sparkles className="h-3 w-3" />
              建议从这里开始
            </Badge>
          </CardHeader>
          <CardContent>
            {courses.loading && !courses.data ? (
              <Skeleton className="h-28 w-full" />
            ) : currentCourse ? (
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
                <RingProgress value={currentCourse.progress_percent ?? 0} size={76} />
                <div className="min-w-0 flex-1 space-y-1.5">
                  <p className="text-[15px] font-semibold">{currentCourse.title}</p>
                  <p className="line-clamp-2 text-[12.5px] text-muted-foreground">
                    {currentCourse.subtitle ?? '继续完成这个阶段的课时，解锁下一阶段。'}
                  </p>
                  <div className="flex flex-wrap items-center gap-3 pt-1 text-[11px] text-muted-foreground">
                    <span className="inline-flex items-center gap-1">
                      <BookOpen className="h-3 w-3" />
                      {currentCourse.lesson_count} 课时
                    </span>
                    <span className="inline-flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {currentCourse.estimated_hours} 小时
                    </span>
                    <Badge variant="secondary">{STAGE_GROUP_LABEL[currentCourse.level]}</Badge>
                  </div>
                </div>
                <Button asChild>
                  <Link href={`/courses/${currentCourse.slug}`}>
                    <PlayCircle className="h-4 w-4" />
                    继续学习
                  </Link>
                </Button>
              </div>
            ) : (
              <EmptyState
                icon={<BookOpen className="h-6 w-6" />}
                title="还没有学习中的课程"
                description="从阶段 1 开始，一步一步掌握 Python 主干知识。"
                action={
                  <Button size="sm" asChild>
                    <Link href="/courses">选择课程</Link>
                  </Button>
                }
                className="border-0 py-8"
              />
            )}
          </CardContent>
        </Card>

        {/* 阶段进度 */}
        <div>
          <SectionTitle title="阶段进度" description="点击任意阶段查看章节与课时。" />
          {courses.loading && !courses.data ? (
            <div className="grid gap-3 sm:grid-cols-2">
              {Array.from({ length: 6 }).map((_, index) => (
                <Skeleton key={index} className="h-24 w-full" />
              ))}
            </div>
          ) : courses.data && courses.data.items.length > 0 ? (
            <div className="grid gap-3 sm:grid-cols-2">
              {courses.data.items.map((course) => (
                <Link
                  key={course.id}
                  href={`/courses/${course.slug}`}
                  className="group rounded-lg border border-border bg-card p-4 transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-md"
                >
                  <div className="flex items-start gap-3">
                    <span
                      className={cn(
                        'flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-[13px] font-bold',
                        (course.progress_percent ?? 0) >= 100
                          ? 'bg-emerald-500/12 text-emerald-500'
                          : 'bg-primary/12 text-primary',
                      )}
                    >
                      {course.stage_no}
                    </span>
                    <div className="min-w-0 flex-1 space-y-1.5">
                      <p className="truncate text-[14px] font-semibold group-hover:text-primary">{course.title}</p>
                      <p className="line-clamp-1 text-[12px] text-muted-foreground">{course.subtitle}</p>
                      <Progress value={course.progress_percent ?? 0} size="sm" showValue />
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <EmptyState title="暂无课程数据" description="后端课程数据可能尚未导入。" />
          )}
        </div>

        {/* 推荐练习 */}
        <div>
          <SectionTitle
            title="为你推荐的练习"
            description="基于你的掌握度与偏好。"
            action={
              <Button variant="ghost" size="sm" asChild>
                <Link href="/problems">
                  全部题目
                  <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </Button>
            }
          />
          {recommend.loading && !recommend.data ? (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {Array.from({ length: 3 }).map((_, index) => (
                <Skeleton key={index} className="h-20 w-full" />
              ))}
            </div>
          ) : recommend.data && recommend.data.length > 0 ? (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {recommend.data.map((problem) => (
                <Link
                  key={problem.id}
                  href={`/problems/${problem.id}`}
                  className="flex items-center gap-3 rounded-lg border border-border bg-card p-3.5 transition-colors hover:border-primary/40"
                >
                  <ListChecks className="h-4 w-4 shrink-0 text-primary" />
                  <div className="min-w-0">
                    <p className="truncate text-[13px] font-medium">{problem.title}</p>
                    <p className="text-[11px] text-muted-foreground">
                      通过率 {Math.round((problem.acceptance_rate ?? 0) * 100)}%
                    </p>
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <EmptyState
              icon={<BookMarked className="h-6 w-6" />}
              title="暂无推荐"
              description="完成几道题后，这里会给出更贴合你水平的推荐。"
            />
          )}
        </div>
      </div>
    </PageContainer>
  );
}

export default function LearnPage(): React.ReactElement {
  return (
    <AuthGate title="登录后查看我的学习" description="学习进度、课时完成情况与个性化推荐都保存在你的账号下。">
      <LearnContent />
    </AuthGate>
  );
}
