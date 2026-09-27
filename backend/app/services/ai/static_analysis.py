"""离线静态代码审查（RuleBasedProvider 的 Code Review 后端）。

基于文本/正则 + `ast` 的启发式规则，覆盖 Code Review 九维度，输出结构化问题列表、
评分与改进建议代码。无需任何外部依赖，纯离线可用。

主要检查项：
- 命名规范（PEP 8：函数/变量 snake_case、类 PascalCase、常量 UPPER）；
- 可变默认参数（`def f(x=[])`）；
- 裸 `except:`；
- `== None` / `!= None`（应使用 `is None` / `is not None`）；
- 未使用的导入；
- `range(len(x))` 反模式；
- 字符串 `+=` 拼接（应使用 `"".join`）；
- 重复代码块；
- 圈复杂度粗估与复杂度提示。
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Any

_MAX_LINE_LENGTH: int = 100

_FUNC_DEF_RE: re.Pattern[str] = re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)\s*\(")
_CLASS_DEF_RE: re.Pattern[str] = re.compile(r"^\s*class\s+([A-Za-z_]\w*)")
_IMPORT_RE: re.Pattern[str] = re.compile(r"^\s*import\s+([A-Za-z_][\w., ]*)$")
_FROM_IMPORT_RE: re.Pattern[str] = re.compile(r"^\s*from\s+[\w.]+\s+import\s+(.+)$")
_BARE_EXCEPT_RE: re.Pattern[str] = re.compile(r"^\s*except\s*:\s*$")
_NONE_CMP_RE: re.Pattern[str] = re.compile(r"[=!]=\s*None\b")
_RANGE_LEN_RE: re.Pattern[str] = re.compile(r"range\(\s*len\(")
_STR_CONCAT_RE: re.Pattern[str] = re.compile(r"\b(\w+)\s*\+=\s*(?:[\"']|\w+\s*\+|f[\"'])")
_COMPLEXITY_KEYWORDS: tuple[str, ...] = ("if ", "elif ", "for ", "while ", " and ", " or ", "except", "with ")


@dataclass(slots=True)
class Issue:
    """单条评审问题。"""

    severity: str
    line: int | None
    title: str
    suggestion: str
    dimension: str = ""

    def as_dict(self) -> dict[str, Any]:
        """转换为 `schemas.ai.ReviewIssue` 兼容字典。"""
        return {
            "severity": self.severity,
            "line": self.line,
            "title": self.title,
            "suggestion": self.suggestion,
        }


@dataclass(slots=True)
class ReviewResult:
    """结构化评审结果（与 `schemas.ai.ReviewOut` 对齐）。"""

    score: int = 100
    summary_md: str = ""
    issues: list[Issue] = field(default_factory=list)
    improved_code: str = ""
    dimensions: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """序列化为 `ReviewOut` 兼容字典。"""
        return {
            "score": int(self.score),
            "summary_md": self.summary_md,
            "issues": [issue.as_dict() for issue in self.issues],
            "improved_code": self.improved_code,
            "degraded": True,
        }


# ---------------------------------------------------------------------------
# 逐项检查
# ---------------------------------------------------------------------------


def _check_method_mutable_default(lines: list[str]) -> list[Issue]:
    """检查函数签名中的可变默认参数（list/dict/set）。"""
    issues: list[Issue] = []
    pattern = re.compile(r"def\s+\w+\s*\(([^)]*)\)")
    for idx, raw in enumerate(lines, start=1):
        match = pattern.search(raw)
        if not match:
            continue
        params = match.group(1)
        if re.search(r"=\s*(\[\]|\{\}|set\(\)|dict\(\)|list\(\))", params):
            issues.append(
                Issue(
                    severity="error",
                    line=idx,
                    title="可变默认参数",
                    suggestion="默认值改用 None，函数体内 `if xs is None: xs = []`，避免跨调用共享同一对象。",
                    dimension="潜在 Bug",
                )
            )
    return issues


def _check_bare_except(lines: list[str]) -> list[Issue]:
    """检查裸 except。"""
    return [
        Issue(
            severity="warning",
            line=idx,
            title="裸 except",
            suggestion="捕获具体异常类型（如 `except ValueError:`），避免吞掉 KeyboardInterrupt/SystemExit。",
            dimension="潜在 Bug",
        )
        for idx, raw in enumerate(lines, start=1)
        if _BARE_EXCEPT_RE.match(raw)
    ]


def _check_none_comparison(lines: list[str]) -> list[Issue]:
    """检查 `== None` / `!= None`。"""
    return [
        Issue(
            severity="warning",
            line=idx,
            title="与 None 用等值比较",
            suggestion="改为 `is None` / `is not None`，符合 PEP 8 且语义更准确。",
            dimension="Python 风格(PEP 8)",
        )
        for idx, raw in enumerate(lines, start=1)
        if _NONE_CMP_RE.search(raw)
    ]


def _check_range_len(lines: list[str]) -> list[Issue]:
    """检查 `range(len(x))` 反模式。"""
    return [
        Issue(
            severity="warning",
            line=idx,
            title="range(len(...)) 反模式",
            suggestion="直接 `for item in x`；需要下标时用 `enumerate(x)`；成对遍历用 `zip(a, b)`。",
            dimension="Python 风格(PEP 8)",
        )
        for idx, raw in enumerate(lines, start=1)
        if _RANGE_LEN_RE.search(raw)
    ]


def _check_str_concat(lines: list[str]) -> list[Issue]:
    """检查循环中的字符串 `+=` 拼接。"""
    issues: list[Issue] = []
    inside_loop = False
    for idx, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        if stripped.startswith(("for ", "while ")):
            inside_loop = True
        if inside_loop and _STR_CONCAT_RE.search(raw):
            issues.append(
                Issue(
                    severity="info",
                    line=idx,
                    title="循环内字符串拼接",
                    suggestion="累积到 list 后 `\"\".join(parts)`，避免 O(n²) 的重复拷贝。",
                    dimension="复杂度",
                )
            )
            inside_loop = False
    return issues


def _collect_imported_names(lines: list[str]) -> list[tuple[str, int]]:
    """收集静态导入的名称与行号（仅顶层 `import x` / `from m import a, b`）。"""
    names: list[tuple[str, int]] = []
    for idx, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        if stripped.startswith(("import ", "from ")):
            found = _parse_import_line(stripped)
            names.extend((name, idx) for name in found)
    return names


def _parse_import_line(line: str) -> list[str]:
    """解析单行导入，返回导入的顶层名称列表。"""
    from_match = _FROM_IMPORT_RE.match(line)
    if from_match:
        items = [part.strip().split(" as ")[-1].strip() for part in from_match.group(1).split(",")]
        return [name for name in items if name and name != "*"]
    import_match = _IMPORT_RE.match(line)
    if import_match:
        parts = [part.strip() for part in import_match.group(1).split(",")]
        return [part.split(" as ")[-1].strip().split(".")[0] for part in parts if part]
    return []


def _check_unused_imports(code: str, lines: list[str]) -> list[Issue]:
    """检查未使用的导入。"""
    issues: list[Issue] = []
    body = "\n".join(line for line in lines if not line.strip().startswith(("import ", "from ")))
    for name, idx in _collect_imported_names(lines):
        if re.search(rf"\b{re.escape(name)}\b", body) is None:
            issues.append(
                Issue(
                    severity="info",
                    line=idx,
                    title=f"未使用的导入：{name}",
                    suggestion=f"删除 `{name}` 的导入，保持依赖清晰。",
                    dimension="可读性",
                )
            )
    return issues


def _check_naming(lines: list[str]) -> list[Issue]:
    """检查命名规范（函数 snake_case / 类 PascalCase）。"""
    issues: list[Issue] = []
    for idx, raw in enumerate(lines, start=1):
        func = _FUNC_DEF_RE.match(raw)
        if func and not re.fullmatch(r"[a-z_][a-z0-9_]*", func.group(1)):
            issues.append(
                Issue("info", idx, f"函数命名不规范：{func.group(1)}", "函数名使用小写下划线（snake_case）。", "命名")
            )
        cls = _CLASS_DEF_RE.match(raw)
        if cls and not re.fullmatch(r"[A-Z][A-Za-z0-9_]*", cls.group(1)):
            issues.append(
                Issue("info", idx, f"类命名不规范：{cls.group(1)}", "类名使用大驼峰（PascalCase）。", "命名")
            )
    return issues


def _check_long_lines(lines: list[str]) -> list[Issue]:
    """检查超长行（PEP 8 建议 ≤79/本项目 ≤100）。"""
    return [
        Issue("info", idx, "行长度超限", f"第 {idx} 行长度 {len(raw)}，建议 ≤{_MAX_LINE_LENGTH}，可拆分或换行。", "Python 风格(PEP 8)")
        for idx, raw in enumerate(lines, start=1)
        if len(raw) > _MAX_LINE_LENGTH
    ]


def _check_duplicate_blocks(lines: list[str], min_len: int = 4) -> list[Issue]:
    """检查重复代码块（连续 ≥min_len 行的归一化片段重复出现）。"""
    normalized = [line.strip() for line in lines]
    seen: dict[tuple[str, ...], int] = {}
    issues: list[Issue] = []
    for i in range(len(normalized) - min_len + 1):
        window = tuple(normalized[i : i + min_len])
        if not any(window):  # 跳过纯空行
            continue
        if window in seen:
            issues.append(
                Issue(
                    "warning",
                    i + 1,
                    "疑似重复代码块",
                    f"与第 {seen[window]} 行起的代码块重复，可抽取为函数或循环复用。",
                    "重复代码",
                )
            )
            break  # 只报一次，避免噪声
        seen[window] = i + 1
    return issues


def _estimate_complexity(code: str) -> int:
    """粗估圈复杂度（以分支关键字计数 + 1）。"""
    return 1 + sum(code.count(keyword) for keyword in _COMPLEXITY_KEYWORDS)


def _check_complexity(code: str, lines: list[str], max_complexity: int = 10) -> list[Issue]:
    """复杂度提示：圈复杂度超阈值或存在深层嵌套。"""
    issues: list[Issue] = []
    complexity = _estimate_complexity(code)
    if complexity > max_complexity:
        issues.append(
            Issue(
                "warning",
                None,
                f"圈复杂度偏高（约 {complexity}）",
                "拆分条件分支、抽取函数或使用早返回，降低单函数复杂度。",
                "复杂度",
            )
        )
    for idx, raw in enumerate(lines, start=1):
        indent = len(raw) - len(raw.lstrip(" "))
        if raw.strip().startswith(("for ", "while ", "if ")) and indent >= 16:
            issues.append(
                Issue("info", idx, "嵌套层级过深", "深层嵌套建议抽取函数或使用早返回（guard clause）。", "可读性")
            )
            break
    return issues


def _improve_code(code: str) -> str:
    """基于启发式生成「改进后代码」：修复常见可机械修正的问题。"""
    improved = code
    improved = re.sub(r"(==|!=)\s*None", lambda m: "is None" if m.group(1) == "==" else "is not None", improved)
    improved = re.sub(r"except\s*:\s*", "except Exception:  # 建议收窄为具体异常\n", improved)
    improved = re.sub(
        r"def\s+(\w+)\s*\(([^)]*)=\s*\[\]\s*\)",
        r"def \1(\2=None):\n    if \2 is None:\n        \2 = []",
        improved,
    )
    return improved if improved != code else ""


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------


def review_code(code: str) -> ReviewResult:
    """对一段代码执行离线静态审查。

    Args:
        code: 待审查源码。

    Returns:
        `ReviewResult`（含问题列表、评分、改进代码）。
    """
    source = code or ""
    lines = source.splitlines()
    issues: list[Issue] = []
    issues += _check_method_mutable_default(lines)
    issues += _check_bare_except(lines)
    issues += _check_none_comparison(lines)
    issues += _check_range_len(lines)
    issues += _check_str_concat(lines)
    issues += _check_unused_imports(source, lines)
    issues += _check_naming(lines)
    issues += _check_long_lines(lines)
    issues += _check_duplicate_blocks(lines)
    issues += _check_complexity(source, lines)

    # 语法可解析性检查（正确性维度）
    syntax_issue = _syntax_check(source)
    if syntax_issue:
        issues.insert(0, syntax_issue)

    severity_weight = {"error": 12, "warning": 6, "info": 2}
    penalty = sum(severity_weight.get(issue.severity, 2) for issue in issues)
    result = ReviewResult(
        score=max(0, 100 - penalty),
        issues=issues,
        improved_code=_improve_code(source),
    )
    result.dimensions = _dimension_summary(issues)
    result.summary_md = _build_summary(result)
    return result


def _syntax_check(source: str) -> Issue | None:
    """正确性维度：能否通过 AST 解析。"""
    if not source.strip():
        return None
    try:
        ast.parse(source)
    except SyntaxError as exc:
        return Issue("error", exc.lineno, f"语法错误：{exc.msg}", "按报错提示修正语法（括号/引号/冒号/缩进）。", "正确性")
    return None


def _dimension_summary(issues: list[Issue]) -> dict[str, str]:
    """按九维度汇总「通过/问题数」。"""
    from app.services.ai.prompts import REVIEW_DIMENSIONS

    summary: dict[str, str] = {}
    for dimension in REVIEW_DIMENSIONS:
        count = sum(1 for issue in issues if issue.dimension == dimension)
        summary[dimension] = "通过" if count == 0 else f"{count} 项待改进"
    return summary


def _build_summary(result: ReviewResult) -> str:
    """生成总体分析 Markdown。"""
    lines = [f"离线静态审查完成，综合评分 **{result.score}/100**。"]
    if not result.issues:
        lines.append("未发现明显问题，代码整体符合基本规范。")
        return "\n".join(lines)
    counts: dict[str, int] = {}
    for issue in result.issues:
        counts[issue.severity] = counts.get(issue.severity, 0) + 1
    lines.append(
        "共发现 "
        + "、".join(f"{counts.get(sev, 0)} 个{sev}" for sev in ("error", "warning", "info"))
        + " 问题，建议优先修复 error 级别。"
    )
    return "\n".join(lines)


# 兼容别名：便于 RuleBasedProvider 直接调用
def analyze(code: str) -> ReviewResult:
    """`review_code` 的别名。"""
    return review_code(code)


__all__ = ["Issue", "ReviewResult", "analyze", "review_code"]
