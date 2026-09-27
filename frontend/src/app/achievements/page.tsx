'use client';

import { useMemo, useState } from 'react';
import { Award, CheckCircle2, Lock, Sparkles, Trophy, Zap } from 'lucide-react';
import { achievementApi } from '@/lib/api';
import { cn } from '@/lib/utils';
import { useFetch } from '@/hooks/useFetch';
import { useToaster } from '@/hooks/useToast';
import { AuthGate } from '@/components/common/auth-gate';
import { PageContainer } from '@/components/layout/page-container';
import { EmptyState } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress, RingProgress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import { SectionTitle, StatCard } from '@/components/ui/stat-card';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table';
import type { AchievementOut } from '@/lib/types';

const CATEGORY_LABELS: Record<string, string> = {
  learning: '学习',
  problem: '刷题',
  practice: '练习',
  project: '项目',
  streak: '坚持',
  challenge: '挑战',
  social: '社区',
  special: '特殊',
};

/** 每日任务 code → 说明（后端 UserDailyTaskOut.code）。 */
const DAILY_TASK_HINT: Record<string, string> = {
  daily_login: '每天登录一次即可完成',
  daily_lesson: '完成任意 1 个课时',
  daily_problem: '通过任意 1 道题目',
  daily_minutes: '累计学习满指定分钟数',
  daily_quiz: '完成 1 次随堂测验',
  daily_project: '推进任意 1 个实战项目',
};

