'use client';

import { useEffect, useState } from 'react';
import { useTheme } from 'next-themes';
import { Cpu, Download, KeyRound, Moon, Palette, Shield, Sun, Trash2, UserCog } from 'lucide-react';
import { authApi, userApi } from '@/lib/api';
import { AI_MODE_DESC, AI_MODE_LABEL } from '@/lib/constants';
import { cn } from '@/lib/utils';
import { useFetch } from '@/hooks/useFetch';
import { useToaster } from '@/hooks/useToast';
import { useAuth } from '@/hooks/useAuth';
import { useThemeStore } from '@/store/theme';
import { AuthGate } from '@/components/common/auth-gate';
import { PageContainer } from '@/components/layout/page-container';
import { Alert } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Field, Input } from '@/components/ui/input';
import { Modal } from '@/components/ui/modal';
import { Select } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Switch } from '@/components/ui/switch';
import type { AiMode } from '@/lib/types';

const LEARNING_MODE_OPTIONS = [
  { value: 'system', label: '系统学习（按路线图）' },
  { value: 'free', label: '自由学习' },
  { value: 'drill', label: '专项刷题' },
  { value: 'exam', label: '考试模式' },
  { value: 'project', label: '项目驱动' },
  { value: 'challenge', label: '挑战模式' },
  { value: 'ai', label: 'AI 陪练' },
];

const THEME_OPTIONS = [
  { value: 'dark', label: '深色（默认）', icon: <Moon className="h-3.5 w-3.5" /> },
  { value: 'light', label: '浅色', icon: <Sun className="h-3.5 w-3.5" /> },
  { value: 'system', label: '跟随系统', icon: <Palette className="h-3.5 w-3.5" /> },
];

const GOAL_OPTIONS = [120, 180, 300, 420, 600].map((value) => ({ value: String(value), label: `${value} 分钟 / 周` }));

