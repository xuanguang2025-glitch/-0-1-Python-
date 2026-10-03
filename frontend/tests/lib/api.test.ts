// @vitest-environment jsdom
/**
 * `src/lib/api.ts` —— 请求客户端，**并发刷新红线**所在。
 *
 * 核心风险（docs/API.md §5.2）：401 时若不做单飞刷新，
 * 3 个并发请求会打 3 次 /auth/refresh；若不做「仅重试一次」，
 * 刷新成功后重试仍 401 会造成无限递归。
 * 本文件用「按路径分派」的 mock 断言调用次数，规避并发时序不确定性。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';

import { ApiRequestError, apiGet, apiPost, configureApiClient } from '@/lib/api';
import { err, jsonResponse, mockFetchByPath, ok, unauthorized } from '../helpers/fetch-mock';

const onTokensRefreshed = vi.fn();
const onSessionExpired = vi.fn();

beforeEach(() => {
  onTokensRefreshed.mockReset();
  onSessionExpired.mockReset();
  configureApiClient({
    getAccessToken: () => 'access-token',
    getRefreshToken: () => 'refresh-token',
    onTokensRefreshed,
    onSessionExpired,
  });
});

describe('api · 基础解包', () => {
  it('用例9：成功响应脱壳为 data', async () => {
    mockFetchByPath({ '/x': () => ok({ a: 1 }) });
    await expect(apiGet('/x')).resolves.toEqual({ a: 1 });
  });

  it('用例10：失败响应抛 ApiRequestError，携带 code 与 status', async () => {
    mockFetchByPath({ '/x': () => err('PROBLEM_NOT_FOUND', '题目不存在', 400) });
    const promise = apiGet('/x');
    await expect(promise).rejects.toBeInstanceOf(ApiRequestError);
    await expect(promise).rejects.toMatchObject({ code: 'PROBLEM_NOT_FOUND', status: 400 });
  });

  it('用例16：204 无内容解析为 null', async () => {
    mockFetchByPath({ '/x': () => jsonResponse(null, 204) });
    await expect(apiGet('/x')).resolves.toBeNull();
  });

  it('用例18：query 忽略空值但保留数字 0', async () => {
    const { calls } = mockFetchByPath({ '/x': () => ok(null) });
    await apiGet('/x', { a: 1, b: '', c: undefined, d: null, e: 0 });
    const url = calls[0]!.url;
    expect(url).toContain('a=1');
    expect(url).toContain('e=0'); // 0 是有效值，不能被当空值丢弃
    expect(url).not.toContain('b=');
    expect(url).not.toContain('c=');
    expect(url).not.toContain('d=');
  });

  it('POST 会发送 JSON body 与 Content-Type', async () => {
    const { calls } = mockFetchByPath({ '/x': () => ok({ id: '1' }) });
    await apiPost('/x', { name: 'a' });
    const init = calls[0]!.init as RequestInit;
    expect(init.method).toBe('POST');
    expect((init.headers as Record<string, string>)['Content-Type']).toBe('application/json');
    expect(init.body).toBe(JSON.stringify({ name: 'a' }));
  });

  it('携带 Authorization 头', async () => {
    const { calls } = mockFetchByPath({ '/x': () => ok(null) });
    await apiGet('/x');
    expect((calls[0]!.init as RequestInit).headers).toMatchObject({ Authorization: 'Bearer access-token' });
  });
});

describe('api · 401 单飞刷新（并发红线）', () => {
  it('用例11：3 个并发 401 只触发 1 次 /auth/refresh', async () => {
    let businessCalls = 0;
    const mock = mockFetchByPath({
      '/auth/refresh': () => {
        businessCalls += 1;
        return ok({ access_token: 'new', refresh_token: 'new2' });
      },
      '/x': () => unauthorized(),
    });

    const results = await Promise.allSettled([apiGet('/x'), apiGet('/x'), apiGet('/x')]);

    // 三个业务请求重试后仍拿不到有效响应 —— 这里让 /auth/refresh 成功但业务继续 401
    expect(results).toHaveLength(3);
    expect(mock.countOf('/auth/refresh')).toBe(1); // ★ 核心断言：单飞
  });

  it('用例12：刷新成功后仅重试一次，不得无限递归', async () => {
    const mock = mockFetchByPath({
      '/auth/refresh': () => ok({ access_token: 'new', refresh_token: 'new2' }),
      '/x': () => unauthorized(),
    });

    await expect(apiGet('/x')).rejects.toBeInstanceOf(ApiRequestError);

    expect(mock.countOf('/auth/refresh')).toBe(1);
    expect(mock.countOf('/x')).toBe(2); // 首次 + 重试一次，共 2 次，不得更多
  });

  it('刷新成功后重试拿到数据则正常 resolve', async () => {
    let attempt = 0;
    const mock = mockFetchByPath({
      '/auth/refresh': () => ok({ access_token: 'new', refresh_token: 'new2' }),
      '/x': () => {
        attempt += 1;
        return attempt === 1 ? unauthorized() : ok({ recovered: true });
      },
    });

    await expect(apiGet('/x')).resolves.toEqual({ recovered: true });
    expect(mock.countOf('/auth/refresh')).toBe(1);
    expect(onTokensRefreshed).toHaveBeenCalledTimes(1);
  });

  it('用例13：刷新失败 → onSessionExpired 被调用 1 次并抛 401', async () => {
    mockFetchByPath({
      '/auth/refresh': () => unauthorized(),
      '/x': () => unauthorized(),
    });

    await expect(apiGet('/x')).rejects.toMatchObject({ status: 401 });
    expect(onSessionExpired).toHaveBeenCalledTimes(1);
  });

  it('用例14/19：无 refresh token 时不发刷新请求，直接结束会话', async () => {
    configureApiClient({ getRefreshToken: () => null });
    const mock = mockFetchByPath({ '/x': () => unauthorized() });

    await expect(apiGet('/x')).rejects.toMatchObject({ status: 401 });
    expect(mock.countOf('/auth/refresh')).toBe(0); // ★ 不得发出刷新请求
    expect(onSessionExpired).toHaveBeenCalledTimes(1);
  });

  it('用例15：401 + FORBIDDEN 不触发刷新（无意义的刷新）', async () => {
    const mock = mockFetchByPath({ '/x': () => err('FORBIDDEN', '权限不足', 403) });

    await expect(apiGet('/x')).rejects.toMatchObject({ code: 'FORBIDDEN' });
    expect(mock.countOf('/auth/refresh')).toBe(0);
    expect(onSessionExpired).not.toHaveBeenCalled();
  });
});

describe('api · blob 与非常规响应', () => {
  it('用例17：blob 选项返回 Blob 实例', async () => {
    mockFetchByPath({ '/export': () => jsonResponse({ rows: [] }) });
    const result = await apiGet('/export', undefined, { blob: true });
    expect(result).toBeInstanceOf(Blob);
  });

  it('blob 请求失败时抛错而非返回空', async () => {
    mockFetchByPath({ '/export': () => err('INTERNAL_ERROR', '导出失败', 500) });
    await expect(apiGet('/export', undefined, { blob: true })).rejects.toBeInstanceOf(ApiRequestError);
  });

  it('非统一结构（纯文本）时原样返回', async () => {
    mockFetchByPath({ '/health': () => jsonResponse('pong') });
    await expect(apiGet('/health')).resolves.toBe('pong');
  });
});
