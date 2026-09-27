'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { MessageCircle, Megaphone, Sparkles, ThumbsUp, Users } from 'lucide-react';
import { notificationApi } from '@/lib/api';
import { formatRelativeTime } from '@/lib/utils';
import { useFetch } from '@/hooks/useFetch';
import { useAuth } from '@/hooks/useAuth';
import { useToast } from '@/hooks/useToast';
import { PageContainer } from '@/components/layout/page-container';
import { Alert, EmptyState } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { StatCard } from '@/components/ui/stat-card';
import { Field, Textarea } from '@/components/ui/input';

interface LocalPost {
  id: string;
  author: string;
  content: string;
  createdAt: string;
  likes: number;
}

const STORAGE_KEY = 'community.posts';

const TOPICS = [
  { title: '新手提问区', desc: '语法、报错、环境问题都可以问', count: 0 },
  { title: '题目讨论', desc: '分享解法思路与踩坑记录', count: 0 },
  { title: '项目晒作品', desc: '展示你完成的项目，获取反馈', count: 0 },
  { title: '学习打卡', desc: '记录每天的进度，互相监督', count: 0 },
];

/** 学习社区：公告 + 讨论区（本地草稿，后端社区接口未在本期契约内）。 */
export default function CommunityPage(): React.ReactElement {
  const toast = useToast();
  const { user } = useAuth();
  const announcements = useFetch(() => notificationApi.announcements(5), []);
  const [posts, setPosts] = useState<LocalPost[]>([]);
  const [draft, setDraft] = useState('');

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem('pythonlab:community.posts');
      if (raw) setPosts(JSON.parse(raw) as LocalPost[]);
    } catch {
      setPosts([]);
    }
  }, []);

  const persist = (next: LocalPost[]): void => {
    setPosts(next);
    try {
      window.localStorage.setItem('pythonlab:community.posts', JSON.stringify(next));
    } catch {
      /* 忽略存储失败 */
    }
  };

  const publish = (): void => {
    if (!draft.trim()) {
      toast({ title: '内容不能为空', variant: 'warning' });
      return;
    }
    const post: LocalPost = {
      id: `p-${Date.now()}`,
      author: user?.display_name ?? user?.username ?? '匿名学习者',
      content: draft.trim(),
      createdAt: new Date().toISOString(),
      likes: 0,
    };
    persist([post, ...posts]);
    setDraft('');
    toast({ title: '已发布到本地草稿箱', description: '社区服务上线后将自动同步', variant: 'success' });
  };

  const like = (id: string): void => {
    persist(posts.map((post) => (post.id === id ? { ...post, likes: post.likes + 1 } : post)));
  };

  const remove = (id: string): void => {
    persist(posts.filter((post) => post.id !== id));
  };

  return (
    <PageContainer title="学习社区" description="提问、讨论、晒作品，一个人学不如一群人学。">
      <div className="space-y-6">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="我的帖子" value={posts.length} icon={<MessageCircle className="h-3.5 w-3.5" />} tone="primary" />
          <StatCard label="获得点赞" value={posts.reduce((sum, post) => sum + post.likes, 0)} icon={<ThumbsUp className="h-3.5 w-3.5" />} tone="accent" />
          <StatCard label="讨论板块" value={TOPICS.length} icon={<Users className="h-3.5 w-3.5" />} />
          <StatCard label="平台公告" value={announcements.data?.length ?? 0} icon={<Megaphone className="h-3.5 w-3.5" />} loading={announcements.loading && !announcements.data} />
        </div>

        <Alert
          variant="info"
          title="社区服务建设中"
          description="目前帖子保存在本机浏览器。服务端社区接口上线后会自动同步，届时可跨设备查看与回复。"
        />

        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_300px]">
          <div className="space-y-4">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-1.5">
                  <Sparkles className="h-4 w-4 text-accent" />
                  发布新帖
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <Field label="内容" hint="可以贴代码、报错信息或学习心得">
                  <Textarea
                    rows={4}
                    value={draft}
                    onChange={(event) => setDraft(event.target.value)}
                    placeholder="例如：为什么 print(sum([])) 输出 0，而 max([]) 会报错？"
                  />
                </Field>
                <div className="flex justify-end">
                  <Button onClick={publish}>发布</Button>
                </div>
              </CardContent>
            </Card>

            {posts.length === 0 ? (
              <EmptyState
                icon={<MessageCircle className="h-6 w-6" />}
                title="还没有帖子"
                description="写下你的第一个问题或心得吧。"
              />
            ) : (
              <div className="space-y-3">
                {posts.map((post) => (
                  <Card key={post.id} className="p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 space-y-1.5">
                        <div className="flex items-center gap-2">
                          <p className="text-[13px] font-medium">{post.author}</p>
                          <span className="text-[11px] text-muted-foreground">{formatRelativeTime(post.createdAt)}</span>
                        </div>
                        <p className="whitespace-pre-wrap text-[12.5px] leading-relaxed text-muted-foreground">{post.content}</p>
                      </div>
                      <div className="flex shrink-0 items-center gap-1">
                        <Button size="sm" variant="ghost" onClick={() => like(post.id)}>
                          <ThumbsUp className="h-3.5 w-3.5" />
                          {post.likes}
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => remove(post.id)}>
                          删除
                        </Button>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </div>

          <aside className="space-y-4">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-1.5">
                  <Megaphone className="h-4 w-4 text-primary" />
                  最新公告
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {announcements.loading && !announcements.data ? (
                  <Skeleton className="h-24 w-full" />
                ) : announcements.data && announcements.data.length > 0 ? (
                  announcements.data.map((item) => (
                    <div key={item.id} className="rounded-lg border border-border p-3">
                      <p className="text-[12.5px] font-medium">{item.title}</p>
                      <p className="mt-1 line-clamp-2 text-[11.5px] text-muted-foreground">{item.content_md}</p>
                    </div>
                  ))
                ) : (
                  <p className="py-3 text-center text-[12px] text-muted-foreground">暂无公告</p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle>讨论板块</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {TOPICS.map((topic) => (
                  <div key={topic.title} className="rounded-lg border border-border p-3">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-[12.5px] font-medium">{topic.title}</p>
                      <Badge variant="secondary">{topic.count}</Badge>
                    </div>
                    <p className="mt-0.5 text-[11px] text-muted-foreground">{topic.desc}</p>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Button variant="outline" className="w-full" asChild>
              <Link href="/ai-tutor">
                <Sparkles className="h-3.5 w-3.5" />
                问题太急？试试 AI 导师
              </Link>
            </Button>
          </aside>
        </div>
      </div>
    </PageContainer>
  );
}
