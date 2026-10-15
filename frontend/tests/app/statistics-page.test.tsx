// @vitest-environment jsdom
/**
 * `src/app/statistics/page.tsx` —— 统计分析页（328 行）。
 *
 * 该页并行发起 6 个 `useFetch`：overview / trend / categories / heatmap / report / ranking。
 * 覆盖重点：核心指标格式化、空值兜底（图表无数据时不崩）、以及三个筛选器
 * （天数 Tabs、指标 Select、周期 Tabs）是否正确进入请求参数。
 *
 * ## 断言按代码事实
 * - `formatMinutes(90)` → `'1.5 小时'`（>=60 分钟走小时，一位小数）
 * - `formatMinutes(0)` → `'0 分钟'`
 * - 「击败比例」是 `formatPercent(percentile / 100, 0)` —— percentile 本身是百分数，
 *   要先除以 100 再格式化，所以 percentile=80 渲染成 `80%` 而不是 `8000%`
 * - `ranking.my_rank` 为 null 时显示 `—`
 * - 分类正确率：`total > 0` 时算 `Math.round(solved / total * 100)`，否则回退用 `score`
 * - `<Toaster />` 挂在 providers，不在页面树内（本页无 toast 断言需求）
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act, fireEvent, waitFor } from '@testing-library/react';
import type { UserBrief } from '@/lib/types';

import StatisticsPage from '@/app/statistics/page';
import { useAuthStore } from '@/store/auth';
import { err, mockFetchByPath, ok } from '../helpers/fetch-mock';

vi.mock('next/navigation', () => ({
  usePathname: () => '/statistics',
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn(), prefetch: vi.fn(), refresh: vi.fn() }),
  redirect: vi.fn(),
}));

const BASE_URL = 'http://localhost:3000';

const USER: UserBrief = {
  id: 'u-1',
  email: 'tester@example.com',
  username: 'tester',
  display_name: '测试用户',
  role: 'user',
  level: 1,
  xp: 0,
};

const OVERVIEW = {
  total_minutes: 90,
  solved: 42,
  submissions: 60,
  accepted: 45,
  acceptance_rate: 0.75,
  streak_days: 5,
  xp: 1280,
  level: 7,
  rank_percentile: 80,
  run_count: 30,
  projects: 2,
  courses: 3,
  strongest_topic: null,
};

const TREND = {
  metric: 'submissions',
  points: [
    { date: '2026-09-25', value: 3 },
    { date: '2026-09-26', value: 8 },
  ],
  total: 11,
};

const CATEGORIES = {
  categories: [
    { category: '数组', solved: 8, total: 10, score: 80 },
    { category: '字符串', solved: 3, total: 4, score: 75 },
  ],
};

const HEATMAP = {
  points: [
    { date: '2026-09-25', count: 2, minutes: 30 },
    { date: '2026-09-26', count: 5, minutes: 60 },
  ],
  total_count: 7,
  active_days: 2,
  max_count: 5,
};

const REPORT = {
  period: 'week',
  start_date: '2026-09-21',
  end_date: '2026-09-27',
  summary_md: '本周你一共提交了 11 次，通过 8 次。',
  highlights: ['数组正确率提升', '连续学习 5 天'],
  metrics: { minutes: 120, lessons: 4, submissions: 11, accepted: 8, acceptance_rate: 0.727 },
  weak_topics: [],
  recommendations: [{ type: 'problem', id: 'p-9', title: '推荐练习：动态规划', reason: '你在动态规划上正确率偏低' }],
  degraded: false,
};

const RANKING = { my_rank: 12, total_users: 340, percentile: 96.5, xp: 1280 };

type FetchMock = ReturnType<typeof mockFetchByPath>;

interface SetupOptions {
  overview?: unknown;
  /** overview 失败响应（独立于 ok() 信封，故单列一个选项）。 */
  overviewError?: Response;
  trend?: unknown;
  categories?: unknown;
  heatmap?: unknown;
  report?: unknown;
  ranking?: unknown;
}

/**
 * 取子请求响应。
 * 用 `in` 判断而不是 `??` —— 后者会把「显式传null」也当成空值回退到默认数据，
 * 导致「后端返回 null」这类用例测不到真实分支。
 */
