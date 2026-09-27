'use client';

import Link from 'next/link';
import { useState } from 'react';
import { ChevronLeft, ChevronRight, Clock, FolderKanban, Layers, PlayCircle, Search } from 'lucide-react';
import { projectApi } from '@/lib/api';
import { DIFFICULTY_LABEL, DIFFICULTY_STYLE } from '@/lib/constants';
import { useDebounce } from '@/hooks/useDebounce';
import { useFetch } from '@/hooks/useFetch';
import { PageContainer } from '@/components/layout/page-container';
import { EmptyState, ErrorState } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';
import { Select } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';

const CATEGORY_OPTIONS = [
  { value: '', label: '全部分类' },
  { value: 'tool', label: '命令行工具' },
  { value: 'data', label: '数据处理' },
  { value: 'web', label: 'Web 应用' },
  { value: 'automation', label: '自动化脚本' },
  { value: 'game', label: '小游戏' },
];

const PAGE_SIZE = 12;

/** 项目列表：按分类筛选 + 分页。 */
export default function ProjectsPage(): React.ReactElement {
  const [category, setCategory] = useState('');
  const [keyword, setKeyword] = useState('');
  const [page, setPage] = useState(1);
  const debouncedKeyword = useDebounce(keyword, 300);

  const request = useFetch(
    () => projectApi.list({ category: category || undefined, page, page_size: PAGE_SIZE }),
    [category, page],
  );

  const items = (request.data?.items ?? []).filter((project) =>
    debouncedKeyword.trim() ? project.title.toLowerCase().includes(debouncedKeyword.trim().toLowerCase()) : true,
  );
  const totalPages = request.data?.pages ?? 1;

  return (
    <PageContainer
      title="项目实战"
      description="把零散的知识拼成能跑的东西 —— 这才是学 Python 的意义。"
      actions={
        <Badge variant="secondary" className="gap-1">
          <FolderKanban className="h-3 w-3" />
          共 {request.data?.total ?? 0} 个项目
        </Badge>
      }
    >
      <div className="space-y-5">
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-card p-3">
          <div className="min-w-[200px] flex-1">
            <Input
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              placeholder="搜索项目名称"
              icon={<Search className="h-3.5 w-3.5" />}
            />
          </div>
          <div className="w-40">
            <Select
              value={category}
              options={CATEGORY_OPTIONS}
              onChange={(event) => {
                setCategory(event.target.value);
                setPage(1);
              }}
            />
          </div>
        </div>

        {request.loading && !request.data ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, index) => (
              <Skeleton key={index} className="h-40 w-full" />
            ))}
          </div>
        ) : request.error && !request.data ? (
          <ErrorState title="项目列表加载失败" description={request.error} onRetry={request.refresh} />
        ) : items.length === 0 ? (
          <EmptyState
            icon={<FolderKanban className="h-6 w-6" />}
            title="暂无项目"
            description="项目内容可能还在录入中，先去看看课程或题库吧。"
            action={
              <Button size="sm" variant="outline" asChild>
                <Link href="/problems">去刷题</Link>
              </Button>
            }
          />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {items.map((project) => (
              <Card key={project.id} interactive className="flex h-full flex-col">
                <CardContent className="flex flex-1 flex-col gap-3 pt-5">
                  <div className="flex items-start justify-between gap-2">
                    <Badge className={DIFFICULTY_STYLE[project.difficulty]}>{DIFFICULTY_LABEL[project.difficulty]}</Badge>
                    <Badge variant="secondary">Lv.{project.level}</Badge>
                  </div>

                  <div className="space-y-1.5">
                    <h3 className="text-[15px] font-semibold leading-tight">{project.title}</h3>
                    <p className="line-clamp-2 text-[12.5px] leading-relaxed text-muted-foreground">
                      {project.summary ?? '暂无简介'}
                    </p>
                  </div>

                  <div className="mt-auto space-y-3">
                    <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
                      <span className="inline-flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {project.estimated_hours} 小时
                      </span>
                      <span className="inline-flex items-center gap-1">
                        <Layers className="h-3 w-3" />
                        {project.category}
                      </span>
                    </div>

                    {typeof project.my_progress_percent === 'number' ? (
                      <Progress value={project.my_progress_percent} size="sm" showValue />
                    ) : null}

                    <Button size="sm" className="w-full" asChild>
                      <Link href={`/projects/${project.id}`}>
                        <PlayCircle className="h-3.5 w-3.5" />
                        {project.my_progress_percent ? '继续项目' : '开始项目'}
                      </Link>
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {totalPages > 1 ? (
          <div className="flex items-center justify-center gap-3">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((prev) => prev - 1)}>
              <ChevronLeft className="h-3.5 w-3.5" />
              上一页
            </Button>
            <span className="text-[12px] text-muted-foreground">
              第 {page} / {totalPages} 页
            </span>
            <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage((prev) => prev + 1)}>
              下一页
              <ChevronRight className="h-3.5 w-3.5" />
            </Button>
          </div>
        ) : null}
      </div>
    </PageContainer>
  );
}
