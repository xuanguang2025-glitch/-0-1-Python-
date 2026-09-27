import { Skeleton } from '@/components/ui/skeleton';

/** 路由级加载骨架。 */
export default function Loading(): React.ReactElement {
  return (
    <div className="mx-auto max-w-[1200px] space-y-4 px-4 py-8">
      <Skeleton className="h-7 w-48" />
      <Skeleton className="h-4 w-72" />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, index) => (
          <Skeleton key={index} className="h-28 w-full" />
        ))}
      </div>
    </div>
  );
}
