import type { Metadata } from 'next';
import { Suspense } from 'react';
import { AuthForm } from '@/components/auth/auth-form';
import { Skeleton } from '@/components/ui/skeleton';

export const dynamic = 'force-dynamic';

export const metadata: Metadata = {
  title: '登录',
  description: '登录 PYTHON LAB，继续你的 Python 学习进度。',
};

export default function LoginPage(): React.ReactElement {
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-sm space-y-4 px-4 py-20">
          <Skeleton className="h-7 w-40" />
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-11 w-full" />
        </div>
      }
    >
      <AuthForm mode="login" />
    </Suspense>
  );
}
