/**
 * localStorage 安全读写封装（SSR 保护）。
 * Access Token 放内存，Refresh Token 与 UI 偏好放 localStorage。
 */

const PREFIX = 'pythonlab:';

function isBrowser(): boolean {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined';
}

export function readLocal<T>(key: string, fallback: T): T {
  if (!isBrowser()) return fallback;
  try {
    const raw = window.localStorage.getItem(PREFIX + key);
    if (raw === null) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export function writeLocal<T>(key: string, value: T): void {
  if (!isBrowser()) return;
  try {
    window.localStorage.setItem(PREFIX + key, JSON.stringify(value));
  } catch {
    /* 隐私模式或配额不足时静默失败 */
  }
}

export function removeLocal(key: string): void {
  if (!isBrowser()) return;
  try {
    window.localStorage.removeItem(PREFIX + key);
  } catch {
    /* noop */
  }
}

export const STORAGE_KEYS = {
  refreshToken: 'auth.refresh_token',
  remember: 'auth.remember',
  editorDraft: 'editor.draft',
  recentFiles: 'editor.recent',
} as const;
