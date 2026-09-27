'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LockKeyhole } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/alert';
import { PageContainer } from '@/components/layout/page-container';
import { Skeleton } from '@/components/ui/skeleton';

export interface AuthGateProps {
  children: React.ReactNode;
  title?: string;
  description?: string;
}

/**
 * 登录门禁：未登录时给出明确引导（而不是白屏或跳走），
 * 会话恢复期间显示骨架，避免误判为未登录。
 */
export function AuthGate({
  children,
  title = '请先登录',
  description = '登录后即可查看你的学习进度、代码存档与统计数据。',
}: AuthGateProps): React.ReactElement {
  const { hydrated, isAuthenticated, loading } = useAuth();
  const pathname = usePathname();

  if (!hydrated || (loading && !isAuthenticated)) {
    return (
      <PageContainer>
        <div className="space-y-4">
          <Skeleton className="h-7 w-48" />
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, index) => (
              <Skeleton key={index} className="h-24 w-full" />
            ))}
          </div>
          <Skeleton className="h-64 w-full" />
        </div>
      </PageContainer>
    );
  }

  if (!isAuthenticated) {
    return (
      <PageContainer>
        <EmptyState
          icon={<LockKeyhole className="h-6 w-6" />}
          title={title}
          description={description}
          className="py-20"
          action={
            <div className="flex gap-3">
              <Button asChild>
                <Link href={`/login?redirect=${encodeURIComponent(pathname)}`}>登录</Link>
              </Button>
              <Button variant="outline" asChild>
                <Link href={`/register?redirect=${encodeURIComponent(pathname)}`}>注册新账号</Link>
              </Button>
            </div>
          }
        />
      </PageContainer>
    );
  }

  return <>{children}</>;
}
