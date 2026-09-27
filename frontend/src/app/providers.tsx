'use client';

import { useEffect } from 'react';
import { ThemeProvider, useTheme } from 'next-themes';
import { useThemeStore } from '@/store/theme';
import { Toaster } from '@/components/ui/toast';

/** 把 next-themes 的解析结果同步到 zustand（供 Monaco 等使用）。 */
function ThemeSync(): null {
  const { resolvedTheme } = useTheme();
  const setResolved = useThemeStore((state) => state.setResolved);

  useEffect(() => {
    if (resolvedTheme === 'light' || resolvedTheme === 'dark') {
      setResolved(resolvedTheme);
    }
  }, [resolvedTheme, setResolved]);

  return null;
}

export interface ProvidersProps {
  children: React.ReactNode;
}

/**
 * 全局 Provider：
 * - next-themes（class 策略，默认深色）
 * - Toast 容器
 */
export function Providers({ children }: ProvidersProps): React.ReactElement {
  return (
    <ThemeProvider attribute="class" defaultTheme="dark" enableSystem disableTransitionOnChange>
      <ThemeSync />
      {children}
      <Toaster />
    </ThemeProvider>
  );
}
