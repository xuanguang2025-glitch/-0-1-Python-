'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Bot,
  Loader2,
  MessageSquarePlus,
  Send,
  Sparkles,
  Trash2,
  WifiOff,
  Zap,
} from 'lucide-react';
import { aiApi } from '@/lib/api';
import { AI_MODE_DESC, AI_MODE_LABEL } from '@/lib/constants';
import { cn } from '@/lib/utils';
import { useFetch } from '@/hooks/useFetch';
import { useAuth } from '@/hooks/useAuth';
import { useToaster } from '@/hooks/useToast';
import { AuthGate } from '@/components/common/auth-gate';
import { Markdown } from '@/components/markdown';
import { PageContainer } from '@/components/layout/page-container';
import { Alert, EmptyState } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Textarea } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import type { AiHintLevel, AiMode } from '@/lib/types';

interface Bubble {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  degraded?: boolean;
  kind?: string;
}

const LEVEL_OPTIONS: { value: AiHintLevel; label: string }[] = [
  { value: 'hint', label: '只给提示' },
  { value: 'approach', label: '给方法思路' },
  { value: 'partial', label: '给部分代码' },
  { value: 'full', label: '给完整答案' },
  { value: 'explain', label: '讲解原理' },
];

const QUICK_PROMPTS = [
  '列表推导式和 for 循环该怎么选？',
  '为什么我的函数修改了列表？',
  '解释一下生成器和迭代器的区别',
  '这道题用什么都行不通，帮我理思路',
  '给我一道适合练 dict 的小题目',
];

