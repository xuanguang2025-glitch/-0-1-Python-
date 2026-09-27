'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  ChevronDown,
  Code2,
  Loader2,
  Play,
  RotateCcw,
  Save,
  Send,
  Sparkles,
  Terminal,
  Wand2,
  XCircle,
} from 'lucide-react';
import { aiApi, editorApi } from '@/lib/api';
import { DEFAULT_PYTHON_CODE } from '@/lib/constants';
import { extractErrorLine, formatCode } from '@/lib/format';
import { cn } from '@/lib/utils';
import { useLocalStorage } from '@/hooks/useLocalStorage';
import { usePythonRunner } from '@/hooks/usePythonRunner';
import { useToaster } from '@/hooks/useToast';
import { useAuth } from '@/hooks/useAuth';
import { useThemeStore } from '@/store/theme';
import { MonacoEditor } from '@/components/code/monaco-editor';
import { FileTree, type FileNode } from '@/components/code/file-tree';
import { ResultPanel } from '@/components/code/result-panel';
import { Markdown } from '@/components/markdown';
import { Alert } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/input';
import { Dropdown } from '@/components/ui/dropdown';
import { Navbar } from '@/components/layout/navbar';
import { useRouter } from 'next/navigation';

const INITIAL_FILES: FileNode[] = [{ path: 'main.py', content: DEFAULT_PYTHON_CODE, isEntry: true }];

interface ProblemItem {
  line: number;
  message: string;
}

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  degraded?: boolean;
}

