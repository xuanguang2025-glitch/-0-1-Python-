'use client';

import { useEffect, useState } from 'react';
import { Award, CalendarDays, Mail, Save, Target, Trophy, User, Zap } from 'lucide-react';
import { statisticsApi, userApi } from '@/lib/api';
import { levelName } from '@/lib/constants';
import { formatMinutes } from '@/lib/utils';
import { useFetch } from '@/hooks/useFetch';
import { useToaster } from '@/hooks/useToast';
import { useAuth } from '@/hooks/useAuth';
import { AuthGate } from '@/components/common/auth-gate';
import { PageContainer } from '@/components/layout/page-container';
import { Alert } from '@/components/ui/alert';
import { Avatar } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Field, Input, Textarea } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import { StatCard } from '@/components/ui/stat-card';

const TIMEZONE_OPTIONS = ['UTC', 'Asia/Shanghai', 'Asia/Tokyo', 'Europe/London', 'America/New_York'];

/** 个人资料：资料编辑 + 学习概览。 */
function ProfileContent(): React.ReactElement {
  const toaster = useToaster();
  const { user, refreshProfile } = useAuth();

  const profile = useFetch(() => userApi.profile(), []);
  const stats = useFetch(() => statisticsApi.overview(), []);

  const [form, setForm] = useState({
    display_name: '',
    avatar_url: '',
    bio: '',
    timezone: 'Asia/Shanghai',
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!profile.data) return;
    setForm({
      display_name: profile.data.display_name ?? '',
      avatar_url: profile.data.avatar_url ?? '',
      bio: profile.data.bio ?? '',
      timezone: profile.data.timezone ?? 'Asia/Shanghai',
    });
  }, [profile.data]);

  const save = async (): Promise<void> => {
    setSaving(true);
    try {
      await userApi.updateProfile({
        display_name: form.display_name,
        avatar_url: form.avatar_url || null,
        bio: form.bio,
        timezone: form.timezone,
      });
      toaster.success('资料已保存');
      profile.refresh();
      void refreshProfile();
    } catch (error) {
      toaster.error('保存失败', error instanceof Error ? error.message : '请稍后再试');
    } finally {
      setSaving(false);
    }
  };

  const xp = stats.data?.xp ?? user?.xp ?? 0;
  const level = stats.data?.level ?? user?.level ?? 1;

  return (
    <PageContainer title="个人资料" description="完善资料，让你的学习档案更完整。">
      <div className="grid gap-5 lg:grid-cols-[300px_minmax(0,1fr)]">
        {/* 概览卡 */}
        <div className="space-y-4">
          <Card>
            <CardContent className="flex flex-col items-center gap-3 pt-6">
              <Avatar src={form.avatar_url || profile.data?.avatar_url} name={form.display_name || user?.username} size={88} ring />
              <div className="space-y-1 text-center">
                <p className="text-[15px] font-semibold">{form.display_name || user?.username || 'Python 学习者'}</p>
                <p className="text-[12px] text-muted-foreground">@{user?.username ?? '—'}</p>
              </div>
              <div className="flex flex-wrap justify-center gap-1.5">
                <Badge variant="default" className="gap-1">
                  <Trophy className="h-3 w-3" />
                  Lv.{level} {levelName(level)}
                </Badge>
                <Badge variant="secondary" className="gap-1">
                  <Zap className="h-3 w-3" />
                  {xp} XP
                </Badge>
                {user?.role !== 'user' && user?.role ? <Badge variant="accent">{user.role}</Badge> : null}
              </div>
              {form.bio ? (
                <p className="text-center text-[12px] leading-relaxed text-muted-foreground">{form.bio}</p>
              ) : null}
            </CardContent>
          </Card>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
            <StatCard label="累计学习" value={formatMinutes(stats.data?.total_minutes ?? 0)} icon={<Target className="h-3.5 w-3.5" />} loading={stats.loading && !stats.data} />
            <StatCard label="解题数量" value={stats.data?.solved ?? 0} icon={<Award className="h-3.5 w-3.5" />} tone="success" loading={stats.loading && !stats.data} />
            <StatCard label="连续天数" value={`${stats.data?.streak_days ?? 0} 天`} icon={<CalendarDays className="h-3.5 w-3.5" />} tone="warning" loading={stats.loading && !stats.data} />
          </div>
        </div>

        {/* 编辑表单 */}
        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-1.5">
                <User className="h-4 w-4 text-primary" />
                基本资料
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {profile.loading && !profile.data ? (
                <Skeleton className="h-64 w-full" />
              ) : (
                <>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <Field label="昵称" hint="用于排行榜展示">
                      <Input
                        value={form.display_name}
                        onChange={(event) => setForm({ ...form, display_name: event.target.value })}
                        placeholder="Python 学习者"
                      />
                    </Field>
                    <Field label="邮箱" hint="登录账号，暂不支持修改">
                      <Input value={user?.email ?? ''} disabled icon={<Mail className="h-3.5 w-3.5" />} />
                    </Field>
                  </div>

                  <Field label="头像链接" hint="填写图片 URL（2MB 以内的 jpg / png / webp）">
                    <Input
                      value={form.avatar_url}
                      onChange={(event) => setForm({ ...form, avatar_url: event.target.value })}
                      placeholder="https://example.com/avatar.png"
                    />
                  </Field>

                  <Field label="个人简介" hint="最多 500 字，介绍你的学习目标">
                    <Textarea
                      rows={4}
                      value={form.bio}
                      onChange={(event) => setForm({ ...form, bio: event.target.value })}
                      placeholder="我正在系统学习 Python，目标是……"
                    />
                  </Field>

                  <Field label="时区" hint="影响学习任务与连续天数的计算">
                    <div className="flex flex-wrap gap-1.5">
                      {TIMEZONE_OPTIONS.map((zone) => (
                        <button
                          key={zone}
                          type="button"
                          onClick={() => setForm({ ...form, timezone: zone })}
                          className={
                            form.timezone === zone
                              ? 'rounded-full border border-primary/40 bg-primary/12 px-2.5 py-1 text-[11.5px] text-primary'
                              : 'rounded-full border border-border px-2.5 py-1 text-[11.5px] text-muted-foreground hover:bg-muted'
                          }
                        >
                          {zone}
                        </button>
                      ))}
                    </div>
                  </Field>

                  <div className="flex justify-end">
                    <Button loading={saving} onClick={() => void save()}>
                      <Save className="h-4 w-4" />
                      保存资料
                    </Button>
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle>等级进度</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="flex items-center justify-between text-[12px]">
                <span className="text-muted-foreground">Lv.{level} · {levelName(level)}</span>
                <span>{xp} XP</span>
              </div>
              <Progress value={Math.min(100, (xp / Math.max(1, (level + 1) * 100)) * 100)} size="md" />
              <p className="text-[11px] text-muted-foreground">通过完成课时、通过题目与成就获得 XP。</p>
            </CardContent>
          </Card>

          <Alert
            variant="info"
            title="数据隐私"
            description="你的代码与学习记录仅自己可见；排行榜只展示昵称与成绩。可在设置页导出或删除数据。"
          />
        </div>
      </div>
    </PageContainer>
  );
}

export default function ProfilePage(): React.ReactElement {
  return (
    <AuthGate title="登录后查看个人资料" description="登录后可以编辑昵称、头像与简介。">
      <ProfileContent />
    </AuthGate>
  );
}
