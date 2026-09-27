'use client';

import Link from 'next/link';
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  Code2,
  Lightbulb,
  ListChecks,
  Play,
  Swords,
  Target,
  Zap,
} from 'lucide-react';
import { lessonApi } from '@/lib/api';
import { DIFFICULTY_LABEL } from '@/lib/constants';
import { cn } from '@/lib/utils';
import { useFetch } from '@/hooks/useFetch';
import { useAuth } from '@/hooks/useAuth';
import { usePythonRunner } from '@/hooks/usePythonRunner';
import { useToaster } from '@/hooks/useToast';
import { PageContainer } from '@/components/layout/page-container';
import { Markdown } from '@/components/markdown';
import { CodeBlock } from '@/components/code/code-block';
import { ResultPanel } from '@/components/code/result-panel';
import { Alert, EmptyState, ErrorState } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Modal } from '@/components/ui/modal';
import { Progress, RingProgress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import type { ChapterOut, LessonQuizItem } from '@/lib/types';

const LESSON_TYPE_LABEL: Record<string, string> = {
  concept: '概念课',
  practice: '练习课',
  quiz: '测验课',
  project: '项目课',
};

const NOTES = [
  '写完代码先自己读一遍：变量名是否表意清楚，缩进是否一致。',
  '遇到报错先看最后一行，Python 的报错信息通常已经指出了原因。',
  '不确定的地方用 print() 打印中间结果，比盯着看更有效。',
];

const COMMON_MISTAKES = [
  { title: '缩进错误', desc: 'Python 用缩进表达代码块，混用 Tab 与空格会直接报错。' },
  { title: '忘记冒号', desc: 'if / for / while / def / class 语句末尾必须带英文冒号。' },
  { title: '字符串与数字相加', desc: '需要先用 str() / int() 显式转换类型。' },
  { title: '可变默认参数', desc: 'def f(xs=[]) 会跨调用共享列表，应写成 xs=None 再赋值。' },
];

export interface LessonViewProps {
  lessonId: string;
}

/** 课时页：左 course_outline 目录 / 中内容 / 右进度 / 底部上下节。 */
export function LessonView({ lessonId }: LessonViewProps): React.ReactElement {
  const toaster = useToaster();
  const { isAuthenticated } = useAuth();
  const detail = useFetch(() => lessonApi.detail(lessonId), [lessonId]);
  const runner = usePythonRunner();

  const [tab, setTab] = useState('content');
  const [code, setCode] = useState('');
  const [resultOpen, setResultOpen] = useState(false);
  const [completing, setCompleting] = useState(false);
  const [quizAnswers, setQuizAnswers] = useState<Record<string, string>>({});
  const [quizResult, setQuizResult] = useState<{ correct_count: number; total: number; passed: boolean } | null>(null);
  const [quizSubmitting, setQuizSubmitting] = useState(false);
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const startedAt = useRef<number>(Date.now());

  const lesson = detail.data;
  const topics = lesson?.topics ?? [];
  const progressPercent = lesson?.progress?.progress_percent ?? 0;
  const completed = useMemo(() => (lesson?.progress?.completed_at ?? null) !== null, [lesson]);

  /** 完整章节树（后端权威数据，不再用 prev/next 拼兜底）。 */
  const outline: ChapterOut[] = lesson?.course_outline ?? [];

  useEffect(() => {
    startedAt.current = Date.now();
  }, [lessonId]);

  useEffect(() => {
    setCode('');
    setQuizAnswers({});
    setQuizResult(null);
    setTab('content');
  }, [lessonId]);

  useEffect(() => {
    if (lesson?.starter_code && !code) setCode(lesson.starter_code);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lesson?.starter_code]);

  const quiz: LessonQuizItem[] = useMemo(() => {
    if (!lesson?.quiz_json) return [];
    return Array.isArray(lesson.quiz_json) ? lesson.quiz_json : [];
  }, [lesson]);

  const runCode = async (): Promise<void> => {
    if (!code.trim()) {
      toaster.info('请先输入代码');
      return;
    }
    setResultOpen(true);
    await runner.run([{ path: 'main.py', content: code }], { entry: 'main.py' });
  };

  const markComplete = async (): Promise<void> => {
    if (!lesson) return;
    if (!isAuthenticated) {
      toaster.info('登录后才能记录学习进度');
      return;
    }
    setCompleting(true);
    const timeSpent = Math.round((Date.now() - startedAt.current) / 1000);
    try {
      const result = await lessonApi.complete(lesson.id, timeSpent);
      toaster.success('课时已完成', `获得 ${result.xp_earned} XP${result.level_up ? ' · 等级提升！' : ''}`);
      detail.refresh();
    } catch (error) {
      toaster.error('提交失败', error instanceof Error ? error.message : '请稍后再试');
    } finally {
      setCompleting(false);
    }
  };

  const submitQuiz = async (): Promise<void> => {
    if (quiz.length === 0) return;
    setQuizSubmitting(true);
    try {
      const answers = quiz.map((item, index) => ({
        qid: item.qid ?? item.id ?? String(index),
        value: quizAnswers[item.qid ?? item.id ?? String(index)] ?? '',
      }));
      const result = await lessonApi.quiz(lessonId, answers);
      setQuizResult(result);
      toaster[result.passed ? 'success' : 'error'](
        result.passed ? '随堂练习通过' : '再试一次',
        `答对 ${result.correct_count} / ${result.total} 题`,
      );
    } catch (error) {
      toaster.error('提交失败', error instanceof Error ? error.message : '请稍后再试');
    } finally {
      setQuizSubmitting(false);
    }
  };

  if (detail.loading && !detail.data) {
    return (
      <PageContainer>
        <div className="grid gap-5 lg:grid-cols-[240px_1fr_240px]">
          <Skeleton className="h-80 w-full" />
          <Skeleton className="h-96 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      </PageContainer>
    );
  }

  if (detail.error && !detail.data) {
    return (
      <PageContainer title="课时内容">
        <ErrorState title="课时加载失败" description={detail.error} onRetry={detail.refresh} />
      </PageContainer>
    );
  }

  if (!lesson) {
    return (
      <PageContainer title="课时内容">
        <EmptyState icon={<BookOpen className="h-6 w-6" />} title="未找到该课时" description={`id = ${lessonId}`} />
      </PageContainer>
    );
  }

  const difficultyLabel = DIFFICULTY_LABEL[lesson.difficulty] ?? lesson.difficulty;

  return (
    <PageContainer width="wide">
      {/* 面包屑 */}
      {lesson.course_title || lesson.chapter_title ? (
        <nav className="mb-4 flex flex-wrap items-center gap-1.5 text-[11.5px] text-muted-foreground">
          {lesson.course_slug ? (
            <Link href={`/courses/${lesson.course_slug}`} className="hover:text-foreground hover:underline">
              {lesson.course_title ?? '课程'}
            </Link>
          ) : (
            <span>{lesson.course_title ?? '课程'}</span>
          )}
          {lesson.chapter_title ? (
            <>
              <span>/</span>
              <span>{lesson.chapter_title}</span>
            </>
          ) : null}
          <span>/</span>
          <span className="text-foreground">{lesson.title}</span>
          {lesson.total_lessons > 0 ? (
            <span className="ml-1">
              （第 {lesson.lesson_index + 1} / {lesson.total_lessons} 节）
            </span>
          ) : null}
        </nav>
      ) : null}

      <div className="grid gap-5 lg:grid-cols-[240px_minmax(0,1fr)_230px]">
        {/* ============ 左侧：完整章节目录（course_outline） ============ */}
        <aside className="order-2 lg:order-1">
          <div className="scroll-area space-y-3 rounded-lg border border-border bg-card p-3 lg:sticky lg:top-[4.5rem] lg:max-h-[calc(100vh-6rem)]">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">章节目录</p>

            {outline.length === 0 ? (
              <p className="px-1 text-[12px] text-muted-foreground">暂无章节数据。</p>
            ) : (
              <div className="space-y-2">
                {outline.map((chapter) => {
                  const isCurrentChapter = chapter.lessons.some((item) => item.id === lesson.id);
                  const isCollapsed = collapsed[chapter.id] ?? !isCurrentChapter;
                  return (
                    <div key={chapter.id} className="space-y-0.5">
                      <button
                        type="button"
                        onClick={() => setCollapsed((prev) => ({ ...prev, [chapter.id]: !isCollapsed }))}
                        className="flex w-full items-center gap-1.5 rounded-md px-1.5 py-1 text-left text-[11.5px] font-semibold text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground"
                      >
                        {isCollapsed ? (
                          <ChevronRight className="h-3.5 w-3.5 shrink-0" />
                        ) : (
                          <ChevronDown className="h-3.5 w-3.5 shrink-0" />
                        )}
                        <span className="line-clamp-2">
                          {chapter.order_index + 1}. {chapter.title}
                        </span>
                      </button>

                      {!isCollapsed ? (
                        <ul className="space-y-0.5 pl-1.5">
                          {chapter.lessons.map((item) => {
                            const active = item.id === lesson.id;
                            const done = item.status === 'completed' || item.progress_percent >= 100;
                            return (
                              <li key={item.id}>
                                <Link
                                  href={`/lesson/${item.id}`}
                                  className={cn(
                                    'flex items-start gap-1.5 rounded-md px-2 py-1.5 text-[12.5px] transition-colors',
                                    active
                                      ? 'bg-primary/12 font-medium text-primary'
                                      : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                                  )}
                                >
                                  {done ? (
                                    <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" />
                                  ) : (
                                    <span className="mt-1 h-2 w-2 shrink-0 rounded-full border border-current" />
                                  )}
                                  <span className="line-clamp-2">{item.title}</span>
                                </Link>
                              </li>
                            );
                          })}
                        </ul>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            )}

            {topics.length > 0 ? (
              <div className="space-y-1.5 border-t border-border pt-3">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">本课要点</p>
                <div className="flex flex-wrap gap-1.5">
                  {topics.map((topic) => (
                    <Badge key={topic.id} variant="secondary">
                      {topic.name}
                    </Badge>
                  ))}
                </div>
              </div>
            ) : null}

            <div className="space-y-1.5 border-t border-border pt-3 text-[11px] text-muted-foreground">
              <div className="flex justify-between">
                <span>难度</span>
                <span>{difficultyLabel}</span>
              </div>
              <div className="flex justify-between">
                <span>类型</span>
                <span>{LESSON_TYPE_LABEL[lesson.lesson_type] ?? '课时'}</span>
              </div>
              <div className="flex justify-between">
                <span>预计</span>
                <span>{lesson.estimated_minutes} 分钟</span>
              </div>
              <div className="flex justify-between">
                <span>奖励</span>
                <span>+{lesson.xp_reward} XP</span>
              </div>
            </div>
          </div>
        </aside>

        {/* ============ 中间：教学内容 ============ */}
        <main className="order-1 min-w-0 space-y-4 lg:order-2">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
              <Badge variant="default">{LESSON_TYPE_LABEL[lesson.lesson_type] ?? '课时'}</Badge>
              <span className="inline-flex items-center gap-1">
                <Clock className="h-3 w-3" />
                {lesson.estimated_minutes} 分钟
              </span>
              {completed ? (
                <Badge variant="success" className="gap-1">
                  <CheckCircle2 className="h-3 w-3" />
                  已完成
                </Badge>
              ) : null}
            </div>
            <h1 className="text-xl font-semibold tracking-tight">{lesson.title}</h1>
            {lesson.summary ? <p className="text-[13px] text-muted-foreground">{lesson.summary}</p> : null}
          </div>

          <Tabs value={tab} onValueChange={setTab}>
            <TabsList className="w-full justify-start overflow-x-auto">
              <TabsTrigger value="content">
                <BookOpen className="h-3.5 w-3.5" />
                教学内容
              </TabsTrigger>
              <TabsTrigger value="practice">
                <Code2 className="h-3.5 w-3.5" />
                代码示例
              </TabsTrigger>
              <TabsTrigger value="quiz">
                <ListChecks className="h-3.5 w-3.5" />
                随堂练习
              </TabsTrigger>
              <TabsTrigger value="challenge">
                <Swords className="h-3.5 w-3.5" />
                挑战题
              </TabsTrigger>
            </TabsList>

            {/* 正文：理论 / 示例 / 练习 / 注意事项 / 常见错误 */}
            <TabsContent value="content" className="space-y-4 pt-4">
              <Card>
                <CardContent className="pt-5">
                  {lesson.content_md ? (
                    <Markdown
                      content={lesson.content_md}
                      onRunCode={(snippet) => {
                        setCode(snippet);
                        setTab('practice');
                        toaster.info('已载入示例代码', '切到「代码示例」标签即可运行');
                      }}
                    />
                  ) : (
                    <EmptyState
                      icon={<BookOpen className="h-6 w-6" />}
                      title="本课时暂无正文内容"
                      description="可以先去「代码示例」动手练习，内容还在录入中。"
                      className="border-0 py-8"
                    />
                  )}
                </CardContent>
              </Card>

              <div className="grid gap-4 sm:grid-cols-2">
                <Card>
                  <CardHeader className="flex-row items-center gap-2 pb-2">
                    <Lightbulb className="h-4 w-4 text-accent" />
                    <CardTitle>注意事项</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ul className="space-y-2">
                      {NOTES.map((note) => (
                        <li key={note} className="flex items-start gap-2 text-[12.5px] text-muted-foreground">
                          <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                          {note}
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="flex-row items-center gap-2 pb-2">
                    <AlertTriangle className="h-4 w-4 text-amber-500" />
                    <CardTitle>常见错误</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2.5">
                    {COMMON_MISTAKES.map((item) => (
                      <div key={item.title} className="rounded-md border border-border bg-muted/25 p-2.5">
                        <p className="text-[12.5px] font-medium">{item.title}</p>
                        <p className="mt-0.5 text-[12px] text-muted-foreground">{item.desc}</p>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              </div>
            </TabsContent>

            {/* 代码示例：可运行 */}
            <TabsContent value="practice" className="space-y-4 pt-4">
              <Alert
                variant="info"
                title="动手改一改，再运行看看"
                description="按 Ctrl + Enter 也能直接运行当前代码。需要保存到编辑器可点右上角「在编辑器中打开」。"
              />
              <CodeBlock
                code={code || lesson.starter_code || '# 本课时暂无示例代码\n'}
                filename="main.py"
                showLineNumbers
                onRun={() => void runCode()}
                running={runner.running}
                onOpenInEditor={() => {
                  try {
                    window.localStorage.setItem('pythonlab:editor.draft', JSON.stringify(code));
                  } catch {
                    /* 忽略存储失败 */
                  }
                  window.open('/editor', '_blank');
                }}
                onFormat={() => setCode((prev) => (prev.trim() ? `${prev.replace(/[ \t]+$/gm, '').replace(/\n+$/, '')}\n` : prev))}
                maxHeight={420}
              />
              <div className="flex flex-wrap gap-2">
                <Button onClick={() => void runCode()} loading={runner.running}>
                  <Play className="h-4 w-4" />
                  运行代码
                </Button>
                {lesson.solution_code ? (
                  <Button
                    variant="outline"
                    onClick={() => {
                      setCode(lesson.solution_code ?? '');
                      toaster.info('已载入参考解答', '建议先自己写一遍再看参考代码');
                    }}
                  >
                    查看参考解答
                  </Button>
                ) : null}
                <Button variant="ghost" onClick={() => setCode(lesson.starter_code ?? '')}>
                  重置代码
                </Button>
              </div>
            </TabsContent>

            {/* 随堂练习 */}
            <TabsContent value="quiz" className="space-y-4 pt-4">
              {quiz.length === 0 ? (
                <EmptyState
                  icon={<ListChecks className="h-6 w-6" />}
                  title="本课时没有随堂测验"
                  description="可以直接去题库练习相关题目。"
                  action={
                    <Button size="sm" variant="outline" asChild>
                      <Link href="/problems">去题库</Link>
                    </Button>
                  }
                />
              ) : (
                <Card>
                  <CardHeader>
                    <CardTitle>随堂练习（共 {quiz.length} 题）</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {quiz.map((item, index) => {
                      const qid = item.qid ?? item.id ?? String(index);
                      const text = item.q ?? item.question ?? `第 ${index + 1} 题`;
                      return (
                        <div key={qid} className="space-y-2 rounded-lg border border-border p-3">
                          <p className="text-[13px] font-medium">
                            {index + 1}. {text}
                          </p>
                          <div className="space-y-1.5">
                            {(item.options ?? []).map((option) => (
                              <label
                                key={option}
                                className={cn(
                                  'flex cursor-pointer items-center gap-2 rounded-md border px-2.5 py-1.5 text-[12.5px] transition-colors',
                                  quizAnswers[qid] === option
                                    ? 'border-primary/45 bg-primary/10 text-primary'
                                    : 'border-border hover:bg-muted/60',
                                )}
                              >
                                <input
                                  type="radio"
                                  name={qid}
                                  value={option}
                                  checked={quizAnswers[qid] === option}
                                  onChange={() => setQuizAnswers((prev) => ({ ...prev, [qid]: option }))}
                                  className="h-3.5 w-3.5"
                                />
                                {option}
                              </label>
                            ))}
                          </div>
                        </div>
                      );
                    })}

                    {quizResult ? (
                      <Alert
                        variant={quizResult.passed ? 'success' : 'warning'}
                        title={`答对 ${quizResult.correct_count} / ${quizResult.total} 题`}
                        description={quizResult.passed ? '很棒，继续下一节吧！' : '回顾一下错题，再提交一次。'}
                      />
                    ) : null}

                    <Button loading={quizSubmitting} onClick={() => void submitQuiz()}>
                      提交答案
                    </Button>
                  </CardContent>
                </Card>
              )}
            </TabsContent>

            {/* 挑战题 */}
            <TabsContent value="challenge" className="space-y-4 pt-4">
              <Card>
                <CardHeader className="flex-row items-center gap-2">
                  <Swords className="h-4 w-4 text-primary" />
                  <CardTitle>挑战题</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <p className="text-[12.5px] leading-relaxed text-muted-foreground">
                    学完本节后，建议到题库挑 1-2 道同主题题目巩固。判题会给出 AC / WA / RE / TLE / MLE 结果、耗时与内存占用。
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" asChild>
                      <Link href="/problems">
                        <Target className="h-3.5 w-3.5" />
                        去题库挑战
                      </Link>
                    </Button>
                    <Button size="sm" variant="outline" asChild>
                      <Link href="/editor">
                        <Code2 className="h-3.5 w-3.5" />
                        打开编辑器
                      </Link>
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>

          {/* 底部上下节 */}
          <div className="flex items-center justify-between gap-3 border-t border-border pt-4">
            {lesson.prev_lesson ? (
              <Button variant="outline" asChild>
                <Link href={`/lesson/${lesson.prev_lesson.id}`}>
                  <ArrowLeft className="h-3.5 w-3.5" />
                  <span className="hidden max-w-[10rem] truncate sm:inline">{lesson.prev_lesson.title}</span>
                  <span className="sm:hidden">上一节</span>
                </Link>
              </Button>
            ) : (
              <span />
            )}

            <Button loading={completing} onClick={() => void markComplete()} variant={completed ? 'outline' : 'default'}>
              <CheckCircle2 className="h-4 w-4" />
              {completed ? '再次标记完成' : '标记为已完成'}
            </Button>

            {lesson.next_lesson ? (
              <Button variant="outline" asChild>
                <Link href={`/lesson/${lesson.next_lesson.id}`}>
                  <span className="hidden max-w-[10rem] truncate sm:inline">{lesson.next_lesson.title}</span>
                  <span className="sm:hidden">下一节</span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </Button>
            ) : (
              <span />
            )}
          </div>
        </main>

        {/* ============ 右侧：进度 ============ */}
        <aside className="order-3 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>学习进度</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex justify-center">
                <RingProgress value={progressPercent} size={84} />
              </div>
              <Progress value={progressPercent} size="sm" />
              <p className="text-center text-[11px] text-muted-foreground">
                {progressPercent >= 100 ? '本课时已完成' : '完成本节后可获得 XP'}
              </p>
              <div className="flex items-center justify-center gap-1.5 rounded-md bg-muted/40 py-2 text-[12px]">
                <Zap className="h-3.5 w-3.5 text-accent" />
                +{lesson.xp_reward} XP
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>学习建议</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-[12px] text-muted-foreground">
              <p>1. 先看正文理解概念，别急着抄代码。</p>
              <p>2. 在「代码示例」里改一个参数，观察输出变化。</p>
              <p>3. 做完随堂练习再点「标记为已完成」。</p>
              <Button variant="outline" size="sm" className="mt-1 w-full" asChild>
                <Link href="/ai-tutor">
                  <Lightbulb className="h-3.5 w-3.5" />
                  有疑问问 AI 导师
                </Link>
              </Button>
            </CardContent>
          </Card>
        </aside>
      </div>

      {/* 运行结果弹窗 */}
      <Modal
        open={resultOpen}
        onClose={() => setResultOpen(false)}
        title="运行结果"
        size="lg"
        footer={
          <Button variant="outline" onClick={() => setResultOpen(false)}>
            关闭
          </Button>
        }
      >
        <ResultPanel result={runner.result} running={runner.running} error={runner.error} className="min-h-[280px]" />
      </Modal>
    </PageContainer>
  );
}
