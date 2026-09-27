"""文本处理工具：输出归一化、截断、脱敏、Markdown 辅助。

判题对比默认使用 `trimmed` 规则：统一换行 + 去每行尾空格 + 去首尾空行。
"""

from __future__ import annotations

import re
from typing import Iterable

_EMAIL_RE: re.Pattern[str] = re.compile(r"([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
_MULTI_BLANK_RE: re.Pattern[str] = re.compile(r"\n{3,}")


def normalize_newlines(text: str) -> str:
    """统一换行为 `\n`（兼容 CRLF / CR）。"""
    return (text or "").replace("\r\n", "\n").replace("\r", "\n")


def strip_trailing_spaces(text: str) -> str:
    """去掉每行末尾的空白字符。"""
    return "\n".join(line.rstrip() for line in normalize_newlines(text).split("\n"))


def normalize_output(text: str) -> str:
    """按 `trimmed` 规则归一化输出：统一换行 + 去行尾空格 + 去首尾空行。"""
    return strip_trailing_spaces(text).strip("\n")


def truncate(text: str, limit: int, suffix: str = "...(已截断)") -> str:
    """按字符数截断文本并在末尾追加提示。"""
    raw = text or ""
    if limit <= 0 or len(raw) <= limit:
        return raw
    return raw[:limit] + suffix


def truncate_bytes(text: str, limit_bytes: int) -> str:
    """按 UTF-8 字节数截断（避免入库时超出列限制）。"""
    raw = (text or "").encode("utf-8")
    if len(raw) <= limit_bytes:
        return text or ""
    return raw[:limit_bytes].decode("utf-8", errors="ignore")


def mask_email(email: str) -> str:
    """脱敏邮箱：`zhangsan@example.com` → `z***n@example.com`。"""
    def _replace(match: re.Match[str]) -> str:
        name, domain = match.group(1), match.group(2)
        if len(name) <= 2:
            masked = name[0] + "***"
        else:
            masked = f"{name[0]}***{name[-1]}"
        return f"{masked}@{domain}"

    return _EMAIL_RE.sub(_replace, email or "")


def slugify(text: str, max_length: int = 80) -> str:
    """把中文/英文标题转换为 URL 友好的 slug（保留中文字符）。"""
    value = (text or "").strip().lower()
    value = re.sub(r"[\s_]+", "-", value)
    value = re.sub(r"[^\w\u4e00-\u9fff-]", "", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value[:max_length]


def excerpt(text: str, limit: int = 120) -> str:
    """生成纯文本摘要（去除 Markdown 标记后截断）。"""
    plain = re.sub(r"[#*`>\[\]()!]", "", normalize_newlines(text or ""))
    plain = re.sub(r"\s+", " ", plain).strip()
    return truncate(plain, limit, suffix="…")


def count_words(text: str) -> int:
    """粗略统计中英文混排文本的字数（中文按字计，英文按词计）。"""
    raw = text or ""
    chinese = len(re.findall(r"[\u4e00-\u9fff]", raw))
    english = len(re.findall(r"[A-Za-z]+", raw))
    return chinese + english


def join_lines(lines: Iterable[str], sep: str = "\n") -> str:
    """拼接多行文本，自动跳过 None。"""
    return sep.join(line for line in lines if line is not None)


def highlight(text: str, keyword: str, radius: int = 30) -> str:
    """生成搜索结果高亮片段（返回关键词附近的文本）。"""
    raw = normalize_newlines(text or "")
    if not keyword:
        return truncate(raw, radius * 2, suffix="…")
    index = raw.lower().find(keyword.lower())
    if index < 0:
        return truncate(raw, radius * 2, suffix="…")
    start = max(0, index - radius)
    end = min(len(raw), index + len(keyword) + radius)
    snippet = raw[start:end]
    return ("…" if start > 0 else "") + snippet + ("…" if end < len(raw) else "")


def collapse_blank_lines(text: str) -> str:
    """把连续 3 行以上空行压缩为 2 行（Markdown 排版用）。"""
    return _MULTI_BLANK_RE.sub("\n\n", normalize_newlines(text))
