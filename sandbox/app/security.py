"""执行前源码静态检查（第一层防线）。

只拦截**明确无正当教学用途**的危险调用；`eval/exec` 等由运行时守卫
（`guard.py`）兜底，避免误伤正常课程代码。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Pattern, Tuple

# (规则名, 正则, 提示)
RULES: Tuple[Tuple[str, str, str], ...] = (
    ("subprocess", r"\bsubprocess\b", "禁止导入/调用 subprocess"),
    ("multiprocessing", r"\bmultiprocessing\b", "禁止使用 multiprocessing"),
    ("ctypes", r"\bctypes\b|\bcffi\b", "禁止使用 ctypes/cffi 直接调用系统库"),
    ("pty", r"\bpty\b|\bopenpty\b", "禁止使用伪终端"),
    ("importlib", r"\bimportlib\b|\breload\s*\(", "禁止动态导入与模块重载"),
    ("os.system", r"\bos\s*\.\s*(system|popen|exec\w*|spawn\w*|fork|forkpty|kill)\b", "禁止执行系统命令"),
    ("os.remove", r"\bos\s*\.\s*(remove|unlink|rmdir|removedirs|rename|replace)\s*\(", "禁止删除/重命名文件"),
    ("shutil.rmtree", r"\bshutil\s*\.\s*(rmtree|move)\b", "禁止删除目录树"),
    ("socket", r"\bsocket\s*\.\s*(socket|create_connection|socketpair|create_server)\b", "禁止创建网络连接"),
    ("urlopen", r"\burlopen\b|\brequests\s*\.\s*(get|post)\b|\bhttp\s*\.\s*client\b", "禁止发起 HTTP 请求"),
    ("dunder_import", r"__import__\s*\(", "禁止使用 __import__ 绕过导入白/黑名单"),
    ("breakpoint", r"\bbreakpoint\s*\(\s*\)|\bpdb\s*\.\s*set_trace\b", "禁止进入调试器"),
)

# 必须在**未剥离字符串**的源码上匹配的规则（路径本身就是字符串字面量）
RAW_RULES: Tuple[Tuple[str, str, str], ...] = (
    (
        "sensitive_read",
        r"open\s*\(\s*[rRbBuUfF]{0,2}\s*[\"']\s*"
        r"(/etc/|/proc/|/sys/|/root/|/boot/|/var/|/home/|"
        r"C:\\Windows|C:/Windows|C:\\ProgramData|C:/ProgramData|~/.ssh|~/.aws)",
        "禁止读取系统敏感文件",
    ),
)

_COMPILED: Tuple[Tuple[str, Pattern[str], str], ...] = tuple(
    (name, re.compile(pattern), hint) for name, pattern, hint in RULES
)

_RAW_COMPILED: Tuple[Tuple[str, Pattern[str], str], ...] = tuple(
    (name, re.compile(pattern), hint) for name, pattern, hint in RAW_RULES
)

# 注释/字符串里的同名文本会命中规则，这里做一次轻量剥离以降低误报
_STRING_RE = re.compile(r"(?s)(\"\"\".*?\"\"\"|'''.*?'''|\"[^\"\\n]*\"|'[^'\\n]*')")
_COMMENT_RE = re.compile(r"#[^\n]*")


@dataclass
class ScanResult:
    """静态检查结果。"""

    blocked: bool = False
    rule: str = ""
    hint: str = ""
    file_path: str = ""
    line: int = 0

    def as_message(self) -> str:
        """生成可直接返回给调用方的错误文本。"""
        if not self.blocked:
            return ""
        location = f" ({self.file_path}:{self.line})" if self.file_path else ""
        return f"[security] {self.hint}{location} [rule={self.rule}]"


def _strip_noise(source: str) -> str:
    """去掉字符串字面量与行注释，降低误报。"""
    without_strings = _STRING_RE.sub('""', source)
    return _COMMENT_RE.sub("", without_strings)


def scan_source(source: str) -> ScanResult:
    """扫描单份源码，命中规则则返回 blocked=True。

    顺序：先在**原始源码**上跑路径类规则（路径是字符串字面量，不能剥离），
    再在**剥离字符串与注释**后的文本上跑其余规则以降低误报。
    """
    for name, pattern, hint in _RAW_COMPILED:
        match = pattern.search(source)
        if match:
            line = source.count("\n", 0, match.start()) + 1
            return ScanResult(blocked=True, rule=name, hint=hint, line=line)

    cleaned = _strip_noise(source)
    for name, pattern, hint in _COMPILED:
        match = pattern.search(cleaned)
        if match:
            line = cleaned.count("\n", 0, match.start()) + 1
            return ScanResult(blocked=True, rule=name, hint=hint, line=line)
    return ScanResult()


def scan_files(files: Iterable["object"]) -> ScanResult:
    """扫描文件列表（`FileSpec` 或任意含 path/content 属性的对象）。"""
    for file_spec in files:
        path = str(getattr(file_spec, "path", "main.py"))
        content = str(getattr(file_spec, "content", "") or "")
        result = scan_source(content)
        if result.blocked:
            result.file_path = path
            return result
    return ScanResult()


def scan_text_lines(text: str) -> ScanResult:
    """扫描 stdin/环境变量等无文件名文本。"""
    return scan_source(text)


def rule_names() -> List[str]:
    """返回全部规则名（供 `/limits` 展示）。"""
    return [name for name, _pattern, _hint in RULES]
