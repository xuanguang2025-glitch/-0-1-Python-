// @vitest-environment node
/**
 * `resolveErrorMessage`（`src/store/auth.ts:144`）—— 错误码 → 中文文案映射表。
 *
 * 说明：team-lead 给的路径是 `tests/lib/resolve-error-message.test.ts`，
 * 但源码里它并不在 `lib/`，而是 `store/auth.ts` 的具名导出（唯一一个），
 * 因此测试文件放在 `tests/store/` 下与源码同构。
 *
 * 这张表是**用户直接看到的字符串**，属产品契约：后端改文案以外的码不会自动变，
 * 只能改这里，所以必须有逐码断言防回归。
 * 同时它与 `lib/api.ts` 的 ApiRequestError 强耦合（靠 `.code`），
 * 因此这里用真实的 ApiRequestError 而不是手搓对象。
 */
import { describe, it, expect } from 'vitest';

import { resolveErrorMessage } from '@/store/auth';
import { ApiRequestError } from '@/lib/api';

const FALLBACK = '登录失败，请检查账号或密码';

/** 构造一个带后端错误码的真实 ApiRequestError。 */
function apiError(code: string, message = '后端原始文案'): ApiRequestError {
  return new ApiRequestError(message, 400, code);
}

describe('resolveErrorMessage · 已知错误码映射（逐码断言）', () => {
  const cases: readonly [string, string][] = [
    ['INVALID_CREDENTIALS', '账号或密码错误'],
    ['EMAIL_EXISTS', '该邮箱已被注册'],
    ['USERNAME_EXISTS', '该用户名已被占用'],
    ['WEAK_PASSWORD', '密码强度不足，至少 8 位并包含字母和数字'],
    ['VALIDATION_ERROR', '请检查表单填写是否完整'],
    ['RATE_LIMITED', '操作过于频繁，请稍后再试'],
    ['ACCOUNT_SUSPENDED', '账号已被禁用，请联系管理员'],
  ];

  it.each(cases)('%s -> %s', (code, expected) => {
    // 后端返回的 message 一律被忽略：已知码必须走中文表
    expect(resolveErrorMessage(apiError(code, 'raw backend message'), FALLBACK)).toBe(expected);
  });

  it('7 个码互不撞车：漏配或误配会立刻暴露', () => {
    const mapped = cases.map(([code]) => resolveErrorMessage(apiError(code, 'x'), FALLBACK));
    expect(mapped).toHaveLength(7);
    expect(new Set(mapped).size).toBe(7);
  });

  it('已知码会屏蔽后端 message（防止后端英文直出到界面）', () => {
    expect(resolveErrorMessage(apiError('INVALID_CREDENTIALS', 'Invalid credentials'), FALLBACK)).not.toContain(
      'Invalid',
    );
  });
});

describe('resolveErrorMessage · 未知错误码的兜底', () => {
  it('未知码但带 message 时透传后端 message', () => {
    const err = apiError('SOME_NEW_CODE_FROM_BACKEND', '后端新增的提示文案');
    expect(resolveErrorMessage(err, FALLBACK)).toBe('后端新增的提示文案');
  });

  it('未知码且 message 为空串时用 fallback（不返回空串给用户）', () => {
    const err = new ApiRequestError('', 400, 'SOME_NEW_CODE');
    expect(resolveErrorMessage(err, FALLBACK)).toBe(FALLBACK);
  });

  it('普通 Error 无 code 时用其 message', () => {
    expect(resolveErrorMessage(new Error('Network Error'), FALLBACK)).toBe('Network Error');
  });

  it.each([
    ['字符串抛出', 'boom'],
    ['数字抛出', 500],
    ['null', null],
    ['undefined', undefined],
    ['普通对象', { code: 'INVALID_CREDENTIALS' }],
  ])('%s（非 Error）一律用 fallback，绝不崩也不返回 undefined', (_label, thrown) => {
    const result = resolveErrorMessage(thrown, FALLBACK);
    expect(result).toBe(FALLBACK);
    expect(result).not.toBeUndefined();
    expect(typeof result).toBe('string');
  });
});

describe('resolveErrorMessage · 与 ApiRequestError 的耦合', () => {
  it('真实 401 TOKEN_EXPIRED 没有对应码，透传 message', () => {
    const err = new ApiRequestError('登录已过期，请重新登录', 401, 'TOKEN_EXPIRED');
    expect(resolveErrorMessage(err, FALLBACK)).toBe('登录已过期，请重新登录');
  });

  it('错误码大小写敏感：invalid_credentials 不应命中表', () => {
    expect(resolveErrorMessage(apiError('invalid_credentials', 'x'), FALLBACK)).toBe('x');
  });

  it('fallback 参数为空串时返回空串而非 undefined（调用方可能传空）', () => {
    expect(resolveErrorMessage('boom', '')).toBe('');
  });
});
