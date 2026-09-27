'use client';

import Link from 'next/link';
import { useMemo } from 'react';
import {
  ArrowRight,
  BarChart3,
  BookOpen,
  Bot,
  Braces,
  Code2,
  FolderKanban,
  Gauge,
  GraduationCap,
  Layers,
  ListChecks,
  Play,
  Sparkles,
  Target,
  Terminal,
  Trophy,
  Zap,
} from 'lucide-react';
import { courseApi } from '@/lib/api';
import { STAGES, STAGE_GROUP_LABEL, SITE_SUBTITLE, SITE_TAGLINE, type StageSeed } from '@/lib/constants';
import { cn } from '@/lib/utils';
import { useFetch } from '@/hooks/useFetch';
import { useAuth } from '@/hooks/useAuth';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { PageContainer } from '@/components/layout/page-container';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import { SectionTitle } from '@/components/ui/stat-card';
import { CodeBlock } from '@/components/code/code-block';
import type { StageOut } from '@/lib/types';

const FEATURES = [
  { icon: <Code2 className="h-4 w-4" />, title: '在线 Python 编辑器', desc: '多文件、自动保存、格式化、语法高亮，浏览器里直接写代码。' },
  { icon: <ListChecks className="h-4 w-4" />, title: '智能判题', desc: 'AC / WA / RE / TLE / MLE 全状态，测试点、耗时、内存一目了然。' },
  { icon: <Bot className="h-4 w-4" />, title: 'AI 学习导师', desc: '初学者 / 标准 / 进阶三种模式，只给提示不给答案，陪你学会。' },
  { icon: <BarChart3 className="h-4 w-4" />, title: '学习数据看板', desc: '连续天数、时长趋势、知识点掌握度，进步看得见。' },
  { icon: <FolderKanban className="h-4 w-4" />, title: '真实项目实战', desc: '从命令行工具到 Web API，分步骤完成 10 个完整项目。' },
  { icon: <Trophy className="h-4 w-4" />, title: '等级与成就', desc: 'XP、7 级成长体系、成就徽章与每日任务，学习像闯关。' },
];

const FLOW = [
  { step: '01', title: '学语法', desc: '18 个阶段循序渐进，每节课都有理论、代码、示例与练习。', icon: <GraduationCap className="h-4 w-4" /> },
  { step: '02', title: '写代码', desc: '内置编辑器边学边练，Ctrl+Enter 运行，错误即时反馈。', icon: <Terminal className="h-4 w-4" /> },
  { step: '03', title: '解决问题', desc: '分级题库 + 错题本 + AI 讲解，把不会的变成会的。', icon: <Target className="h-4 w-4" /> },
  { step: '04', title: '完成项目', desc: '综合项目作品集，学完就能展示自己的成果。', icon: <Zap className="h-4 w-4" /> },
];

const SAMPLE_CODE = `from dataclasses import dataclass


@dataclass
class Student:
    name: str
    scores: list[int]

    @property
    def average(self) -> float:
        return sum(self.scores) / len(self.scores) if self.scores else 0.0


students = [
    Student("小明", [92, 88, 95]),
    Student("小红", [78, 85, 90]),
]

for s in sorted(students, key=lambda x: -x.average):
    print(f"{s.name}: {s.average:.1f}")
`;

