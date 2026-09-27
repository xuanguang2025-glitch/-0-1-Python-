"""离线错误分析引擎（RuleBasedProvider 的错误分析后端）。

能力：
- 从报错文本 / traceback 中识别异常类型、文件与行号；
- 映射到知识点，输出「错误位置 → 错误原因 → 涉及知识点 → 修改方法 → 类似案例」。

覆盖异常（≥12）：SyntaxError / IndentationError / NameError / TypeError /
ValueError / IndexError / KeyError / AttributeError / ZeroDivisionError /
RecursionError / ImportError / FileNotFoundError。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# 匹配 traceback 中的帧信息：File "xxx.py", line 12, in func
_FRAME_RE: re.Pattern[str] = re.compile(r'File "(?P<file>[^"]+)", line (?P<line>\d+)(?:, in (?P<func>\S+))?')
# 匹配异常类型：最后一行的 `NameError: ...`
_EXC_RE: re.Pattern[str] = re.compile(r"(?P<type>[A-Za-z_][A-Za-z0-9_]*(?:Error|Exception|Interrupt|Exit))(?::\s*(?P<msg>.*))?")


@dataclass(slots=True)
class ExceptionKnowledge:
    """单个异常的领域知识。"""

    topic: str
    cause: str
    fixes: list[str]
    example: str


# 知识点 → 详细知识库
KNOWLEDGE: dict[str, ExceptionKnowledge] = {
    "SyntaxError": ExceptionKnowledge(
        topic="语法基础",
        cause="代码不符合 Python 语法规则（缺少括号/引号、误用关键字等）。",
        fixes=[
            "看报错箭头 ^ 指向的位置及**前一行**，多半是括号/引号未闭合。",
            "检查是否漏写英文冒号 `:`（if/for/def/class 行尾）。",
            "确认中英文标点：应为英文 `()` `[]` `{}` `:` `,`。",
        ],
        example="print('hello'   # SyntaxError: '(' was never closed",
    ),
    "IndentationError": ExceptionKnowledge(
        topic="缩进与代码块",
        cause="缩进不一致——混用 Tab 与空格，或冒号后未缩进 / 缩进量错误。",
        fixes=[
            "统一使用 4 个空格，禁止 Tab 与空格混用。",
            "`if/for/while/def/class/try` 行尾冒号后，下一行必须缩进。",
            "检查是否有凭空多出缩进的空行或复制粘贴残留。",
        ],
        example="def f():\nprint('x')  # IndentationError: expected an indented block",
    ),
    "NameError": ExceptionKnowledge(
        topic="变量与作用域",
        cause="使用了尚未定义或拼写错误的变量/函数名。",
        fixes=[
            "核对变量名拼写与大小写（Python 区分大小写）。",
            "确认变量在使用前已赋值，且定义位置在函数作用域内。",
            "函数内若需修改外部变量，用 `global` / `nonlocal` 或改为传参。",
        ],
        example="print(total)  # NameError: name 'total' is not defined",
    ),
    "TypeError": ExceptionKnowledge(
        topic="数据类型与运算",
        cause="对不兼容的类型执行了运算，或函数实参个数/类型不符。",
        fixes=[
            "确认操作数类型一致，必要时用 `int()`/`str()` 显式转换。",
            "检查是否把 `str` 与 `int` 相加；输入来自 `input()` 时默认是字符串。",
            "核对函数调用参数个数与位置是否匹配。",
        ],
        example="print('年龄: ' + 18)  # TypeError: can only concatenate str (not \"int\") to str",
    ),
    "ValueError": ExceptionKnowledge(
        topic="数值转换与校验",
        cause="类型正确但取值不合法（如把非数字字符串转 int）。",
        fixes=[
            "转换前校验内容，或用 `try/except ValueError` 兜底。",
            "用 `str.isdigit()` / 正则判断输入，再 `int()`。",
            "注意空字符串、带空格或小数点的输入。",
        ],
        example="n = int('abc')  # ValueError: invalid literal for int() with base 10: 'abc'",
    ),
    "IndexError": ExceptionKnowledge(
        topic="列表与索引",
        cause="下标超出序列长度（含空列表）。",
        fixes=[
            "用 `len(x)` 校验下标范围，注意索引从 0 开始、最大为 `len(x)-1`。",
            "遍历元素优先用 `for item in x`，需要下标时用 `enumerate(x)`。",
            "考虑空列表边界情况。",
        ],
        example="nums = [1, 2]\nprint(nums[5])  # IndexError: list index out of range",
    ),
    "KeyError": ExceptionKnowledge(
        topic="字典操作",
        cause="访问了字典中不存在的键。",
        fixes=[
            "用 `d.get(key, default)` 代替 `d[key]`。",
            "先用 `if key in d:` 判断，或用 `d.setdefault(key, [])`。",
            "检查键的拼写与数据类型（`'1'` 与 `1` 不同）。",
        ],
        example="cfg = {'a': 1}\nprint(cfg['b'])  # KeyError: 'b'",
    ),
    "AttributeError": ExceptionKnowledge(
        topic="对象与属性",
        cause="对象没有该属性/方法，或对象是 None。",
        fixes=[
            "用 `dir(obj)` / `type(obj)` 查看真实可用的属性。",
            "检查方法名拼写，如 `append` 不是 `push`。",
            "确认对象非 None（继续向下取属性前先判空）。",
        ],
        example="s = None\nprint(s.upper())  # AttributeError: 'NoneType' object has no attribute 'upper'",
    ),
    "ZeroDivisionError": ExceptionKnowledge(
        topic="算术运算",
        cause="除数为 0。",
        fixes=[
            "运算前检查除数非 0，或用 `try/except ZeroDivisionError`。",
            "对平均数等场景先判断样本数是否为空。",
            "注意 `//` 整除与 `%` 取模同样会报此错。",
        ],
        example="print(10 / 0)  # ZeroDivisionError: division by zero",
    ),
    "RecursionError": ExceptionKnowledge(
        topic="递归与基线条件",
        cause="递归缺少终止条件或终止条件不可达，超过最大递归深度。",
        fixes=[
            "检查递归函数是否包含能收敛的 base case。",
            "确认每次递归的参数都在朝 base case 靠近（如 n-1）。",
            "能用循环替代时改用迭代，或适当提高 `sys.setrecursionlimit`（谨慎）。",
        ],
        example="def f(n):\n    return f(n-1)\nf(5)  # RecursionError: maximum recursion depth exceeded",
    ),
    "ImportError": ExceptionKnowledge(
        topic="模块与导入",
        cause="找不到模块，或模块中不存在要导入的名称。",
        fixes=[
            "确认模块已安装（`pip install xxx`）且名称拼写正确。",
            "检查导入路径与文件名是否一致（大小写敏感）。",
            "避免文件名与标准库重名（如自建 `json.py`）。",
        ],
        example="import pandas  # ModuleNotFoundError: No module named 'pandas'",
    ),
    "FileNotFoundError": ExceptionKnowledge(
        topic="文件与路径",
        cause="打开的文件不存在或路径写错（相对路径依赖当前工作目录）。",
        fixes=[
            "用绝对路径，或结合 `os.path.dirname(__file__)` 定位脚本目录。",
            "打开前用 `os.path.exists(path)` 判断存在性。",
            "注意转义：Windows 路径用 `r'C:\\dir\\f.txt'` 或正斜杠。",
        ],
        example="open('data.txt')  # FileNotFoundError: [Errno 2] No such file or directory: 'data.txt'",
    ),
}

# 异常别名归一（如 ModuleNotFoundError 归到 ImportError）
_ALIASES: dict[str, str] = {
    "ModuleNotFoundError": "ImportError",
    "TabError": "IndentationError",
    "UnboundLocalError": "NameError",
    "FileExistsError": "FileNotFoundError",
}


@dataclass(slots=True)
class ErrorAnalysis:
    """结构化错误分析结果（与 `schemas.ai.ErrorAnalysisOut` 对齐）。"""

    error_type: str = "runtime"
    cause: str = ""
    location: str | None = None
    fix_steps: list[str] = field(default_factory=list)
    minimal_example: str | None = None
    related_topics: list[str] = field(default_factory=list)
    matched: bool = False
    line: int | None = None

    def as_dict(self) -> dict[str, Any]:
        """序列化为 `ErrorAnalysisOut` 兼容字典。"""
        return {
            "error_type": self.error_type,
            "cause": self.cause,
            "location": self.location,
            "fix_steps": list(self.fix_steps),
            "minimal_example": self.minimal_example,
            "related_topics": list(self.related_topics),
            "degraded": True,
        }

    def to_markdown(self) -> str:
        """渲染为中文 Markdown（人类可读）。"""
        lines = [
            f"### 错误分析：{self.error_type}",
            f"- **错误位置**：{self.location or '未在 traceback 中定位到具体行'}",
            f"- **错误原因**：{self.cause or '根据报错信息未能精确归类，请补充完整 traceback。'}",
            "- **涉及知识点**：" + ("、".join(self.related_topics) or "—"),
            "- **修改方法**：",
        ]
        for idx, step in enumerate(self.fix_steps or ["对照报错逐行检查变量名与类型。"], start=1):
            lines.append(f"  {idx}. {step}")
        if self.minimal_example:
            lines.append("")
            lines.append("类似案例（最小复现）：")
            lines.append("```python")
            lines.append(self.minimal_example)
            lines.append("```")
        return "\n".join(lines)


def _extract_frames(traceback_text: str) -> list[tuple[str, int]]:
    """从 traceback 中提取所有 `(文件, 行号)` 帧。"""
    return [(m.group("file"), int(m.group("line"))) for m in _FRAME_RE.finditer(traceback_text or "")]


def detect_exception(text: str) -> tuple[str, str]:
    """从报错文本中识别异常类型与消息。

    Args:
        text: 报错信息或 traceback。

    Returns:
        `(异常类名, 消息)`；识别不到时返回 `("runtime", 原文摘要)`。
    """
    raw = text or ""
    # 优先取最后一个匹配（traceback 末尾通常是最外层异常）
    matches = list(_EXC_RE.finditer(raw))
    if matches:
        last = matches[-1]
        exc_type = last.group("type")
        message = (last.group("msg") or "").strip()
        return exc_type, message
    return "runtime", raw.strip()[:200]


def normalize_type(exc_type: str) -> str:
    """把异常别名归一为标准类型名。"""
    return _ALIASES.get(exc_type, exc_type)


def locate_line(traceback_text: str) -> tuple[str | None, int | None]:
    """定位报错的文件与行号（取用户代码中最后一帧）。

    Args:
        traceback_text: 完整 traceback。

    Returns:
        `(位置描述, 行号)`；无法定位时均为 None。
    """
    frames = _extract_frames(traceback_text)
    if not frames:
        return None, None
    # 过滤掉标准库/框架帧，优先展示最近的一个业务文件帧
    for file_path, line_no in reversed(frames):
        if "site-packages" not in file_path and "lib/python" not in file_path:
            return f"{file_path}:{line_no}", line_no
    file_path, line_no = frames[-1]
    return f"{file_path}:{line_no}", line_no


def analyze_error(
    code: str,
    error_message: str,
    traceback_text: str | None = None,
) -> ErrorAnalysis:
    """离线分析一段报错，返回结构化结果。

    Args:
        code: 出错的代码（可空）。
        error_message: 报错信息（必填）。
        traceback_text: 完整 traceback（可选，用于定位行号）。

    Returns:
        `ErrorAnalysis`。
    """
    combined = "\n".join(part for part in (error_message, traceback_text) if part)
    exc_type, message = detect_exception(combined)
    normalized = normalize_type(exc_type)
    location, line = locate_line(traceback_text or "")

    analysis = ErrorAnalysis(
        error_type=normalized,
        location=location,
        line=line,
    )
    knowledge = KNOWLEDGE.get(normalized)
    if knowledge is None:
        analysis.cause = (
            f"识别到异常 `{exc_type}`（{message or '无附加信息'}）。"
            "未能匹配内置知识库，请结合报错位置逐行检查。"
        )
        analysis.fix_steps = ["阅读报错最后一行的异常信息。", "定位到该行，检查变量类型与取值是否如预期。"]
        analysis.related_topics = ["调试方法"]
        return analysis

    analysis.matched = True
    analysis.cause = knowledge.cause
    analysis.fix_steps = list(knowledge.fixes)
    analysis.minimal_example = knowledge.example
    analysis.related_topics = [knowledge.topic, normalized]
    # 若能在代码中定位到行，补充上下文说明
    if line and code:
        source_lines = code.splitlines()
        if 1 <= line <= len(source_lines):
            snippet = source_lines[line - 1].strip()
            analysis.location = f"{location} → 源码：{snippet}"
    if message:
        analysis.cause = f"{analysis.cause}（报错信息：{message}）"
    return analysis


def format_exception_markdown(analysis: ErrorAnalysis) -> str:
    """把错误分析渲染为 Markdown（供 RuleBasedProvider 纯文本输出）。"""
    return analysis.to_markdown()


__all__ = [
    "KNOWLEDGE",
    "ErrorAnalysis",
    "ExceptionKnowledge",
    "analyze_error",
    "detect_exception",
    "format_exception_markdown",
    "locate_line",
    "normalize_type",
]
