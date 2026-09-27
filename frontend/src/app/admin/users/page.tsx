'use client';

import { useState } from 'react';
import { ChevronLeft, ChevronRight, KeyRound, Pencil, Plus, Search, Trash2, UserPlus } from 'lucide-react';
import { adminApi } from '@/lib/api';
import { cn } from '@/lib/utils';
import { useDebounce } from '@/hooks/useDebounce';
import { useFetch } from '@/hooks/useFetch';
import { useToaster } from '@/hooks/useToast';
import { EmptyState, ErrorState } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Field, Input } from '@/components/ui/input';
import { Modal, ConfirmDialog } from '@/components/ui/modal';
import { Select } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table';
import type { AdminUserItem, UserRole } from '@/lib/types';

const ROLE_OPTIONS = [
  { value: 'user', label: '普通用户' },
  { value: 'admin', label: '管理员' },
  { value: 'superadmin', label: '超级管理员' },
];

const STATUS_LABEL: Record<string, string> = { active: '正常', suspended: '已禁用', deleted: '已删除' };

const PAGE_SIZE = 20;

/** 用户管理：列表 + 角色调整 + 新建 + 重置密码 + 软删除骨架。 */
export default function AdminUsersPage(): React.ReactElement {
  const toaster = useToaster();
  const [keyword, setKeyword] = useState('');
  const [page, setPage] = useState(1);
  const debounced = useDebounce(keyword, 300);
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState({ email: '', username: '', password: '', role: 'user' });
  const [saving, setSaving] = useState(false);
  const [resetUser, setResetUser] = useState<AdminUserItem | null>(null);
  const [newPassword, setNewPassword] = useState('');
  const [deleteTarget, setDeleteTarget] = useState<AdminUserItem | null>(null);

  const list = useFetch(
    () => adminApi.users({ keyword: debounced || undefined, page, page_size: PAGE_SIZE }),
    [debounced, page],
  );

  const create = async (): Promise<void> => {
    if (!form.email || !form.username || !form.password) {
      toaster.error('请填写邮箱、用户名与密码');
      return;
    }
    setSaving(true);
    try {
      await adminApi.createUser(form);
      toaster.success('用户已创建', form.username);
      setCreateOpen(false);
      setForm({ email: '', username: '', password: '', role: 'user' });
      list.refresh();
    } catch (error) {
      toaster.error('创建失败', error instanceof Error ? error.message : '请稍后再试');
    } finally {
      setSaving(false);
    }
  };

  const changeRole = async (user: AdminUserItem, role: string): Promise<void> => {
    try {
      await adminApi.updateUser(user.id, { role });
      toaster.success('角色已更新', `${user.username} → ${role}`);
      list.refresh();
    } catch (error) {
      toaster.error('更新失败', error instanceof Error ? error.message : '请稍后再试');
    }
  };

  const toggleStatus = async (user: AdminUserItem): Promise<void> => {
    const next = user.status === 'active' ? 'suspended' : 'active';
    try {
      await adminApi.updateUser(user.id, { status: next });
      toaster.success(next === 'active' ? '已恢复账号' : '已禁用账号', user.username);
      list.refresh();
    } catch (error) {
      toaster.error('操作失败', error instanceof Error ? error.message : '请稍后再试');
    }
  };

  const resetPassword = async (): Promise<void> => {
    if (!resetUser) return;
    if (newPassword.length < 8) {
      toaster.error('新密码至少 8 位');
      return;
    }
    try {
      await adminApi.resetUserPassword(resetUser.id, newPassword);
      toaster.success('密码已重置', resetUser.username);
      setResetUser(null);
      setNewPassword('');
    } catch (error) {
      toaster.error('重置失败', error instanceof Error ? error.message : '请稍后再试');
    }
  };

  const removeUser = async (): Promise<void> => {
    if (!deleteTarget) return;
    try {
      await adminApi.deleteUser(deleteTarget.id);
      toaster.success('已软删除用户', deleteTarget.username);
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
            placeholder="搜索邮箱 / 用户名"
            icon={<Search className="h-3.5 w-3.5" />}
          />
        </div>
        <Badge variant="secondary">共 {list.data?.total ?? 0} 位用户</Badge>
        <Button onClick={() => setCreateOpen(true)}>
          <UserPlus className="h-4 w-4" />
          新建用户
        </Button>
      </div>

      <Card>
        <CardContent className="pt-5">
          {list.loading && !list.data ? (
            <Skeleton className="h-64 w-full" />
          ) : list.error && !list.data ? (
            <ErrorState title="用户列表加载失败" description={list.error} onRetry={list.refresh} />
          ) : items.length === 0 ? (
            <EmptyState title="没有匹配的用户" description="换个关键词试试。" className="border-0 py-8" />
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>用户</TH>
                  <TH>邮箱</TH>
                  <TH>角色</TH>
                  <TH>状态</TH>
                  <TH>等级 / XP</TH>
                  <TH>注册时间</TH>
                  <TH className="text-right">操作</TH>
                </TR>
              </THead>
              <TBody>
                {items.map((user) => (
                  <TR key={user.id}>
                    <TD>
                      <div className="space-y-0.5">
                        <p className="font-medium">{user.display_name || user.username}</p>
                        <p className="text-[11px] text-muted-foreground">@{user.username}</p>
                      </div>
                    </TD>
                    <TD className="text-muted-foreground">{user.email}</TD>
                    <TD>
                      <div className="w-32">
                        <Select
                          controlSize="sm"
                          value={user.role}
                          options={ROLE_OPTIONS}
                          onChange={(event) => void changeRole(user, event.target.value as UserRole)}
                        />
                      </div>
                    </TD>
                    <TD>
                      <Badge variant={user.status === 'active' ? 'success' : user.status === 'suspended' ? 'warning' : 'secondary'}>
                        {STATUS_LABEL[user.status] ?? user.status}
                      </Badge>
                    </TD>
                    <TD>
                      Lv.{user.level} · {user.xp}
                    </TD>
                    <TD className="text-muted-foreground">
                      {user.created_at ? new Date(user.created_at).toLocaleDateString('zh-CN') : '—'}
                    </TD>
                    <TD>
                      <div className="flex items-center justify-end gap-1">
                        <Button
                          size="icon-sm"
                          variant="ghost"
                          aria-label="重置密码"
                          onClick={() => setResetUser(user)}
                          title="重置密码"
                        >
                          <KeyRound className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => void toggleStatus(user)}
                        >
                          {user.status === 'active' ? '禁用' : '恢复'}
                        </Button>
                        <Button
                          size="icon-sm"
                          variant="ghost"
                          aria-label="删除用户"
                          onClick={() => setDeleteTarget(user)}
                          className={cn('text-destructive')}
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

      {/* 新建用户 */}
      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="新建用户"
        description="管理员可直接创建账号并分配角色。"
        footer={
          <>
            <Button variant="ghost" onClick={() => setCreateOpen(false)}>
              取消
            </Button>
            <Button loading={saving} onClick={() => void create()}>
              <Plus className="h-4 w-4" />
              创建
            </Button>
          </>
        }
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="邮箱" required>
            <Input value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} placeholder="user@example.com" />
          </Field>
          <Field label="用户名" required>
            <Input value={form.username} onChange={(event) => setForm({ ...form, username: event.target.value })} placeholder="pythonista" />
          </Field>
          <Field label="初始密码" hint="至少 8 位" required>
            <Input type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} />
          </Field>
          <Field label="角色">
            <Select value={form.role} options={ROLE_OPTIONS} onChange={(event) => setForm({ ...form, role: event.target.value })} />
          </Field>
        </div>
      </Modal>

      {/* 重置密码 */}
      <Modal
        open={Boolean(resetUser)}
        onClose={() => setResetUser(null)}
        title={`重置 ${resetUser?.username ?? ''} 的密码`}
        size="sm"
        footer={
          <>
            <Button variant="ghost" onClick={() => setResetUser(null)}>
              取消
            </Button>
            <Button onClick={() => void resetPassword()}>确认重置</Button>
          </>
        }
      >
        <Field label="新密码" hint="至少 8 位，建议提醒用户登录后修改" required>
          <Input type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} />
        </Field>
      </Modal>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title={`确认删除用户 ${deleteTarget?.username ?? ''}？`}
        description="该操作为软删除，30 天内可恢复。"
        danger
        confirmText="确认删除"
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => void removeUser()}
      />
    </div>
  );
}
