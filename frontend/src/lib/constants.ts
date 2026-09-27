import type { AiMode, Difficulty, ProblemType, SubmissionStatus } from './types';

export const SITE_NAME = 'PYTHON LAB';
export const SITE_TAGLINE = '从零开始，系统掌握 Python';
export const SITE_SUBTITLE = '学习语法，编写代码，解决问题，完成真实项目。';

/** 顶部主导航（首页 课程 编程 题库 项目 AI导师 挑战）。 */
export interface NavItem {
  label: string;
  href: string;
  description?: string;
}

export const MAIN_NAV: NavItem[] = [
  { label: '首页', href: '/' },
  { label: '课程', href: '/courses', description: '18 阶段系统路线图' },
  { label: '编程', href: '/editor', description: '在线 Python 编辑器' },
  { label: '题库', href: '/problems', description: '分级练习与判题' },
  { label: '项目', href: '/projects', description: '10 个实战项目' },
  { label: 'AI导师', href: '/ai-tutor', description: '随时答疑与讲解' },
  { label: '挑战', href: '/challenges', description: '日 / 周 / 月赛' },
];

/** 用户下拉菜单项。 */
export const USER_MENU: NavItem[] = [
  { label: '学习看板', href: '/dashboard' },
  { label: '我的养成', href: '/progress' },
  { label: '统计分析', href: '/statistics' },
  { label: '我的成就', href: '/achievements' },
  { label: '收藏夹', href: '/bookmarks' },
  { label: '错题本', href: '/wrong-answers' },
  { label: '个人资料', href: '/profile' },
  { label: '设置', href: '/settings' },
];

export const DIFFICULTY_LABEL: Record<Difficulty, string> = {
  easy: '入门',
  medium: '简单',
  hard: '中等',
  expert: '困难',
};

export const DIFFICULTY_STYLE: Record<Difficulty, string> = {
  easy: 'bg-emerald-500/12 text-emerald-500 border-emerald-500/25',
  medium: 'bg-sky-500/12 text-sky-500 border-sky-500/25',
  hard: 'bg-amber-500/12 text-amber-500 border-amber-500/25',
  expert: 'bg-rose-500/12 text-rose-500 border-rose-500/25',
};

export const PROBLEM_TYPE_LABEL: Record<ProblemType, string> = {
  choice: '选择题',
  judge: '判断题',
  blank: '填空题',
  completion: '补全题',
  coding: '编程题',
  debug: '调试题',
  algorithm: '算法题',
};

export const SUBMISSION_STATUS_LABEL: Record<SubmissionStatus, string> = {
  pending: '等待中',
  judging: '判题中',
  accepted: '通过',
  wrong_answer: '答案错误',
  runtime_error: '运行错误',
  time_limit_exceeded: '超时',
  memory_limit_exceeded: '内存超限',
  compile_error: '语法错误',
  security_error: '安全拦截',
  internal_error: '系统错误',
};

export const SUBMISSION_STATUS_STYLE: Record<SubmissionStatus, string> = {
  pending: 'bg-muted text-muted-foreground border-border',
  judging: 'bg-sky-500/12 text-sky-500 border-sky-500/25',
  accepted: 'bg-emerald-500/12 text-emerald-500 border-emerald-500/25',
  wrong_answer: 'bg-rose-500/12 text-rose-500 border-rose-500/25',
  runtime_error: 'bg-orange-500/12 text-orange-500 border-orange-500/25',
  time_limit_exceeded: 'bg-amber-500/12 text-amber-500 border-amber-500/25',
  memory_limit_exceeded: 'bg-purple-500/12 text-purple-500 border-purple-500/25',
  compile_error: 'bg-rose-500/12 text-rose-500 border-rose-500/25',
  security_error: 'bg-destructive/12 text-destructive border-destructive/25',
  internal_error: 'bg-destructive/12 text-destructive border-destructive/25',
};

/** 判定短标（AC / WA / RE / TLE / MLE / CE / SE）。 */
export const VERDICT_SHORT: Record<SubmissionStatus, string> = {
  pending: 'PD',
  judging: 'JG',
  accepted: 'AC',
  wrong_answer: 'WA',
  runtime_error: 'RE',
  time_limit_exceeded: 'TLE',
  memory_limit_exceeded: 'MLE',
  compile_error: 'CE',
  security_error: 'SE',
  internal_error: 'IE',
};

export const AI_MODE_LABEL: Record<AiMode, string> = {
  beginner: '初学者',
  standard: '标准',
  advanced: '进阶',
};

export const AI_MODE_DESC: Record<AiMode, string> = {
  beginner: '类比 + 一步一动，慢讲原理',
  standard: '直接解释，给出思路与要点',
  advanced: '复杂度 / 惯用法 / 最佳实践',
};

/** 18 阶段路线图（后端不可用时作为静态兜底，保证首页不空白）。 */
export interface StageSeed {
  stage_no: number;
  title: string;
  subtitle: string;
  level: 'beginner' | 'intermediate' | 'advanced';
  estimated_hours: number;
  slug: string;
}

