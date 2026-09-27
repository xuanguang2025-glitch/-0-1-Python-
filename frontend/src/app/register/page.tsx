import type { Metadata } from 'next';
import { Suspense } from 'react';
import { AuthForm } from '@/components/auth/auth-form';
import { Skeleton } from '@/components/ui/skeleton';

export const dynamic = 'force-dynamic';

export const metadata: Metadata = {
  title: '注册',
  description: '免费注册 PYTHON LAB，解锁全部课程、题库与在线编辑器。',
};

export default function RegisterPage(): React.ReactElement {
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-sm space-y-4 px-4 py-20">
          <Skeleton className="h-7 w-40" />
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-11 w-full" />
        </div>
      }
    >
      <AuthForm mode="register" />
    </Suspense>
  );
}
