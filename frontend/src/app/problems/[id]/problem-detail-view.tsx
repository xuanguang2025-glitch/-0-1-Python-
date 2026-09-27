'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  Clock,
  Code2,
  Cpu,
  History,
  Info,
  Lightbulb,
  Play,
  Send,
  Sparkles,
  Target,
  XCircle,
} from 'lucide-react';
import { aiApi, problemApi, submissionApi } from '@/lib/api';
import {
  DIFFICULTY_LABEL,
  DIFFICULTY_STYLE,
  PROBLEM_TYPE_LABEL,
  SUBMISSION_STATUS_LABEL,
  SUBMISSION_STATUS_STYLE,
  VERDICT_SHORT,
} from '@/lib/constants';
import { cn, formatMemory, formatPercent, formatTime } from '@/lib/utils';
import { useFetch } from '@/hooks/useFetch';
import { usePythonRunner } from '@/hooks/usePythonRunner';
import { useToaster } from '@/hooks/useToast';
import { MonacoEditor } from '@/components/code/monaco-editor';
import { ResultPanel } from '@/components/code/result-panel';
import { Markdown } from '@/components/markdown';
import { PageContainer } from '@/components/layout/page-container';
import { Alert, EmptyState, ErrorState } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table';
import type { SubmissionOut, SubmissionStatus } from '@/lib/types';

const TEMPLATE = `import sys


def main() -> None:
    # 从标准输入读取数据
    data = sys.stdin.read().split()
    # TODO: 在这里实现你的解法
    print(data)


if __name__ == "__main__":
    main()
`;

const POLL_MAX = 30;

export interface ProblemDetailViewProps {
  problemId: string;
}