/** 在线编辑器：多文件 + 运行 + AI 助手 + 输出面板。 */
export default function EditorPage(): React.ReactElement {
  const toaster = useToaster();
  const { isAuthenticated } = useAuth();
  const router = useRouter();
  const resolved = useThemeStore((state) => state.resolved);
  const runner = usePythonRunner();

  const [files, setFiles] = useLocalStorage<FileNode[]>('editor.files', INITIAL_FILES);
  const [activePath, setActivePath] = useState<string>(INITIAL_FILES[0].path);
  const [stdin, setStdin] = useState('');
  const [bottomTab, setBottomTab] = useState('terminal');
  const [sideTab, setSideTab] = useState('result');
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [mobilePane, setMobilePane] = useState<'files' | 'editor' | 'panel'>('editor');

  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [review, setReview] = useState<string | null>(null);

  const saveTimer = useRef<number | null>(null);

  const safeFiles = useMemo(() => (Array.isArray(files) && files.length > 0 ? files : INITIAL_FILES), [files]);
  const activeFile = useMemo(
    () => safeFiles.find((file) => file.path === activePath) ?? safeFiles[0],
    [safeFiles, activePath],
  );

  useEffect(() => {
    if (!safeFiles.some((file) => file.path === activePath)) setActivePath(safeFiles[0].path);
  }, [safeFiles, activePath]);

  const updateActiveContent = useCallback(
    (content: string) => {
      setFiles((prev) => prev.map((file) => (file.path === activeFile.path ? { ...file, content } : file)));
      setDirty(true);
    },
    [activeFile.path, setFiles],
  );

  /** 保存快照：写后端历史（失败仅提示，不影响本地草稿）。 */
  const saveSnapshot = useCallback(
    async (silent = false) => {
      if (!isAuthenticated) {
        if (!silent) toaster.info('本地草稿已保存', '登录后可同步到云端代码历史');
        setDirty(false);
        return;
      }
      setSaving(true);
      try {
        await editorApi.saveSnapshot({
          context_type: 'editor',
          file_path: activeFile.path,
          code: activeFile.content,
          label: '自动保存',
          source: 'editor',
        });
        setDirty(false);
        if (!silent) toaster.success('已保存', `${activeFile.path} 已同步到代码历史`);
      } catch (error) {
        if (!silent) toaster.error('保存失败', error instanceof Error ? error.message : '请稍后再试');
      } finally {
        setSaving(false);
      }
    },
    [activeFile, isAuthenticated, toaster],
  );

  /** 自动保存：停止输入 3 秒后写入后端。 */
  useEffect(() => {
    if (!dirty) return;
    if (saveTimer.current) window.clearTimeout(saveTimer.current);
    saveTimer.current = window.setTimeout(() => void saveSnapshot(true), 3000);
    return () => {
      if (saveTimer.current) window.clearTimeout(saveTimer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeFile.content, dirty]);

  const run = useCallback(async () => {
    setSideTab('result');
    setMobilePane('panel');
    setBottomTab('output');
    await runner.run(
      safeFiles.map((file) => ({ path: file.path, content: file.content })),
      { entry: activeFile.path, stdin: stdin || undefined },
    );
  }, [activeFile.path, runner, safeFiles, stdin]);

  /** Ctrl+S：保存到本地 + 云端。 */
  const handleSave = useCallback(() => {
    void saveSnapshot(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [saveSnapshot]);

  const problems: ProblemItem[] = useMemo(() => {
    const stderr = runner.result?.stderr ?? '';
    if (!stderr) return [];
    return stderr
      .split('\n')
      .map((line) => line.trim())
      .filter((line) => line.length > 0)
      .map((line, index) => {
        const match = /line (\d+)/.exec(line);
        return { line: match ? Number(match[1]) : index + 1, message: line };
      });
  }, [runner.result]);

  const hasError = Boolean(runner.result && (runner.result.exit_code !== 0 || runner.result.stderr));

  useEffect(() => {
    if (problems.length > 0) setBottomTab('problems');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runner.result?.request_id]);

  const askAi = async (question: string): Promise<void> => {
    const trimmed = question.trim();
    if (!trimmed) return;
    setChatMessages((prev) => [...prev, { role: 'user', content: trimmed }]);
    setChatInput('');
    setChatLoading(true);
    try {
      const response = await aiApi.chat({
        message: trimmed,
        mode: 'standard',
        scene: 'free',
        context: { type: 'editor', code: activeFile.content },
      });
      setChatMessages((prev) => [
        ...prev,
        { role: 'assistant', content: response.content_md, degraded: response.degraded },
      ]);
    } catch (error) {
      setChatMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `暂时无法连接 AI 服务：${error instanceof Error ? error.message : '未知错误'}`,
          degraded: true,
        },
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  const runReview = async (): Promise<void> => {
    setReviewing(true);
    setReview(null);
    try {
      const result = await aiApi.review({ code: activeFile.content, language: 'python', context_type: 'editor' });
      setReview(
        `**代码评分：${result.score}/100**\n\n${result.summary_md}${
          result.issues.length
            ? `\n\n${result.issues
                .map(
                  (issue) =>
                    `- \`${issue.severity}\`${issue.line ? ` 第 ${issue.line} 行` : ''} · ${issue.title}：${issue.suggestion}`,
                )
                .join('\n')}`
            : ''
        }`,
      );
    } catch (error) {
      setReview(`代码审查服务暂时不可用：${error instanceof Error ? error.message : '未知错误'}`);
    } finally {
      setReviewing(false);
    }
  };

  const createFile = (path: string, content: string): void => {
    setFiles((prev) => [...prev, { path, content }]);
    setActivePath(path);
    toaster.success('已创建文件', path);
  };

  const deleteFile = (path: string): void => {
    setFiles((prev) => {
      const next = prev.filter((file) => file.path !== path);
      return next.length > 0 ? next : INITIAL_FILES;
    });
    toaster.info('已删除文件', path);
  };

  const renameFile = (from: string, to: string): void => {
    setFiles((prev) =>
      prev.map((file) =>
        file.path === from ? { ...file, path: to, isEntry: file.isEntry || from === activePath } : file,
      ),
    );
    if (activePath === from) setActivePath(to);
    toaster.success('已重命名', `${from} → ${to}`);
  };

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <Navbar />
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      {/* ============ 工具栏 ============ */}
      <div className="flex shrink-0 flex-wrap items-center gap-2 border-b border-border bg-card/60 px-3 py-2">
        <span className="flex items-center gap-1.5 text-[13px] font-semibold">
          <Code2 className="h-4 w-4 text-primary" />
          在线编辑器
        </span>
        <Badge variant="secondary" className="font-mono text-[10px]">
          Python 3
        </Badge>
        {dirty ? <Badge variant="warning">未保存</Badge> : <Badge variant="success">已保存</Badge>}

        <div className="ml-auto flex items-center gap-1.5">
          <Button size="sm" variant="ghost" className="lg:hidden" onClick={() => setMobilePane('files')}>
            文件
          </Button>
          <Button size="sm" variant="ghost" className="lg:hidden" onClick={() => setMobilePane('panel')}>
            面板
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              updateActiveContent(formatCode(activeFile.content, 'python'));
              toaster.success('已格式化');
            }}
          >
            <Wand2 className="h-3.5 w-3.5" />
            格式化
          </Button>
          <Button size="sm" variant="outline" loading={saving} onClick={() => void saveSnapshot(false)}>
            <Save className="h-3.5 w-3.5" />
            保存
          </Button>
          <Button size="sm" loading={runner.running} onClick={() => void run()}>
            <Play className="h-3.5 w-3.5" />
            运行
            <span className="hidden text-[10px] opacity-70 sm:inline">Ctrl+↵</span>
          </Button>
        </div>
      </div>

      {!isAuthenticated ? (
        <div className="shrink-0 px-3 pt-2">
          <Alert
            variant="info"
            title="当前为未登录状态"
            description="代码保存在本地浏览器；登录后可同步代码历史、运行代码并获得 AI 辅导。"
            action={
              <Button size="sm" variant="outline" onClick={() => router.push('/login?redirect=/editor')}>
                去登录
              </Button>
            }
          />
        </div>
      ) : null}

      {/* ============ 主体 ============ */}
      <div className="flex min-h-0 flex-1">
        {/* 左侧文件树 */}
        <div
          className={cn(
            'w-52 shrink-0 border-r border-border bg-card/40',
            mobilePane === 'files' ? 'block' : 'hidden lg:block',
          )}
        >
          <FileTree
            files={safeFiles}
            activePath={activeFile.path}
            onSelect={(path) => {
              setActivePath(path);
              setMobilePane('editor');
            }}
            onCreate={createFile}
            onDelete={deleteFile}
            onRename={renameFile}
          />
          <div className="border-t border-border p-2.5 text-[11px] leading-relaxed text-muted-foreground">
            <p className="font-medium text-foreground">快捷键</p>
            <p>Ctrl + Enter 运行</p>
            <p>Ctrl + S 保存</p>
            <p>输入停止 3 秒自动保存</p>
          </div>
        </div>

        {/* 中间编辑器 + 底部面板 */}
        <div className={cn('flex min-w-0 flex-1 flex-col', mobilePane === 'editor' ? 'flex' : 'hidden lg:flex')}>
          <div className="flex items-center gap-2 border-b border-border px-2 py-1.5">
            <span className="flex items-center gap-1.5 rounded-t-md bg-muted px-2.5 py-1 font-mono text-[12px]">
              {activeFile.path}
              {dirty ? <span className="h-1.5 w-1.5 rounded-full bg-accent" /> : null}
            </span>
            <div className="ml-auto flex items-center gap-1">
              <Button
                size="icon-sm"
                variant="ghost"
                aria-label="重置当前文件"
                onClick={() => updateActiveContent(DEFAULT_PYTHON_CODE)}
              >
                <RotateCcw className="h-3.5 w-3.5" />
              </Button>
              <span className="text-[11px] text-muted-foreground">
                {resolved === 'dark' ? '深色' : '浅色'} · 行号 · 折叠
              </span>
            </div>
          </div>

          <div className="min-h-0 flex-1">
            <MonacoEditor
              value={activeFile.content}
              onChange={updateActiveContent}
              language="python"
              onRun={() => void run()}
              onSave={handleSave}
            />
          </div>

          {/* 底部 Terminal / Output / Problems */}
          <div className="h-52 shrink-0 border-t border-border bg-card/40">
            <div className="flex items-center gap-1 border-b border-border px-2 py-1.5">
              {[
                { key: 'terminal', label: 'Terminal', icon: <Terminal className="h-3.5 w-3.5" /> },
                { key: 'output', label: 'Output', icon: <Play className="h-3.5 w-3.5" /> },
                {
                  key: 'problems',
                  label: `Problems${problems.length ? ` (${problems.length})` : ''}`,
                  icon: hasError ? <AlertTriangle className="h-3.5 w-3.5" /> : <CheckCircle2 className="h-3.5 w-3.5" />,
                },
              ].map((item) => (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => setBottomTab(item.key)}
                  className={cn(
                    'inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-[12px] transition-colors',
                    bottomTab === item.key ? 'bg-muted text-foreground' : 'text-muted-foreground hover:text-foreground',
                  )}
                >
                  {item.icon}
                  {item.label}
                </button>
              ))}
              <div className="ml-auto flex items-center gap-2">
                <span className="text-[11px] text-muted-foreground">
                  {runner.result ? `耗时 ${runner.result.time_ms}ms · 内存 ${Math.round(runner.result.memory_kb / 1024)}MB` : '尚未运行'}
                </span>
                <Button size="sm" variant="ghost" onClick={() => runner.reset()}>
                  清空
                </Button>
              </div>
            </div>

            <div className="scroll-area h-[calc(100%-2.25rem)] p-3 font-mono text-[12px]">
              {bottomTab === 'terminal' ? (
                <div className="space-y-2 font-sans">
                  <p className="text-[12px] text-muted-foreground">
                    $ python {activeFile.path} {stdin ? '< stdin' : ''}
                  </p>
                  <Textarea
                    value={stdin}
                    onChange={(event) => setStdin(event.target.value)}
                    rows={3}
                    placeholder="标准输入（stdin），每行一个值"
                    className="font-mono text-[12px]"
                  />
                  <Button size="sm" loading={runner.running} onClick={() => void run()}>
                    <Play className="h-3.5 w-3.5" />
                    运行当前文件
                  </Button>
                </div>
              ) : bottomTab === 'output' ? (
                runner.result ? (
                  <pre className="whitespace-pre-wrap">
                    {runner.result.stdout || <span className="text-muted-foreground">（无输出）</span>}
                    {runner.result.stderr ? <span className="text-rose-500">{runner.result.stderr}</span> : null}
                  </pre>
                ) : (
                  <p className="text-muted-foreground">点击「运行」后，标准输出会显示在这里。</p>
                )
              ) : problems.length > 0 ? (
                <div className="space-y-1 font-sans">
                  {problems.map((problem, index) => (
                    <div key={index} className="flex items-start gap-2 rounded-md border border-rose-500/25 bg-rose-500/8 p-2">
                      <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-rose-500" />
                      <span className="min-w-0 flex-1 break-all text-[12px]">{problem.message}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-emerald-500">没有发现问题。</p>
              )}
            </div>
          </div>
        </div>

        {/* 右侧：运行结果 / AI 助手 */}
        <div
          className={cn(
            'w-full shrink-0 border-l border-border bg-card/30 lg:w-80',
            mobilePane === 'panel' ? 'block' : 'hidden lg:block',
          )}
        >
          <Tabs value={sideTab} onValueChange={setSideTab} className="flex h-full flex-col">
            <div className="border-b border-border p-1.5">
              <TabsList className="w-full">
                <TabsTrigger value="result" className="flex-1 justify-center">
                  <Play className="h-3.5 w-3.5" />
                  运行结果
                </TabsTrigger>
                <TabsTrigger value="ai" className="flex-1 justify-center">
                  <Bot className="h-3.5 w-3.5" />
                  AI 助手
                </TabsTrigger>
              </TabsList>
            </div>

            <TabsContent value="result" className="min-h-0 flex-1">
              <ResultPanel
                result={runner.result}
                running={runner.running}
                error={runner.error}
                emptyHint="在上方点击「运行」，或按 Ctrl + Enter"
                className="h-full overflow-auto"
              />
            </TabsContent>

            <TabsContent value="ai" className="flex min-h-0 flex-1 flex-col">
              <div className="flex items-center gap-1.5 border-b border-border px-3 py-2">
                <Sparkles className="h-3.5 w-3.5 text-accent" />
                <span className="text-[12px] font-medium">AI 代码助手</span>
                <Button size="sm" variant="ghost" className="ml-auto h-6 px-2 text-[11px]" loading={reviewing} onClick={() => void runReview()}>
                  审查代码
                </Button>
              </div>

              <div className="scroll-area flex-1 space-y-3 p-3">
                {review ? (
                  <div className="rounded-lg border border-primary/25 bg-primary/5 p-3">
                    <div className="mb-1 flex items-center gap-1.5 text-[11px] font-medium text-primary">
                      <CheckCircle2 className="h-3 w-3" />
                      代码审查
                    </div>
                    <Markdown content={review} className="prose-sm" />
                  </div>
                ) : null}

                {chatMessages.length === 0 && !review ? (
                  <div className="space-y-2 text-[12.5px] text-muted-foreground">
                    <p>可以问我：</p>
                    {['这段代码为什么报错？', '帮我优化这个循环', '解释一下生成器的用法'].map((item) => (
                      <button
                        key={item}
                        type="button"
                        onClick={() => void askAi(item)}
                        className="block w-full rounded-md border border-border px-2.5 py-1.5 text-left text-[12px] transition-colors hover:bg-muted"
                      >
                        {item}
                      </button>
                    ))}
                  </div>
                ) : null}

                {chatMessages.map((message, index) => (
                  <div
                    key={index}
                    className={cn(
                      'rounded-lg border p-2.5',
                      message.role === 'user' ? 'border-border bg-muted/40' : 'border-primary/20 bg-primary/5',
                    )}
                  >
                    <div className="mb-1 flex items-center gap-1.5 text-[10.5px] text-muted-foreground">
                      {message.role === 'user' ? '我' : 'AI 导师'}
                      {message.degraded ? <Badge variant="warning">离线助手</Badge> : null}
                    </div>
                    {message.role === 'user' ? (
                      <p className="whitespace-pre-wrap text-[12.5px]">{message.content}</p>
                    ) : (
                      <Markdown content={message.content} />
                    )}
                  </div>
                ))}

                {chatLoading ? (
                  <p className="flex items-center gap-2 text-[12px] text-muted-foreground">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    正在思考…
                  </p>
                ) : null}
              </div>

              <div className="border-t border-border p-2">
                <div className="flex items-end gap-1.5">
                  <Textarea
                    value={chatInput}
                    onChange={(event) => setChatInput(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' && !event.shiftKey) {
                        event.preventDefault();
                        void askAi(chatInput);
                      }
                    }}
                    rows={2}
                    placeholder="问点关于当前代码的问题…"
                    className="text-[12px]"
                  />
                  <Button size="icon" loading={chatLoading} onClick={() => void askAi(chatInput)} aria-label="发送">
                    <Send className="h-3.5 w-3.5" />
                  </Button>
                </div>
                <Dropdown
                  align="start"
                  items={[
                    { label: '解释当前代码', onSelect: () => void askAi('请解释当前代码做了什么') },
                    { label: '找 bug', onSelect: () => void askAi('帮我找出当前代码里的潜在问题') },
                    { label: '优化建议', onSelect: () => void askAi('这段代码有哪些可以优化的地方？') },
                  ]}
                  trigger={() => (
                    <button
                      type="button"
                      className="mt-1.5 inline-flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground"
                    >
                      快捷提问
                      <ChevronDown className="h-3 w-3" />
                    </button>
                  )}
                />
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </div>
      </div>
    </div>
  );
}