'use client';

import { SITE_NAME } from '@/lib/constants';

/** 全局错误页：不暴露堆栈，提供返回首页入口。 */
export default function GlobalError({ reset }: { error: Error & { digest?: string }; reset: () => void }): React.ReactElement {
  return (
    <div className="flex min-h-[70vh] flex-col items-center justify-center gap-4 px-4 text-center">
      <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">ERROR</p>
      <h1 className="text-2xl font-semibold tracking-tight">页面出现了一点问题</h1>
      <p className="max-w-md text-[13px] text-muted-foreground">
        可能是后端服务尚未启动或网络波动。你可以重试，或先回到首页继续浏览。
      </p>
      <div className="flex gap-3">
        <button
          type="button"
          onClick={reset}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
        >
          重试
        </button>
        <a
          href="/"
          className="rounded-md border border-border px-4 py-2 text-sm font-medium transition-colors hover:bg-muted"
        >
          返回 {SITE_NAME}
        </a>
      </div>
    </div>
  );
}
