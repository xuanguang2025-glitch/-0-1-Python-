'use client';

import Link from 'next/link';
import { useState } from 'react';
import { CalendarClock, Flag, Swords, Target, Timer, Trophy, Users } from 'lucide-react';
import { challengeApi } from '@/lib/api';
import { cn, formatRelativeTime } from '@/lib/utils';
import { useFetch } from '@/hooks/useFetch';
import { useToaster } from '@/hooks/useToast';
import { useAuth } from '@/hooks/useAuth';
import { AuthGate } from '@/components/common/auth-gate';
import { PageContainer } from '@/components/layout/page-container';
import { EmptyState, ErrorState } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { StatCard } from '@/components/ui/stat-card';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table';
import type { ChallengeBrief, LeaderboardEntry } from '@/lib/types';

const TYPE_LABEL: Record<string, string> = { daily: '日赛', weekly: '周赛', monthly: '月赛', special: '特别赛' };

/** 后端 ChallengeBrief 无 status 字段，由 is_open + end_at 推导展示状态。 */
function challengeState(challenge: ChallengeBrief): 'active' | 'ended' {
  if (!challenge.is_open) return 'ended';
  if (challenge.end_at && new Date(challenge.end_at).getTime() < Date.now()) return 'ended';
  return 'active';
}

