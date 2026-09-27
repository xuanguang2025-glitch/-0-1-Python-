'use client';

import { useEffect, useRef, useState } from 'react';
import { cn } from '@/lib/utils';

export interface DropdownItem {
  label: string;
  onSelect?: () => void;
  href?: string;
  icon?: React.ReactNode;
  danger?: boolean;
  disabled?: boolean;
  separatorBefore?: boolean;
}

export interface DropdownProps {
  /** 触发元素，接收 open 状态。 */
  trigger: (state: { open: boolean }) => React.ReactNode;
  items: DropdownItem[];
  align?: 'start' | 'end';
  className?: string;
}

/** 点击外部与 Esc 自动关闭的下拉菜单。 */
export function Dropdown({ trigger, items, align = 'end', className }: DropdownProps): React.ReactElement {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const onClickOutside = (event: MouseEvent): void => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent): void => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onClickOutside);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onClickOutside);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  return (
    <div ref={rootRef} className={cn('relative', className)}>
      <div onClick={() => setOpen((prev) => !prev)}>{trigger({ open })}</div>
      {open ? (
        <div
          role="menu"
          className={cn(
            'absolute top-[calc(100%+6px)] z-40 min-w-[190px] overflow-hidden rounded-lg border border-border bg-popover p-1 shadow-lg animate-fade-in',
            align === 'end' ? 'right-0' : 'left-0',
          )}
        >
          {items.map((item, index) => (
            <div key={`${item.label}-${index}`}>
              {item.separatorBefore ? <div className="my-1 h-px bg-border" /> : null}
              {item.href ? (
                <a
                  href={item.href}
                  role="menuitem"
                  className="flex items-center gap-2 rounded-md px-2.5 py-2 text-[13px] text-popover-foreground transition-colors hover:bg-muted"
                  onClick={() => setOpen(false)}
                >
                  {item.icon}
                  {item.label}
                </a>
              ) : (
                <button
                  type="button"
                  role="menuitem"
                  disabled={item.disabled}
                  className={cn(
                    'flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-[13px] transition-colors hover:bg-muted disabled:opacity-50',
                    item.danger ? 'text-destructive' : 'text-popover-foreground',
                  )}
                  onClick={() => {
                    item.onSelect?.();
                    setOpen(false);
                  }}
                >
                  {item.icon}
                  {item.label}
                </button>
              )}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
