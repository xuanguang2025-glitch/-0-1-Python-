"""轻量文本差异工具（行级 diff，供判题输出对比与代码版本比较使用）。

实现基于标准库 `difflib`，不引入额外依赖；输出为统一 diff 文本 + hunk 列表，
便于前端渲染（无需再解析）。
"""

from __future__ import annotations

import difflib
from typing import Any

from app.utils.text import normalize_newlines


def unified_diff_text(
    left: str,
    right: str,
    *,
    left_label: str = "expected",
    right_label: str = "actual",
    context: int = 3,
) -> str:
    """生成统一格式 diff 文本。"""
    left_lines = normalize_newlines(left or "").splitlines()
    right_lines = normalize_newlines(right or "").splitlines()
    return "\n".join(
        difflib.unified_diff(left_lines, right_lines, fromfile=left_label, tofile=right_label, lineterm="", n=context)
    )


def build_hunks(left: str, right: str, *, context: int = 3) -> list[dict[str, Any]]:
    """生成结构化 hunk 列表，供前端左右对比视图使用。

    Returns:
        形如 `[{"old_start": 1, "old_lines": 2, "new_start": 1, "new_lines": 2,
        "lines": [{"type": "add|del|ctx", "text": "..."}]}]`。
    """
    left_lines = normalize_newlines(left or "").splitlines()
    right_lines = normalize_newlines(right or "").splitlines()
    matcher = difflib.SequenceMatcher(a=left_lines, b=right_lines, autojunk=False)
    hunks: list[dict[str, Any]] = []

    for group in matcher.get_grouped_opcodes(n=context):
        lines: list[dict[str, str]] = []
        old_start = group[0][1] + 1
        new_start = group[0][3] + 1
        old_count = 0
        new_count = 0
        for tag, i1, i2, j1, j2 in group:
            if tag in ("replace", "delete"):
                for text in left_lines[i1:i2]:
                    lines.append({"type": "del", "text": text})
                    old_count += 1
            if tag in ("replace", "insert"):
                for text in right_lines[j1:j2]:
                    lines.append({"type": "add", "text": text})
                    new_count += 1
            if tag == "equal":
                for text in left_lines[i1:i2]:
                    lines.append({"type": "ctx", "text": text})
                    old_count += 1
                    new_count += 1
        hunks.append(
            {
                "old_start": old_start,
                "old_lines": old_count,
                "new_start": new_start,
                "new_lines": new_count,
                "lines": lines,
            }
        )
    return hunks


def similarity_ratio(left: str, right: str) -> float:
    """计算两段文本的相似度（0.0 - 1.0），用于模糊对比或抄袭初筛。"""
    return difflib.SequenceMatcher(a=normalize_newlines(left or ""), b=normalize_newlines(right or ""), autojunk=False).ratio()


def first_difference_line(left: str, right: str) -> int | None:
    """返回首个不同行的行号（1 起）；完全一致时返回 None。"""
    left_lines = normalize_newlines(left or "").splitlines()
    right_lines = normalize_newlines(right or "").splitlines()
    for index, (a, b) in enumerate(zip(left_lines, right_lines), start=1):
        if a != b:
            return index
    if len(left_lines) != len(right_lines):
        return min(len(left_lines), len(right_lines)) + 1
    return None
