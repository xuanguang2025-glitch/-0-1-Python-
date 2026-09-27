'use client';

import dynamic from 'next/dynamic';
import { useCallback } from 'react';
import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useThemeStore } from '@/store/theme';

/** Monaco 官方主题名映射。 */
function monacoTheme(resolved: 'light' | 'dark'): string {
  return resolved === 'dark' ? 'vs-dark' : 'light';
}

/** Monaco 体积大且依赖 window，必须禁用 SSR 懒加载。 */
const Monaco = dynamic(() => import('@monaco-editor/react'), {
  ssr: false,
  loading: () => (
    <div className="flex h-full min-h-[240px] w-full items-center justify-center bg-muted/40 text-muted-foreground">
      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
      <span className="text-[13px]">编辑器加载中…</span>
    </div>
  ),
});

export interface MonacoEditorProps {
  value: string;
  onChange?: (value: string) => void;
  language?: string;
  /** 高度，默认自适应父容器。 */
  height?: string | number;
  readOnly?: boolean;
  fontSize?: number;
  minimap?: boolean;
  wordWrap?: boolean;
  /** Ctrl/Cmd + Enter。 */
  onRun?: () => void;
  /** Ctrl/Cmd + S。 */
  onSave?: () => void;
  className?: string;
  options?: Record<string, unknown>;
}

/**
 * Monaco Editor 封装：
 * - 禁用 SSR（Next.js App Router 下必须）
 * - 跟随全局主题（深 / 浅）
 * - 内置 Ctrl+Enter 运行、Ctrl+S 保存快捷键
 */
export function MonacoEditor({
  value,
  onChange,
  language = 'python',
  height = '100%',
  readOnly = false,
  fontSize = 14,
  minimap = false,
  wordWrap = true,
  onRun,
  onSave,
  className,
  options,
}: MonacoEditorProps): React.ReactElement {
  const resolved = useThemeStore((state) => state.resolved);

  const handleMount = useCallback(
    (editor: unknown, monaco: unknown): void => {
      const m = monaco as { KeyMod?: { CtrlCmd: number }; KeyCode?: { Enter: number; KeyS: number } };
      const ed = editor as {
        addCommand: (keybinding: number, handler: () => void) => void;
        getAction?: (id: string) => { run: () => void } | null;
      };
      if (!m.KeyMod || !m.KeyCode || typeof ed.addCommand !== 'function') return;
      if (onRun) ed.addCommand(m.KeyMod.CtrlCmd | m.KeyCode.Enter, onRun);
      if (onSave) ed.addCommand(m.KeyMod.CtrlCmd | m.KeyCode.KeyS, onSave);
    },
    [onRun, onSave],
  );

  return (
    <div className={cn('h-full w-full overflow-hidden', className)}>
      <Monaco
        height={height}
        language={language}
        theme={monacoTheme(resolved)}
        value={value}
        onChange={(next) => onChange?.(next ?? '')}
        onMount={handleMount}
        options={{
          fontSize,
          readOnly,
          minimap: { enabled: minimap },
          wordWrap: wordWrap ? 'on' : 'off',
          lineNumbers: 'on',
          folding: true,
          foldingStrategy: 'indentation',
          automaticLayout: true,
          tabSize: 4,
          insertSpaces: true,
          renderWhitespace: 'selection',
          scrollBeyondLastLine: false,
          smoothScrolling: true,
          cursorBlinking: 'smooth',
          fontFamily: "'JetBrains Mono', 'Cascadia Code', Consolas, monospace",
          padding: { top: 12, bottom: 12 },
          bracketPairColorization: { enabled: true },
          guides: { indentation: true },
          ...options,
        }}
      />
    </div>
  );
}
