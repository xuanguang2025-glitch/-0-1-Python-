'use client';

import Link from 'next/link';
import { useState } from 'react';
import { Bookmark, BookmarkPlus, FolderOpen, Trash2 } from 'lucide-react';
import { bookmarkApi } from '@/lib/api';
import { cn, formatRelativeTime } from '@/lib/utils';
import { useFetch } from '@/hooks/useFetch';
import { useToaster } from '@/hooks/useToast';
import { AuthGate } from '@/components/common/auth-gate';
import { CodeBlock } from '@/components/code/code-block';
import { PageContainer } from '@/components/layout/page-container';
import { EmptyState, ErrorState } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Field, Input } from '@/components/ui/input';
import { Modal } from '@/components/ui/modal';
import { Select } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';

const KIND_OPTIONS = [
  { value: '', label: '全部类型' },
  { value: 'problem', label: '题目' },
  { value: 'lesson', label: '课时' },
  { value: 'project', label: '项目' },
  { value: 'snippet', label: '代码片段' },
];

const KIND_LABEL: Record<string, string> = {
  problem: '题目',
  lesson: '课时',
  project: '项目',
  snippet: '代码片段',
};

/** 收藏夹：收藏列表 + 分类集合 + 新建收藏。 */
function BookmarksContent(): React.ReactElement {
  const toaster = useToaster();
  const [kind, setKind] = useState('');
  const [collection, setCollection] = useState('');
  const [page, setPage] = useState(1);
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState({ title: '', collection: '', code_snippet: '', tags: '' });

  const list = useFetch(
    () => bookmarkApi.list({ kind: kind || undefined, collection: collection || undefined, page, page_size: 20 }),
    [kind, collection, page],
  );
  const collections = useFetch(() => bookmarkApi.collections(), []);

  const create = async (): Promise<void> => {
    if (!form.title.trim()) {
      toaster.error('请填写收藏标题');
      return;
    }
    try {
      await bookmarkApi.create({
        kind: form.code_snippet ? 'snippet' : 'problem',
        title: form.title.trim(),
        collection: form.collection.trim() || undefined,
        code_snippet: form.code_snippet || undefined,
        tags: form.tags ? form.tags.split(',').map((tag) => tag.trim()).filter(Boolean) : undefined,
      });
      toaster.success('已收藏');
      setCreateOpen(false);
      setForm({ title: '', collection: '', code_snippet: '', tags: '' });
      list.refresh();
      collections.refresh();
    } catch (error) {
      toaster.error('收藏失败', error instanceof Error ? error.message : '请稍后再试');
    }
  };

  const remove = async (id: string): Promise<void> => {
    try {
      await bookmarkApi.remove(id);
      list.refresh();
      collections.refresh();
      toaster.success('已移除收藏');
    } catch (error) {
      toaster.error('移除失败', error instanceof Error ? error.message : '请稍后再试');
    }
  };

  const items = list.data?.items ?? [];

  return (
    <PageContainer
      title="我的收藏"
      description="收藏题目、课时与代码片段，随时回看。"
      actions={
        <Button size="sm" onClick={() => setCreateOpen(true)}>
          <BookmarkPlus className="h-3.5 w-3.5" />
          新建收藏
        </Button>
      }
    >
      <div className="grid gap-5 lg:grid-cols-[220px_minmax(0,1fr)]">
        {/* 集合 */}
        <aside className="space-y-3">
          <Card>
            <CardContent className="space-y-1 pt-5">
              <button
                type="button"
                onClick={() => {
                  setCollection('');
                  setPage(1);
                }}
                className={cn(
                  'flex w-full items-center justify-between rounded-md px-2.5 py-2 text-left text-[12.5px] transition-colors',
                  collection === '' ? 'bg-primary/12 text-primary' : 'hover:bg-muted',
                )}
              >
                <span className="inline-flex items-center gap-1.5">
                  <FolderOpen className="h-3.5 w-3.5" />
                  全部收藏
                </span>
                <span className="text-[11px] text-muted-foreground">{list.data?.total ?? 0}</span>
              </button>
              {(collections.data?.collections ?? []).map((item) => (
                <button
                  key={item.name}
                  type="button"
                  onClick={() => {
                    setCollection(item.name);
                    setPage(1);
                  }}
                  className={cn(
                    'flex w-full items-center justify-between rounded-md px-2.5 py-2 text-left text-[12.5px] transition-colors',
                    collection === item.name ? 'bg-primary/12 text-primary' : 'hover:bg-muted',
                  )}
                >
                  <span className="truncate">{item.name}</span>
                  <span className="text-[11px] text-muted-foreground">{item.count}</span>
                </button>
              ))}
            </CardContent>
          </Card>
        </aside>

        {/* 列表 */}
        <main className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <Tabs
              value={kind}
              onValueChange={(value) => {
                setKind(value);
                setPage(1);
              }}
            >
              <TabsList>
                <TabsTrigger value="">全部</TabsTrigger>
                <TabsTrigger value="problem">题目</TabsTrigger>
                <TabsTrigger value="lesson">课时</TabsTrigger>
                <TabsTrigger value="snippet">代码</TabsTrigger>
              </TabsList>
            </Tabs>
            <div className="ml-auto w-40">
              <Select
                controlSize="sm"
                value={kind}
                options={KIND_OPTIONS}
                onChange={(event) => {
                  setKind(event.target.value);
                  setPage(1);
                }}
              />
            </div>
          </div>

          {list.loading && !list.data ? (
            <div className="space-y-2">
              {Array.from({ length: 4 }).map((_, index) => (
                <Skeleton key={index} className="h-24 w-full" />
              ))}
            </div>
          ) : list.error && !list.data ? (
            <ErrorState title="收藏加载失败" description={list.error} onRetry={list.refresh} />
          ) : items.length === 0 ? (
            <EmptyState
              icon={<Bookmark className="h-6 w-6" />}
              title="还没有收藏"
              description="在题目或课时页点击收藏，就会出现在这里。"
              action={
                <Button size="sm" variant="outline" asChild>
                  <Link href="/problems">去题库看看</Link>
                </Button>
              }
            />
          ) : (
            <div className="space-y-3">
              {items.map((item) => (
                <Card key={item.id} className="p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 flex-1 space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-[13.5px] font-medium">{item.title}</p>
                        <Badge variant="secondary">{KIND_LABEL[item.kind] ?? item.kind}</Badge>
                        {item.collection ? <Badge variant="outline">{item.collection}</Badge> : null}
                      </div>
                      {(item.tags ?? []).length > 0 ? (
                        <div className="flex flex-wrap gap-1.5">
                          {item.tags.map((tag) => (
                            <span key={tag} className="rounded border border-border px-1.5 text-[10.5px] text-muted-foreground">
                              {tag}
                            </span>
                          ))}
                        </div>
                      ) : null}
                      <p className="text-[11px] text-muted-foreground">收藏于 {formatRelativeTime(item.created_at)}</p>
                      {item.code_snippet ? (
                        <CodeBlock code={item.code_snippet} filename="snippet.py" maxHeight={180} />
                      ) : null}
                    </div>
                    <div className="flex shrink-0 items-center gap-1.5">
                      {item.ref_id && item.kind === 'problem' ? (
                        <Button size="sm" variant="outline" asChild>
                          <Link href={`/problems/${item.ref_id}`}>打开题目</Link>
                        </Button>
                      ) : null}
                      <Button size="icon-sm" variant="ghost" aria-label="移除收藏" onClick={() => void remove(item.id)}>
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </main>
      </div>

      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="新建收藏"
        description="可以收藏代码片段，或单纯记录一条学习笔记。"
        footer={
          <>
            <Button variant="ghost" onClick={() => setCreateOpen(false)}>
              取消
            </Button>
            <Button onClick={() => void create()}>保存</Button>
          </>
        }
      >
        <div className="space-y-3">
          <Field label="标题" required>
            <Input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} placeholder="例如：列表推导式常用写法" />
          </Field>
          <Field label="所属集合" hint="留空则归入默认集合">
            <Input value={form.collection} onChange={(event) => setForm({ ...form, collection: event.target.value })} placeholder="Python 技巧" />
          </Field>
          <Field label="代码片段" hint="填写后类型会自动标记为代码片段">
            <Input
              value={form.code_snippet}
              onChange={(event) => setForm({ ...form, code_snippet: event.target.value })}
              placeholder="print('hello')"
            />
          </Field>
          <Field label="标签" hint="逗号分隔">
            <Input value={form.tags} onChange={(event) => setForm({ ...form, tags: event.target.value })} placeholder="列表, 推导式" />
          </Field>
        </div>
      </Modal>
    </PageContainer>
  );
}

export default function BookmarksPage(): React.ReactElement {
  return (
    <AuthGate title="登录后查看收藏" description="收藏内容保存在你的账号下，支持按集合分类。">
      <BookmarksContent />
    </AuthGate>
  );
}
