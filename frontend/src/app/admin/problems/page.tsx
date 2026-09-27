'use client';

import { useState } from 'react';
import { ChevronLeft, ChevronRight, Pencil, Plus, Search, Trash2, Upload } from 'lucide-react';
import { adminApi } from '@/lib/api';
import { DIFFICULTY_LABEL, DIFFICULTY_STYLE, PROBLEM_TYPE_LABEL } from '@/lib/constants';
import { formatPercent } from '@/lib/utils';
import { useDebounce } from '@/hooks/useDebounce';
import { useFetch } from '@/hooks/useFetch';
import { useToaster } from '@/hooks/useToast';
import { Alert, EmptyState, ErrorState } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Field, Input, Textarea } from '@/components/ui/input';
import { Modal, ConfirmDialog } from '@/components/ui/modal';
import { Select } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table';
import type { ProblemBrief } from '@/lib/types';

const DIFFICULTY_OPTIONS = ['easy', 'medium', 'hard', 'expert'].map((value) => ({
  value,
  label: DIFFICULTY_LABEL[value as keyof typeof DIFFICULTY_LABEL],
}));

const TYPE_OPTIONS = ['coding', 'algorithm', 'debug', 'choice', 'judge', 'blank', 'completion'].map((value) => ({
  value,
  label: PROBLEM_TYPE_LABEL[value as keyof typeof PROBLEM_TYPE_LABEL],
}));

const PAGE_SIZE = 20;

const EMPTY_FORM = {
  slug: '',
  title: '',
  difficulty: 'easy',
  problem_type: 'coding',
  category: 'basics',
  statement_md: '',
  time_limit_ms: '1000',
  memory_limit_mb: '128',
};

