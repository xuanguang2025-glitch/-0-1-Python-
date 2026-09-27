'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';

export interface SidebarItem {
  label: string;
  href: string;
  icon?: React.ReactNode;
  badge?: string | number;
}

export interface SidebarGroup {
  title?: string;
  items: SidebarItem[];
}

export interface SidebarProps {
  groups: SidebarGroup[];
  /** 顶部标题。 */
  title?: string;
  className?: string;
  /** 紧凑模式（用于课程目录等）。 */
  dense?: boolean;
  footer?: React.ReactNode;
}

/** 通用侧边导航：支持分组、当前项高亮、窄屏横向滚动。 */
export function Sidebar({ groups, title, className, dense = false, footer }: SidebarProps): React.ReactElement {
  const pathname = usePathname();

  return (
    <aside className={cn('w-full shrink-0 lg:w-60', className)}>
      <nav
        className={cn(
          'scroll-area flex gap-1 overflow-x-auto rounded-lg border border-border bg-card p-2 lg:sticky lg:top-[4.5rem] lg:max-h-[calc(100vh-6rem)] lg:flex-col lg:overflow-x-hidden',
          dense ? 'lg:gap-0.5' : 'lg:gap-1',
        )}
        aria-label={title ?? '侧边导航'}
      >
        {title ? <p className="hidden px-2 pb-1 pt-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground lg:block">{title}</p> : null}

        {groups.map((group, groupIndex) => (
          <div key={group.title ?? groupIndex} className="flex shrink-0 flex-row items-center gap-1 lg:flex-col lg:items-stretch">
            {group.title ? (
              <p className="hidden px-2 pt-3 pb-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground lg:block">
                {group.title}
              </p>
            ) : null}
            {group.items.map((item) => {
              const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    'flex shrink-0 items-center gap-2 whitespace-nowrap rounded-md px-2.5 py-2 text-[13px] font-medium transition-colors',
                    dense ? 'lg:text-[12.5px]' : '',
                    active
                      ? 'bg-primary/12 text-primary'
                      : 'text-muted-foreground hover:bg-muted/70 hover:text-foreground',
                  )}
                >
                  {item.icon}
                  <span>{item.label}</span>
                  {item.badge !== undefined ? (
                    <span className="ml-auto rounded-full bg-muted px-1.5 text-[10px] text-muted-foreground">{item.badge}</span>
                  ) : null}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>
      {footer ? <div className="mt-3 hidden lg:block">{footer}</div> : null}
    </aside>
  );
}