/** 成就体系：徽章墙 + 每日任务 + XP 明细。 */
function AchievementsContent(): React.ReactElement {
  const toaster = useToaster();
  const [category, setCategory] = useState('');

  const list = useFetch(() => achievementApi.list(category || undefined), [category]);
  const tasks = useFetch(() => achievementApi.dailyTasks(), []);
  const xp = useFetch(() => achievementApi.xp({ page: 1, page_size: 20 }), []);

  const achievements: AchievementOut[] = list.data ?? [];
  const unlocked = achievements.filter((item) => item.unlocked);
  const unlockRate = achievements.length > 0 ? Math.round((unlocked.length / achievements.length) * 100) : 0;

  const categories = useMemo(() => {
    const set = new Set(achievements.map((item) => item.category));
    return Array.from(set);
  }, [achievements]);

  const checkTask = async (id: string): Promise<void> => {
    try {
      const result = await achievementApi.checkTask(id);
      toaster[result.completed ? 'success' : 'info'](
        result.completed ? `任务完成，+${result.xp_earned} XP` : '任务进度已更新',
        `${result.progress}/${result.target}`,
      );
      tasks.refresh();
      xp.refresh();
    } catch (error) {
      toaster.error('领取失败', error instanceof Error ? error.message : '请稍后再试');
    }
  };

  return (
    <PageContainer
      title="我的成就"
      description="徽章、XP 与每日任务 —— 把学习变成看得见的成长。"
    >
      <div className="space-y-6">
        <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
          <Card>
            <CardContent className="flex flex-col items-center gap-3 pt-6">
              <RingProgress value={unlockRate} size={116} label={`${unlockRate}%`} />
              <p className="text-[13px] font-medium">成就解锁率</p>
              <p className="text-[12px] text-muted-foreground">
                已解锁 {unlocked.length} / {achievements.length} 个徽章
              </p>
            </CardContent>
          </Card>

          <div className="grid gap-3 sm:grid-cols-2">
            <StatCard
              label="已解锁徽章"
              value={unlocked.length}
              icon={<Trophy className="h-3.5 w-3.5" />}
              tone="accent"
              loading={list.loading && !list.data}
            />
            <StatCard
              label="今日任务完成"
              value={`${tasks.data?.filter((task) => task.completed).length ?? 0}/${tasks.data?.length ?? 0}`}
              icon={<CheckCircle2 className="h-3.5 w-3.5" />}
              tone="success"
              loading={tasks.loading && !tasks.data}
            />
            <StatCard
              label="累计 XP"
              value={xp.data?.items.reduce((sum, item) => sum + Math.max(0, item.amount), 0) ?? 0}
              hint="最近 20 笔记录"
              icon={<Zap className="h-3.5 w-3.5" />}
              tone="primary"
              loading={xp.loading && !xp.data}
            />
            <StatCard
              label="最近获得"
              value={xp.data?.items[0]?.amount ?? 0}
              hint={xp.data?.items[0]?.reason ?? '暂无记录'}
              icon={<Sparkles className="h-3.5 w-3.5" />}
              loading={xp.loading && !xp.data}
            />
          </div>
        </div>

        {/* 每日任务 */}
        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>每日任务</CardTitle>
            <Badge variant="secondary">每天 0 点刷新</Badge>
          </CardHeader>
          <CardContent className="space-y-2.5">
            {tasks.loading && !tasks.data ? (
              <>
                <Skeleton className="h-14 w-full" />
                <Skeleton className="h-14 w-full" />
              </>
            ) : tasks.data && tasks.data.length > 0 ? (
              tasks.data.map((task) => (
                <div key={task.id} className="flex flex-wrap items-center gap-3 rounded-lg border border-border p-3">
                  <span
                    className={cn(
                      'flex h-8 w-8 shrink-0 items-center justify-center rounded-full',
                      task.completed ? 'bg-success/15 text-success' : 'bg-muted text-muted-foreground',
                    )}
                  >
                    {task.completed ? <CheckCircle2 className="h-4 w-4" /> : <Award className="h-4 w-4" />}
                  </span>
                  <div className="min-w-0 flex-1 space-y-1.5">
                    <p className="text-[13px] font-medium">{task.title}</p>
                    {task.code ? (
                      <p className="text-[11.5px] text-muted-foreground">{DAILY_TASK_HINT[task.code] ?? task.code}</p>
                    ) : null}
                    <Progress value={task.progress} max={task.target} size="sm" showValue />
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[11.5px] text-muted-foreground">+{task.xp_reward} XP</span>
                    <Button
                      size="sm"
                      variant={task.completed ? 'outline' : 'default'}
                      disabled={task.completed}
                      onClick={() => void checkTask(task.id)}
                    >
                      {task.completed ? '已完成' : '领取'}
                    </Button>
                  </div>
                </div>
              ))
            ) : (
              <EmptyState
                title="今日暂无任务"
                description="完成一节课或提交一道题后，任务会自动出现。"
                className="border-0 py-8"
              />
            )}
          </CardContent>
        </Card>

        {/* 徽章墙 */}
        <div>
          <SectionTitle
            title="徽章墙"
            description="按分类筛选成就，点击查看条件。"
            action={
              <Tabs value={category} onValueChange={setCategory}>
                <TabsList>
                  <TabsTrigger value="">全部</TabsTrigger>
                  {categories.map((item) => (
                    <TabsTrigger key={item} value={item}>
                      {CATEGORY_LABELS[item] ?? item}
                    </TabsTrigger>
                  ))}
                </TabsList>
              </Tabs>
            }
          />

          {list.loading && !list.data ? (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {Array.from({ length: 8 }).map((_, index) => (
                <Skeleton key={index} className="h-28 w-full" />
              ))}
            </div>
          ) : achievements.length > 0 ? (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {achievements.map((item) => (
                <Card
                  key={item.id}
                  className={cn('p-4 transition-colors', item.unlocked ? 'border-accent/40' : 'opacity-75')}
                >
                  <div className="flex items-start gap-3">
                    <span
                      className={cn(
                        'flex h-10 w-10 shrink-0 items-center justify-center rounded-lg',
                        item.unlocked ? 'bg-accent/20 text-accent-foreground' : 'bg-muted text-muted-foreground',
                      )}
                    >
                      {item.unlocked ? <Trophy className="h-5 w-5" /> : <Lock className="h-4 w-4" />}
                    </span>
                    <div className="min-w-0 space-y-1">
                      <p className="truncate text-[13.5px] font-semibold">{item.name}</p>
                      <p className="line-clamp-2 text-[11.5px] text-muted-foreground">{item.description}</p>
                      <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
                        <Badge variant={item.unlocked ? 'accent' : 'secondary'}>
                          {CATEGORY_LABELS[item.category] ?? item.category}
                        </Badge>
                        <span className="text-[10.5px] text-muted-foreground">+{item.xp_reward} XP</span>
                      </div>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          ) : (
            <EmptyState
              icon={<Trophy className="h-6 w-6" />}
              title="暂无成就数据"
              description="后端成就接口暂时不可用，或分类下暂无成就。"
            />
          )}
        </div>

        {/* XP 明细 */}
        <div>
          <SectionTitle title="XP 明细" description="最近的 XP 获取与消耗记录。" />
          <Card>
            <CardContent className="pt-5">
              {xp.loading && !xp.data ? (
                <Skeleton className="h-40 w-full" />
              ) : xp.data && xp.data.items.length > 0 ? (
                <Table>
                  <THead>
                    <TR>
                      <TH>时间</TH>
                      <TH>原因</TH>
                      <TH>变动</TH>
                      <TH>余额</TH>
                    </TR>
                  </THead>
                  <TBody>
                    {xp.data.items.map((item) => (
                      <TR key={item.id}>
                        <TD className="text-muted-foreground">
                          {item.created_at ? new Date(item.created_at).toLocaleString('zh-CN') : '—'}
                        </TD>
                        <TD>{item.reason || '—'}</TD>
                        <TD className={item.amount >= 0 ? 'text-emerald-500' : 'text-rose-500'}>
                          {item.amount >= 0 ? `+${item.amount}` : item.amount}
                        </TD>
                        <TD>{item.balance_after}</TD>
                      </TR>
                    ))}
                  </TBody>
                </Table>
              ) : (
                <EmptyState title="暂无 XP 记录" description="完成课时、通过题目即可获得 XP。" className="border-0 py-8" />
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </PageContainer>
  );
}

export default function AchievementsPage(): React.ReactElement {
  return (
    <AuthGate title="登录后查看我的成就" description="徽章、每日任务与 XP 明细都绑定在你的账号上。">
      <AchievementsContent />
    </AuthGate>
  );
}
