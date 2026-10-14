// @vitest-environment jsdom
/**
 * `src/app/ai-tutor/page.tsx` —— AI 对话的重复提交防护。
 *
 * `send()` 原先用**纯 state** `sending` 做判断（`if (!message || sending) return;`），
 * 同一 tick 内连点会穿帮：闭包读到的是旧值 `false`，`setSending(true)` 只是排队。
 * 现已改为 `useSubmitGuard` 的 ref 守卫。`removeConversation()` 原先**完全没有任何
 * 守卫**，连点会重复 DELETE 会话。
 *
 * 连点一律用同步 `button.click()`，不用 `userEvent.click()` —— 后者每次都会 await
 * 并让 React 重渲染，第二击会被 DOM 的 disabled 挡掉，只能测到 disabled 属性，
 * 测不到守卫，是假绿。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act, fireEvent } from '@testing-library/react';
import type { UserBrief } from '@/lib/types';

import AiTutorPage from '@/app/ai-tutor/page';
import { useAuthStore } from '@/store/auth';
import { err, mockFetchByPath, ok } from '../helpers/fetch-mock';

// jsdom 未实现 Element.prototype.scrollTo，而页面的自动滚动 effect 会调用它
beforeEach(() => {
  if (!Element.prototype.scrollTo) {
    Element.prototype.scrollTo = vi.fn();
  }
});

vi.mock('next/navigation', () => ({
  usePathname: () => '/ai-tutor',
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn(), prefetch: vi.fn(), refresh: vi.fn() }),
  redirect: vi.fn(),
}));

const USER: UserBrief = {
  id: 'u-1',
  email: 'tester@example.com',
  username: 'tester',
  display_name: '测试用户',
  role: 'user',
  level: 1,
  xp: 0,
};

const CHAT_REPLY = {
  message_id: 'm-2',
  conversation_id: 'c-1',
  content_md: '这是 AI 的回复',
  degraded: false,
  kind: 'answer',
  suggestions: [],
};

/** 可控 deferred。 */
function deferred<T>(): { promise: Promise<T>; resolve: (v: T) => void; reject: (e: unknown) => void } {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function setup() {
  useAuthStore.setState({
    hydrated: true,
    accessToken: 'test-access-token',
    refreshToken: 'test-refresh-token',
    user: USER,
    loading: false,
    error: null,
  });

  const chatGate = deferred<Response>();
  const deleteGate = deferred<Response>();

  const fetchMock = mockFetchByPath({
    // 具体路径优先
    '/ai/conversations': () => ok({ items: [], total: 0, page: 1, page_size: 20 }),
    '/ai/status': () => ok({ degraded: false, remaining_quota: 100 }),
    '/ai/chat': () => chatGate.promise as unknown as Response,
    '/ai/conversations/': () => deleteGate.promise as unknown as Response,
  });

  render(<AiTutorPage />);
  return { fetchMock, chatGate, deleteGate };
}

afterEach(() => {
  useAuthStore.setState({ accessToken: null, refreshToken: null, user: null, hydrated: false, loading: false, error: null });
});

/** 往输入框写入文本。发送按钮读的是 `input` state，必须先填再点。 */
async function typeMessage(text: string): Promise<void> {
  // 页面里还有 Navbar 的搜索框，必须用 placeholder 精确定位 AI 输入框
  const textarea = screen.getByPlaceholderText('描述你的问题（Enter 发送，Shift + Enter 换行）') as HTMLTextAreaElement;
  await act(async () => {
    fireEvent.change(textarea, { target: { value: text } });
    await Promise.resolve();
  });
}

describe('ai-tutor · 发消息重复提交', () => {
  it('★ send：pending 期间同步连点三次，只发出一次 /ai/chat', async () => {
    const { fetchMock } = setup();
    await typeMessage('你好');

    const sendBtn = await screen.findByRole('button', { name: '发送' });

    await act(async () => {
      sendBtn.click();
      sendBtn.click();
      sendBtn.click();
      await Promise.resolve();
    });

    // ★ 核心断言：3 次点击 → 1 次 chat 请求。无守卫时这里是 3。
    expect(fetchMock.countOf('/ai/chat')).toBe(1);
  });

  it('快速提问按钮在发送中同样被守卫拦住', async () => {
    const { fetchMock } = setup();

    // 空会话态下的快捷提问按钮（自带文案，无需先输入）。
    // 注意同一文案会同时出现在空态引导区和建议区，取第一个即可。
    const quickBtns = await screen.findAllByRole('button', { name: /列表推导式/ });
    const quickBtn = quickBtns[0] as HTMLElement;

    await act(async () => {
      quickBtn.click();
      quickBtn.click();
      await Promise.resolve();
    });

    expect(fetchMock.countOf('/ai/chat')).toBe(1);
  });

  it('发送中显示「AI 正在思考」且发送按钮禁用', async () => {
    setup();
    await typeMessage('你好');
    const sendBtn = await screen.findByRole('button', { name: '发送' });

    await act(async () => {
      sendBtn.click();
      await Promise.resolve();
    });

    expect(screen.getByText('AI 正在思考…')).toBeTruthy();
    expect(screen.getByRole('button', { name: '发送' })).toBeDisabled();
  });

  it('发送失败后复位：可再次发送', async () => {
    const { fetchMock, chatGate } = setup();
    await typeMessage('你好');
    const sendBtn = await screen.findByRole('button', { name: '发送' });

    await act(async () => {
      sendBtn.click();
      await Promise.resolve();
    });
    expect(fetchMock.countOf('/ai/chat')).toBe(1);

    await act(async () => {
      chatGate.reject(err('AI_UNAVAILABLE', 'AI 服务暂不可用', 503));
      await chatGate.promise.catch(() => undefined);
    });

    // 复位 → 可再次发送
    const retry = await screen.findByRole('button', { name: '发送' });
    expect(retry).not.toBeDisabled();

    await typeMessage('再试一次');
    await act(async () => {
      retry.click();
      await Promise.resolve();
    });
    expect(fetchMock.countOf('/ai/chat')).toBe(2);
  });

  it('成功后正常落地回复并复位', async () => {
    const { chatGate } = setup();
    await typeMessage('你好');
    const sendBtn = await screen.findByRole('button', { name: '发送' });

    await act(async () => {
      sendBtn.click();
      await Promise.resolve();
    });

    await act(async () => {
      chatGate.resolve(ok(CHAT_REPLY));
      await chatGate.promise;
    });

    expect(await screen.findByText('这是 AI 的回复')).toBeTruthy();
    expect(screen.getByRole('button', { name: '发送' })).not.toBeDisabled();
  });
});