/** 首页：Hero + 能力矩阵 + 学习路径 + 18 阶段路线图。 */
export default function HomePage(): React.ReactElement {
  const { isAuthenticated } = useAuth();

  const stagesRequest = useFetch<StageOut[]>(() => courseApi.stages(), []);
  const stages: (StageSeed & { lesson_count?: number; progress_percent?: number })[] = useMemo(() => {
    if (stagesRequest.data && stagesRequest.data.length > 0) {
      return stagesRequest.data.map((stage) => ({
        stage_no: stage.stage_no,
        slug: stage.slug,
        title: stage.title,
        subtitle: stage.subtitle ?? '',
        level: stage.level,
        estimated_hours: stage.estimated_hours,
        lesson_count: stage.lesson_count,
        progress_percent: stage.progress_percent,
      }));
    }
    // 后端不可用时的静态兜底，保证首页始终完整
    return STAGES;
  }, [stagesRequest.data]);

  const grouped = useMemo(() => {
    return (['beginner', 'intermediate', 'advanced'] as const).map((level) => ({
      level,
      label: STAGE_GROUP_LABEL[level],
      items: stages.filter((stage) => stage.level === level),
    }));
  }, [stages]);

  const totalLessons = stages.reduce((sum, stage) => sum + (stage.lesson_count ?? 0), 0);
  const totalHours = stages.reduce((sum, stage) => sum + stage.estimated_hours, 0);

  return (
    <PageContainer width="full" contentClassName="px-0 py-0" showFooter>
      {/* ============ Hero ============ */}
      <section className="relative overflow-hidden border-b border-border">
        <div
          aria-hidden
          className="pointer-events-none absolute -right-24 -top-32 h-72 w-72 rounded-full bg-primary/12 blur-3xl"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute -left-20 top-24 h-56 w-56 rounded-full bg-accent/12 blur-3xl"
        />
        <div className="mx-auto grid max-w-[1200px] gap-10 px-4 py-16 lg:grid-cols-[1.05fr_0.95fr] lg:py-24">
          <div className="space-y-6">
            <Badge variant="accent" className="gap-1.5 py-1">
              <Sparkles className="h-3 w-3" />
              18 阶段 · {totalLessons || 200}+ 课时 · 1000+ 题目 · 10 个项目
            </Badge>

            <h1 className="text-4xl font-bold leading-[1.15] tracking-tight sm:text-5xl">
              从零开始，
              <br />
              系统掌握 <span className="text-primary">Python</span>
              <span className="text-accent">.</span>
            </h1>

            <p className="max-w-xl text-[15px] leading-relaxed text-muted-foreground sm:text-base">
              {SITE_SUBTITLE}
            </p>

            <div className="flex flex-wrap items-center gap-3">
              <Button size="lg" asChild>
                <Link href={isAuthenticated ? '/learn' : '/register'}>
                  {isAuthenticated ? '继续学习' : '免费开始学习'}
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
              <Button size="lg" variant="outline" asChild>
                <Link href="/playground">
                  <Play className="h-4 w-4" />
                  立即试用编辑器
                </Link>
              </Button>
            </div>

            <dl className="grid max-w-lg grid-cols-3 gap-4 pt-4">
              {[
                { label: '学习阶段', value: '18', icon: <Layers className="h-3.5 w-3.5" /> },
                { label: '预计学时', value: `${totalHours || 180}h`, icon: <Gauge className="h-3.5 w-3.5" /> },
                { label: '练习题目', value: '1000+', icon: <Braces className="h-3.5 w-3.5" /> },
              ].map((item) => (
                <div key={item.label} className="rounded-lg border border-border bg-card/60 p-3">
                  <dt className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                    {item.icon}
                    {item.label}
                  </dt>
                  <dd className="mt-1 text-xl font-semibold tracking-tight">{item.value}</dd>
                </div>
              ))}
            </dl>
          </div>

          <div className="space-y-4">
            <CodeBlock code={SAMPLE_CODE} filename="example_dataclass.py" showLineNumbers maxHeight={380} />
            <p className="text-[12px] text-muted-foreground">
              每一节课都有可运行的示例代码，复制、运行、改一改，立刻看到结果。
            </p>
          </div>
        </div>
      </section>

      {/* ============ 能力矩阵 ============ */}
      <section className="mx-auto max-w-[1200px] px-4 py-14">
        <SectionTitle title="一个平台，覆盖学习全流程" description={SITE_TAGLINE} />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((feature) => (
            <Card key={feature.title} interactive className="h-full">
              <CardContent className="space-y-2.5 pt-5">
                <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-primary/12 text-primary">
                  {feature.icon}
                </span>
                <p className="text-[14px] font-semibold">{feature.title}</p>
                <p className="text-[12.5px] leading-relaxed text-muted-foreground">{feature.desc}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      {/* ============ 学习闭环 ============ */}
      <section className="border-y border-border bg-card/35">
        <div className="mx-auto max-w-[1200px] px-4 py-14">
          <SectionTitle title="四步学习闭环" description="学 → 练 → 纠 → 用，每一步都有对应的工具支撑。" />
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {FLOW.map((item) => (
              <div key={item.step} className="relative rounded-lg border border-border bg-background p-4">
                <span className="absolute right-3 top-3 font-mono text-[22px] font-bold text-muted-foreground/25">
                  {item.step}
                </span>
                <span className="inline-flex h-8 w-8 items-center justify-center rounded-md bg-accent/18 text-accent-foreground">
                  {item.icon}
                </span>
                <p className="mt-3 text-[14px] font-semibold">{item.title}</p>
                <p className="mt-1 text-[12.5px] leading-relaxed text-muted-foreground">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ============ 18 阶段路线图 ============ */}
      <section className="mx-auto max-w-[1200px] px-4 py-14">
        <SectionTitle
          title="18 阶段学习路线图"
          description="从第一行 print 到工程化实战，每阶段都有明确目标与课时安排。"
          action={
            <Button variant="outline" size="sm" asChild>
              <Link href="/courses">
                查看全部课程
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </Button>
          }
        />

        {stagesRequest.loading && !stagesRequest.data ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 9 }).map((_, index) => (
              <Skeleton key={index} className="h-[104px] w-full" />
            ))}
          </div>
        ) : (
          <div className="space-y-10">
            {grouped.map((group) => (
              <div key={group.level} className="space-y-4">
                <div className="flex items-center gap-3">
                  <h3 className="text-[15px] font-semibold">{group.label}</h3>
                  <span className="text-[12px] text-muted-foreground">{group.items.length} 个阶段</span>
                  <span className="h-px flex-1 bg-border" />
                </div>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {group.items.map((stage) => (
                    <Link
                      key={stage.stage_no}
                      href={`/courses/${stage.slug}`}
                      className="group rounded-lg border border-border bg-card p-4 transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-md"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0 space-y-1.5">
                          <p className="text-[11px] font-medium text-muted-foreground">
                            STAGE {String(stage.stage_no).padStart(2, '0')}
                          </p>
                          <p className="truncate text-[14px] font-semibold group-hover:text-primary">{stage.title}</p>
                          <p className="line-clamp-2 text-[12px] leading-relaxed text-muted-foreground">{stage.subtitle}</p>
                        </div>
                        <span
                          className={cn(
                            'flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-[13px] font-bold',
                            stage.level === 'beginner' && 'bg-emerald-500/12 text-emerald-500',
                            stage.level === 'intermediate' && 'bg-primary/12 text-primary',
                            stage.level === 'advanced' && 'bg-accent/18 text-accent-foreground',
                          )}
                        >
                          {stage.stage_no}
                        </span>
                      </div>

                      <div className="mt-3 flex items-center gap-3 text-[11px] text-muted-foreground">
                        <span className="inline-flex items-center gap-1">
                          <BookOpen className="h-3 w-3" />
                          {stage.lesson_count ? `${stage.lesson_count} 课时` : `${stage.estimated_hours} 小时`}
                        </span>
                        {typeof stage.progress_percent === 'number' ? (
                          <span className="ml-auto w-24">
                            <Progress value={stage.progress_percent} size="sm" showValue />
                          </span>
                        ) : (
                          <Badge variant="secondary" className="ml-auto">
                            {stage.estimated_hours} 小时
                          </Badge>
                        )}
                      </div>
                    </Link>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* ============ 底部 CTA ============ */}
      <section className="border-t border-border bg-card/35">
        <div className="mx-auto flex max-w-[1200px] flex-col items-center gap-4 px-4 py-14 text-center">
          <h2 className="text-2xl font-semibold tracking-tight">今天写下第一行 Python</h2>
          <p className="max-w-xl text-[13.5px] text-muted-foreground">
            免费注册即可解锁全部课程、题库与在线编辑器。学习进度自动保存，随时继续。
          </p>
          <div className="flex flex-wrap justify-center gap-3">
            <Button size="lg" asChild>
              <Link href="/register">
                创建免费账号
                <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
            <Button size="lg" variant="outline" asChild>
              <Link href="/ai-tutor">先和 AI 导师聊聊</Link>
            </Button>
          </div>
        </div>
      </section>
    </PageContainer>
  );
}