/** AI 导师：对话式答疑，三档模式 + 提示级别 + 离线降级。 */
function AiTutorContent(): React.ReactElement {
  const toaster = useToaster();
  const { isAuthenticated } = useAuth();

  const status = useFetch(() => aiApi.status(), [], { enabled: isAuthenticated });
  const conversations = useFetch(() => aiApi.conversations({ page: 1, page_size: 20 }), [], { enabled: isAuthenticated });

  const [mode, setMode] = useState<AiMode>('standard');
  const [level, setLevel] = useState<AiHintLevel>('approach');
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Bubble[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>(QUICK_PROMPTS.slice(0, 3));
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, sending]);

  const degraded = status.data?.degraded ?? false;

  const openConversation = async (id: string): Promise<void> => {
    setConversationId(id);
    try {
      const detail = await aiApi.conversation(id);
      setMessages(
        detail.messages.map((message) => ({
          id: message.id,
          role: message.role === 'user' ? 'user' : 'assistant',
          content: message.content_md,
          kind: message.kind,
        })),
      );
    } catch {
      toaster.error('会话加载失败');
    }
  };

  const send = async (text: string): Promise<void> => {
    const message = text.trim();
    if (!message || sending) return;
    setMessages((prev) => [...prev, { id: `u-${Date.now()}`, role: 'user', content: message }]);
    setInput('');
    setSending(true);
    try {
      const response = await aiApi.chat({
        conversation_id: conversationId ?? undefined,
        message,
        mode,
        scene: 'tutor',
        level,
      });
      setConversationId(response.conversation_id);
      setMessages((prev) => [
        ...prev,
        { id: response.message_id, role: 'assistant', content: response.content_md, degraded: response.degraded, kind: response.kind },
      ]);
      if (response.suggestions?.length) setSuggestions(response.suggestions);
      conversations.refresh();
    } catch (error) {
      const raw = error instanceof Error ? error.message : '未知错误';
      const friendly = raw.includes('FULL_ANSWER')
        ? '练习模式下不直接给完整答案，换一个提示级别或者自己再试试。'
        : raw;
      setMessages((prev) => [
        ...prev,
        { id: `e-${Date.now()}`, role: 'assistant', content: `暂时无法连接 AI 服务：${friendly}`, degraded: true },
      ]);
    } finally {
      setSending(false);
    }
  };

  const newConversation = (): void => {
    setConversationId(null);
    setMessages([]);
    setSuggestions(QUICK_PROMPTS.slice(0, 3));
  };

  const removeConversation = async (id: string): Promise<void> => {
    try {
      await aiApi.deleteConversation(id);
      if (conversationId === id) newConversation();
      conversations.refresh();
      toaster.success('已删除会话');
    } catch {
      toaster.error('删除失败');
    }
  };

  const quotaLabel = useMemo(() => {
    if (!status.data) return '—';
    if (status.data.remaining_quota < 0) return '不限';
    return `${status.data.remaining_quota} 次`;
  }, [status.data]);

  return (
    <PageContainer width="wide">
      <div className="grid gap-4 lg:grid-cols-[240px_minmax(0,1fr)_260px]">
        {/* 会话列表 */}
        <aside className="space-y-3">
          <Button className="w-full" onClick={newConversation}>
            <MessageSquarePlus className="h-4 w-4" />
            新建对话
          </Button>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle>历史会话</CardTitle>
            </CardHeader>
            <CardContent className="space-y-1">
              {conversations.loading && !conversations.data ? (
                <>
                  <Skeleton className="h-8 w-full" />
                  <Skeleton className="h-8 w-full" />
                </>
              ) : conversations.data && conversations.data.items.length > 0 ? (
                conversations.data.items.map((item) => (
                  <div
                    key={item.id}
                    className={cn(
                      'group flex items-center gap-1 rounded-md px-2 py-1.5 transition-colors',
                      conversationId === item.id ? 'bg-primary/12' : 'hover:bg-muted',
                    )}
                  >
                    <button
                      type="button"
                      onClick={() => void openConversation(item.id)}
                      className="min-w-0 flex-1 truncate text-left text-[12.5px]"
                    >
                      {item.title || '未命名对话'}
                    </button>
                    <Button
                      size="icon-sm"
                      variant="ghost"
                      aria-label="删除会话"
                      className="opacity-0 group-hover:opacity-100"
                      onClick={() => void removeConversation(item.id)}
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  </div>
                ))
              ) : (
                <p className="py-2 text-[12px] text-muted-foreground">还没有会话记录</p>
              )}
            </CardContent>
          </Card>
        </aside>

        {/* 对话区 */}
        <main className="min-w-0 space-y-3">
          <Card>
            <CardHeader className="gap-3 pb-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="flex items-center gap-1.5 text-[14px] font-semibold">
                  <Bot className="h-4 w-4 text-primary" />
                  AI 学习导师
                </span>
                {degraded ? (
                  <Badge variant="warning" className="gap-1">
                    <WifiOff className="h-3 w-3" />
                    离线助手
                  </Badge>
                ) : (
                  <Badge variant="success" className="gap-1">
                    <Sparkles className="h-3 w-3" />
                    {status.data?.model ?? 'AI 在线'}
                  </Badge>
                )}
                <div className="ml-auto flex items-center gap-2">
                  <span className="hidden text-[11px] text-muted-foreground sm:inline">提示级别</span>
                  <div className="w-32">
                    <Select
                      controlSize="sm"
                      value={level}
                      options={LEVEL_OPTIONS}
                      onChange={(event) => setLevel(event.target.value as AiHintLevel)}
                    />
                  </div>
                </div>
              </div>

              <Tabs value={mode} onValueChange={(value) => setMode(value as AiMode)}>
                <TabsList>
                  {(['beginner', 'standard', 'advanced'] as AiMode[]).map((item) => (
                    <TabsTrigger key={item} value={item}>
                      {AI_MODE_LABEL[item]}
                    </TabsTrigger>
                  ))}
                </TabsList>
              </Tabs>
              <p className="text-[11.5px] text-muted-foreground">{AI_MODE_DESC[mode]}</p>
            </CardHeader>

            <CardContent className="space-y-3">
              <div ref={scrollRef} className="scroll-area h-[420px] space-y-3 rounded-lg border border-border bg-muted/20 p-3">
                {messages.length === 0 ? (
                  <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
                    <Bot className="h-7 w-7 text-primary" />
                    <p className="text-[13px] font-medium">有什么 Python 问题都可以问我</p>
                    <p className="max-w-sm text-[12px] text-muted-foreground">
                      练习模式下我默认只给提示和方法，不直接给完整答案 —— 这样你才能真正学会。
                    </p>
                    <div className="flex flex-wrap justify-center gap-1.5">
                      {QUICK_PROMPTS.slice(0, 3).map((prompt) => (
                        <button
                          key={prompt}
                          type="button"
                          onClick={() => void send(prompt)}
                          className="rounded-full border border-border px-2.5 py-1 text-[11.5px] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                        >
                          {prompt}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : (
                  messages.map((bubble) => (
                    <div
                      key={bubble.id}
                      className={cn(
                        'flex gap-2.5',
                        bubble.role === 'user' ? 'justify-end' : 'justify-start',
                      )}
                    >
                      {bubble.role === 'assistant' ? (
                        <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary">
                          <Bot className="h-3.5 w-3.5" />
                        </span>
                      ) : null}
                      <div
                        className={cn(
                          'max-w-[86%] rounded-lg border p-3',
                          bubble.role === 'user'
                            ? 'border-primary/30 bg-primary/12'
                            : 'border-border bg-card',
                        )}
                      >
                        {bubble.degraded ? (
                          <Badge variant="warning" className="mb-1.5">
                            离线助手
                          </Badge>
                        ) : null}
                        {bubble.role === 'user' ? (
                          <p className="whitespace-pre-wrap text-[13px]">{bubble.content}</p>
                        ) : (
                          <Markdown content={bubble.content} />
                        )}
                      </div>
                    </div>
                  ))
                )}

                {sending ? (
                  <div className="flex items-center gap-2 text-[12px] text-muted-foreground">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    AI 正在思考…
                  </div>
                ) : null}
              </div>

              {suggestions.length > 0 ? (
                <div className="flex flex-wrap gap-1.5">
                  {suggestions.map((item) => (
                    <button
                      key={item}
                      type="button"
                      onClick={() => void send(item)}
                      className="rounded-full border border-border px-2.5 py-1 text-[11.5px] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                    >
                      {item}
                    </button>
                  ))}
                </div>
              ) : null}

              <div className="flex items-end gap-2">
                <Textarea
                  rows={2}
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' && !event.shiftKey) {
                      event.preventDefault();
                      void send(input);
                    }
                  }}
                  placeholder="描述你的问题（Enter 发送，Shift + Enter 换行）"
                />
                <Button size="icon" loading={sending} onClick={() => void send(input)} aria-label="发送">
                  <Send className="h-4 w-4" />
                </Button>
              </div>
            </CardContent>
          </Card>
        </main>

        {/* 状态侧栏 */}
        <aside className="space-y-3">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle>AI 服务状态</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-[12px]">
              <div className="flex justify-between">
                <span className="text-muted-foreground">提供方</span>
                <span>{status.data?.provider ?? '—'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">模型</span>
                <span className="max-w-[120px] truncate">{status.data?.model ?? '—'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">剩余额度</span>
                <span className="inline-flex items-center gap-1">
                  <Zap className="h-3 w-3 text-accent" />
                  {quotaLabel}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">运行模式</span>
                <Badge variant={degraded ? 'warning' : 'success'}>{degraded ? '本地降级' : '在线'}</Badge>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle>提问技巧</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-[12px] text-muted-foreground">
              <p>· 贴上报错信息和你的思路</p>
              <p>· 说明你已经试过什么</p>
              <p>· 想要思路就切到「只给提示」</p>
              <p>· 想彻底搞懂就用「讲解原理」</p>
            </CardContent>
          </Card>

          <Alert
            variant="info"
            title="练习模式说明"
            description="默认不直接给完整答案，避免影响你的思考。切换到「给完整答案」可解锁（部分场景仍受限制）。"
          />
        </aside>
      </div>
    </PageContainer>
  );
}

export default function AiTutorPage(): React.ReactElement {
  return (
    <AuthGate title="登录后使用 AI 导师" description="AI 导师会记住你的对话上下文，并给出贴合水平的讲解。">
      <AiTutorContent />
    </AuthGate>
  );
}
