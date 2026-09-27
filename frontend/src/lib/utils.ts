import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/** 合并 Tailwind 类名，后者覆盖前者（shadcn/ui 约定）。 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/** 秒 → 「2 小时 15 分」/「12 分 30 秒」风格的可读文本。 */
export function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '0 分钟';
  const total = Math.round(seconds);
  if (total < 60) return `${total} 秒`;
  const minutes = Math.floor(total / 60);
  if (minutes < 60) return `${minutes} 分钟`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? `${hours} 小时 ${rest} 分` : `${hours} 小时`;
}

/** 分钟 → 「6.5 小时」。 */
export function formatMinutes(minutes: number): string {
  if (!Number.isFinite(minutes) || minutes <= 0) return '0 分钟';
  if (minutes < 60) return `${Math.round(minutes)} 分钟`;
  return `${(minutes / 60).toFixed(1)} 小时`;
}

/** KB → MB / KB 文本。 */
export function formatMemory(kb: number): string {
  if (!Number.isFinite(kb) || kb <= 0) return '0 KB';
  if (kb < 1024) return `${Math.round(kb)} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
}

/** 毫秒 → ms/s。 */
export function formatTime(ms: number): string {
  if (!Number.isFinite(ms) || ms < 0) return '—';
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

/** 大数字 → 1.2k / 3.4w。 */
export function formatCompact(value: number): string {
  if (!Number.isFinite(value)) return '0';
  if (Math.abs(value) < 1000) return String(value);
  if (Math.abs(value) < 10000) return `${(value / 1000).toFixed(1)}k`;
  return `${(value / 10000).toFixed(1)}w`;
}

/** 0.775 → 77.5%。 */
export function formatPercent(ratio: number, digits = 1): string {
  if (!Number.isFinite(ratio)) return '0%';
  return `${(ratio * 100).toFixed(digits)}%`;
}

/** ISO 时间 → YYYY-MM-DD。 */
export function formatDate(input: string | Date | null | undefined): string {
  if (!input) return '—';
  const date = typeof input === 'string' ? new Date(input) : input;
  if (Number.isNaN(date.getTime())) return '—';
  const y = date.getFullYear();
  const m = `${date.getMonth() + 1}`.padStart(2, '0');
  const d = `${date.getDate()}`.padStart(2, '0');
  return `${y}-${m}-${d}`;
}

/** ISO 时间 → 「3 分钟前」。 */
export function formatRelativeTime(input: string | Date | null | undefined): string {
  if (!input) return '—';
  const date = typeof input === 'string' ? new Date(input) : input;
  if (Number.isNaN(date.getTime())) return '—';
  const diff = Date.now() - date.getTime();
  const abs = Math.abs(diff);
  const suffix = diff >= 0 ? '前' : '后';
  const minute = 60_000;
  const hour = 60 * minute;
  const day = 24 * hour;
  if (abs < minute) return '刚刚';
  if (abs < hour) return `${Math.floor(abs / minute)} 分钟${suffix}`;
  if (abs < day) return `${Math.floor(abs / hour)} 小时${suffix}`;
  if (abs < 30 * day) return `${Math.floor(abs / day)} 天${suffix}`;
  return formatDate(date);
}

/** 截断文本。 */
export function truncate(text: string, max = 120): string {
  if (text.length <= max) return text;
  return `${text.slice(0, max)}…`;
}

/** 取昵称首字母用于头像兜底。 */
export function initials(name: string | null | undefined): string {
  if (!name) return 'P';
  const trimmed = name.trim();
  if (!trimmed) return 'P';
  return trimmed.slice(0, 2).toUpperCase();
}

/** 从 Content-Disposition 解析文件名。 */
export function parseFilename(header: string | null, fallback: string): string {
  if (!header) return fallback;
  const match = /filename\*?=(?:UTF-8'')?["']?([^;"']+)/i.exec(header);
  return match ? decodeURIComponent(match[1]) : fallback;
}
