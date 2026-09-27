'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';
import { AlertTriangle, BookX, CheckCircle2, RefreshCw, Trash2 } from 'lucide-react';
import { mistakeApi } from '@/lib/api';
import { cn, formatRelativeTime } from '@/lib/utils';
import { useFetch } from '@/hooks/useFetch';
import { useToaster } from '@/hooks/useToast';
import { AuthGate } from '@/components/common/auth-gate';
import { PageContainer } from '@/components/layout/page-container';
import { EmptyState, ErrorState } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { StatCard } from '@/components/ui/stat-card';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';

const RESOLVED_OPTIONS = [
  { value: '', label: '全部错题' },
  { value: 'false', label: '待复习' },
  { value: 'true', label: '已掌握' },
];

/** 错题本：错题列表 + 复习队列（间隔重复）。 */
function WrongAnswersContent(): React.ReactElement {
  const toaster = useToaster();
  const [resolved, setResolved] = useState('');
  const [page, setPage] = useState(1);

  const list = useFetch(
    () => mistakeApi.list({ resolved: resolved || undefined, page, page_size: 20 }),
    [resolved, page],
  );
  const queue = useFetch(() => mistakeApi.reviewQueue(10), []);

  const items = list.data?.items ?? [];
  const pending = useMemo(() => items.filter((item) => !item.resolved).length, [items]);

  const toggleResolve = async (id: string, next: boolean): Promise<void> => {
    try {
      await mistakeApi.resolve(id, next);
      list.refresh();
      queue.refresh();
      toaster.success(next ? '已标记为掌握' : '已加入复习队列');
    } catch (error) {
      toaster.error('操作失败', error instanceof Error ? error.message : '请稍后再试');
    }
  };

  const remove = async (id: string): Promise<void> => {
    try {
      await mistakeApi.remove(id);
      list.refresh();
      queue.refresh();
      toaster.success('已删除');
    } catch (error) {
      toaster.error('删除失败', error instanceof Error ? error.message : '请稍后再试');
    }
  };

  return (
    <PageContainer title="错题本" description="把错的题变成会的题 —— 按间隔重复自动安排复习。">
      <div className="space-y-6">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="错题总数" value={list.data?.total ?? 0} icon={<BookX className="h-3.5 w-3.5" />} loading={list.loading && !list.data} />
          <StatCard label="待复习" value={pending} tone="warning" icon={<AlertTriangle className="h-3.5 w-3.5" />} loading={list.loading && !list.data} />
          <StatCard label="今日复习队列" value={queue.data?.length ?? 0} tone="primary" icon={<RefreshCw className="h-3.5 w-3.5" />} loading={queue.loading && !queue.data} />
          <StatCard
            label="已掌握"
            value={items.filter((item) => item.resolved).length}
            tone="success"
            icon={<CheckCircle2 className="h-3.5 w-3.5" />}
            loading={list.loading && !list.data}
          />
        </div>

        {/* 复习队列 */}
        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>今日复习队列</CardTitle>
            <Button size="sm" variant="ghost" onClick={queue.refresh}>
              <RefreshCw className="h-3.5 w-3.5" />
              刷新
            </Button>
          </CardHeader>
          <CardContent className="space-y-2">
            {queue.loading && !queue.data ? (
              <Skeleton className="h-20 w-full" />
            ) : queue.data && queue.data.length > 0 ? (
              queue.data.map((item) => (
                <div key={item.id} className="flex flex-wrap items-center gap-3 rounded-lg border border-border p-3">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13px] font-medium">{item.title}</p>
                    <p className="text-[11.5px] text-muted-foreground">
                      {item.error_type ?? '未分类'} · 已复习 {item.review_count} 次 · 下次复习{' '}
                      {item.next_review_at ? formatRelativeTime(item.next_review_at) : '待安排'}
                    </p>
                  </div>
                  <Button size="sm" variant="outline" onClick={() => void toggleResolve(item.id, true)}>
                    我掌握了
                  </Button>
                  {item.problem_id ? (
                    <Button size="sm" asChild>
                      <Link href={`/problems/${item.problem_id}`}>重做一遍</Link>
                    </Button>
                  ) : null}
                </div>
              ))
            ) : (
              <EmptyState
                title="今日没有需要复习的错题"
                description="做题时出错的题目会自动进入错题本。"
                className="border-0 py-8"
              />
            )}
          </CardContent>
        </Card>

        {/* 错题列表 */}
        <div>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-[15px] font-semibold">全部错题</h2>
            <div className="w-36">
              <Select
                controlSize="sm"
                value={resolved}
                options={RESOLVED_OPTIONS}
                onChange={(event) => {
                  setResolved(event.target.value);
                  setPage(1);
                }}
              />
            </div>
          </div>

          {list.loading && !list.data ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, index) => (
                <Skeleton key={index} className="h-20 w-full" />
              ))}
            </div>
          ) : list.error && !list.data ? (
            <ErrorState title="错题加载失败" description={list.error} onRetry={list.refresh} />
          ) : items.length === 0 ? (
            <EmptyState
              icon={<BookX className="h-6 w-6" />}
              title="错题本还是空的"
              description="提交判题未通过的题目会自动收集到这里。"
              action={
                <Button size="sm" asChild>
                  <Link href="/problems">去刷题</Link>
                </Button>
              }
            />
          ) : (
            <div className="space-y-2">
              {items.map((item) => (
                <Card key={item.id} className={cn('p-4', item.resolved && 'opacity-75')}>
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 flex-1 space-y-1.5">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-[13.5px] font-medium">{item.title}</p>
                        {item.resolved ? (
                          <Badge variant="success">已掌握</Badge>
                        ) : (
                          <Badge variant="warning">待复习</Badge>
                        )}
                        {item.error_type ? <Badge variant="secondary">{item.error_type}</Badge> : null}
                      </div>
                      {item.note_md ? (
                        <p className="line-clamp-2 text-[12px] text-muted-foreground">{item.note_md}</p>
                      ) : null}
                      <p className="text-[11px] text-muted-foreground">
                        收录于 {formatRelativeTime(item.created_at)} · 复习 {item.review_count} 次
                      </p>
                    </div>

                    <div className="flex shrink-0 items-center gap-1.5">
                      {item.problem_id ? (
                        <Button size="sm" variant="outline" asChild>
                          <Link href={`/problems/${item.problem_id}`}>重做</Link>
                        </Button>
                      ) : null}
                      <Button size="sm" variant="ghost" onClick={() => void toggleResolve(item.id, !item.resolved)}>
                        {item.resolved ? '恢复待复习' : '标记掌握'}
                      </Button>
                      <Button size="icon-sm" variant="ghost" aria-label="删除错题" onClick={() => void remove(item.id)}>
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>
      </div>
    </PageContainer>
  );
}

export default function WrongAnswersPage(): React.ReactElement {
  return (
    <AuthGate title="登录后查看错题本" description="错题本会根据你的判题结果自动收集错题并安排复习。">
      <WrongAnswersContent />
    </AuthGate>
  );
}
