'use client';

import { ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface SelectProps extends Omit<React.SelectHTMLAttributes<HTMLSelectElement>, 'children' | 'size'> {
  options: SelectOption[];
  /** 未选中时显示的占位项（value 为空字符串）。 */
  placeholder?: string;
  /** 高度尺寸（避免与原生 size 属性冲突而改名）。 */
  controlSize?: 'sm' | 'md';
}

/** 原生 select 的样式封装：可靠、可访问、无额外依赖。 */
export function Select({
  options,
  placeholder,
  className,
  controlSize = 'md',
  value,
  ...props
}: SelectProps): React.ReactElement {
  const isEmpty = value === undefined || value === null || value === '';
  return (
    <div className="relative inline-flex w-full">
      <select
        value={value}
        className={cn(
          'w-full appearance-none rounded-md border border-input bg-transparent pr-8 text-sm transition-colors',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background',
          'disabled:cursor-not-allowed disabled:opacity-60',
          controlSize === 'sm' ? 'h-8 pl-2.5 text-[13px]' : 'h-9 pl-3',
          className,
        )}
        {...props}
      >
        {placeholder ? (
          <option value="" disabled hidden={!isEmpty}>
            {placeholder}
          </option>
        ) : null}
        {options.map((option) => (
          <option key={option.value} value={option.value} disabled={option.disabled}>
            {option.label}
          </option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
    </div>
  );
}