/** 设置页：外观、学习偏好、AI 模式、账号安全。 */
function SettingsContent(): React.ReactElement {
  const toaster = useToaster();
  const { theme, setTheme } = useTheme();
  const setMode = useThemeStore((state) => state.setMode);
  const { logout } = useAuth();

  const profile = useFetch(() => userApi.profile(), []);
  const [aiMode, setAiMode] = useState<AiMode>('standard');
  const [learningMode, setLearningMode] = useState('system');
  const [weeklyGoal, setWeeklyGoal] = useState('300');
  const [publicProfile, setPublicProfile] = useState(true);
  const [savingPrefs, setSavingPrefs] = useState(false);

  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [changingPassword, setChangingPassword] = useState(false);

  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deletePassword, setDeletePassword] = useState('');
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (!profile.data) return;
    setAiMode((profile.data.ai_mode as AiMode) ?? 'standard');
    setLearningMode(profile.data.learning_mode ?? 'system');
    setWeeklyGoal(String(profile.data.weekly_goal_minutes ?? 300));
    setPublicProfile(profile.data.public_profile ?? true);
  }, [profile.data]);

  const changeTheme = (value: string): void => {
    setTheme(value);
    if (value === 'light' || value === 'dark' || value === 'system') setMode(value);
  };

  const savePreferences = async (): Promise<void> => {
    setSavingPrefs(true);
    try {
      await userApi.preferences({
        ai_mode: aiMode,
        learning_mode: learningMode,
        weekly_goal_minutes: Number(weeklyGoal),
        theme_preference: theme ?? 'dark',
        public_profile: publicProfile,
      });
      toaster.success('偏好已保存');
      profile.refresh();
    } catch (error) {
      toaster.error('保存失败', error instanceof Error ? error.message : '请稍后再试');
    } finally {
      setSavingPrefs(false);
    }
  };

  const changePassword = async (): Promise<void> => {
    if (newPassword.length < 8) {
      toaster.error('新密码至少 8 位');
      return;
    }
    if (newPassword !== confirmPassword) {
      toaster.error('两次输入的新密码不一致');
      return;
    }
    setChangingPassword(true);
    try {
      await authApi.changePassword(oldPassword, newPassword);
      toaster.success('密码已修改', '下次登录请使用新密码');
      setOldPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (error) {
      toaster.error('修改失败', error instanceof Error ? error.message : '请检查原密码');
    } finally {
      setChangingPassword(false);
    }
  };

  const exportData = (format: 'json' | 'zip'): void => {
    window.open(`/api/users/me/export?format=${format}`, '_blank');
    toaster.info('正在导出数据', '浏览器会开始下载文件');
  };

  const deleteAccount = async (): Promise<void> => {
    setDeleting(true);
    try {
      await userApi.deleteAccount(deletePassword);
      toaster.success('账号已注销');
      setDeleteOpen(false);
      await logout();
    } catch (error) {
      toaster.error('注销失败', error instanceof Error ? error.message : '请检查密码');
    } finally {
      setDeleting(false);
    }
  };

  return (
    <PageContainer title="设置" description="外观、学习偏好与账号安全。">
      <div className="grid gap-5 lg:grid-cols-2">
        {/* 外观 */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-1.5">
              <Palette className="h-4 w-4 text-primary" />
              外观主题
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-3 gap-2">
              {THEME_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => changeTheme(option.value)}
                  className={cn(
                    'flex flex-col items-center gap-1.5 rounded-lg border p-3 text-[12px] transition-colors',
                    theme === option.value
                      ? 'border-primary/45 bg-primary/10 text-primary'
                      : 'border-border text-muted-foreground hover:bg-muted',
                  )}
                >
                  {option.icon}
                  {option.label}
                </button>
              ))}
            </div>
            <p className="text-[11.5px] text-muted-foreground">
              深色模式为默认主题，适合长时间写代码；浅色模式在强光环境下更清晰。
            </p>
          </CardContent>
        </Card>

        {/* 学习偏好 */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-1.5">
              <UserCog className="h-4 w-4 text-primary" />
              学习偏好
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {profile.loading && !profile.data ? (
              <Skeleton className="h-48 w-full" />
            ) : (
              <>
                <Field label="学习模式" hint="影响推荐策略与练习侧重">
                  <Select value={learningMode} options={LEARNING_MODE_OPTIONS} onChange={(event) => setLearningMode(event.target.value)} />
                </Field>
                <Field label="每周学习目标" hint="用于看板与报告的进度计算">
                  <Select value={weeklyGoal} options={GOAL_OPTIONS} onChange={(event) => setWeeklyGoal(event.target.value)} />
                </Field>
                <div className="flex items-center justify-between rounded-lg border border-border p-3">
                  <div>
                    <p className="text-[12.5px] font-medium">公开我的资料</p>
                    <p className="text-[11px] text-muted-foreground">关闭后排行榜只显示昵称与成绩</p>
                  </div>
                  <Switch checked={publicProfile} onCheckedChange={setPublicProfile} label="公开资料" />
                </div>
                <Button loading={savingPrefs} onClick={() => void savePreferences()}>
                  保存偏好
                </Button>
              </>
            )}
          </CardContent>
        </Card>

        {/* AI 模式 */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-1.5">
              <Cpu className="h-4 w-4 text-primary" />
              AI 导师模式
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {(['beginner', 'standard', 'advanced'] as AiMode[]).map((mode) => (
              <button
                key={mode}
                type="button"
                onClick={() => setAiMode(mode)}
                className={cn(
                  'flex w-full items-start gap-3 rounded-lg border p-3 text-left transition-colors',
                  aiMode === mode ? 'border-primary/45 bg-primary/10' : 'border-border hover:bg-muted/60',
                )}
              >
                <span
                  className={cn(
                    'mt-0.5 h-3.5 w-3.5 shrink-0 rounded-full border',
                    aiMode === mode ? 'border-primary bg-primary' : 'border-border',
                  )}
                />
                <span className="min-w-0">
                  <span className="flex items-center gap-1.5 text-[13px] font-medium">
                    {AI_MODE_LABEL[mode]}
                    {aiMode === mode ? <Badge variant="default">当前</Badge> : null}
                  </span>
                  <span className="mt-0.5 block text-[11.5px] text-muted-foreground">{AI_MODE_DESC[mode]}</span>
                </span>
              </button>
            ))}
            <Button variant="outline" loading={savingPrefs} onClick={() => void savePreferences()}>
              保存 AI 模式
            </Button>
          </CardContent>
        </Card>

        {/* 账号安全 */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-1.5">
              <Shield className="h-4 w-4 text-primary" />
              账号安全
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field label="当前密码" required>
              <Input
                type="password"
                value={oldPassword}
                onChange={(event) => setOldPassword(event.target.value)}
                placeholder="••••••••"
                icon={<KeyRound className="h-3.5 w-3.5" />}
              />
            </Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="新密码" hint="至少 8 位" required>
                <Input type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} />
              </Field>
              <Field label="确认新密码" required>
                <Input type="password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} />
              </Field>
            </div>
            <Button loading={changingPassword} onClick={() => void changePassword()}>
              修改密码
            </Button>

            <div className="space-y-2 border-t border-border pt-4">
              <p className="text-[12.5px] font-medium">数据管理</p>
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" size="sm" onClick={() => exportData('json')}>
                  <Download className="h-3.5 w-3.5" />
                  导出学习数据
                </Button>
                <Button variant="outline" size="sm" onClick={() => exportData('zip')}>
                  <Download className="h-3.5 w-3.5" />
                  导出全部代码
                </Button>
              </div>
            </div>

            <div className="space-y-2 border-t border-border pt-4">
              <Alert
                variant="warning"
                title="危险操作：注销账号"
                description="注销后账号会被软删除，登录信息失效，学习记录不再可用（数据保留 30 天）。"
                action={
                  <Button size="sm" variant="destructive" onClick={() => setDeleteOpen(true)}>
                    <Trash2 className="h-3.5 w-3.5" />
                    注销
                  </Button>
                }
              />
            </div>
          </CardContent>
        </Card>
      </div>

      <Modal
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        title="确认注销账号？"
        description="注销后账号会被软删除，登录信息失效，学习记录不再可用（数据保留 30 天）。"
        size="sm"
        footer={
          <>
            <Button variant="ghost" onClick={() => setDeleteOpen(false)} disabled={deleting}>
              取消
            </Button>
            <Button variant="destructive" loading={deleting} onClick={() => void deleteAccount()}>
              确认注销
            </Button>
          </>
        }
      >
        <Field label="当前密码" required hint="为安全起见，请再次输入密码">
          <Input
            type="password"
            value={deletePassword}
            onChange={(event) => setDeletePassword(event.target.value)}
            placeholder="••••••••"
            icon={<KeyRound className="h-3.5 w-3.5" />}
          />
        </Field>
      </Modal>
    </PageContainer>
  );
}

export default function SettingsPage(): React.ReactElement {
  return (
    <AuthGate title="登录后修改设置" description="设置项保存在你的账号下，跨设备同步。">
      <SettingsContent />
    </AuthGate>
  );
}
