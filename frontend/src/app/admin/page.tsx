'use client';

import Link from 'next/link';
import { Activity, AlertTriangle, Bot, Database, FolderKanban, GraduationCap, ListChecks, Server, Users } from 'lucide-react';
import { adminApi, healthApi } from '@/lib/api';
import { formatPercent } from '@/lib/utils';
import { useFetch } from '@/hooks/useFetch';
import { Alert, ErrorState } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { StatCard } from '@/components/ui/stat-card';

const MODULES = [
  { href: '/admin/users', label: '用户管理', desc: '角色、状态、密码重置', icon: <Users className="h-4 w-4" /> },
  { href: '/admin/courses', label: '课程管理', desc: '阶段、章节与课时', icon: <GraduationCap className="h-4 w-4" /> },
  { href: '/admin/problems', label: '题目管理', desc: '题面、测试用例、导入', icon: <ListChecks className="h-4 w-4" /> },
  { href: '/admin/projects', label: '项目管理', desc: '项目文件与步骤', icon: <FolderKanban className="h-4 w-4" /> },
];

/** 后台总览：核心指标 + 依赖状态 + 模块入口。 */
export default function AdminDashboardPage(): React.ReactElement {
  const dashboard = useFetch(() => adminApi.dashboard(), []);
  const deps = useFetch(() => healthApi.deps(), []);

  const data = dashboard.data;

  return (
    <div className="space-y-5">
      {dashboard.error && !dashboard.data ? (
        <ErrorState title="后台数据加载失败" description={dashboard.error} onRetry={dashboard.refresh} />
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="用户总数" value={data?.users_total ?? 0} icon={<Users className="h-3.5 w-3.5" />} tone="primary" loading={dashboard.loading && !data} />
        <StatCard label="今日活跃" value={data?.active_today ?? 0} icon={<Activity className="h-3.5 w-3.5" />} tone="success" loading={dashboard.loading && !data} />
        <StatCard label="今日提交" value={data?.submissions_today ?? 0} icon={<ListChecks className="h-3.5 w-3.5" />} loading={dashboard.loading && !data} />
        <StatCard label="整体通过率" value={formatPercent(data?.acceptance_rate ?? 0, 1)} icon={<GraduationCap className="h-3.5 w-3.5" />} loading={dashboard.loading && !data} />
        <StatCard label="今日 AI 调用" value={data?.ai_calls_today ?? 0} icon={<Bot className="h-3.5 w-3.5" />} tone="accent" loading={dashboard.loading && !data} />
        <StatCard label="错误率" value={formatPercent(data?.error_rate ?? 0, 2)} icon={<AlertTriangle className="h-3.5 w-3.5" />} tone="warning" loading={dashboard.loading && !data} />
        <StatCard label="执行器" value={data?.runner ?? '—'} icon={<Server className="h-3.5 w-3.5" />} loading={dashboard.loading && !data} />
        <StatCard label="数据库" value={data?.db_flavor ?? '—'} hint={`缓存：${data?.cache_backend ?? '—'}`} icon={<Database className="h-3.5 w-3.5" />} loading={dashboard.loading && !data} />
      </div>

      {/* 依赖状态 */}
      <Card>
        <CardHeader className="flex-row items-center justify-between pb-2">
          <CardTitle>依赖服务状态</CardTitle>
          <Button size="sm" variant="ghost" onClick={deps.refresh}>
            刷新
          </Button>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {deps.loading && !deps.data ? (
            <p className="text-[12px] text-muted-foreground">正在检测…</p>
          ) : deps.data ? (
            <>
              <DepItem label="数据库" value={deps.data.db.flavor} ok={deps.data.db.ok} />
              <DepItem label="缓存" value={deps.data.cache.backend} ok={deps.data.cache.ok} />
              <DepItem label="队列" value={deps.data.queue.backend} ok />
              <DepItem label="执行器" value={deps.data.runner.mode} ok={deps.data.runner.ok} />
              <DepItem label="AI" value={deps.data.ai.degraded ? `${deps.data.ai.provider}（降级）` : deps.data.ai.provider} ok={!deps.data.ai.degraded} />
            </>
          ) : (
            <Alert variant="warning" title="无法获取依赖状态" description="后端健康检查接口暂不可用。" />
          )}
        </CardContent>
      </Card>

      {/* 模块入口 */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {MODULES.map((module) => (
          <Card key={module.href} interactive className="p-4">
            <CardContent className="space-y-2 p-0">
              <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-primary/12 text-primary">
                {module.icon}
              </span>
              <p className="text-[14px] font-semibold">{module.label}</p>
              <p className="text-[11.5px] text-muted-foreground">{module.desc}</p>
              <Button size="sm" variant="outline" className="w-full" asChild>
                <Link href={module.href}>进入管理</Link>
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

function DepItem({ label, value, ok }: { label: string; value: string; ok: boolean }): React.ReactElement {
  return (
    <div className="rounded-lg border border-border p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11.5px] text-muted-foreground">{label}</span>
        <Badge variant={ok ? 'success' : 'danger'}>{ok ? '正常' : '异常'}</Badge>
      </div>
      <p className="mt-1.5 truncate font-mono text-[12px]">{value}</p>
    </div>
  );
}
