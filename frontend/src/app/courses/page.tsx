'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';
import { BookOpen, ChevronLeft, ChevronRight, Clock, Filter, GraduationCap, Search } from 'lucide-react';
import { courseApi } from '@/lib/api';
import { STAGE_GROUP_LABEL } from '@/lib/constants';
import { cn } from '@/lib/utils';
import { useDebounce } from '@/hooks/useDebounce';
import { useFetch } from '@/hooks/useFetch';
import { AuthGate } from '@/components/common/auth-gate';
import { PageContainer } from '@/components/layout/page-container';
import { EmptyState, ErrorState } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import { Select } from '@/components/ui/select';
import type { CourseLevel } from '@/lib/types';

const LEVEL_OPTIONS = [
  { value: '', label: '全部难度' },
  { value: 'beginner', label: '基础语法' },
  { value: 'intermediate', label: '进阶能力' },
  { value: 'advanced', label: '工程实战' },
];

const LEVEL_BADGE: Record<CourseLevel, 'success' | 'default' | 'accent'> = {
  beginner: 'success',
  intermediate: 'default',
  advanced: 'accent',
};

const PAGE_SIZE = 12;

/** 课程列表：难度筛选 + 关键词 + 分页。 */
function CoursesContent(): React.ReactElement {
  const [level, setLevel] = useState('');
  const [keyword, setKeyword] = useState('');
  const [page, setPage] = useState(1);
  const debouncedKeyword = useDebounce(keyword, 300);

  const request = useFetch(
    () => courseApi.list({ level: level || undefined, page, page_size: PAGE_SIZE }),
    [level, page],
  );

  const items = useMemo(() => {
    const list = request.data?.items ?? [];
    const word = debouncedKeyword.trim().toLowerCase();
    if (!word) return list;
    return list.filter(
      (course) =>
        course.title.toLowerCase().includes(word) ||
        (course.subtitle ?? '').toLowerCase().includes(word) ||
        course.slug.includes(word),
    );
  }, [request.data, debouncedKeyword]);

  const totalPages = request.data?.pages ?? 1;

  return (
    <PageContainer
      title="全部课程"
      description="18 个阶段，从 Python 基础语法一路走到工程化实战。"
      actions={
        <Badge variant="secondary" className="gap-1">
          <GraduationCap className="h-3 w-3" />
          共 {request.data?.total ?? 18} 个阶段
        </Badge>
      }
    >
      <div className="space-y-5">
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-card p-3">
          <div className="w-48">
            <Input
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              placeholder="按标题筛选"
              icon={<Search className="h-3.5 w-3.5" />}
            />
          </div>
          <div className="flex items-center gap-2">
            <Filter className="h-3.5 w-3.5 text-muted-foreground" />
            <div className="w-36">
              <Select
                value={level}
                options={LEVEL_OPTIONS}
                onChange={(event) => {
                  setLevel(event.target.value);
                  setPage(1);
                }}
              />
            </div>
          </div>
          <div className="ml-auto flex flex-wrap gap-1.5">
            {(Object.keys(STAGE_GROUP_LABEL) as CourseLevel[]).map((group) => (
              <button
                key={group}
                type="button"
                onClick={() => {
                  setLevel(level === group ? '' : group);
                  setPage(1);
                }}
                className={cn(
                  'rounded-full border px-2.5 py-1 text-[11px] transition-colors',
                  level === group
                    ? 'border-primary/40 bg-primary/12 text-primary'
                    : 'border-border text-muted-foreground hover:bg-muted',
                )}
              >
                {STAGE_GROUP_LABEL[group]}
              </button>
            ))}
          </div>
        </div>

        {request.loading && !request.data ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, index) => (
              <Skeleton key={index} className="h-40 w-full" />
            ))}
          </div>
        ) : request.error && !request.data ? (
          <ErrorState title="课程列表加载失败" description={request.error} onRetry={request.refresh} />
        ) : items.length === 0 ? (
          <EmptyState
            icon={<BookOpen className="h-6 w-6" />}
            title="没有匹配的课程"
            description="换个关键词或清除筛选条件再试试。"
            action={
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setKeyword('');
                  setLevel('');
                  setPage(1);
                }}
              >
                清除筛选
              </Button>
            }
          />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {items.map((course) => (
              <Card key={course.id} interactive className="flex h-full flex-col">
                <CardContent className="flex flex-1 flex-col gap-3 pt-5">
                  <div className="flex items-start justify-between gap-3">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/12 text-[14px] font-bold text-primary">
                      {course.stage_no}
                    </span>
                    <Badge variant={LEVEL_BADGE[course.level]}>{STAGE_GROUP_LABEL[course.level]}</Badge>
                  </div>

                  <div className="space-y-1.5">
                    <h3 className="text-[15px] font-semibold leading-tight">{course.title}</h3>
                    <p className="line-clamp-2 text-[12.5px] leading-relaxed text-muted-foreground">
                      {course.subtitle ?? course.description_md ?? '暂无简介'}
                    </p>
                  </div>

                  <div className="mt-auto space-y-3">
                    <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
                      <span className="inline-flex items-center gap-1">
                        <BookOpen className="h-3 w-3" />
                        {course.lesson_count} 课时
                      </span>
                      <span className="inline-flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {course.estimated_hours} 小时
                      </span>
                    </div>

                    {typeof course.progress_percent === 'number' ? (
                      <Progress value={course.progress_percent} size="sm" showValue />
                    ) : null}

                    <Button variant="outline" size="sm" className="w-full" asChild>
                      <Link href={`/courses/${course.slug}`}>查看阶段内容</Link>
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {totalPages > 1 ? (
          <div className="flex items-center justify-center gap-3">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((prev) => Math.max(1, prev - 1))}>
              <ChevronLeft className="h-3.5 w-3.5" />
              上一页
            </Button>
            <span className="text-[12px] text-muted-foreground">
              第 {page} / {totalPages} 页
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))}
            >
              下一页
              <ChevronRight className="h-3.5 w-3.5" />
            </Button>
          </div>
        ) : null}
      </div>
    </PageContainer>
  );
}

export default function CoursesPage(): React.ReactElement {
  // 未登录也可浏览课程，仅进度信息需要登录
  return (
    <AuthGate title="登录后查看学习进度" description="课程列表对所有人开放，登录后还能看到每个阶段的完成度。">
      <CoursesContent />
    </AuthGate>
  );
}
