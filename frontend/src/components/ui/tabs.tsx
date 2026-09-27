'use client';

import { createContext, useContext, useId, useState } from 'react';
import { cn } from '@/lib/utils';

interface TabsContextValue {
  value: string;
  setValue: (value: string) => void;
  baseId: string;
}

const TabsContext = createContext<TabsContextValue | null>(null);

function useTabsContext(): TabsContextValue {
  const ctx = useContext(TabsContext);
  if (!ctx) throw new Error('Tabs 子组件必须在 <Tabs> 内使用');
  return ctx;
}

export interface TabsProps {
  value?: string;
  defaultValue?: string;
  onValueChange?: (value: string) => void;
  className?: string;
  children: React.ReactNode;
}

/** 标签页容器（受控 / 非受控皆可）。 */
export function Tabs({ value, defaultValue = '', onValueChange, className, children }: TabsProps): React.ReactElement {
  const [inner, setInner] = useState(defaultValue);
  const baseId = useId();
  const current = value ?? inner;

  const setValue = (next: string): void => {
    if (value === undefined) setInner(next);
    onValueChange?.(next);
  };

  return (
    <TabsContext.Provider value={{ value: current, setValue, baseId }}>
      <div className={className}>{children}</div>
    </TabsContext.Provider>
  );
}

export function TabsList({ className, ...props }: React.HTMLAttributes<HTMLDivElement>): React.ReactElement {
  return (
    <div
      role="tablist"
      className={cn('inline-flex items-center gap-1 rounded-lg border border-border bg-muted/50 p-1', className)}
      {...props}
    />
  );
}

export interface TabsTriggerProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  value: string;
}

export function TabsTrigger({ value, className, children, ...props }: TabsTriggerProps): React.ReactElement {
  const { value: current, setValue, baseId } = useTabsContext();
  const active = current === value;
  return (
    <button
      type="button"
      role="tab"
      id={`${baseId}-tab-${value}`}
      aria-selected={active}
      onClick={() => setValue(value)}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[13px] font-medium transition-colors',
        active ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground',
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}

export interface TabsContentProps extends React.HTMLAttributes<HTMLDivElement> {
  value: string;
}

export function TabsContent({ value, className, children, ...props }: TabsContentProps): React.ReactElement | null {
  const { value: current, baseId } = useTabsContext();
  if (current !== value) return null;
  return (
    <div role="tabpanel" id={`${baseId}-panel-${value}`} className={cn('animate-fade-in', className)} {...props}>
      {children}
    </div>
  );
}
