'use client';

import { cn } from '@/lib/utils';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  /** 输入框左侧图标。 */
  icon?: React.ReactNode;
  /** 是否处于错误态。 */
  invalid?: boolean;
}

/** 文本输入框。 */
export function Input({ className, icon, invalid = false, ...props }: InputProps): React.ReactElement {
  const input = (
    <input
      className={cn(
        'h-9 w-full rounded-md border bg-transparent px-3 text-sm transition-colors placeholder:text-muted-foreground',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background',
        'disabled:cursor-not-allowed disabled:opacity-60',
        invalid ? 'border-destructive focus-visible:ring-destructive' : 'border-input',
        icon ? 'pl-9' : '',
        className,
      )}
      {...props}
    />
  );
  if (!icon) return input;
  return (
    <div className="relative w-full">
      <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">{icon}</span>
      {input}
    </div>
  );
}

export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  invalid?: boolean;
}

/** 多行文本输入。 */
export function Textarea({ className, invalid = false, ...props }: TextareaProps): React.ReactElement {
  return (
    <textarea
      className={cn(
        'w-full rounded-md border bg-transparent p-3 text-sm transition-colors placeholder:text-muted-foreground',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background',
        invalid ? 'border-destructive' : 'border-input',
        className,
      )}
      {...props}
    />
  );
}

export function Label({ className, ...props }: React.LabelHTMLAttributes<HTMLLabelElement>): React.ReactElement {
  return <label className={cn('text-[13px] font-medium text-foreground', className)} {...props} />;
}

export interface FieldProps {
  label: string;
  htmlFor?: string;
  hint?: string;
  error?: string | null;
  required?: boolean;
  children: React.ReactNode;
}

/** 表单字段容器：标签 + 控件 + 提示 / 错误。 */
export function Field({ label, htmlFor, hint, error, required, children }: FieldProps): React.ReactElement {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={htmlFor}>
        {label}
        {required ? <span className="ml-0.5 text-destructive">*</span> : null}
      </Label>
      {children}
      {error ? <p className="text-[12px] text-destructive">{error}</p> : null}
      {!error && hint ? <p className="text-[12px] text-muted-foreground">{hint}</p> : null}
    </div>
  );
}