/** 挑战赛：列表 + 参加 + 排行榜。 */
function ChallengesContent(): React.ReactElement {
  const toaster = useToaster();
  const { isAuthenticated } = useAuth();
  const [status, setStatus] = useState<'active' | 'ended'>('active');
  const [type, setType] = useState('');
  const [joined, setJoined] = useState<Record<string, boolean>>({});
  const [selected, setSelected] = useState<ChallengeBrief | null>(null);

  const list = useFetch(() => challengeApi.list({ status, type: type || undefined, page: 1, page_size: 20 }), [status, type]);
  const mine = useFetch(() => challengeApi.mine({ page: 1, page_size: 10 }), [], { enabled: isAuthenticated });
  const leaderboard = useFetch(
    () => (selected ? challengeApi.leaderboard(selected.id, 20) : Promise.resolve({ entries: [], total: 0, updated_at: null })),
    [selected?.id],
    { enabled: Boolean(selected) },
  );

  const join = async (challenge: ChallengeBrief): Promise<void> => {
    if (!isAuthenticated) {
      toaster.info('请先登录再参加挑战');
      return;
    }
    try {
      await challengeApi.join(challenge.id);
      setJoined((prev) => ({ ...prev, [challenge.id]: true }));
      mine.refresh();
      toaster.success('已报名', `${challenge.title} 加油！`);
    } catch (error) {
      toaster.error('报名失败', error instanceof Error ? error.message : '请稍后再试');
    }
  };

  const challenges = list.data?.items ?? [];

  return (
    <PageContainer title="挑战赛" description="日赛、周赛、月赛 —— 和同水平的人一起做题。">
      <div className="space-y-6">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="进行中" value={challenges.filter((c) => challengeState(c) === 'active').length} icon={<Swords className="h-3.5 w-3.5" />} tone="primary" loading={list.loading && !list.data} />
          <StatCard label="我参加的" value={mine.data?.total ?? 0} icon={<Flag className="h-3.5 w-3.5" />} loading={mine.loading && !mine.data} />
          <StatCard label="可获 XP" value={challenges.length * 200} hint="估算值，以榜单为准" icon={<Trophy className="h-3.5 w-3.5" />} tone="accent" loading={list.loading && !list.data} />
          <StatCard label="参与人数" value={challenges.reduce((sum, c) => sum + (c.participant_count ?? 0), 0)} icon={<Users className="h-3.5 w-3.5" />} tone="success" loading={list.loading && !list.data} />
        </div>

        <Card>
          <CardHeader className="flex-row flex-wrap items-center justify-between gap-3">
            <CardTitle>挑战列表</CardTitle>
            <div className="flex items-center gap-2">
              <Tabs value={status} onValueChange={(value) => setStatus(value as 'active' | 'ended')}>
                <TabsList>
                  <TabsTrigger value="active">进行中</TabsTrigger>
                  <TabsTrigger value="ended">已结束</TabsTrigger>
                </TabsList>
              </Tabs>
              <Tabs value={type} onValueChange={setType}>
                <TabsList>
                  <TabsTrigger value="">全部</TabsTrigger>
                  <TabsTrigger value="daily">日赛</TabsTrigger>
                  <TabsTrigger value="weekly">周赛</TabsTrigger>
                  <TabsTrigger value="monthly">月赛</TabsTrigger>
                </TabsList>
              </Tabs>
            </div>
          </CardHeader>

          <CardContent className="space-y-3">
            {list.loading && !list.data ? (
              <>
                <Skeleton className="h-24 w-full" />
                <Skeleton className="h-24 w-full" />
              </>
            ) : list.error && !list.data ? (
              <ErrorState title="挑战列表加载失败" description={list.error} onRetry={list.refresh} />
            ) : challenges.length === 0 ? (
              <EmptyState
                icon={<Swords className="h-6 w-6" />}
                title="当前没有挑战赛"
                description="挑战赛会定期开放，可以先刷题库热身。"
                action={
                  <Button size="sm" variant="outline" asChild>
                    <Link href="/problems">去刷题</Link>
                  </Button>
                }
                className="border-0 py-8"
              />
            ) : (
              challenges.map((challenge) => {
                const isJoined = joined[challenge.id] || challenge.my_status != null;
                const ended = challengeState(challenge) === 'ended';
                return (
                  <div
                    key={challenge.id}
                    className={cn('rounded-lg border p-4 transition-colors', ended ? 'border-border opacity-80' : 'border-border hover:border-primary/40')}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0 space-y-1.5">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge variant={!ended ? 'success' : 'secondary'}>
                            {TYPE_LABEL[challenge.challenge_type] ?? challenge.challenge_type}
                          </Badge>
                          <Badge variant={!ended ? 'info' : 'secondary'}>{!ended ? '进行中' : '已结束'}</Badge>
                          {isJoined ? <Badge variant="accent">已报名</Badge> : null}
                        </div>
                        <p className="text-[14.5px] font-semibold">{challenge.title}</p>
                        <p className="line-clamp-2 text-[12.5px] text-muted-foreground">
                          {challenge.problem_count} 道题 · 单题难度以题目页为准 · 奖励 +{challenge.xp_reward} XP
                        </p>
                        <div className="flex flex-wrap items-center gap-3 pt-1 text-[11px] text-muted-foreground">
                          <span className="inline-flex items-center gap-1">
                            <Target className="h-3 w-3" />
                            {challenge.problem_count} 题
                          </span>
                          <span className="inline-flex items-center gap-1">
                            <Users className="h-3 w-3" />
                            {challenge.participant_count} 人参加
                          </span>
                          <span className="inline-flex items-center gap-1">
                            <Timer className="h-3 w-3" />
                            {!ended ? '结束于 ' : ''}
                            {formatRelativeTime(challenge.end_at)}
                          </span>
                        </div>
                      </div>

                      <div className="flex shrink-0 flex-col gap-2">
                        <Button size="sm" disabled={ended || isJoined} onClick={() => void join(challenge)}>
                          {isJoined ? '已报名' : ended ? '已结束' : '立即参加'}
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => setSelected(challenge)}>
                          查看榜单
                        </Button>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </CardContent>
        </Card>

        {/* 我的挑战记录 */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle>我的挑战记录</CardTitle>
          </CardHeader>
          <CardContent>
            {mine.loading && !mine.data ? (
              <Skeleton className="h-32 w-full" />
            ) : mine.data && mine.data.items.length > 0 ? (
              <Table>
                <THead>
                  <TR>
                    <TH>挑战</TH>
                    <TH>得分</TH>
                    <TH>通过测试点</TH>
                    <TH>排名</TH>
                    <TH>参加时间</TH>
                  </TR>
                </THead>
                <TBody>
                  {mine.data.items.map((item) => (
                    <TR key={item.id}>
                      <TD className="font-mono text-[12px]">{item.challenge_id.slice(0, 8)}…</TD>
                      <TD>{item.score}</TD>
                      <TD>{item.passed_cases}</TD>
                      <TD>{item.rank ?? '—'}</TD>
                      <TD className="text-muted-foreground">
                        {item.submitted_at ? new Date(item.submitted_at).toLocaleDateString('zh-CN') : '未提交'}
                      </TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            ) : (
              <EmptyState title="还没有参加过挑战" description="报名一场日赛，感受一下限时做题的节奏。" className="border-0 py-8" />
            )}
          </CardContent>
        </Card>

        {/* 排行榜 */}
        {selected ? (
          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle className="flex items-center gap-1.5">
                <Trophy className="h-4 w-4 text-accent" />
                {selected.title} · 排行榜
              </CardTitle>
              <Button size="sm" variant="ghost" onClick={() => setSelected(null)}>
                收起
              </Button>
            </CardHeader>
            <CardContent>
              {leaderboard.loading && !leaderboard.data ? (
                <Skeleton className="h-40 w-full" />
              ) : leaderboard.data && leaderboard.data.entries.length > 0 ? (
                <Table>
                  <THead>
                    <TR>
                      <TH>名次</TH>
                      <TH>昵称</TH>
                      <TH>得分</TH>
                      <TH>总耗时</TH>
                    </TR>
                  </THead>
                  <TBody>
                    {leaderboard.data.entries.map((entry: LeaderboardEntry) => (
                      <TR key={entry.rank}>
                        <TD>
                          <span
                            className={cn(
                              'inline-flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-semibold',
                              entry.rank === 1 && 'bg-accent/20 text-accent-foreground',
                              entry.rank === 2 && 'bg-muted text-foreground',
                              entry.rank === 3 && 'bg-primary/15 text-primary',
                              entry.rank > 3 && 'text-muted-foreground',
                            )}
                          >
                            {entry.rank}
                          </span>
                        </TD>
                        <TD>{entry.display_name}</TD>
                        <TD>{entry.score}</TD>
                        <TD>{Math.round(entry.total_time_ms / 1000)}s</TD>
                      </TR>
                    ))}
                  </TBody>
                </Table>
              ) : (
                <EmptyState
                  icon={<CalendarClock className="h-5 w-5" />}
                  title="暂无榜单数据"
                  description="挑战结束后会生成最终榜单（仅展示昵称与成绩）。"
                  className="border-0 py-8"
                />
              )}
            </CardContent>
          </Card>
        ) : null}
      </div>
    </PageContainer>
  );
}

export default function ChallengesPage(): React.ReactElement {
  return (
    <AuthGate title="登录后参加挑战" description="挑战赛需要登录报名，成绩会记录到你的学习档案。">
      <ChallengesContent />
    </AuthGate>
  );
}
