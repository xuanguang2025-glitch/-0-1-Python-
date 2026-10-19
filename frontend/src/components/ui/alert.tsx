'use client';

import { AlertTriangle, CheckCircle2, Info, RefreshCw, XCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from './button';

export type AlertVariant = 'info' | 'success' | 'warning' | 'error';

const STYLES: Record<AlertVariant, { wrap: string; icon: React.ReactNode }> = {
  info: { wrap: 'border-sky-500/30 bg-sky-500/8 text-sky-600 dark:text-sky-400', icon: <Info className="h-4 w-4" /> },
  success: {
    wrap: 'border-emerald-500/30 bg-emerald-500/8 text-emerald-600 dark:text-emerald-400',
    icon: <CheckCircle2 className="h-4 w-4" />,
  },
  warning: {
    wrap: 'border-amber-500/30 bg-amber-500/8 text-amber-600 dark:text-amber-400',
    icon: <AlertTriangle className="h-4 w-4" />,
  },
  error: {
    wrap: 'border-rose-500/30 bg-rose-500/8 text-rose-600 dark:text-rose-400',
    icon: <XCircle className="h-4 w-4" />,
  },
};

export interface AlertProps {
  variant?: AlertVariant;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
  children?: React.ReactNode;
}

/**
 * 各 variant 的实时播报分级（live region）。
 *
 * - `error` → `role="alert"`：隐含 `aria-live="assertive"`，**立即**打断播报。
 *   只给「用户必须马上知道」的错误用——目前全站 2 处：登录/注册失败
 *   （`auth-form.tsx`）、判题运行错误（`problem-detail-view.tsx`）。
 * - 其余三种 → `role="status"`：隐含 `aria-live="polite"`，等读完当前内容再播报。
 *
 * **为什么 `warning` 不做 assertive**（本项目的实际用法决定的，不是通用惯例）：
 * warning 承载的多是「降级提示」而非紧急状况——
 *   · dashboard「部分数据暂时无法获取…页面其余内容仍可正常使用」
 *   · admin「无法获取依赖状态／后端健康检查接口暂不可用」
 *   · project「项目尚未初始化」（其实是引导文案）
 *   · **随堂练习未通过的判题结果**（`lesson-view.tsx` 用 `passed ? 'success' : 'warning'`）
 * 对这些内容打断用户当前朗读是负体验；尤其判题结果是用户正等着看的反馈。
 *
 * 两个刻意的「不做」：
 * 1. 不显式写 `aria-live` / `aria-atomic`——role 已隐含
 *    （alert → assertive + atomic；status → polite + atomic），重复写属冗余。
 * 2. role 只落在**最外层 div**：挂在内部元素上读屏软件不会播报整条提示。
 */
const LIVE_ROLE: Record<AlertVariant, 'alert' | 'status'> = {
  error: 'alert',
  warning: 'status',
  success: 'status',
  info: 'status',
};

/** 提示条。 */
export function Alert({ variant = 'info', title, description, action, className, children }: AlertProps): React.ReactElement {
  const style = STYLES[variant];
  return (
    <div role={LIVE_ROLE[variant]} className={cn('flex items-start gap-2.5 rounded-lg border p-3', style.wrap, className)}>
      <span className="mt-0.5 shrink-0">{style.icon}</span>
      <div className="min-w-0 flex-1 space-y-1">
        <p className="text-[13px] font-medium">{title}</p>
        {description ? <p className="text-[12px] leading-relaxed opacity-85">{description}</p> : null}
        {children}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}

export interface ErrorStateProps {
  title?: string;
  description?: string;
  onRetry?: () => void;
  className?: string;
}

/**
 * 接口失败占位：后端未就绪时页面统一渲染它，绝不白屏。
 *
 * `role="alert"`（隐含 `aria-live="assertive"`）：**加在最外层 div**，与 `Alert`
 * 的 `error` variant 同级——都是「用户必须立刻知道」的错误。
 *
 * 关键前提（曾被我误判为「静态占位、加了没用」）：它**不是**页面加载就存在的，
 * 而是在请求失败之后才插入 DOM 的。典型形态（全站 17 处一致）：
 * ```
 * {loading && !data ? <Skeleton/> : error && !data ? <ErrorState/> : ...}
 * ```
 * 加载中显示骨架屏，骨架消失、错误提示出现——这正是 live region 必须覆盖的瞬间。
 * 没有播报的话，读屏用户只看到骨架消失，会以为页面是空的。
 *
 * 为什么不加 `aria-label`：`role="alert"` 是 name-from-author-only，可访问名称
 * 为空是**正常**的；播报依据是子树内容，所以 title/description 必须留在本区域内。
 *
 * 兄弟组件 `EmptyState` 刻意**不加** role：它表达「暂无数据」这一正常业务态
 * （49 处「暂无课程/暂无题目」），是用户主动查询后的预期结果之一，不是异常，
 * 用 `role="status"` 都属过重。
 */
export function ErrorState({
  title = '数据暂时加载失败',
  description = '后端服务可能尚未启动，稍后重试即可。',
  onRetry,
  className,
}: ErrorStateProps): React.ReactElement {
  return (
    <div
      role="alert"
      className={cn(
        'flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border bg-muted/25 px-6 py-10 text-center',
        className,
      )}
    >
      <AlertTriangle className="h-6 w-6 text-amber-500" />
      <div className="space-y-1">
        <p className="text-sm font-medium">{title}</p>
        <p className="text-[12px] text-muted-foreground">{description}</p>
      </div>
      {onRetry ? (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RefreshCw className="h-3.5 w-3.5" />
          重新加载
        </Button>
      ) : null}
    </div>
  );
}

export interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}

/** 空态占位。 */
export function EmptyState({ icon, title, description, action, className }: EmptyStateProps): React.ReactElement {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border px-6 py-12 text-center',
        className,
      )}
    >
      {icon ? <span className="text-muted-foreground">{icon}</span> : null}
      <div className="space-y-1">
        <p className="text-sm font-medium">{title}</p>
        {description ? <p className="mx-auto max-w-md text-[12px] text-muted-foreground">{description}</p> : null}
      </div>
      {action}
    </div>
  );
}
