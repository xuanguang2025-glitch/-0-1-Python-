'use client';

import { cn } from '@/lib/utils';
import { Navbar } from './navbar';
import { Footer } from './footer';

export interface PageContainerProps {
  children: React.ReactNode;
  /** 页面标题（渲染在内容顶部）。 */
  title?: string;
  description?: string;
  /** 标题右侧操作区。 */
  actions?: React.ReactNode;
  /** 左侧侧边栏节点。 */
  sidebar?: React.ReactNode;
  /** 是否展示页脚。 */
  showFooter?: boolean;
  /** 是否展示顶部导航（编辑器等全屏页可关闭）。 */
  showNavbar?: boolean;
  /** 内容最大宽度。 */
  width?: 'default' | 'wide' | 'full' | 'prose';
  className?: string;
  contentClassName?: string;
}

const WIDTHS = {
  default: 'max-w-[1400px]',
  wide: 'max-w-[1600px]',
  full: 'max-w-none',
  prose: 'max-w-3xl',
} as const;

/** 页面骨架：统一导航、宽度、间距、页脚。 */
export function PageContainer({
  children,
  title,
  description,
  actions,
  sidebar,
  showFooter = true,
  showNavbar = true,
  width = 'default',
  className,
  contentClassName,
}: PageContainerProps): React.ReactElement {
  return (
    <div className={cn('flex min-h-screen flex-col bg-background', className)}>
      {showNavbar ? <Navbar /> : null}

      <main className={cn('mx-auto w-full flex-1 px-4 py-6', WIDTHS[width], contentClassName)}>
        {title ? (
          <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
            <div className="space-y-1">
              <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
              {description ? <p className="text-[13px] text-muted-foreground">{description}</p> : null}
            </div>
            {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
          </div>
        ) : null}

        {sidebar ? (
          <div className="flex flex-col gap-5 lg:flex-row">
            {sidebar}
            <div className="min-w-0 flex-1">{children}</div>
          </div>
        ) : (
          children
        )}
      </main>

      {showFooter ? <Footer /> : null}
    </div>
  );
}
