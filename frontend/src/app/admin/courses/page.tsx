'use client';

import { useState } from 'react';
import { ChevronLeft, ChevronRight, Pencil, Plus, Search, Trash2 } from 'lucide-react';
import { adminApi } from '@/lib/api';
import { STAGE_GROUP_LABEL } from '@/lib/constants';
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
import type { CourseBrief } from '@/lib/types';

const LEVEL_OPTIONS = [
  { value: 'beginner', label: '基础语法' },
  { value: 'intermediate', label: '进阶能力' },
  { value: 'advanced', label: '工程实战' },
];

const PAGE_SIZE = 20;

const EMPTY_FORM = {
  slug: '',
  stage_no: '1',
  title: '',
  subtitle: '',
  level: 'beginner',
  estimated_hours: '8',
  description_md: '',
};

/** 课程管理：列表 + 新建 / 编辑 / 删除骨架。 */
export default function AdminCoursesPage(): React.ReactElement {
  const toaster = useToaster();
  const [keyword, setKeyword] = useState('');
  const [page, setPage] = useState(1);
  const debounced = useDebounce(keyword, 300);
  const [editing, setEditing] = useState<CourseBrief | null>(null);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<CourseBrief | null>(null);

  const list = useFetch(
    () => adminApi.courses({ keyword: debounced || undefined, page, page_size: PAGE_SIZE }),
    [debounced, page],
  );

  const openCreate = (): void => {
    setEditing(null);
    setForm(EMPTY_FORM);
    setOpen(true);
  };

  const openEdit = (course: CourseBrief): void => {
    setEditing(course);
    setForm({
      slug: course.slug,
      stage_no: String(course.stage_no),
      title: course.title,
      subtitle: course.subtitle ?? '',
      level: course.level,
      estimated_hours: String(course.estimated_hours ?? 8),
      description_md: course.description_md ?? '',
    });
    setOpen(true);
  };

  const submit = async (): Promise<void> => {
    if (!form.title || !form.slug) {
      toaster.error('slug 与标题必填');
      return;
    }
    setSaving(true);
    const payload = {
      slug: form.slug,
      stage_no: Number(form.stage_no),
      title: form.title,
      subtitle: form.subtitle || null,
      level: form.level,
      estimated_hours: Number(form.estimated_hours),
      description_md: form.description_md || null,
    };
    try {
      if (editing) {
        await adminApi.updateCourse(editing.id, payload);
        toaster.success('课程已更新');
      } else {
        await adminApi.createCourse(payload);
        toaster.success('课程已创建');
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
      await adminApi.deleteCourse(deleteTarget.id);
      toaster.success('已删除课程');
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
            placeholder="搜索课程标题 / slug"
            icon={<Search className="h-3.5 w-3.5" />}
          />
        </div>
        <Badge variant="secondary">共 {list.data?.total ?? 0} 个阶段</Badge>
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4" />
          新建课程
        </Button>
      </div>

      <Card>
        <CardContent className="pt-5">
          {list.loading && !list.data ? (
            <Skeleton className="h-64 w-full" />
          ) : list.error && !list.data ? (
            <ErrorState title="课程列表加载失败" description={list.error} onRetry={list.refresh} />
          ) : items.length === 0 ? (
            <EmptyState title="暂无课程" description="点击「新建课程」创建第一个阶段。" className="border-0 py-8" />
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>阶段</TH>
                  <TH>标题</TH>
                  <TH>Slug</TH>
                  <TH>难度组</TH>
                  <TH>课时 / 学时</TH>
                  <TH className="text-right">操作</TH>
                </TR>
              </THead>
              <TBody>
                {items.map((course) => (
                  <TR key={course.id}>
                    <TD className="font-mono text-[12px]">{String(course.stage_no).padStart(2, '0')}</TD>
                    <TD>
                      <div className="space-y-0.5">
                        <p className="font-medium">{course.title}</p>
                        <p className="max-w-[280px] truncate text-[11px] text-muted-foreground">{course.subtitle}</p>
                      </div>
                    </TD>
                    <TD className="font-mono text-[11.5px] text-muted-foreground">{course.slug}</TD>
                    <TD>
                      <Badge variant="secondary">{STAGE_GROUP_LABEL[course.level]}</Badge>
                    </TD>
                    <TD>
                      {course.lesson_count} / {course.estimated_hours}h
                    </TD>
                    <TD>
                      <div className="flex items-center justify-end gap-1">
                        <Button size="icon-sm" variant="ghost" aria-label="编辑课程" onClick={() => openEdit(course)}>
                          <Pencil className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          size="icon-sm"
                          variant="ghost"
                          aria-label="删除课程"
                          className="text-destructive"
                          onClick={() => setDeleteTarget(course)}
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
        title={editing ? `编辑课程：${editing.title}` : '新建课程'}
        description="课程对应学习路线图中的一个阶段。"
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
          <Field label="Slug" hint="唯一标识，如 stage-01-python-basics" required>
            <Input value={form.slug} onChange={(event) => setForm({ ...form, slug: event.target.value })} />
          </Field>
          <Field label="阶段序号" required>
            <Input
              type="number"
              min={1}
              max={18}
              value={form.stage_no}
              onChange={(event) => setForm({ ...form, stage_no: event.target.value })}
            />
          </Field>
          <Field label="标题" required>
            <Input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} />
          </Field>
          <Field label="副标题">
            <Input value={form.subtitle} onChange={(event) => setForm({ ...form, subtitle: event.target.value })} />
          </Field>
          <Field label="难度组">
            <Select value={form.level} options={LEVEL_OPTIONS} onChange={(event) => setForm({ ...form, level: event.target.value })} />
          </Field>
          <Field label="预计学时">
            <Input
              type="number"
              min={1}
              value={form.estimated_hours}
              onChange={(event) => setForm({ ...form, estimated_hours: event.target.value })}
            />
          </Field>
          <div className="sm:col-span-2">
            <Field label="阶段简介（Markdown）">
              <Textarea
                rows={4}
                value={form.description_md}
                onChange={(event) => setForm({ ...form, description_md: event.target.value })}
              />
            </Field>
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title={`确认删除课程「${deleteTarget?.title ?? ''}」？`}
        description="会级联删除章节与课时，请谨慎操作。"
        danger
        confirmText="确认删除"
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => void remove()}
      />
    </div>
  );
}
