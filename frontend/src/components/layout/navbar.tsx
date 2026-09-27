'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { useTheme } from 'next-themes';
import {
  Bell,
  BookOpen,
  ChevronDown,
  Code2,
  GraduationCap,
  LayoutDashboard,
  LogOut,
  Menu,
  Moon,
  Search,
  Settings,
  Sun,
  Trophy,
  User,
  X,
} from 'lucide-react';
import { MAIN_NAV, SITE_NAME } from '@/lib/constants';
import { cn } from '@/lib/utils';
import { useAuth } from '@/hooks/useAuth';
import { notificationApi } from '@/lib/api';
import type { NotificationOut } from '@/lib/types';
import { Avatar } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Dropdown } from '@/components/ui/dropdown';
import { Input } from '@/components/ui/input';

/** 主题切换按钮。 */
export function ThemeToggle(): React.ReactElement {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);
  const isDark = resolvedTheme !== 'light';

  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label="切换主题"
      onClick={() => setTheme(isDark ? 'light' : 'dark')}
      title={isDark ? '切换到浅色' : '切换到深色'}
    >
      {mounted && isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </Button>
  );
}

/** 通知铃铛：未读数量轮询 + 下拉列表。 */
function NotificationBell(): React.ReactElement {
  const [count, setCount] = useState(0);
  const [items, setItems] = useState<NotificationOut[]>([]);
  const { isAuthenticated } = useAuth();

  useEffect(() => {
    if (!isAuthenticated) return;
    let alive = true;
    const load = (): void => {
      notificationApi
        .unreadCount()
        .then((res) => alive && setCount(res.count))
        .catch(() => undefined);
      notificationApi
        .list({ page: 1, page_size: 5 })
        .then((res) => alive && setItems(res.items))
        .catch(() => undefined);
    };
    load();
    const timer = window.setInterval(load, 60_000);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, [isAuthenticated]);

  return (
    <Dropdown
      items={[
        { label: '查看全部通知', href: '/notifications', icon: <Bell className="h-3.5 w-3.5" /> },
        ...(items.length
          ? items.slice(0, 5).map((item) => ({ label: item.title, href: '/notifications' }))
          : [{ label: '暂无新通知', disabled: true }]),
      ]}
      trigger={({ open }) => (
        <Button variant="ghost" size="icon" aria-label="通知" className={cn(open && 'bg-muted')}>
          <span className="relative">
            <Bell className="h-4 w-4" />
            {count > 0 ? (
              <span className="absolute -right-1.5 -top-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-semibold text-destructive-foreground">
                {count > 99 ? '99+' : count}
              </span>
            ) : null}
          </span>
        </Button>
      )}
    />
  );
}

/** 顶部主导航。 */
export function Navbar(): React.ReactElement {
  const pathname = usePathname();
  const router = useRouter();
  const { user, isAuthenticated, hydrated, logout } = useAuth();
  const [keyword, setKeyword] = useState('');
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => setMobileOpen(false), [pathname]);

  const submitSearch = (event: React.FormEvent): void => {
    event.preventDefault();
    const q = keyword.trim();
    if (!q) return;
    router.push(`/search?q=${encodeURIComponent(q)}`);
  };

  const isActive = (href: string): boolean =>
    href === '/' ? pathname === '/' : pathname === href || pathname.startsWith(`${href}/`);

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/85 backdrop-blur supports-[backdrop-filter]:bg-background/70">
      <div className="mx-auto flex h-14 max-w-[1400px] items-center gap-3 px-4">
        <Link href="/" className="flex shrink-0 items-center gap-2" aria-label={SITE_NAME}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo.svg" alt="" className="h-7 w-7" />
          <span className="hidden text-[15px] font-bold tracking-tight sm:inline">
            PYTHON<span className="text-primary"> LAB</span>
          </span>
        </Link>

        <nav className="hidden items-center gap-0.5 lg:flex" aria-label="主导航">
          {MAIN_NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              title={item.description}
              className={cn(
                'rounded-md px-2.5 py-1.5 text-[13px] font-medium transition-colors',
                isActive(item.href) ? 'bg-muted text-foreground' : 'text-muted-foreground hover:bg-muted/60 hover:text-foreground',
              )}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <form onSubmit={submitSearch} className="ml-auto hidden w-56 md:block xl:w-72">
          <Input
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            placeholder="搜索课程 / 题目 / 项目"
            aria-label="站内搜索"
            icon={<Search className="h-3.5 w-3.5" />}
            className="h-8"
          />
        </form>

        <div className="ml-auto flex items-center gap-1 md:ml-0">
          <ThemeToggle />
          {isAuthenticated ? <NotificationBell /> : null}

          {!hydrated ? (
            <div className="h-8 w-8 animate-pulse-soft rounded-full bg-muted" />
          ) : isAuthenticated && user ? (
            <Dropdown
              items={[
                { label: '学习看板', href: '/dashboard', icon: <LayoutDashboard className="h-3.5 w-3.5" /> },
                { label: '我的课程', href: '/learn', icon: <BookOpen className="h-3.5 w-3.5" /> },
                { label: '我的成就', href: '/achievements', icon: <Trophy className="h-3.5 w-3.5" /> },
                { label: '个人资料', href: '/profile', icon: <User className="h-3.5 w-3.5" /> },
                { label: '设置', href: '/settings', icon: <Settings className="h-3.5 w-3.5" />, separatorBefore: true },
                { label: '退出登录', danger: true, icon: <LogOut className="h-3.5 w-3.5" />, onSelect: () => void logout() },
              ]}
              trigger={({ open }) => (
                <button
                  type="button"
                  className={cn('flex items-center gap-1.5 rounded-full p-0.5 pr-1 transition-colors hover:bg-muted', open && 'bg-muted')}
                  aria-label="用户菜单"
                >
                  <Avatar name={user.display_name ?? user.username} size={30} ring />
                  <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                </button>
              )}
            />
          ) : (
            <div className="flex items-center gap-2">
              <Button variant="ghost" size="sm" onClick={() => router.push('/login')}>
                登录
              </Button>
              <Button size="sm" onClick={() => router.push('/register')}>
                免费注册
              </Button>
            </div>
          )}

          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden"
            aria-label="打开菜单"
            onClick={() => setMobileOpen((prev) => !prev)}
          >
            {mobileOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </Button>
        </div>
      </div>

      {mobileOpen ? (
        <div className="border-t border-border bg-background px-4 py-3 lg:hidden">
          <form onSubmit={submitSearch} className="mb-3">
            <Input
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              placeholder="搜索课程 / 题目 / 项目"
              icon={<Search className="h-3.5 w-3.5" />}
            />
          </form>
          <div className="grid grid-cols-2 gap-2">
            {MAIN_NAV.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  'flex items-center gap-2 rounded-md border border-border px-3 py-2 text-[13px]',
                  isActive(item.href) ? 'bg-muted font-medium' : 'text-muted-foreground',
                )}
              >
                <NavIcon href={item.href} />
                {item.label}
              </Link>
            ))}
          </div>
        </div>
      ) : null}
    </header>
  );
}

function NavIcon({ href }: { href: string }): React.ReactElement {
  if (href === '/editor') return <Code2 className="h-3.5 w-3.5" />;
  if (href === '/courses' || href === '/learn') return <GraduationCap className="h-3.5 w-3.5" />;
  if (href === '/challenges') return <Trophy className="h-3.5 w-3.5" />;
  if (href === '/') return <LayoutDashboard className="h-3.5 w-3.5" />;
  return <BookOpen className="h-3.5 w-3.5" />;
}

/** 未读数徽标的复用导出（其他页面若要展示可用）。 */
export function UnreadBadge({ count }: { count: number }): React.ReactElement | null {
  if (count <= 0) return null;
  return <Badge variant="danger">{count > 99 ? '99+' : count}</Badge>;
}
