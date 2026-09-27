'use client';

import Link from 'next/link';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  ArrowRight,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  FileText,
  ListChecks,
  PlayCircle,
  Play,
  Target,
} from 'lucide-react';
import { courseApi } from '@/lib/api';
import { DIFFICULTY_LABEL, STAGE_GROUP_LABEL } from '@/lib/constants';
import { cn } from '@/lib/utils';
import { useFetch } from '@/hooks/useFetch';
import { useAuth } from '@/hooks/useAuth';
import { useToaster } from '@/hooks/useToast';
import { PageContainer } from '@/components/layout/page-container';
import { Alert, EmptyState, ErrorState } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress, RingProgress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import type { LessonBrief } from '@/lib/types';

const LESSON_TYPE_LABEL: Record<string, string> = {
  concept: '概念',
  practice: '练习',
  quiz: '测验',
  project: '项目',
};

export interface CourseDetailViewProps {
  slug: string;
}

/** 课程详情：阶段大纲 + 章节课时 + 报名与进度。 */
export function CourseDetailView({ slug }: CourseDetailViewProps): React.ReactElement {
  const router = useRouter();
  const toaster = useToaster();
  const { isAuthenticated } = useAuth();
  const detail = useFetch(() => courseApi.detail(slug), [slug]);
  const [enrolling, setEnrolling] = useState(false);
  const [openChapters, setOpenChapters] = useState<Record<string, boolean>>({});

  const course = detail.data?.course;
  const chapters = detail.data?.chapters ?? [];
  /** 课程详情接口的 completed_lessons 是**完成数量**（整数），非 id 列表。 */
  const completedCount = detail.data?.progress?.completed_lessons ?? 0;
  const percent = detail.data?.progress?.percent ?? course?.progress_percent ?? 0;

  const isOpen = (id: string, index: number): boolean => openChapters[id] ?? index === 0;
  const toggle = (id: string, index: number): void => {
    setOpenChapters((prev) => ({ ...prev, [id]: !(prev[id] ?? index === 0) }));
  };

  const enroll = async (): Promise<void> => {
    if (!course) return;
    if (!isAuthenticated) {
      router.push(`/login?redirect=${encodeURIComponent(`/courses/${slug}`)}`);
      return;
    }
    setEnrolling(true);
    try {
      await courseApi.enroll(course.id);
      toaster.success('已加入学习', `开始你的「${course.title}」吧`);
      detail.refresh();
    } catch (error) {
      toaster.error('加入失败', error instanceof Error ? error.message : '请稍后再试');
    } finally {
      setEnrolling(false);
    }
  };

  if (detail.loading && !detail.data) {
    return (
      <PageContainer>
        <div className="space-y-4">
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      </PageContainer>
    );
  }

  if (detail.error && !detail.data) {
    return (
      <PageContainer title="课程详情">
        <ErrorState title="课程加载失败" description={detail.error} onRetry={detail.refresh} />
      </PageContainer>
    );
  }

  if (!course) {
    return (
      <PageContainer title="课程详情">
        <EmptyState icon={<BookOpen className="h-6 w-6" />} title="未找到该课程" description={`slug = ${slug}`} />
      </PageContainer>
    );
  }

  const nextLesson = chapters.flatMap((chapter) => chapter.lessons ?? [])[0] ?? null;

  return (
    <PageContainer>
      <div className="space-y-6">
        {/* 头部 */}
        <Card>
          <CardContent className="pt-5">
            <div className="flex flex-col gap-5 sm:flex-row sm:items-start">
              <div className="flex-1 space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="default">STAGE {String(course.stage_no).padStart(2, '0')}</Badge>
                  <Badge variant="secondary">{STAGE_GROUP_LABEL[course.level]}</Badge>
                  <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
                    <BookOpen className="h-3 w-3" />
                    {course.lesson_count} 课时
                  </span>
                  <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
                    <Clock className="h-3 w-3" />
                    约 {course.estimated_hours} 小时
                  </span>
                </div>

                <div className="space-y-2">
                  <h1 className="text-2xl font-semibold tracking-tight">{course.title}</h1>
                  <p className="text-[13.5px] text-muted-foreground">{course.subtitle ?? '本阶段暂无简介。'}</p>
                </div>

                {course.description_md ? (
                  <p className="line-clamp-3 text-[12.5px] leading-relaxed text-muted-foreground">{course.description_md}</p>
                ) : null}

                <div className="flex flex-wrap gap-2 pt-1">
                  {nextLesson ? (
                    <Button asChild>
                      <Link href={`/lesson/${nextLesson.id}`}>
                        <PlayCircle className="h-4 w-4" />
                        {percent > 0 ? '继续学习' : '开始学习'}
                      </Link>
                    </Button>
                  ) : null}
                  <Button variant="outline" loading={enrolling} onClick={() => void enroll()}>
                    <Target className="h-4 w-4" />
                    加入我的课程
                  </Button>
                </div>
              </div>

              <div className="flex shrink-0 flex-col items-center gap-2 sm:pt-2">
                <RingProgress value={percent} label={`${Math.round(percent)}%`} size={92} />
                <p className="text-[11px] text-muted-foreground">阶段完成度</p>
                <p className="text-[11px] text-muted-foreground">
                  已完成 {completedCount} / {course.lesson_count} 课时
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {!isAuthenticated ? (
          <Alert
            variant="info"
            title="登录后可记录学习进度"
            description="登录后完成的课时会自动同步，并计入连续学习天数与 XP。"
            action={
              <Button size="sm" variant="outline" asChild>
                <Link href={`/login?redirect=${encodeURIComponent(`/courses/${slug}`)}`}>登录</Link>
              </Button>
            }
          />
        ) : null}

        {/* 章节大纲 */}
        <div className="grid gap-5 lg:grid-cols-[1.6fr_1fr]">
          <div className="space-y-3">
            <h2 className="text-[15px] font-semibold">章节目录</h2>
            {chapters.length === 0 ? (
              <EmptyState
                icon={<FileText className="h-6 w-6" />}
                title="该阶段还没有章节内容"
                description="内容可能还在录入中，稍后再来看看。"
              />
            ) : (
              chapters.map((chapter, index) => (
                <div key={chapter.id} className="overflow-hidden rounded-lg border border-border bg-card">
                  <button
                    type="button"
                    onClick={() => toggle(chapter.id, index)}
                    className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-muted/50"
                  >
                    {isOpen(chapter.id, index) ? (
                      <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
                    ) : (
                      <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                    )}
                    <span className="text-[13.5px] font-medium">{chapter.title}</span>
                    <span className="ml-auto text-[11px] text-muted-foreground">
                      {chapter.lessons?.length ?? chapter.lesson_count} 课时
                    </span>
                  </button>

                  {isOpen(chapter.id, index) ? (
                    <div className="border-t border-border">
                      {chapter.summary_md ? (
                        <p className="border-b border-border bg-muted/25 px-4 py-2.5 text-[12px] text-muted-foreground">
                          {chapter.summary_md}
                        </p>
                      ) : null}
                      {(chapter.lessons ?? []).length === 0 ? (
                        <p className="px-4 py-3 text-[12px] text-muted-foreground">本章暂无课时。</p>
                      ) : (
                        (chapter.lessons ?? []).map((lesson: LessonBrief) => {
                          const done = lesson.status === 'completed' || lesson.progress_percent >= 100;
                          return (
                            <Link
                              key={lesson.id}
                              href={`/lesson/${lesson.id}`}
                              className="flex items-center gap-3 border-b border-border px-4 py-2.5 transition-colors last:border-0 hover:bg-muted/45"
                            >
                              <span
                                className={cn(
                                  'flex h-5 w-5 shrink-0 items-center justify-center rounded-full border',
                                  done
                                    ? 'border-emerald-500/35 bg-emerald-500/12 text-emerald-500'
                                    : 'border-border text-muted-foreground',
                                )}
                              >
                                {done ? <CheckCircle2 className="h-3 w-3" /> : <Play className="h-2.5 w-2.5" />}
                              </span>
                              <span className="min-w-0 flex-1 truncate text-[13px]">{lesson.title}</span>
                              <Badge variant="outline">{LESSON_TYPE_LABEL[lesson.lesson_type] ?? '课时'}</Badge>
                              <span className="hidden text-[11px] text-muted-foreground sm:inline">
                                {DIFFICULTY_LABEL[lesson.difficulty]} · {lesson.estimated_minutes} 分钟
                              </span>
                            </Link>
                          );
                        })
                      )}
                    </div>
                  ) : null}
                </div>
              ))
            )}
          </div>

          {/* 侧栏信息 */}
          <div className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>阶段信息</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-[12.5px]">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">难度</span>
                  <Badge variant="secondary">{STAGE_GROUP_LABEL[course.level]}</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">课时数</span>
                  <span>{course.lesson_count}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">预计学时</span>
                  <span>{course.estimated_hours} 小时</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">我的进度</span>
                  <span>{Math.round(percent)}%</span>
                </div>
                <Progress value={percent} size="sm" />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>学完这个阶段，你能够</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-[12.5px] text-muted-foreground">
                <p className="flex items-start gap-2">
                  <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" />
                  掌握本阶段全部语法要点与常见写法
                </p>
                <p className="flex items-start gap-2">
                  <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" />
                  独立完成配套练习与随堂测验
                </p>
                <p className="flex items-start gap-2">
                  <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" />
                  用代码实现一个可运行的小程序
                </p>
                <Button variant="outline" size="sm" className="mt-2 w-full" asChild>
                  <Link href="/problems">
                    <ListChecks className="h-3.5 w-3.5" />
                    去刷相关题目
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                </Button>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </PageContainer>
  );
}
