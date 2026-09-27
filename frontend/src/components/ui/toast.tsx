'use client';

import { AlertTriangle, CheckCircle2, Info, X, XCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useUiStore, type ToastVariant } from '@/store/ui';

const ICONS: Record<ToastVariant, React.ReactNode> = {
  default: <Info className="h-4 w-4" />,
  info: <Info className="h-4 w-4 text-sky-500" />,
  success: <CheckCircle2 className="h-4 w-4 text-emerald-500" />,
  error: <XCircle className="h-4 w-4 text-rose-500" />,
  warning: <AlertTriangle className="h-4 w-4 text-amber-500" />,
};

const BORDERS: Record<ToastVariant, string> = {
  default: 'border-border',
  info: 'border-sky-500/35',
  success: 'border-emerald-500/35',
  error: 'border-rose-500/35',
  warning: 'border-amber-500/35',
};

/** Toast 容器：挂载在 RootLayout（Providers）中，读取 zustand 队列渲染。 */
export function Toaster(): React.ReactElement {
  const toasts = useUiStore((state) => state.toasts);
  const dismiss = useUiStore((state) => state.dismiss);

  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-[min(360px,calc(100vw-2rem))] flex-col gap-2">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          role="status"
          className={cn(
            'pointer-events-auto flex items-start gap-2.5 rounded-lg border bg-popover p-3 shadow-lg animate-slide-up',
            BORDERS[toast.variant],
          )}
        >
          <span className="mt-0.5 shrink-0">{ICONS[toast.variant]}</span>
          <div className="min-w-0 flex-1">
            <p className="text-[13px] font-medium leading-tight">{toast.title}</p>
            {toast.description ? (
              <p className="mt-1 text-[12px] leading-snug text-muted-foreground">{toast.description}</p>
            ) : null}
          </div>
          <button
            type="button"
            aria-label="关闭提示"
            className="shrink-0 rounded p-0.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            onClick={() => dismiss(toast.id)}
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      ))}
    </div>
  );
}
