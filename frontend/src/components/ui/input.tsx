'use client';

import { Fragment, cloneElement, isValidElement, useId, useMemo } from 'react';

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

/**
 * HTML 规范定义的 labelable elements（可被 `<label for>` 关联的元素）中，
 * **只保留「接受值的表单控件」**。
 *
 * 刻意排除 `button`：button 通常自带可见文字，其可访问名由内容派生；
 * 一旦用 `<label for>` 关联，部分辅助技术（含 dom-accessibility-api）
 * 会用 label 文本**覆盖**按钮自身的可访问名（本项目实测：
 * `<Field label="操作"><button>提交</button></Field>` 的按钮名从「提交」变成「操作」），
 * 反而削弱可访问性。此外 label 的点击会转发为按钮点击，改变交互行为。
 *
 * @see https://html.spec.whatwg.org/multipage/forms.html#category-label
 */
const LABELABLE_TAGS = new Set(['input', 'meter', 'output', 'progress', 'select', 'textarea']);

/**
 * 把自动生成的 `id` 注入 children，并返回该 id。
 *
 * 返回 `undefined` 表示**不能建立关联**，此时调用方不应渲染 `htmlFor`。
 *
 * 三种情况：
 * 1. children 是原生元素且标签 ∈ LABELABLE_TAGS → 注入（input/select/textarea…）
 * 2. children 是自定义组件（`typeof type !== 'string'`）→ 注入。
 *    本项目的 `Input` / `Select` / `Textarea` 都是转发型（把 `...props` 透传给
 *    原生元素），已核实 `id` 不会被吞掉。
 * 3. 其余 → 不注入。包括：
 *    - Fragment（`type === Symbol(react.fragment)`，虽isValidElement 为 true 但
 *      **只接受 key/children**，注入 id 会产生指向空处的无效关联）
 *    - 数组 / null / 字符串
 *    - `div` 等容器元素（如 `profile/page.tsx:153` 的「时区」字段，本质是分组标题）
 */
function injectControlId(children: React.ReactNode, autoId: string): { child: React.ReactNode; controlId?: string } {
  if (!isValidElement(children)) return { child: children };
  const type = children.type;
  // Fragment 必须先排除：它的 type 是 symbol，会被下面的「自定义组件」分支误判
  if (type === Fragment) return { child: children };
  // 自定义组件：转发型，注入
  if (typeof type !== 'string') return { child: cloneElement(children, { id: autoId } as never), controlId: autoId };
  // 原生元素：仅白名单内可标签化
  if (LABELABLE_TAGS.has(type)) return { child: cloneElement(children, { id: autoId } as never), controlId: autoId };
  return { child: children };
}

export interface FieldProps {
  label: string;
  /**
   * 关联控件的 id。**通常不需要手动传** —— 未传时Field 会用 `useId()` 自动生成
   * 并注入给 children。仅在 children 不是可标签化控件、或需要指向外部控件时才传。
   */
  htmlFor?: string;
  hint?: string;
  error?: string | null;
  required?: boolean;
  children: React.ReactNode;
}

/**
 * 表单字段容器：标签 + 控件 + 提示 / 错误。
 *
 * 自动建立 `<label for>` ↔ 控件 `id` 关联，调用方零改动即可获得可访问性；
 * children 不可标签化时不产生无效关联（见 `injectControlId`）。
 */
export function Field({ label, htmlFor, hint, error, required, children }: FieldProps): React.ReactElement {
  const autoId = useId();
  const injected = useMemo(
    () => (htmlFor ? { child: children } : injectControlId(children, autoId)),
    [children, autoId, htmlFor],
  );
  // 显式传入的 htmlFor 优先；未传且 children 可标签化时用自动生成的 id
  const controlId = htmlFor ?? injected.controlId;

  return (
    <div className="space-y-1.5">
      <Label htmlFor={controlId}>
        {label}
        {required ? <span className="ml-0.5 text-destructive">*</span> : null}
      </Label>
      {injected.child}
      {error ? <p className="text-[12px] text-destructive">{error}</p> : null}
      {!error && hint ? <p className="text-[12px] text-muted-foreground">{hint}</p> : null}
    </div>
  );
}
