'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';
import {
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Filter,
  ListChecks,
  Shuffle,
  Sparkles,
  Target,
} from 'lucide-react';
import { problemApi } from '@/lib/api';
import { DIFFICULTY_LABEL, DIFFICULTY_STYLE, PROBLEM_TYPE_LABEL, VERDICT_SHORT } from '@/lib/constants';
import { cn, formatPercent } from '@/lib/utils';
import { useDebounce } from '@/hooks/useDebounce';
import { useFetch } from '@/hooks/useFetch';
import { useToaster } from '@/hooks/useToast';
import { AuthGate } from '@/components/common/auth-gate';
import { PageContainer } from '@/components/layout/page-container';
import { EmptyState, ErrorState } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';

const PAGE_SIZE = 20;

const STATUS_OPTIONS = [
  { value: 'all', label: '全部状态' },
  { value: 'unsolved', label: '未解决' },
  { value: 'solved', label: '已解决' },
];

const SORT_OPTIONS = [
  { value: '-created_at', label: '最新加入' },
  { value: 'difficulty', label: '难度从易到难' },
  { value: '-acceptance_rate', label: '通过率从高到低' },
  { value: 'order_index', label: '默认顺序' },
];

/** 题库列表：多维筛选 + 随机挑题 + 推荐。 */
function ProblemsContent(): React.ReactElement {
  const toaster = useToaster();
  const [keyword, setKeyword] = useState('');
  const [difficulty, setDifficulty] = useState('');
  const [category, setCategory] = useState('');
  const [type, setType] = useState('');
  const [status, setStatus] = useState('all');
  const [sort, setSort] = useState('-created_at');
  const [page, setPage] = useState(1);
  const debouncedKeyword = useDebounce(keyword, 300);

  const filters = useFetch(() => problemApi.filters(), []);
  const list = useFetch(
    () =>
      problemApi.list({
        keyword: debouncedKeyword || undefined,
        difficulty: difficulty || undefined,
        category: category || undefined,
        type: type || undefined,
        status: status === 'all' ? undefined : status,
        sort,
        page,
        page_size: PAGE_SIZE,
      }),
    [debouncedKeyword, difficulty, category, type, status, sort, page],
  );

  const difficultyOptions = useMemo(
    () => [
      { value: '', label: '全部难度' },
      ...(filters.data?.difficulties.map((item) => ({ value: item.value, label: `${item.label} (${item.count})` })) ?? [
        { value: 'easy', label: '入门' },
        { value: 'medium', label: '简单' },
        { value: 'hard', label: '中等' },
        { value: 'expert', label: '困难' },
      ]),
    ],
    [filters.data],
  );

  const categoryOptions = useMemo(
    () => [
      { value: '', label: '全部分类' },
      ...(filters.data?.categories.map((item) => ({ value: item.value, label: `${item.label} (${item.count})` })) ?? []),
    ],
    [filters.data],
  );

  const typeOptions = useMemo(
    () => [
      { value: '', label: '全部题型' },
      ...(filters.data?.types.map((item) => ({ value: item.value, label: `${item.label} (${item.count})` })) ?? []),
    ],
    [filters.data],
  );

  const randomProblem = async (): Promise<void> => {
    try {
      const problem = await problemApi.random({
        difficulty: difficulty || undefined,
        category: category || undefined,
        exclude_solved: status === 'unsolved',
      });
      window.location.href = `/problems/${problem.id}`;
    } catch (error) {
      toaster.error('随机挑题失败', error instanceof Error ? error.message : '请稍后再试');
    }
  };

  const items = list.data?.items ?? [];
  const totalPages = list.data?.pages ?? 1;

  return (
    <PageContainer
      title="题库"
      description="分级练习 + 智能判题，覆盖从语法到算法的全部知识点。"
      actions={
        <>
          <Button size="sm" variant="outline" onClick={() => void randomProblem()}>
            <Shuffle className="h-3.5 w-3.5" />
            随机一题
          </Button>
          <Button size="sm" variant="outline" asChild>
            <Link href="/challenges">
              <Target className="h-3.5 w-3.5" />
              参加挑战
            </Link>
          </Button>
        </>
      }
    >
      <div className="space-y-5">
        {/* 筛选区 */}
        <Card>
          <CardContent className="space-y-3 pt-5">
            <div className="flex flex-wrap items-center gap-3">
              <div className="min-w-[180px] flex-1">
                <Input
                  value={keyword}
                  onChange={(event) => {
                    setKeyword(event.target.value);
                    setPage(1);
                  }}
                  placeholder="搜索题目名称或关键词"
                  icon={<Sparkles className="h-3.5 w-3.5" />}
                />
              </div>
              <div className="w-36">
                <Select value={difficulty} options={difficultyOptions} onChange={(e) => { setDifficulty(e.target.value); setPage(1); }} />
              </div>
              <div className="w-36">
                <Select value={category} options={categoryOptions} onChange={(e) => { setCategory(e.target.value); setPage(1); }} />
              </div>
              <div className="w-32">
                <Select value={type} options={typeOptions} onChange={(e) => { setType(e.target.value); setPage(1); }} />
              </div>
              <div className="w-32">
                <Select value={status} options={STATUS_OPTIONS} onChange={(e) => { setStatus(e.target.value); setPage(1); }} />
              </div>
              <div className="w-40">
                <Select value={sort} options={SORT_OPTIONS} onChange={(e) => { setSort(e.target.value); setPage(1); }} />
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setKeyword('');
                  setDifficulty('');
                  setCategory('');
                  setType('');
                  setStatus('all');
                  setSort('-created_at');
                  setPage(1);
                }}
              >
                <Filter className="h-3.5 w-3.5" />
                重置
              </Button>
            </div>

            {filters.data?.tags && filters.data.tags.length > 0 ? (
              <div className="flex flex-wrap items-center gap-1.5 border-t border-border pt-3">
                <span className="text-[11px] text-muted-foreground">热门标签：</span>
                {filters.data.tags.slice(0, 12).map((tag) => (
                  <button
                    key={tag.value}
                    type="button"
                    onClick={() => {
                      setKeyword(tag.value);
                      setPage(1);
                    }}
                    className={cn(
                      'rounded-full border px-2 py-0.5 text-[11px] transition-colors',
                      keyword === tag.value
                        ? 'border-primary/40 bg-primary/12 text-primary'
                        : 'border-border text-muted-foreground hover:bg-muted',
                    )}
                  >
                    {tag.label}
                  </button>
                ))}
              </div>
            ) : null}
          </CardContent>
        </Card>

        {/* 列表 */}
        {list.loading && !list.data ? (
          <div className="space-y-2">
            {Array.from({ length: 8 }).map((_, index) => (
              <Skeleton key={index} className="h-16 w-full" />
            ))}
          </div>
        ) : list.error && !list.data ? (
          <ErrorState title="题库加载失败" description={list.error} onRetry={list.refresh} />
        ) : items.length === 0 ? (
          <EmptyState
            icon={<ListChecks className="h-6 w-6" />}
            title="没有符合条件的题目"
            description="试试放宽筛选条件，或者随机挑一题练练手。"
            action={
              <Button size="sm" variant="outline" onClick={() => void randomProblem()}>
                <Shuffle className="h-3.5 w-3.5" />
                随机一题
              </Button>
            }
          />
        ) : (
          <>
            <div className="overflow-hidden rounded-lg border border-border">
              <div className="hidden grid-cols-[2.5rem_1fr_6rem_6rem_7rem_6rem] gap-3 border-b border-border bg-muted/40 px-4 py-2 text-[11px] font-medium text-muted-foreground lg:grid">
                <span>状态</span>
                <span>题目</span>
                <span>难度</span>
                <span>题型</span>
                <span>通过率</span>
                <span className="text-right">操作</span>
              </div>
              {items.map((problem, index) => (
                <div
                  key={problem.id}
                  className="grid grid-cols-1 gap-3 border-b border-border px-4 py-3 transition-colors last:border-0 hover:bg-muted/35 lg:grid-cols-[2.5rem_1fr_6rem_6rem_7rem_6rem] lg:items-center"
                >
                  <span className="flex items-center gap-2 text-[11px] text-muted-foreground">
                    {problem.my_status === 'accepted' ? (
                      <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                    ) : (
                      <span className="inline-flex h-4 w-4 items-center justify-center rounded-full border border-border text-[9px]">
                        {(page - 1) * PAGE_SIZE + index + 1}
                      </span>
                    )}
                  </span>

                  <div className="min-w-0 space-y-1">
                    <Link href={`/problems/${problem.id}`} className="block truncate text-[13.5px] font-medium hover:text-primary">
                      {problem.title}
                    </Link>
                    <div className="flex flex-wrap items-center gap-1.5 lg:hidden">
                      <Badge className={DIFFICULTY_STYLE[problem.difficulty]}>{DIFFICULTY_LABEL[problem.difficulty]}</Badge>
                      <Badge variant="secondary">{PROBLEM_TYPE_LABEL[problem.problem_type]}</Badge>
                      {problem.my_status ? <Badge variant="outline">{VERDICT_SHORT[problem.my_status]}</Badge> : null}
                    </div>
                    {problem.tags && problem.tags.length > 0 ? (
                      <div className="hidden flex-wrap gap-1 lg:flex">
                        {problem.tags.slice(0, 3).map((tag) => (
                          <span key={tag} className="rounded border border-border px-1.5 text-[10.5px] text-muted-foreground">
                            {tag}
                          </span>
                        ))}
                      </div>
                    ) : null}
                  </div>

                  <span className="hidden lg:block">
                    <Badge className={DIFFICULTY_STYLE[problem.difficulty]}>{DIFFICULTY_LABEL[problem.difficulty]}</Badge>
                  </span>
                  <span className="hidden text-[12px] text-muted-foreground lg:block">
                    {PROBLEM_TYPE_LABEL[problem.problem_type]}
                  </span>
                  <span className="hidden text-[12px] text-muted-foreground lg:block">
                    {formatPercent(problem.acceptance_rate ?? 0, 0)}
                  </span>
                  <span className="text-right">
                    <Button size="sm" variant="outline" asChild>
                      <Link href={`/problems/${problem.id}`}>去做题</Link>
                    </Button>
                  </span>
                </div>
              ))}
            </div>

            {totalPages > 1 ? (
              <div className="flex items-center justify-center gap-3">
                <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((prev) => Math.max(1, prev - 1))}>
                  <ChevronLeft className="h-3.5 w-3.5" />
                  上一页
                </Button>
                <span className="text-[12px] text-muted-foreground">
                  第 {page} / {totalPages} 页 · 共 {list.data?.total ?? 0} 题
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
          </>
        )}
      </div>
    </PageContainer>
  );
}

export default function ProblemsPage(): React.ReactElement {
  return (
    <AuthGate title="登录后开始刷题" description="题目列表公开可见，登录后可以记录做题状态、提交判题并保存错题。">
      <ProblemsContent />
    </AuthGate>
  );
}