function pick(options: SetupOptions, key: keyof SetupOptions, fallback: unknown): unknown {
  return key in options ? options[key] : fallback;
}

/** 挂载页面；所有子请求即时返回，便于断言渲染结果。 */
function setup(options: SetupOptions = {}) {
  const fetchMock = mockFetchByPath({
    // 注册顺序即匹配顺序：具体路径必须排在 /statistics 前缀之外
    '/statistics/trend': () => ok(pick(options, 'trend', TREND)),
    '/statistics/categories': () => ok(pick(options, 'categories', CATEGORIES)),
    '/statistics/heatmap': () => ok(pick(options, 'heatmap', HEATMAP)),
    '/statistics/report': () => ok(pick(options, 'report', REPORT)),
    '/statistics/ranking': () => ok(pick(options, 'ranking', RANKING)),
    '/statistics/overview': () => options.overviewError ?? ok(pick(options, 'overview', OVERVIEW)),
  });

  useAuthStore.setState({
    hydrated: true,
    accessToken: 'test-access-token',
    refreshToken: 'test-refresh-token',
    user: USER,
    loading: false,
    error: null,
  });

  render(<StatisticsPage />);
  return { fetchMock };
}

/** 取最近一次某路径请求的查询参数。 */
function lastQuery(fetchMock: FetchMock, path: string): URLSearchParams {
  const calls = fetchMock.calls.filter((c) => c.url.includes(path));
  return new URL(calls[calls.length - 1]!.url, BASE_URL).searchParams;
}

beforeEach(() => {
  // 页面不读时间，无需 fake；但清掉可能的 location 改动保持环境干净
  Object.defineProperty(window, 'location', {
    configurable: true,
    writable: true,
    value: { ...window.location, href: 'http://localhost:3000/statistics' },
  });
});

afterEach(() => {
  useAuthStore.setState({ accessToken: null, refreshToken: null, user: null, hydrated: false, loading: false, error: null });
  vi.restoreAllMocks();
});

describe('statistics · 核心指标渲染', () => {
  it('总览指标按格式化函数渲染（时长/通过率/连续/等级）', async () => {
    setup();

    expect(await screen.findByText('累计学习时长')).toBeTruthy();
    // formatMinutes(90) → '1.5 小时'（不是 '90 分钟'）
    expect(screen.getByText('1.5 小时')).toBeTruthy();
    expect(screen.getByText('解题数量')).toBeTruthy();
    expect(screen.getByText('42')).toBeTruthy();
    // hint: `共 ${submissions} 次提交`
    expect(screen.getByText('共 60 次提交')).toBeTruthy();
    // formatPercent(0.75, 1) → '75.0%'
    expect(screen.getByText('75.0%')).toBeTruthy();
    // streak 与 level 带单位后缀
    expect(screen.getByText('5 天')).toBeTruthy();
    expect(screen.getByText('Lv.7')).toBeTruthy();
    expect(screen.getByText('1280')).toBeTruthy();
  });

  it('排名与击败比例：percentile 先除以 100 再格式化', async () => {
    setup();
    await screen.findByText('我的排名');

    // my_rank=12 / total_users=340
    expect(screen.getByText('第 12 / 340')).toBeTruthy();
    // formatPercent(96.5 / 100, 0) → '97%'（不是 9650%）
    expect(screen.getByText('97%')).toBeTruthy();
  });

  it('my_rank 为 null（未上榜）→ 排名显示占位符，不渲染「第 null」', async () => {
    // RankingOut.my_rank 是 `number | null`，后端在未上榜 / 新用户场景返回 null。
    // 修复前 statistics/page.tsx:126 只判了 ranking.data 存在就直接插值，
    // 于是 null 被渲染成字符串「第 null / 340」；现已改为判空后显示「—」。
    setup({ ranking: { ...RANKING, my_rank: null } });
    await screen.findByText('我的排名');

    expect(screen.getByText('—')).toBeTruthy();
    expect(screen.queryByText(/第 null/)).toBeNull();
    // 击败比例不受影响，仍按 percentile 计算
    expect(screen.getByText('97%')).toBeTruthy();
  });

  it('my_rank 为 0 时不能被当成空值（0 是有效名次）', async () => {
    // 防回归：修复时若用真值判断（my_rank ? ... : '—'）会把 0 误判为空。
    setup({ ranking: { ...RANKING, my_rank: 0 } });
    await screen.findByText('我的排名');

    expect(screen.getByText('第 0 / 340')).toBeTruthy();
    expect(screen.queryByText('—')).toBeNull();
  });

  it('overview 全零 → 各指标兜底为 0，不出现 NaN', async () => {
    setup({
      overview: { ...OVERVIEW, total_minutes: 0, solved: 0, submissions: 0, acceptance_rate: 0, streak_days: 0, xp: 0 },
    });
    await screen.findByText('累计学习时长');

    // formatMinutes(0) → '0 分钟'；formatPercent(0, 1) → '0.0%'
    expect(screen.getByText('0 分钟')).toBeTruthy();
    expect(screen.getByText('0.0%')).toBeTruthy();
    expect(screen.getByText('0 天')).toBeTruthy();
    expect(screen.queryByText(/NaN/)).toBeNull();
  });
});

