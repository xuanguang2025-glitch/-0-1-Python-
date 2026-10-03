import { vi } from 'vitest';

/** 构造统一响应结构的 Response 替身。 */
export function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? 'OK' : 'Error',
    headers: new Headers({ 'Content-Type': 'application/json' }),
    text: async () => JSON.stringify(body),
    json: async () => body,
    blob: async () => new Blob([JSON.stringify(body)]),
    clone() {
      return this;
    },
  } as unknown as Response;
}

/** 统一成功信封。 */
export const ok = <T,>(data: T, message = '') =>
  jsonResponse({ success: true, data, message, error: null });

/** 统一失败信封（对齐 docs/API.md §4）。 */
export const err = (code: string, message = '失败', status = 400, details: unknown = null) =>
  jsonResponse({ success: false, data: null, message, error: { code, details } }, status);

/** 按调用顺序返回预设响应；用完则抛错以暴露「多发/少发请求」。 */
export function mockFetchSequence(responses: Response[]) {
  const calls: { url: string; init?: RequestInit }[] = [];
  const fn = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
    calls.push({ url: String(url), init });
    const next = responses[calls.length - 1];
    if (!next) throw new Error(`fetch 调用次数超出预期：第 ${calls.length + 1} 次`);
    return next;
  });
  vi.stubGlobal('fetch', fn);
  return { fn, calls };
}

/**
 * 按「路径」而非调用次序分派的 fetch mock。
 * 刷新链路的调用次序受并发时序影响，用顺序队列断言会不稳定。
 */
export function mockFetchByPath(routes: Record<string, () => Response>) {
  const calls: { url: string; init?: RequestInit }[] = [];
  const fn = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
    const href = String(url);
    calls.push({ url: href, init });
    const path = Object.keys(routes).find((key) => href.includes(key));
    if (!path) throw new Error(`fetch 命中未注册路径：${href}`);
    return routes[path]!();
  });
  vi.stubGlobal('fetch', fn);
  return {
    fn,
    calls,
    /** 统计某个路径被调用的次数。 */
    countOf(fragment: string): number {
      return calls.filter((call) => call.url.includes(fragment)).length;
    },
  };
}

/** 永远 401 + 可刷新错误码，用于测单飞刷新。 */
export const unauthorized = () => err('TOKEN_EXPIRED', '登录已过期', 401);
