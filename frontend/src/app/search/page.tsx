'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { BookOpen, Code2, FolderKanban, ListChecks, Search as SearchIcon, Sparkles } from 'lucide-react';
import { searchApi } from '@/lib/api';
import { useDebounce } from '@/hooks/useDebounce';
import { useFetch } from '@/hooks/useFetch';
import { PageContainer } from '@/components/layout/page-container';
import { EmptyState } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';

const TYPE_ICON: Record<string, React.ReactNode> = {
  course: <BookOpen className="h-3.5 w-3.5" />,
  lesson: <BookOpen className="h-3.5 w-3.5" />,
  problem: <ListChecks className="h-3.5 w-3.5" />,
  project: <FolderKanban className="h-3.5 w-3.5" />,
  snippet: <Code2 className="h-3.5 w-3.5" />,
};

const TYPE_LABEL: Record<string, string> = {
  course: '课程',
  lesson: '课时',
  problem: '题目',
  project: '项目',
  snippet: '代码片段',
};

/** 站内搜索：课程 / 课时 / 题目 / 项目 / 代码片段。 */
export default function SearchPage(): React.ReactElement {
  const router = useRouter();
  const params = useSearchParams();
  const initialQuery = params.get('q') ?? '';

  const [keyword, setKeyword] = useState(initialQuery);
  const debounced = useDebounce(keyword, 350);

  useEffect(() => {
    setKeyword(initialQuery);
  }, [initialQuery]);

  const results = useFetch(() => searchApi.search(debounced), [debounced], { enabled: debounced.trim().length > 0 });
  const suggest = useFetch(() => searchApi.suggest(debounced), [debounced], { enabled: debounced.trim().length > 0 });

  const groups = results.data?.groups ?? [];

  return (
    <PageContainer title="搜索" description="搜索课程、课时、题目、项目与代码片段。">
      <div className="space-y-5">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (keyword.trim()) router.replace(`/search?q=${encodeURIComponent(keyword.trim())}`);
          }}
          className="flex gap-2"
        >
          <Input
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            placeholder="输入关键词，例如「列表推导式」"
            icon={<SearchIcon className="h-3.5 w-3.5" />}
            autoFocus
          />
          <Button type="submit">搜索</Button>
        </form>

        {suggest.data && suggest.data.suggestions.length > 0 && debounced.trim() ? (
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[11px] text-muted-foreground">猜你想搜：</span>
            {suggest.data.suggestions.slice(0, 6).map((item) => (
              <button
                key={item.text}
                type="button"
                onClick={() => setKeyword(item.text)}
                className="rounded-full border border-border px-2.5 py-1 text-[11.5px] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                {item.text}
              </button>
            ))}
          </div>
        ) : null}

        {!debounced.trim() ? (
          <EmptyState
            icon={<Sparkles className="h-6 w-6" />}
            title="输入关键词开始搜索"
            description="可以搜索知识点、题目标题、项目名称，甚至代码片段内容。"
          />
        ) : results.loading && !results.data ? (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, index) => (
              <Skeleton key={index} className="h-28 w-full" />
            ))}
          </div>
        ) : groups.length === 0 ? (
          <EmptyState
            icon={<SearchIcon className="h-6 w-6" />}
            title={`没有找到与「${debounced}」相关的内容`}
            description="换个关键词试试，或者直接去题库按难度筛选。"
            action={
              <Button size="sm" variant="outline" asChild>
                <Link href="/problems">去题库</Link>
              </Button>
            }
          />
        ) : (
          <div className="space-y-5">
            <p className="text-[12px] text-muted-foreground">共找到 {results.data?.total ?? 0} 条结果</p>
            {groups.map((group) => (
              <div key={group.type} className="space-y-2">
                <div className="flex items-center gap-2">
                  <Badge variant="secondary" className="gap-1">
                    {TYPE_ICON[group.type] ?? <SearchIcon className="h-3 w-3" />}
                    {TYPE_LABEL[group.type] ?? group.type}
                  </Badge>
                  <span className="text-[11px] text-muted-foreground">{group.items.length} 条</span>
                  <span className="h-px flex-1 bg-border" />
                </div>
                <div className="space-y-2">
                  {group.items.map((item) => (
                    <Link key={`${group.type}-${item.id}`} href={item.url || '/'}>
                      <Card interactive className="p-3.5">
                        <CardContent className="p-0">
                          <p className="text-[13.5px] font-medium">{item.title}</p>
                          {item.subtitle ? (
                            <p className="mt-0.5 line-clamp-2 text-[12px] text-muted-foreground">{item.subtitle}</p>
                          ) : null}
                          {item.highlight ? (
                            <p className="mt-1.5 line-clamp-2 rounded border border-border bg-muted/40 p-2 font-mono text-[11px] text-muted-foreground">
                              {item.highlight}
                            </p>
                          ) : null}
                        </CardContent>
                      </Card>
                    </Link>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </PageContainer>
  );
}