export const STAGES: StageSeed[] = [
  { stage_no: 1, title: 'Python 起步', subtitle: '环境、语法骨架与第一个程序', level: 'beginner', estimated_hours: 6, slug: 'stage-01-python-basics' },
  { stage_no: 2, title: '变量与数据类型', subtitle: '数字、字符串、布尔与类型转换', level: 'beginner', estimated_hours: 8, slug: 'stage-02-variables' },
  { stage_no: 3, title: '运算符与表达式', subtitle: '算术、比较、逻辑与优先级', level: 'beginner', estimated_hours: 6, slug: 'stage-03-operators' },
  { stage_no: 4, title: '流程控制', subtitle: '分支、循环与跳转', level: 'beginner', estimated_hours: 10, slug: 'stage-04-control-flow' },
  { stage_no: 5, title: '字符串', subtitle: '切片、格式化与常用方法', level: 'beginner', estimated_hours: 8, slug: 'stage-05-strings' },
  { stage_no: 6, title: '列表与元组', subtitle: '序列操作、切片与推导式', level: 'beginner', estimated_hours: 10, slug: 'stage-06-lists' },
  { stage_no: 7, title: '字典与集合', subtitle: '映射、哈希与去重', level: 'beginner', estimated_hours: 8, slug: 'stage-07-dicts' },
  { stage_no: 8, title: '函数', subtitle: '参数、返回值与递归', level: 'beginner', estimated_hours: 12, slug: 'stage-08-functions' },
  { stage_no: 9, title: '作用域与模块', subtitle: '命名空间、包管理与导入', level: 'intermediate', estimated_hours: 8, slug: 'stage-09-modules' },
  { stage_no: 10, title: '文件与异常', subtitle: '读写文件、异常处理链', level: 'intermediate', estimated_hours: 10, slug: 'stage-10-files' },
  { stage_no: 11, title: '面向对象', subtitle: '类、继承、多态与魔术方法', level: 'intermediate', estimated_hours: 14, slug: 'stage-11-oop' },
  { stage_no: 12, title: '迭代器生成器', subtitle: '生成器、yield 与惰性求值', level: 'intermediate', estimated_hours: 10, slug: 'stage-12-generators' },
  { stage_no: 13, title: '函数式与高阶函数', subtitle: 'lambda、map/filter/reduce', level: 'intermediate', estimated_hours: 8, slug: 'stage-13-functional' },
  { stage_no: 14, title: '标准库精要', subtitle: 'collections、itertools、datetime', level: 'intermediate', estimated_hours: 12, slug: 'stage-14-stdlib' },
  { stage_no: 15, title: '正则表达式', subtitle: '模式匹配与文本清洗', level: 'advanced', estimated_hours: 8, slug: 'stage-15-regex' },
  { stage_no: 16, title: '并发与异步', subtitle: 'threading、asyncio 与协程', level: 'advanced', estimated_hours: 14, slug: 'stage-16-concurrency' },
  { stage_no: 17, title: '测试与调试', subtitle: 'unittest、pytest 与 pdb', level: 'advanced', estimated_hours: 10, slug: 'stage-17-testing' },
  { stage_no: 18, title: '工程化与实战', subtitle: '虚拟环境、CI 与综合项目', level: 'advanced', estimated_hours: 16, slug: 'stage-18-project' },
];

export const STAGE_GROUP_LABEL: Record<string, string> = {
  beginner: '基础语法',
  intermediate: '进阶能力',
  advanced: '工程实战',
};

/** 等级名称（7 级）。 */
export const LEVEL_NAMES = ['Python 新手', '语法学徒', '代码工匠', '逻辑达人', '算法能手', '工程高手', 'Python 大师'];

/** 等级 XP 阈值，与后端 LEVEL_THRESHOLDS 保持一致。 */
export const LEVEL_THRESHOLDS = [0, 100, 300, 700, 1500, 3000, 6000];

export function levelOf(xp: number): number {
  let level = 1;
  LEVEL_THRESHOLDS.forEach((threshold, index) => {
    if (xp >= threshold) level = index + 1;
  });
  return level;
}

export function levelName(level: number): string {
  return LEVEL_NAMES[Math.min(Math.max(level, 1), LEVEL_NAMES.length) - 1] ?? 'Python 新手';
}

export function nextLevelXp(level: number): number {
  return LEVEL_THRESHOLDS[Math.min(level, LEVEL_THRESHOLDS.length - 1)] ?? 6000;
}

/** 默认 Python 初始代码。 */
export const DEFAULT_PYTHON_CODE = `# 欢迎使用 PYTHON LAB 在线编辑器
# Ctrl + Enter 运行代码，Ctrl + S 保存


def greet(name: str) -> str:
    return f"Hello, {name}!"


if __name__ == "__main__":
    print(greet("Python"))
    print(sum(range(1, 101)))
`;