describe('statistics · 图表与空值兜底', () => {
  it('趋势图有数据时正常渲染，不显示空态提示', async () => {
    setup();
    await screen.findByText('学习趋势');

    expect(screen.queryByText('这段时间还没有记录，先去学一节课吧')).toBeNull();
  });

  it('★ 趋势 points 为空 → 显示空态提示，不崩', async () => {
    setup({ trend: { metric: 'submissions', points: [], total: 0 } });
    await screen.findByText('学习趋势');

    expect(screen.getByText('这段时间还没有记录，先去学一节课吧')).toBeTruthy();
  });

  it('★ 分类数据为空 → 显示空态提示，不崩', async () => {
    setup({ categories: { categories: [] } });
    await screen.findByText('分类正确率');

    expect(screen.getByText('还没有分类统计数据')).toBeTruthy();
  });

  it('★ 热力图 points 为空 → 页面不崩', async () => {
    setup({ heatmap: { points: [], total_count: 0, active_days: 0, max_count: 0 } });
    await screen.findByText('活跃度趋势');

    // 热力图空数据不应抛错，页面其余部分仍渲染
    expect(screen.getByText('累计学习时长')).toBeTruthy();
  });

  it('★ 分类项 total=0 时回退用 score 计算，不产生 NaN', async () => {
    setup({
      categories: { categories: [{ category: '未做题类', solved: 0, total: 0, score: 60 }] },
    });
    await screen.findByText('分类正确率');

    expect(screen.queryByText(/NaN/)).toBeNull();
  });

  it('报告 highlights 为空数组 → 不渲染高亮徽章', async () => {
    setup({ report: { ...REPORT, highlights: [] } });
    await screen.findByText('学习报告');

    expect(screen.queryByText('数组正确率提升')).toBeNull();
  });

  it('报告 recommendations 为空 → 显示「暂无个性化建议」', async () => {
    setup({ report: { ...REPORT, recommendations: [] } });
    await screen.findByText('学习报告');

    expect(screen.getByText('暂无个性化建议')).toBeTruthy();
  });

  it('报告有建议 → 渲染建议标题与理由，并给出跳转链接', async () => {
    setup();
    await screen.findByText('学习报告');

    expect(screen.getByText('推荐练习：动态规划')).toBeTruthy();
    expect(screen.getByText('你在动态规划上正确率偏低')).toBeTruthy();
    expect(screen.getByText('下一步建议')).toBeTruthy();
  });

  it('★ 报告整体为 null（后端无数据）→ 渲染「暂无报告」且关键指标兜底为 0', async () => {
    setup({ report: null });
    await screen.findByText('学习报告');

    expect(screen.getByText('暂无报告')).toBeTruthy();
    // 关键指标用 `?? 0` 兜底
    expect(screen.getByText('0 分钟')).toBeTruthy();
    expect(screen.getByText('暂无个性化建议')).toBeTruthy();
  });

  it('报告日期为 null → 渲染「—」占位', async () => {
    setup({ report: { ...REPORT, start_date: null, end_date: null } });
    await screen.findByText('学习报告');

    const dateLine = Array.from(document.querySelectorAll('p')).find((el) => el.textContent?.includes('~'));
    expect(dateLine).toBeTruthy();
    expect(dateLine!.textContent).toBe('— ~ —');
  });
});

