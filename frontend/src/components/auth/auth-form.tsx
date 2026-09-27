'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import { ArrowRight, CheckCircle2, Lock, Mail, Terminal, User } from 'lucide-react';
import { SITE_TAGLINE } from '@/lib/constants';
import { cn } from '@/lib/utils';
import { useAuth } from '@/hooks/useAuth';
import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Field, Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';

export interface AuthFormProps {
  mode: 'login' | 'register';
}

const HIGHLIGHTS = [
  '18 阶段系统课程，从语法到工程实战',
  '内置在线编辑器，边学边运行代码',
  '1000+ 分级题目与智能判题反馈',
  'AI 导师随时答疑，只给提示不喂答案',
];

/** 登录 / 注册共用表单。 */
export function AuthForm({ mode }: AuthFormProps): React.ReactElement {
  const isLogin = mode === 'login';
  const router = useRouter();
  const params = useSearchParams();
  const redirect = params.get('redirect') ?? '/dashboard';
  const { login, register, loading, error, clearError, isAuthenticated, hydrated } = useAuth();

  const [account, setAccount] = useState('');
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [localError, setLocalError] = useState<string | null>(null);

  useEffect(() => {
    clearError();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  useEffect(() => {
    if (hydrated && isAuthenticated) router.replace(redirect);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hydrated, isAuthenticated]);

  const submit = async (event: React.FormEvent): Promise<void> => {
    event.preventDefault();
    setLocalError(null);

    if (isLogin) {
      if (!account.trim() || !password) {
        setLocalError('请填写账号与密码');
        return;
      }
      const ok = await login(account.trim(), password);
      if (ok) router.replace(redirect);
      return;
    }

    if (!email.trim() || !username.trim() || !password) {
      setLocalError('请完整填写邮箱、用户名与密码');
      return;
    }
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) {
      setLocalError('请输入有效的邮箱地址');
      return;
    }
    if (!/^[A-Za-z0-9_]{3,20}$/.test(username.trim())) {
      setLocalError('用户名需为 3-20 位字母、数字或下划线');
      return;
    }
    if (password.length < 8) {
      setLocalError('密码至少 8 位');
      return;
    }
    if (password !== confirm) {
      setLocalError('两次输入的密码不一致');
      return;
    }
    const ok = await register({ email: email.trim(), username: username.trim(), password });
    if (ok) router.replace(redirect);
  };

  const message = localError ?? error;

  return (
    <div className="grid min-h-screen lg:grid-cols-[1fr_1.05fr]">
      {/* 左侧品牌区 */}
      <section className="relative hidden flex-col justify-between overflow-hidden border-r border-border bg-card/40 p-10 lg:flex">
        <div
          aria-hidden
          className="pointer-events-none absolute -left-16 top-24 h-64 w-64 rounded-full bg-primary/12 blur-3xl"
        />
        <Link href="/" className="flex items-center gap-2">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo.svg" alt="" className="h-8 w-8" />
          <span className="text-[16px] font-bold tracking-tight">
            PYTHON<span className="text-primary"> LAB</span>
          </span>
        </Link>

        <div className="space-y-6">
          <h2 className="text-2xl font-semibold leading-snug tracking-tight">
            从零开始，
            <br />
            系统掌握 <span className="text-primary">Python</span>
          </h2>
          <p className="max-w-sm text-[13px] text-muted-foreground">{SITE_TAGLINE}</p>
          <ul className="space-y-2.5">
            {HIGHLIGHTS.map((item) => (
              <li key={item} className="flex items-start gap-2 text-[13px] text-muted-foreground">
                <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" />
                {item}
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded-lg border border-border bg-background/60 p-4">
          <div className="flex items-center gap-2 text-[12px] text-muted-foreground">
            <Terminal className="h-3.5 w-3.5" />
            python
          </div>
          <pre className="mt-2 font-mono text-[12px] leading-relaxed">
            <span className="tok-keyword">print</span>(<span className="tok-string">"Hello, Python!"</span>)
          </pre>
        </div>
      </section>

      {/* 右侧表单区 */}
      <section className="flex items-center justify-center px-4 py-10">
        <div className="w-full max-w-sm space-y-6">
          <div className="space-y-2 lg:hidden">
            <Link href="/" className="flex items-center gap-2">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/logo.svg" alt="" className="h-7 w-7" />
              <span className="text-[15px] font-bold">
                PYTHON<span className="text-primary"> LAB</span>
              </span>
            </Link>
          </div>

          <div className="space-y-1.5">
            <Badge variant="secondary">{isLogin ? '欢迎回来' : '创建账号'}</Badge>
            <h1 className="text-xl font-semibold tracking-tight">{isLogin ? '登录 PYTHON LAB' : '免费注册'}</h1>
            <p className="text-[13px] text-muted-foreground">
              {isLogin ? '继续你的学习进度与代码存档。' : '注册后即可解锁全部课程、题库与编辑器。'}
            </p>
          </div>

          {message ? <Alert variant="error" title={message} /> : null}

          <form onSubmit={(event) => void submit(event)} className="space-y-4">
            {isLogin ? (
              <Field label="邮箱或用户名" htmlFor="account" required>
                <Input
                  id="account"
                  value={account}
                  autoComplete="username"
                  placeholder="you@example.com"
                  onChange={(event) => setAccount(event.target.value)}
                  icon={<User className="h-3.5 w-3.5" />}
                />
              </Field>
            ) : (
              <>
                <Field label="邮箱" htmlFor="email" required>
                  <Input
                    id="email"
                    type="email"
                    value={email}
                    autoComplete="email"
                    placeholder="you@example.com"
                    onChange={(event) => setEmail(event.target.value)}
                    icon={<Mail className="h-3.5 w-3.5" />}
                  />
                </Field>
                <Field label="用户名" htmlFor="username" hint="3-20 位字母、数字或下划线" required>
                  <Input
                    id="username"
                    value={username}
                    autoComplete="nickname"
                    placeholder="pythonista"
                    onChange={(event) => setUsername(event.target.value)}
                    icon={<User className="h-3.5 w-3.5" />}
                  />
                </Field>
              </>
            )}

            <Field label="密码" htmlFor="password" required hint={isLogin ? undefined : '至少 8 位，建议包含字母与数字'}>
              <Input
                id="password"
                type="password"
                value={password}
                autoComplete={isLogin ? 'current-password' : 'new-password'}
                placeholder="••••••••"
                onChange={(event) => setPassword(event.target.value)}
                icon={<Lock className="h-3.5 w-3.5" />}
              />
            </Field>

            {!isLogin ? (
              <Field label="确认密码" htmlFor="confirm" required>
                <Input
                  id="confirm"
                  type="password"
                  value={confirm}
                  autoComplete="new-password"
                  placeholder="••••••••"
                  onChange={(event) => setConfirm(event.target.value)}
                  icon={<Lock className="h-3.5 w-3.5" />}
                />
              </Field>
            ) : null}

            <Button type="submit" className="w-full" size="lg" loading={loading}>
              {isLogin ? '登录' : '注册并开始学习'}
              <ArrowRight className="h-4 w-4" />
            </Button>
          </form>

          <p className="text-center text-[12.5px] text-muted-foreground">
            {isLogin ? '还没有账号？' : '已经有账号了？'}
            <Link
              href={isLogin ? '/register' : '/login'}
              className={cn('ml-1 font-medium text-primary hover:underline')}
            >
              {isLogin ? '立即注册' : '去登录'}
            </Link>
          </p>

          {!isLogin ? (
            <p className="text-center text-[11px] leading-relaxed text-muted-foreground">
              注册即表示你同意平台的学习数据仅用于个性化推荐与统计。
            </p>
          ) : null}
        </div>
      </section>
    </div>
  );
}
