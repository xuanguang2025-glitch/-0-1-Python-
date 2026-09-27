'use client';

import { useState } from 'react';
import { ChevronLeft, ChevronRight, Pencil, Plus, Search, Trash2 } from 'lucide-react';
import { adminApi } from '@/lib/api';
import { DIFFICULTY_LABEL, DIFFICULTY_STYLE } from '@/lib/constants';
import { useDebounce } from '@/hooks/useDebounce';
import { useFetch } from '@/hooks/useFetch';
import { useToaster } from '@/hooks/useToast';
import { EmptyState, ErrorState } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Field, Input, Textarea } from '@/components/ui/input';
import { Modal, ConfirmDialog } from '@/components/ui/modal';
import { Select } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table';
import type { ProjectBrief } from '@/lib/types';

const DIFFICULTY_OPTIONS = ['easy', 'medium', 'hard', 'expert'].map((value) => ({
  value,
  label: DIFFICULTY_LABEL[value as keyof typeof DIFFICULTY_LABEL],
}));

const PAGE_SIZE = 20;

const EMPTY_FORM = { slug: '', title: '', summary: '', category: 'tool', level: '1', difficulty: 'medium' };

/** 项目管理：列表 + 新建 / 编辑 / 删除骨架。 */
export default function AdminProjectsPage(): React.ReactElement {
  const toaster = useToaster();
  const [keyword, setKeyword] = useState('');
  const [page, setPage] = useState(1);
  const debounced = useDebounce(keyword, 300);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<ProjectBrief | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<ProjectBrief | null>(null);

  const list = useFetch(
    () => adminApi.projects({ keyword: debounced || undefined, page, page_size: PAGE_SIZE }),
    [debounced, page],
  );

  const openCreate = (): void => {
    setEditing(null);
    setForm(EMPTY_FORM);
    setOpen(true);
  };

  const openEdit = (project: ProjectBrief): void => {
    setEditing(project);
    setForm({
      slug: project.slug,
      title: project.title,
      summary: project.summary ?? '',
      category: project.category,
      level: String(project.level),
      difficulty: project.difficulty,
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
      summary: form.summary || null,
      category: form.category,
      level: Number(form.level),
      difficulty: form.difficulty,
    };
    try {
      if (editing) {
        await adminApi.updateProject(editing.id, payload);
        toaster.success('项目已更新');
      } else {
        await adminApi.createProject(payload);
        toaster.success('项目已创建', '请继续添加项目文件与步骤');
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
      await adminApi.deleteProject(deleteTarget.id);
      toaster.success('已删除项目');
      setDeleteTarget(null);
      list.refresh();
    } catch (error) {
      toaster.error('删除失败', error instanceof Error ? error.message : '请稍后再试');
    }
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
            placeholder="搜索项目标题 / slug"
            icon={<Search className="h-3.5 w-3.5" />}
          />
        </div>
        <Badge variant="secondary">共 {list.data?.total ?? 0} 个项目</Badge>
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4" />
          新建项目
        </Button>
      </div>

      <Card>
        <CardContent className="pt-5">
          {list.loading && !list.data ? (
            <Skeleton className="h-64 w-full" />
          ) : list.error && !list.data ? (
            <ErrorState title="项目列表加载失败" description={list.error} onRetry={list.refresh} />
          ) : items.length === 0 ? (
            <EmptyState title="暂无项目" description="点击「新建项目」开始创建实战项目。" className="border-0 py-8" />
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>项目</TH>
                  <TH>Slug</TH>
                  <TH>分类</TH>
                  <TH>难度</TH>
                  <TH>等级</TH>
                  <TH className="text-right">操作</TH>
                </TR>
              </THead>
              <TBody>
                {items.map((project) => (
                  <TR key={project.id}>
                    <TD>
                      <div className="space-y-0.5">
                        <p className="font-medium">{project.title}</p>
                        <p className="max-w-[280px] truncate text-[11px] text-muted-foreground">{project.summary}</p>
                      </div>
                    </TD>
                    <TD className="font-mono text-[11.5px] text-muted-foreground">{project.slug}</TD>
                    <TD className="text-muted-foreground">{project.category}</TD>
                    <TD>
                      <Badge className={DIFFICULTY_STYLE[project.difficulty]}>{DIFFICULTY_LABEL[project.difficulty]}</Badge>
                    </TD>
                    <TD>Lv.{project.level}</TD>
                    <TD>
                      <div className="flex items-center justify-end gap-1">
                        <Button size="icon-sm" variant="ghost" aria-label="编辑项目" onClick={() => openEdit(project)}>
                          <Pencil className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          size="icon-sm"
                          variant="ghost"
                          aria-label="删除项目"
                          className="text-destructive"
                          onClick={() => setDeleteTarget(project)}
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
        title={editing ? `编辑项目：${editing.title}` : '新建项目'}
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
          <Field label="分类" hint="tool / data / web / automation / game">
            <Input value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })} />
          </Field>
          <Field label="难度">
            <Select
              value={form.difficulty}
              options={DIFFICULTY_OPTIONS}
              onChange={(event) => setForm({ ...form, difficulty: event.target.value })}
            />
          </Field>
          <Field label="等级">
            <Input type="number" min={1} value={form.level} onChange={(event) => setForm({ ...form, level: event.target.value })} />
          </Field>
          <div className="sm:col-span-2">
            <Field label="简介">
              <Textarea rows={3} value={form.summary} onChange={(event) => setForm({ ...form, summary: event.target.value })} />
            </Field>
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title={`确认删除项目「${deleteTarget?.title ?? ''}」？`}
        description="项目文件与用户副本会一并失效。"
        danger
        confirmText="确认删除"
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => void remove()}
      />
    </div>
  );
}