describe('statistics · 筛选器进入请求参数', () => {
  it('默认请求携带 days=30 / metric=submissions / period=week', async () => {
    const { fetchMock } = setup();
    await screen.findByText('学习趋势');

    expect(lastQuery(fetchMock, '/statistics/trend').get('days')).toBe('30');
    expect(lastQuery(fetchMock, '/statistics/trend').get('metric')).toBe('submissions');
    expect(lastQuery(fetchMock, '/statistics/report').get('period')).toBe('week');
    expect(lastQuery(fetchMock, '/statistics/heatmap').get('days')).toBe('180');
  });

  it('切换天数 Tabs → trend 请求带新 days', async () => {
    const { fetchMock } = setup();
    await screen.findByText('学习趋势');

    await act(async () => {
      screen.getByRole('tab', { name: '7 天' }).click();
      await Promise.resolve();
    });

    await waitFor(() => expect(lastQuery(fetchMock, '/statistics/trend').get('days')).toBe('7'));
  });

  it('切换指标 Select → trend 请求带新 metric', async () => {
    const { fetchMock } = setup();
    await screen.findByText('学习趋势');

    await act(async () => {
      fireEvent.change(screen.getByRole('combobox'), { target: { value: 'minutes' } });
      await Promise.resolve();
    });

    await waitFor(() => expect(lastQuery(fetchMock, '/statistics/trend').get('metric')).toBe('minutes'));
  });

  it('切换报告周期 Tab → report 请求带新 period', async () => {
    const { fetchMock } = setup();
    await screen.findByText('学习报告');

    await act(async () => {
      screen.getByRole('tab', { name: '本月' }).click();
      await Promise.resolve();
    });

    await waitFor(() => expect(lastQuery(fetchMock, '/statistics/report').get('period')).toBe('month'));
  });
});

describe('statistics · 错误态（BUG-3 修复）', () => {
  it('overview 失败 → 显示错误态与后端文案，而非 8 张全 0 的卡片', async () => {
    setup({ overviewError: err('SERVER_ERROR', '统计服务异常', 500) });

    // 修复前：该页无任何 error 分支，接口失败会静默降级成「全 0 + 空图表」，
    // 用户无法区分「真的没数据」和「接口挂了」。
    expect(await screen.findByText('统计数据加载失败')).toBeTruthy();
    expect(screen.getByText('统计服务异常')).toBeTruthy();
    // 关键：不能再把 0 当成有效指标展示
    expect(screen.queryByText('累计学习时长')).toBeNull();
  });

  it('overview 失败时提供重试入口', async () => {
    setup({ overviewError: err('SERVER_ERROR', '统计服务异常', 500) });
    await screen.findByText('统计数据加载失败');

    expect(screen.getByRole('button', { name: /重试|重新加载/ })).toBeTruthy();
  });

  it('overview 正常时不渲染错误态', async () => {
    setup();
    await screen.findByText('累计学习时长');

    expect(screen.queryByText('统计数据加载失败')).toBeNull();
  });
});

describe('statistics · 未登录门禁', () => {
  it('未登录时展示登录引导而非统计内容', async () => {
    useAuthStore.setState({ hydrated: true, accessToken: null, refreshToken: null, user: null, loading: false, error: null });
    mockFetchByPath({
      '/statistics/trend': () => ok(TREND),
      '/statistics/categories': () => ok(CATEGORIES),
      '/statistics/heatmap': () => ok(HEATMAP),
      '/statistics/report': () => ok(REPORT),
      '/statistics/ranking': () => ok(RANKING),
      '/statistics/overview': () => ok(OVERVIEW),
    });

    render(<StatisticsPage />);

    expect(await screen.findByText('登录后查看统计分析')).toBeTruthy();
    expect(screen.queryByText('累计学习时长')).toBeNull();
  });
});
