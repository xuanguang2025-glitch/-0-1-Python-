'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { CheckCircle2, ListChecks, Play, RotateCcw, Save, Send, Target } from 'lucide-react';
import { projectApi } from '@/lib/api';
import { DIFFICULTY_LABEL, DIFFICULTY_STYLE } from '@/lib/constants';
import { cn } from '@/lib/utils';
import { useFetch } from '@/hooks/useFetch';
import { usePythonRunner } from '@/hooks/usePythonRunner';
import { useToaster } from '@/hooks/useToast';
import { useAuth } from '@/hooks/useAuth';
import { MonacoEditor } from '@/components/code/monaco-editor';
import { FileTree, type FileNode } from '@/components/code/file-tree';
import { ResultPanel } from '@/components/code/result-panel';
import { Markdown } from '@/components/markdown';
import { PageContainer } from '@/components/layout/page-container';
import { Alert, EmptyState, ErrorState } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

export interface ProjectDetailViewProps {
  projectId: string;
}

/** 项目详情：需求 + 步骤 + 多文件工程编辑 + 运行 + 提交。 */
export function ProjectDetailView({ projectId }: ProjectDetailViewProps): React.ReactElement {
  const toaster = useToaster();
  const { isAuthenticated } = useAuth();
  const runner = usePythonRunner();

  const detail = useFetch(() => projectApi.detail(projectId), [projectId]);
  const mine = useFetch(() => projectApi.mine(projectId), [projectId], { enabled: isAuthenticated });

  const [files, setFiles] = useState<FileNode[]>([]);
  const [activePath, setActivePath] = useState('main.py');
  const [starting, setStarting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [tab, setTab] = useState('requirement');

  const project = detail.data?.project;
  const steps = detail.data?.steps ?? [];
  const activeFile = files.find((file) => file.path === activePath) ?? files[0] ?? null;

  /** 初始化用户文件：优先用 my.files_json，其次用项目模板。 */
  useEffect(() => {
    if (mine.data?.files_json && Object.keys(mine.data.files_json).length > 0) {
      setFiles(
        Object.entries(mine.data.files_json).map(([path, content]) => ({
          path,
          content,
          isEntry: path === 'main.py',
        })),
      );
      setActivePath(Object.keys(mine.data.files_json)[0]);
      return;
    }
    if (detail.data?.files && detail.data.files.length > 0) {
      setFiles(
        detail.data.files.map((file) => ({ path: file.path, content: file.content, isEntry: file.is_entry })),
      );
      const entry = detail.data.files.find((file) => file.is_entry) ?? detail.data.files[0];
      setActivePath(entry.path);
    }
  }, [mine.data, detail.data]);

  const start = async (): Promise<void> => {
    if (!isAuthenticated) {
      toaster.info('请先登录再开始项目');
      return;
    }
    setStarting(true);
    try {
      const result = await projectApi.start(projectId);
      setFiles(
        Object.entries(result.files_json).map(([path, content]) => ({ path, content, isEntry: path === 'main.py' })),
      );
      mine.refresh();
      toaster.success('项目已初始化', '文件副本已创建，开始写代码吧');
    } catch (error) {
      toaster.error('初始化失败', error instanceof Error ? error.message : '请稍后再试');
    } finally {
      setStarting(false);
    }
  };

  const saveFiles = useCallback(
    async (silent = false) => {
      if (!isAuthenticated) {
        if (!silent) toaster.info('未登录，代码仅保存在本地');
        return;
      }
      setSaving(true);
      try {
        const map = files.reduce<Record<string, string>>((acc, file) => {
          acc[file.path] = file.content;
          return acc;
        }, {});
        await projectApi.saveFiles(projectId, map);
        if (!silent) toaster.success('已保存项目文件');
      } catch (error) {
        if (!silent) toaster.error('保存失败', error instanceof Error ? error.message : '请稍后再试');
      } finally {
        setSaving(false);
      }
    },
    [files, isAuthenticated, projectId, toaster],
  );

  const run = async (): Promise<void> => {
    if (!activeFile) return;
    await runner.run(
      files.map((file) => ({ path: file.path, content: file.content })),
      { entry: activeFile.isEntry ? activeFile.path : files.find((f) => f.isEntry)?.path ?? activeFile.path },
    );
    setTab('run');
  };

  const submit = async (): Promise<void> => {
    if (!isAuthenticated) {
      toaster.info('请先登录再提交项目');
      return;
    }
    setSubmitting(true);
    try {
      await saveFiles(true);
      const result = await projectApi.submit(projectId);
      toaster.success('提交成功', `获得 ${result.xp_earned} XP`);
      mine.refresh();
      detail.refresh();
    } catch (error) {
      toaster.error('提交失败', error instanceof Error ? error.message : '请检查项目是否完整');
    } finally {
      setSubmitting(false);
    }
  };

  const progressPercent = mine.data?.progress_percent ?? 0;
  const completedSteps = useMemo(() => new Set(mine.data?.completed_steps ?? []), [mine.data]);

  if (detail.loading && !detail.data) {
    return (
      <PageContainer>
        <div className="grid gap-4 lg:grid-cols-[1fr_1.2fr]">
          <Skeleton className="h-96 w-full" />
          <Skeleton className="h-96 w-full" />
        </div>
      </PageContainer>
    );
  }

  if (detail.error && !detail.data) {
    return (
      <PageContainer title="项目详情">
        <ErrorState title="项目加载失败" description={detail.error} onRetry={detail.refresh} />
      </PageContainer>
    );
  }

  if (!project) {
    return (
      <PageContainer title="项目详情">
        <EmptyState icon={<Target className="h-6 w-6" />} title="未找到该项目" description={`id = ${projectId}`} />
      </PageContainer>
    );
  }

  return (
    <PageContainer width="wide">
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]">
        {/* 左：需求与步骤 */}
        <div className="min-w-0 space-y-3">
          <Card>
            <CardContent className="space-y-3 pt-5">
              <div className="flex flex-wrap items-center gap-2">
                <Badge className={DIFFICULTY_STYLE[project.difficulty]}>{DIFFICULTY_LABEL[project.difficulty]}</Badge>
                <Badge variant="secondary">{project.category}</Badge>
                <Badge variant="outline">约 {project.estimated_hours} 小时</Badge>
              </div>
              <h1 className="text-xl font-semibold tracking-tight">{project.title}</h1>
              <p className="text-[13px] text-muted-foreground">{project.summary}</p>
              <div className="space-y-1.5">
                <Progress value={progressPercent} size="sm" showValue />
                <p className="text-[11px] text-muted-foreground">项目完成度</p>
              </div>
              <div className="flex flex-wrap gap-2">
                {!mine.data ? (
                  <Button loading={starting} onClick={() => void start()}>
                    <Play className="h-4 w-4" />
                    开始项目
                  </Button>
                ) : null}
                <Button variant="outline" loading={saving} onClick={() => void saveFiles(false)}>
                  <Save className="h-4 w-4" />
                  保存文件
                </Button>
                <Button variant="outline" loading={submitting} onClick={() => void submit()}>
                  <Send className="h-4 w-4" />
                  提交项目
                </Button>
              </div>
            </CardContent>
          </Card>

          <Tabs value={tab} onValueChange={setTab}>
            <TabsList>
              <TabsTrigger value="requirement">项目需求</TabsTrigger>
              <TabsTrigger value="steps">
                <ListChecks className="h-3.5 w-3.5" />
                实现步骤（{steps.length}）
              </TabsTrigger>
              <TabsTrigger value="run">运行结果</TabsTrigger>
            </TabsList>

            <TabsContent value="requirement" className="pt-3">
              <Card>
                <CardContent className="pt-5">
                  {project.requirement_md ? (
                    <Markdown content={project.requirement_md} />
                  ) : (
                    <EmptyState title="暂无需求说明" className="border-0 py-8" />
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="steps" className="pt-3">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle>实现步骤</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {steps.length === 0 ? (
                    <EmptyState title="暂无步骤" description="项目文档还在整理中。" className="border-0 py-6" />
                  ) : (
                    steps.map((step, index) => {
                      const done = completedSteps.has(step.id) || index < (mine.data?.current_step ?? 0);
                      return (
                        <div
                          key={step.id}
                          className={cn(
                            'rounded-lg border p-3',
                            done ? 'border-emerald-500/30 bg-emerald-500/6' : 'border-border',
                          )}
                        >
                          <p className="flex items-center gap-2 text-[13px] font-medium">
                            <span
                              className={cn(
                                'flex h-5 w-5 items-center justify-center rounded-full text-[10px]',
                                done ? 'bg-emerald-500/15 text-emerald-500' : 'bg-muted text-muted-foreground',
                              )}
                            >
                              {done ? <CheckCircle2 className="h-3 w-3" /> : index + 1}
                            </span>
                            {step.title}
                          </p>
                          {step.description_md ? (
                            <p className="mt-1.5 pl-7 text-[12px] leading-relaxed text-muted-foreground">
                              {step.description_md}
                            </p>
                          ) : null}
                        </div>
                      );
                    })
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="run" className="pt-3">
              <Card>
                <CardContent className="pt-5">
                  <ResultPanel
                    result={runner.result}
                    running={runner.running}
                    error={runner.error}
                    emptyHint="点击「运行项目」执行入口文件"
                    className="min-h-[240px]"
                  />
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>

        {/* 右：代码工程 */}
        <div className="space-y-3">
          {!isAuthenticated ? (
            <Alert variant="info" title="登录后可保存项目文件" description="未登录时可以浏览代码，但修改不会同步到云端。" />
          ) : !mine.data ? (
            <Alert
              variant="warning"
              title="项目尚未初始化"
              description="点击「开始项目」会为你的账号创建一份文件副本，之后的修改都会保存到这份副本。"
              action={
                <Button size="sm" loading={starting} onClick={() => void start()}>
                  开始项目
                </Button>
              }
            />
          ) : null}

          <div className="grid grid-cols-[160px_minmax(0,1fr)] overflow-hidden rounded-lg border border-border">
            <div className="border-r border-border bg-card/40">
              <FileTree
                files={files}
                activePath={activeFile?.path ?? ''}
                onSelect={setActivePath}
                onCreate={(path, content) => setFiles((prev) => [...prev, { path, content }])}
                onDelete={(path) =>
                  setFiles((prev) => (prev.length > 1 ? prev.filter((file) => file.path !== path) : prev))
                }
                onRename={(from, to) =>
                  setFiles((prev) => prev.map((file) => (file.path === from ? { ...file, path: to } : file)))
                }
              />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2 border-b border-border bg-card/60 px-3 py-1.5">
                <span className="font-mono text-[12px]">{activeFile?.path ?? '未选择文件'}</span>
                <div className="ml-auto flex items-center gap-1.5">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => {
                      const template = detail.data?.files.find((file) => file.path === activeFile?.path);
                      if (template && activeFile) {
                        setFiles((prev) =>
                          prev.map((file) => (file.path === activeFile.path ? { ...file, content: template.content } : file)),
                        );
                        toaster.info('已还原为初始模板');
                      }
                    }}
                  >
                    <RotateCcw className="h-3.5 w-3.5" />
                    还原
                  </Button>
                  <Button size="sm" loading={runner.running} onClick={() => void run()}>
                    <Play className="h-3.5 w-3.5" />
                    运行项目
                  </Button>
                </div>
              </div>
              {activeFile ? (
                <MonacoEditor
                  value={activeFile.content}
                  onChange={(content) =>
                    setFiles((prev) => prev.map((file) => (file.path === activeFile.path ? { ...file, content } : file)))
                  }
                  language="python"
                  height={460}
                  onRun={() => void run()}
                  onSave={() => void saveFiles(false)}
                />
              ) : (
                <div className="flex h-[460px] items-center justify-center text-[13px] text-muted-foreground">
                  请先开始项目以生成文件
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </PageContainer>
  );
}