/** 题目详情：题面 + 代码提交判题 + 结果详情 + AI 题解。 */
export function ProblemDetailView({ problemId }: ProblemDetailViewProps): React.ReactElement {
  const toaster = useToaster();
  const runner = usePythonRunner();
  const detail = useFetch(() => problemApi.detail(problemId), [problemId]);
  const submissions = useFetch(() => submissionApi.list({ problem_id: problemId, page: 1, page_size: 20 }), [problemId]);
  const similar = useFetch(() => problemApi.similar(problemId, 5), [problemId]);

  const [code, setCode] = useState(TEMPLATE);
  const [submitting, setSubmitting] = useState(false);
  const [submission, setSubmission] = useState<SubmissionOut | null>(null);
  const [tab, setTab] = useState('statement');
  const [editorTab, setEditorTab] = useState('code');
  const [aiSolution, setAiSolution] = useState<string | null>(null);
  const [aiSolutionLoading, setAiSolutionLoading] = useState(false);
  const [errorAnalysis, setErrorAnalysis] = useState<string | null>(null);

  const problem = detail.data?.problem;
  const samples = detail.data?.sample_cases ?? [];
  const tags = detail.data?.tags ?? [];

  useEffect(() => {
    if (problem?.id) setSubmission(null);
  }, [problem?.id]);

  /** 提交判题：同步返回；pending 时轮询状态。 */
  const submit = async (): Promise<void> => {
    if (!problem) return;
    setSubmitting(true);
    setEditorTab('result');
    try {
      let result = await submissionApi.submit({ problem_id: problem.id, code, language: 'python' });
      let attempts = 0;
      while ((result.status === 'pending' || result.status === 'judging') && attempts < POLL_MAX) {
        await new Promise((resolve) => window.setTimeout(resolve, 1000));
        const polled = await submissionApi.status(result.id);
        attempts += 1;
        if (polled.status !== 'pending' && polled.status !== 'judging') {
          result = await submissionApi.detail(result.id);
          break;
        }
      }
      setSubmission(result);
      const accepted = result.status === 'accepted';
      toaster[accepted ? 'success' : 'error'](
        accepted ? '恭喜，通过全部测试点！' : SUBMISSION_STATUS_LABEL[result.status],
        `${result.passed_cases}/${result.total_cases} 个测试点通过 · 耗时 ${result.time_ms}ms`,
      );
      submissions.refresh();
      detail.refresh();
      if (!accepted && result.error_message) {
        void analyzeError(result.error_message);
      }
    } catch (error) {
      toaster.error('提交失败', error instanceof Error ? error.message : '请稍后再试');
    } finally {
      setSubmitting(false);
    }
  };

  const runSample = async (): Promise<void> => {
    const stdin = samples[0]?.input ?? '';
    setEditorTab('result');
    await runner.run([{ path: 'main.py', content: code }], { entry: 'main.py', stdin });
  };

  const analyzeError = async (message: string): Promise<void> => {
    try {
      const result = await aiApi.analyzeError({
        code,
        error_message: message,
        problem_id: problemId,
      });
      setErrorAnalysis(
        `**错误类型：** ${result.error_type}\n\n**原因：** ${result.cause}\n\n**修复步骤：**\n${result.fix_steps
          .map((step, index) => `${index + 1}. ${step}`)
          .join('\n')}${
          result.related_topics.length ? `\n\n**相关知识：** ${result.related_topics.join('、')}` : ''
        }`,
      );
    } catch {
      setErrorAnalysis(null);
    }
  };

  const loadAiSolution = async (): Promise<void> => {
    setAiSolutionLoading(true);
    try {
      const result = await problemApi.discussionAi(problemId);
      setAiSolution(result.summary_md);
    } catch (error) {
      setAiSolution(`题解暂时不可用：${error instanceof Error ? error.message : '请稍后再试'}`);
    } finally {
      setAiSolutionLoading(false);
    }
  };

  const verdictTone = useMemo(() => {
    if (!submission) return null;
    return SUBMISSION_STATUS_STYLE[submission.status as SubmissionStatus];
  }, [submission]);

  if (detail.loading && !detail.data) {
    return (
      <PageContainer>
        <div className="grid gap-4 lg:grid-cols-2">
          <Skeleton className="h-96 w-full" />
          <Skeleton className="h-96 w-full" />
        </div>
      </PageContainer>
    );
  }

  if (detail.error && !detail.data) {
    return (
      <PageContainer title="题目详情">
        <ErrorState title="题目加载失败" description={detail.error} onRetry={detail.refresh} />
      </PageContainer>
    );
  }

  if (!problem) {
    return (
      <PageContainer title="题目详情">
        <EmptyState icon={<Target className="h-6 w-6" />} title="未找到该题目" description={`id = ${problemId}`} />
      </PageContainer>
    );
  }

  return (
    <PageContainer width="wide">
      <div className="grid gap-4 lg:grid-cols-2">
        {/* ============ 左：题面 ============ */}
        <div className="min-w-0 space-y-3">
          <Card>
            <CardContent className="space-y-3 pt-5">
              <div className="flex flex-wrap items-center gap-2">
                <Badge className={DIFFICULTY_STYLE[problem.difficulty]}>{DIFFICULTY_LABEL[problem.difficulty]}</Badge>
                <Badge variant="secondary">{PROBLEM_TYPE_LABEL[problem.problem_type]}</Badge>
                {detail.data?.my_status ? (
                  <Badge className={SUBMISSION_STATUS_STYLE[detail.data.my_status as SubmissionStatus]}>
                    {VERDICT_SHORT[detail.data.my_status as SubmissionStatus]} · {SUBMISSION_STATUS_LABEL[detail.data.my_status as SubmissionStatus]}
                  </Badge>
                ) : null}
                <span className="ml-auto text-[11px] text-muted-foreground">
                  通过率 {formatPercent(problem.acceptance_rate ?? 0, 1)} · {problem.submission_count ?? 0} 次提交
                </span>
              </div>

              <h1 className="text-xl font-semibold tracking-tight">{problem.title}</h1>

              <div className="flex flex-wrap gap-3 text-[11px] text-muted-foreground">
                <span className="inline-flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  时间限制 {problem.time_limit_ms ?? 1000} ms
                </span>
                <span className="inline-flex items-center gap-1">
                  <Cpu className="h-3 w-3" />
                  内存限制 {problem.memory_limit_mb ?? 128} MB
                </span>
                {tags.length > 0 ? (
                  <span className="inline-flex flex-wrap items-center gap-1">
                    <Info className="h-3 w-3" />
                    {tags.join(' · ')}
                  </span>
                ) : null}
              </div>
            </CardContent>
          </Card>

          <Tabs value={tab} onValueChange={setTab}>
            <TabsList>
              <TabsTrigger value="statement">题面</TabsTrigger>
              <TabsTrigger value="submissions">
                <History className="h-3.5 w-3.5" />
                提交记录
              </TabsTrigger>
              <TabsTrigger value="ai">
                <Bot className="h-3.5 w-3.5" />
                AI 题解
              </TabsTrigger>
              <TabsTrigger value="similar">相似题</TabsTrigger>
            </TabsList>

            <TabsContent value="statement" className="space-y-3 pt-3">
              <Card>
                <CardContent className="pt-5">
                  {problem.statement_md ? (
                    <Markdown content={problem.statement_md} />
                  ) : (
                    <EmptyState title="题面暂缺" description="题目内容可能还在录入中。" className="border-0 py-8" />
                  )}
                </CardContent>
              </Card>

              {problem.input_format || problem.output_format ? (
                <div className="grid gap-3 sm:grid-cols-2">
                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle>输入格式</CardTitle>
                    </CardHeader>
                    <CardContent className="text-[12.5px] text-muted-foreground">
                      {problem.input_format ?? '—'}
                    </CardContent>
                  </Card>
                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle>输出格式</CardTitle>
                    </CardHeader>
                    <CardContent className="text-[12.5px] text-muted-foreground">
                      {problem.output_format ?? '—'}
                    </CardContent>
                  </Card>
                </div>
              ) : null}

              {samples.length > 0 ? (
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle>样例</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {samples.map((sample, index) => (
                      <div key={sample.id} className="grid gap-3 sm:grid-cols-2">
                        <div>
                          <p className="mb-1 text-[11px] text-muted-foreground">输入 #{index + 1}</p>
                          <pre className="code-surface overflow-auto p-2.5">{sample.input || '（空）'}</pre>
                        </div>
                        <div>
                          <p className="mb-1 text-[11px] text-muted-foreground">期望输出 #{index + 1}</p>
                          <pre className="code-surface overflow-auto p-2.5">{sample.expected_output || '（空）'}</pre>
                        </div>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              ) : null}

              {problem.hints_md ? (
                <Alert variant="info" title="提示" description={problem.hints_md} />
              ) : null}
            </TabsContent>

            <TabsContent value="submissions" className="pt-3">
              <Card>
                <CardHeader className="flex-row items-center justify-between">
                  <CardTitle>我的提交</CardTitle>
                  <Button size="sm" variant="ghost" onClick={submissions.refresh}>
                    刷新
                  </Button>
                </CardHeader>
                <CardContent>
                  {submissions.loading && !submissions.data ? (
                    <Skeleton className="h-32 w-full" />
                  ) : submissions.data && submissions.data.items.length > 0 ? (
                    <Table>
                      <THead>
                        <TR>
                          <TH>结果</TH>
                          <TH>测试点</TH>
                          <TH>耗时</TH>
                          <TH>内存</TH>
                          <TH>时间</TH>
                        </TR>
                      </THead>
                      <TBody>
                        {submissions.data.items.map((item) => (
                          <TR key={item.id}>
                            <TD>
                              <Badge className={SUBMISSION_STATUS_STYLE[item.status as SubmissionStatus]}>
                                {VERDICT_SHORT[item.status as SubmissionStatus]}
                              </Badge>
                            </TD>
                            <TD>
                              {item.passed_cases}/{item.total_cases}
                            </TD>
                            <TD>{formatTime(item.time_ms)}</TD>
                            <TD>{formatMemory(item.memory_kb)}</TD>
                            <TD className="text-muted-foreground">{new Date(item.created_at).toLocaleString('zh-CN')}</TD>
                          </TR>
                        ))}
                      </TBody>
                    </Table>
                  ) : (
                    <EmptyState title="还没有提交记录" description="写一版代码提交试试。" className="border-0 py-8" />
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="ai" className="space-y-3 pt-3">
              <Card>
                <CardHeader className="flex-row items-center justify-between">
                  <CardTitle className="flex items-center gap-1.5">
                    <Sparkles className="h-4 w-4 text-accent" />
                    AI 题解要点
                  </CardTitle>
                  <Button size="sm" variant="outline" loading={aiSolutionLoading} onClick={() => void loadAiSolution()}>
                    {aiSolution ? '重新生成' : '生成题解'}
                  </Button>
                </CardHeader>
                <CardContent>
                  {aiSolution ? (
                    <Markdown content={aiSolution} />
                  ) : (
                    <EmptyState
                      icon={<Lightbulb className="h-5 w-5" />}
                      title="还没有题解"
                      description="建议先自己尝试，卡住时再让 AI 给要点提示。"
                      className="border-0 py-6"
                    />
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="similar" className="pt-3">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle>相似题目</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {similar.data && similar.data.length > 0 ? (
                    similar.data.map((item) => (
                      <Link
                        key={item.id}
                        href={`/problems/${item.id}`}
                        className="flex items-center gap-3 rounded-md border border-border px-3 py-2 text-[13px] transition-colors hover:bg-muted/50"
                      >
                        <Target className="h-3.5 w-3.5 text-primary" />
                        <span className="min-w-0 flex-1 truncate">{item.title}</span>
                        <Badge className={DIFFICULTY_STYLE[item.difficulty]}>{DIFFICULTY_LABEL[item.difficulty]}</Badge>
                      </Link>
                    ))
                  ) : (
                    <EmptyState title="暂无相似题目" className="border-0 py-6" />
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>

        {/* ============ 右：编辑器与判题结果 ============ */}
        <div className="space-y-3">
          <div className="overflow-hidden rounded-lg border border-border">
            <div className="flex items-center gap-2 border-b border-border bg-card/60 px-3 py-2">
              <Code2 className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="font-mono text-[12px]">solution.py</span>
              <Badge variant="secondary" className="text-[10px]">
                Python 3
              </Badge>
              <div className="ml-auto flex items-center gap-1.5">
                <Button size="sm" variant="ghost" onClick={() => void runSample()} loading={runner.running}>
                  <Play className="h-3.5 w-3.5" />
                  运行样例
                </Button>
                <Button size="sm" loading={submitting} onClick={() => void submit()}>
                  <Send className="h-3.5 w-3.5" />
                  提交判题
                </Button>
              </div>
            </div>
            <MonacoEditor value={code} onChange={setCode} language="python" height={380} />
          </div>

          <Tabs value={editorTab} onValueChange={setEditorTab}>
            <TabsList>
              <TabsTrigger value="result">判题结果</TabsTrigger>
              <TabsTrigger value="local">本地运行输出</TabsTrigger>
            </TabsList>

            <TabsContent value="result" className="pt-3">
              <Card>
                <CardContent className="pt-5">
                  {submitting ? (
                    <div className="flex items-center gap-2 py-8 text-[13px] text-muted-foreground">
                      <AlertTriangle className="h-4 w-4 animate-pulse-soft" />
                      正在判题，请稍候…
                    </div>
                  ) : submission ? (
                    <div className="space-y-4">
                      <div className={cn('flex flex-wrap items-center gap-3 rounded-lg border p-3', verdictTone)}>
                        <span className="flex items-center gap-1.5 text-[14px] font-semibold">
                          {submission.status === 'accepted' ? (
                            <CheckCircle2 className="h-4 w-4" />
                          ) : (
                            <XCircle className="h-4 w-4" />
                          )}
                          {VERDICT_SHORT[submission.status as SubmissionStatus]} ·{' '}
                          {SUBMISSION_STATUS_LABEL[submission.status as SubmissionStatus]}
                        </span>
                        <span className="text-[12px]">
                          通过 {submission.passed_cases}/{submission.total_cases} 个测试点
                        </span>
                        <span className="text-[12px]">得分 {submission.score}</span>
                        <span className="ml-auto flex items-center gap-3 text-[11px]">
                          <span className="inline-flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            {formatTime(submission.time_ms)}
                          </span>
                          <span className="inline-flex items-center gap-1">
                            <Cpu className="h-3 w-3" />
                            {formatMemory(submission.memory_kb)}
                          </span>
                        </span>
                      </div>

                      {submission.error_message ? (
                        <Alert
                          variant="error"
                          title={submission.error_type ?? '运行错误'}
                          description={submission.error_message}
                        />
                      ) : null}

                      {submission.results && submission.results.length > 0 ? (
                        <Table>
                          <THead>
                            <TR>
                              <TH>测试点</TH>
                              <TH>结果</TH>
                              <TH>耗时</TH>
                              <TH>内存</TH>
                              <TH>输出</TH>
                            </TR>
                          </THead>
                          <TBody>
                            {submission.results.map((item, index) => (
                              <TR key={item.test_case_id}>
                                <TD>#{index + 1}</TD>
                                <TD>
                                  {item.passed ? (
                                    <Badge variant="success">通过</Badge>
                                  ) : (
                                    <Badge variant="danger">未通过</Badge>
                                  )}
                                </TD>
                                <TD>{formatTime(item.time_ms)}</TD>
                                <TD>{formatMemory(item.memory_kb)}</TD>
                                <TD className="max-w-[200px] truncate font-mono text-[11px] text-muted-foreground">
                                  {item.actual_output ?? '（隐藏）'}
                                </TD>
                              </TR>
                            ))}
                          </TBody>
                        </Table>
                      ) : null}

                      {errorAnalysis ? (
                        <div className="rounded-lg border border-primary/25 bg-primary/5 p-3">
                          <p className="mb-1 flex items-center gap-1.5 text-[12px] font-medium text-primary">
                            <Bot className="h-3.5 w-3.5" />
                            AI 错误分析
                          </p>
                          <Markdown content={errorAnalysis} />
                        </div>
                      ) : null}
                    </div>
                  ) : (
                    <EmptyState
                      icon={<Target className="h-5 w-5" />}
                      title="还没有提交记录"
                      description="点击右上角「提交判题」，结果会显示在这里。"
                      className="border-0 py-8"
                    />
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="local" className="pt-3">
              <Card>
                <CardContent className="pt-5">
                  <ResultPanel
                    result={runner.result}
                    running={runner.running}
                    error={runner.error}
                    emptyHint="点击「运行样例」用样例输入试跑代码"
                    className="min-h-[240px]"
                  />
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </PageContainer>
  );
}
