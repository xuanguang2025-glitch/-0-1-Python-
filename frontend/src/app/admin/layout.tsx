'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Activity,
  FolderKanban,
  GraduationCap,
  LayoutDashboard,
  ListChecks,
  ShieldAlert,
  Users,
} from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { PageContainer } from '@/components/layout/page-container';
import { Sidebar, type SidebarGroup } from '@/components/layout/sidebar';
import { Alert, EmptyState } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';

const ADMIN_GROUPS: SidebarGroup[] = [
  {
    title: '总览',
    items: [{ label: '仪表盘', href: '/admin', icon: <LayoutDashboard className="h-3.5 w-3.5" /> }],
  },
  {
    title: '内容管理',
    items: [
      { label: '用户管理', href: '/admin/users', icon: <Users className="h-3.5 w-3.5" /> },
      { label: '课程管理', href: '/admin/courses', icon: <GraduationCap className="h-3.5 w-3.5" /> },
      { label: '题目管理', href: '/admin/problems', icon: <ListChecks className="h-3.5 w-3.5" /> },
      { label: '项目管理', href: '/admin/projects', icon: <FolderKanban className="h-3.5 w-3.5" /> },
    ],
  },
];

/** 后台布局：管理员鉴权 + 侧边导航。 */
export default function AdminLayout({ children }: { children: React.ReactNode }): React.ReactElement {
  const pathname = usePathname();
  const { hydrated, isAuthenticated, isAdmin, loading } = useAuth();

  if (!hydrated || (loading && !isAuthenticated)) {
    return (
      <PageContainer title="后台管理">
        <div className="flex gap-5">
          <Skeleton className="hidden h-64 w-60 lg:block" />
          <Skeleton className="h-64 flex-1" />
        </div>
      </PageContainer>
    );
  }

  if (!isAuthenticated) {
    return (
      <PageContainer title="后台管理">
        <EmptyState
          icon={<ShieldAlert className="h-6 w-6" />}
          title="需要管理员权限"
          description="当前未登录。请使用管理员账号登录后再访问后台。"
          action={
            <Button asChild>
              <Link href={`/login?redirect=${encodeURIComponent(pathname)}`}>去登录</Link>
            </Button>
          }
        />
      </PageContainer>
    );
  }

  if (!isAdmin) {
    return (
      <PageContainer title="后台管理">
        <EmptyState
          icon={<ShieldAlert className="h-6 w-6" />}
          title="权限不足"
          description="当前账号不是管理员，无法访问后台管理功能。"
          action={
            <Button variant="outline" asChild>
              <Link href="/dashboard">返回学习看板</Link>
            </Button>
          }
        />
      </PageContainer>
    );
  }

  return (
    <PageContainer
      title="后台管理"
      description="管理用户、课程、题目与项目内容。所有写操作都会记录审计日志。"
      sidebar={
        <div className="lg:w-60">
          <Sidebar groups={ADMIN_GROUPS} title="管理菜单" />
        </div>
      }
    >
      <div className="space-y-4">
        <Alert
          variant="info"
          title="操作需谨慎"
          description="删除为软删除，可在 30 天内恢复；批量重判会占用判题队列。"
        />
        {children}
      </div>
    </PageContainer>
  );
}
