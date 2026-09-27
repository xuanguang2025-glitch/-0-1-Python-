'use client';

import Link from 'next/link';
import { useState } from 'react';
import { Bell, CheckCheck, Info, Megaphone, Trash2 } from 'lucide-react';
import { notificationApi } from '@/lib/api';
import { cn, formatRelativeTime } from '@/lib/utils';
import { useFetch } from '@/hooks/useFetch';
import { useToaster } from '@/hooks/useToast';
import { AuthGate } from '@/components/common/auth-gate';
import { PageContainer } from '@/components/layout/page-container';
import { EmptyState, ErrorState } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { StatCard } from '@/components/ui/stat-card';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import type { NotificationType } from '@/lib/types';

const TYPE_LABEL: Record<NotificationType, string> = {
  system: '系统',
  achievement: '成就',
  daily: '每日',
  challenge: '挑战',
  ai: 'AI',
  admin: '管理',
};

/** 通知中心：全部 / 未读 筛选 + 公告。 */
function NotificationsContent(): React.ReactElement {
  const toaster = useToaster();
  const [filter, setFilter] = useState<'all' | 'unread'>('all');
  const [page, setPage] = useState(1);

  const list = useFetch(
    () => notificationApi.list({ is_read: filter === 'unread' ? false : undefined, page, page_size: 20 }),
    [filter, page],
  );
  const unread = useFetch(() => notificationApi.unreadCount(), []);
  const announcements = useFetch(() => notificationApi.announcements(5), []);

  const items = list.data?.items ?? [];

  const markRead = async (id: string): Promise<void> => {
    try {
      await notificationApi.read(id);
      list.refresh();
      unread.refresh();
    } catch (error) {
      toaster.error('操作失败', error instanceof Error ? error.message : '请稍后再试');
    }
  };

  const markAllRead = async (): Promise<void> => {
    try {
      const result = await notificationApi.readAll();
      toaster.success(`已标记 ${result.updated} 条为已读`);
      list.refresh();
      unread.refresh();
    } catch (error) {
      toaster.error('操作失败', error instanceof Error ? error.message : '请稍后再试');
    }
  };

  const remove = async (id: string): Promise<void> => {
    try {
      await notificationApi.remove(id);
      list.refresh();
      unread.refresh();
    } catch (error) {
      toaster.error('删除失败', error instanceof Error ? error.message : '请稍后再试');
    }
  };

  return (
    <PageContainer
      title="通知中心"
      description="系统消息、成就解锁、复习提醒与挑战通知都在这里。"
      actions={
        <Button size="sm" variant="outline" onClick={() => void markAllRead()}>
          <CheckCheck className="h-3.5 w-3.5" />
          全部标为已读
        </Button>
      }
    >
      <div className="space-y-6">
        <div className="grid gap-3 sm:grid-cols-3">
          <StatCard label="未读通知" value={unread.data?.count ?? 0} tone="primary" icon={<Bell className="h-3.5 w-3.5" />} loading={unread.loading && !unread.data} />
          <StatCard label="通知总数" value={list.data?.total ?? 0} icon={<Megaphone className="h-3.5 w-3.5" />} loading={list.loading && !list.data} />
          <StatCard label="平台公告" value={announcements.data?.length ?? 0} tone="accent" icon={<Info className="h-3.5 w-3.5" />} loading={announcements.loading && !announcements.data} />
        </div>

        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_300px]">
          <div className="space-y-3">
            <Tabs
              value={filter}
              onValueChange={(value) => {
                setFilter(value as 'all' | 'unread');
                setPage(1);
              }}
            >
              <TabsList>
                <TabsTrigger value="all">全部</TabsTrigger>
                <TabsTrigger value="unread">
                  未读
                  {unread.data && unread.data.count > 0 ? (
                    <span className="ml-1 rounded-full bg-destructive px-1.5 text-[10px] text-destructive-foreground">
                      {unread.data.count}
                    </span>
                  ) : null}
                </TabsTrigger>
              </TabsList>
            </Tabs>

            {list.loading && !list.data ? (
              <div className="space-y-2">
                {Array.from({ length: 5 }).map((_, index) => (
                  <Skeleton key={index} className="h-16 w-full" />
                ))}
              </div>
            ) : list.error && !list.data ? (
              <ErrorState title="通知加载失败" description={list.error} onRetry={list.refresh} />
            ) : items.length === 0 ? (
              <EmptyState
                icon={<Bell className="h-6 w-6" />}
                title={filter === 'unread' ? '没有未读通知' : '暂时没有通知'}
                description="有新消息时会显示在这里，也会在顶部铃铛上提示。"
              />
            ) : (
              items.map((item) => (
                <Card key={item.id} className={cn('p-4', !item.is_read && 'border-primary/35 bg-primary/5')}>
                  <div className="flex items-start gap-3">
                    <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
                      <Bell className="h-3.5 w-3.5" />
                    </span>
                    <div className="min-w-0 flex-1 space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-[13.5px] font-medium">{item.title}</p>
                        <Badge variant="secondary">{TYPE_LABEL[item.type] ?? item.type}</Badge>
                        {!item.is_read ? <Badge variant="default">未读</Badge> : null}
                      </div>
                      {item.content_md ? <p className="text-[12.5px] text-muted-foreground">{item.content_md}</p> : null}
                      <p className="text-[11px] text-muted-foreground">{formatRelativeTime(item.created_at)}</p>
                      {item.link_url ? (
                        <Link href={item.link_url} className="inline-block text-[12px] text-primary hover:underline">
                          查看详情 →
                        </Link>
                      ) : null}
                    </div>
                    <div className="flex shrink-0 items-center gap-1">
                      {!item.is_read ? (
                        <Button size="sm" variant="ghost" onClick={() => void markRead(item.id)}>
                          标为已读
                        </Button>
                      ) : null}
                      <Button size="icon-sm" variant="ghost" aria-label="删除通知" onClick={() => void remove(item.id)}>
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                </Card>
              ))
            )}
          </div>

          {/* 公告 */}
          <aside>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-1.5">
                  <Megaphone className="h-4 w-4 text-primary" />
                  平台公告
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {announcements.loading && !announcements.data ? (
                  <Skeleton className="h-32 w-full" />
                ) : announcements.data && announcements.data.length > 0 ? (
                  announcements.data.map((item) => (
                    <div key={item.id} className="rounded-lg border border-border p-3">
                      <div className="flex items-center gap-2">
                        <p className="text-[12.5px] font-medium">{item.title}</p>
                        {item.is_pinned ? <Badge variant="accent">置顶</Badge> : null}
                      </div>
                      <p className="mt-1 line-clamp-3 text-[11.5px] text-muted-foreground">{item.content_md}</p>
                      <p className="mt-1.5 text-[10.5px] text-muted-foreground">{formatRelativeTime(item.published_at)}</p>
                    </div>
                  ))
                ) : (
                  <p className="py-4 text-center text-[12px] text-muted-foreground">暂无公告</p>
                )}
              </CardContent>
            </Card>
          </aside>
        </div>
      </div>
    </PageContainer>
  );
}

export default function NotificationsPage(): React.ReactElement {
  return (
    <AuthGate title="登录后查看通知" description="通知与公告需要登录后才能查看。">
      <NotificationsContent />
    </AuthGate>
  );
}