/** 题目管理：列表 + 新建 / 编辑 / 删除 / 批量导入入口骨架。 */
export default function AdminProblemsPage(): React.ReactElement {
  const toaster = useToaster();
  const [keyword, setKeyword] = useState('');
  const [difficulty, setDifficulty] = useState('');
  const [page, setPage] = useState(1);
  const debounced = useDebounce(keyword, 300);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<ProblemBrief | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<ProblemBrief | null>(null);

  const list = useFetch(
    () =>
      adminApi.problems({
        keyword: debounced || undefined,
        difficulty: difficulty || undefined,
        page,
        page_size: PAGE_SIZE,
      }),
    [debounced, difficulty, page],
  );

  const openCreate = (): void => {
    setEditing(null);
    setForm(EMPTY_FORM);
    setOpen(true);
  };

  const openEdit = (problem: ProblemBrief): void => {
    setEditing(problem);
    setForm({
      slug: problem.slug,
      title: problem.title,
      difficulty: problem.difficulty,
      problem_type: problem.problem_type,
      category: problem.category,
      statement_md: '',
      time_limit_ms: '1000',
      memory_limit_mb: '128',
    });
    setOpen(true);
  };

  const submit = async (): Promise<void> => {
    if (!form.slug || !form.title) {
      toaster.error('slug 与标题必填');
      return;
    }
    setSaving(true);
    const payload = {
      slug: form.slug,
      title: form.title,
      difficulty: form.difficulty,
      problem_type: form.problem_type,
      category: form.category,
      statement_md: form.statement_md,
      time_limit_ms: Number(form.time_limit_ms),
      memory_limit_mb: Number(form.memory_limit_mb),
    };
    try {
      if (editing) {
        await adminApi.updateProblem(editing.id, payload);
        toaster.success('题目已更新');
      } else {
        await adminApi.createProblem(payload);
        toaster.success('题目已创建', '别忘了补充测试用例');
      }
      setOpen(false);
      list.refresh();
    } catch (error) {
      toaster.error('保存失败', error instanceof Error ? error.message : '请稍后再试');
    } finally {
      setSaving(false);
    }
  };

  const remove = async (): Promise<void> => {
    if (!deleteTarget) return;
    try {
      await adminApi.deleteProblem(deleteTarget.id);
      toaster.success('已删除题目');
      setDeleteTarget(null);
      list.refresh();
    } catch (error) {
      toaster.error('删除失败', error instanceof Error ? error.message : '请稍后再试');
    }
  };

  const importHint = (): void => {
    toaster.info('批量导入接口已就绪', 'POST /api/admin/problems/import（multipart JSON 文件，≤10MB）');
  };

  const items = list.data?.items ?? [];
  const totalPages = list.data?.pages ?? 1;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-[220px] flex-1">
          <Input
            value={keyword}
            onChange={(event) => {
              setKeyword(event.target.value);
              setPage(1);
            }}
            placeholder="搜索题目标题 / slug"
            icon={<Search className="h-3.5 w-3.5" />}
          />
        </div>
        <div className="w-32">
          <Select
            value={difficulty}
            options={[{ value: '', label: '全部难度' }, ...DIFFICULTY_OPTIONS]}
            onChange={(event) => {
              setDifficulty(event.target.value);
              setPage(1);
            }}
          />
        </div>
        <Button variant="outline" onClick={importHint}>
          <Upload className="h-4 w-4" />
          批量导入
        </Button>
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4" />
          新建题目
        </Button>
      </div>

      <Alert
        variant="info"
        title="测试用例管理"
        description="题目创建后需在测试用例面板补充输入 / 期望输出（POST /api/admin/test-cases），本页暂只提供题面字段骨架。"
      />

      <Card>
        <CardContent className="pt-5">
          {list.loading && !list.data ? (
            <Skeleton className="h-64 w-full" />
          ) : list.error && !list.data ? (
            <ErrorState title="题目列表加载失败" description={list.error} onRetry={list.refresh} />
          ) : items.length === 0 ? (
            <EmptyState title="暂无题目" description="点击「新建题目」或使用批量导入。" className="border-0 py-8" />
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>题目</TH>
                  <TH>Slug</TH>
                  <TH>难度</TH>
                  <TH>题型</TH>
                  <TH>分类</TH>
                  <TH>通过率</TH>
                  <TH className="text-right">操作</TH>
                </TR>
              </THead>
              <TBody>
                {items.map((problem) => (
                  <TR key={problem.id}>
                    <TD className="font-medium">{problem.title}</TD>
                    <TD className="font-mono text-[11.5px] text-muted-foreground">{problem.slug}</TD>
                    <TD>
                      <Badge className={DIFFICULTY_STYLE[problem.difficulty]}>{DIFFICULTY_LABEL[problem.difficulty]}</Badge>
                    </TD>
                    <TD className="text-muted-foreground">{PROBLEM_TYPE_LABEL[problem.problem_type]}</TD>
                    <TD className="text-muted-foreground">{problem.category}</TD>
                    <TD>{formatPercent(problem.acceptance_rate ?? 0, 0)}</TD>
                    <TD>
                      <div className="flex items-center justify-end gap-1">
                        <Button size="icon-sm" variant="ghost" aria-label="编辑题目" onClick={() => openEdit(problem)}>
                          <Pencil className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          size="icon-sm"
                          variant="ghost"
                          aria-label="删除题目"
                          className="text-destructive"
                          onClick={() => setDeleteTarget(problem)}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {totalPages > 1 ? (
        <div className="flex items-center justify-center gap-3">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((prev) => prev - 1)}>
            <ChevronLeft className="h-3.5 w-3.5" />
            上一页
          </Button>
          <span className="text-[12px] text-muted-foreground">
            第 {page} / {totalPages} 页
          </span>
          <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage((prev) => prev + 1)}>
            下一页
            <ChevronRight className="h-3.5 w-3.5" />
          </Button>
        </div>
      ) : null}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={editing ? `编辑题目：${editing.title}` : '新建题目'}
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              取消
            </Button>
            <Button loading={saving} onClick={() => void submit()}>
              保存
            </Button>
          </>
        }
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Slug" required>
            <Input value={form.slug} onChange={(event) => setForm({ ...form, slug: event.target.value })} />
          </Field>
          <Field label="标题" required>
            <Input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} />
          </Field>
          <Field label="难度">
            <Select value={form.difficulty} options={DIFFICULTY_OPTIONS} onChange={(event) => setForm({ ...form, difficulty: event.target.value })} />
          </Field>
          <Field label="题型">
            <Select value={form.problem_type} options={TYPE_OPTIONS} onChange={(event) => setForm({ ...form, problem_type: event.target.value })} />
          </Field>
          <Field label="分类" hint="如 basics / strings / algorithms">
            <Input value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })} />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="时间限制(ms)">
              <Input
                type="number"
                value={form.time_limit_ms}
                onChange={(event) => setForm({ ...form, time_limit_ms: event.target.value })}
              />
            </Field>
            <Field label="内存限制(MB)">
              <Input
                type="number"
                value={form.memory_limit_mb}
                onChange={(event) => setForm({ ...form, memory_limit_mb: event.target.value })}
              />
            </Field>
          </div>
          <div className="sm:col-span-2">
            <Field label="题面（Markdown）" hint="包含输入格式、输出格式、样例与约束">
              <Textarea
                rows={6}
                value={form.statement_md}
                onChange={(event) => setForm({ ...form, statement_md: event.target.value })}
              />
            </Field>
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title={`确认删除题目「${deleteTarget?.title ?? ''}」？`}
        description="会同时删除其测试用例与提交记录关联。"
        danger
        confirmText="确认删除"
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => void remove()}
      />
    </div>
  );
}
