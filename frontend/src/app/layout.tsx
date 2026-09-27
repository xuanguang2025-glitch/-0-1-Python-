import type { Metadata, Viewport } from 'next';
import { SITE_NAME, SITE_SUBTITLE, SITE_TAGLINE } from '@/lib/constants';
import { Providers } from './providers';
import './globals.css';

export const metadata: Metadata = {
  title: {
    default: `${SITE_NAME} · ${SITE_TAGLINE}`,
    template: `%s · ${SITE_NAME}`,
  },
  description: SITE_SUBTITLE,
  keywords: ['Python', '编程学习', '在线编辑器', '算法题', 'AI 导师', 'PYTHON LAB'],
  manifest: '/manifest.json',
  icons: { icon: '/logo.svg', apple: '/logo.svg' },
  applicationName: SITE_NAME,
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  themeColor: [
    { media: '(prefers-color-scheme: dark)', color: '#0B1220' },
    { media: '(prefers-color-scheme: light)', color: '#F7F9FB' },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body className="min-h-screen bg-background text-foreground antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
