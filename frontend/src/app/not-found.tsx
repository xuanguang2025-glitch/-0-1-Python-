import Link from 'next/link';
import { Compass } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function NotFound(): React.ReactElement {
  return (
    <div className="flex min-h-[70vh] flex-col items-center justify-center gap-4 px-4 text-center">
      <Compass className="h-8 w-8 text-muted-foreground" />
      <p className="font-mono text-[13px] text-muted-foreground">404 Not Found</p>
      <h1 className="text-2xl font-semibold tracking-tight">这个页面不存在</h1>
      <p className="max-w-md text-[13px] text-muted-foreground">
        链接可能已失效，或者内容还没上线。试试从课程列表或题库开始吧。
      </p>
      <div className="flex gap-3">
        <Button asChild>
          <Link href="/courses">去看课程</Link>
        </Button>
        <Button variant="outline" asChild>
          <Link href="/problems">去刷题库</Link>
        </Button>
      </div>
    </div>
  );
}
