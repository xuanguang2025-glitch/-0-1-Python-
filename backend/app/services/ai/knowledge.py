"""离线知识模板库（RuleBasedProvider 的学习建议 / 练习生成后端）。

无模型时仍能提供有价值的产出：
- 学习计划生成（按目标与周期）；
- 练习题生成（按知识点模板，含参考答案与解析）；
- 单元测试生成（pytest 模板）；
- 代码解释 / 优化 / 重构建议；
- 通用 Python 问题答疑（关键词命中知识点）。

所有模板均为纯字符串拼接，无外部依赖，保证离线可用。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# 知识点 → 练习模板（题干 / 参考答案 / 解析）
PRACTICE_TEMPLATES: dict[str, dict[str, str]] = {
    "变量与数据类型": {
        "prompt": "定义三个变量分别保存你的姓名（字符串）、年龄（整数）、身高（浮点数），并格式化输出。",
        "answer": "name = '小明'\nage = 18\nheight = 1.75\nprint(f'{name} {age} 岁，身高 {height} 米')",
        "explain": "f-string 是推荐的字符串格式化方式，可读性优于 `%` 与 `+` 拼接。",
    },
    "列表与元组": {
        "prompt": "给定 `nums = [3, 1, 4, 1, 5]`，输出去重后升序排列的列表。",
        "answer": "print(sorted(set(nums)))",
        "explain": "`set` 去重（无序），`sorted` 返回新的有序列表，原列表不变。",
    },
    "字典与集合": {
        "prompt": "统计字符串 `'banana'` 中每个字符出现的次数。",
        "answer": "from collections import Counter\nprint(Counter('banana'))",
        "explain": "`collections.Counter` 是计数场景的标准工具，避免手写循环。",
    },
    "循环与迭代": {
        "prompt": "用 `for` 循环打印 1 到 10 的平方。",
        "answer": "for i in range(1, 11):\n    print(i * i)",
        "explain": "`range(1, 11)` 左闭右开，产生 1..10。",
    },
    "函数": {
        "prompt": "编写函数 `is_prime(n)` 判断 n 是否为素数。",
        "answer": "def is_prime(n):\n    if n < 2:\n        return False\n    for i in range(2, int(n ** 0.5) + 1):\n        if n % i == 0:\n            return False\n    return True",
        "explain": "只需试除到 √n；注意 n<2 的边界。",
    },
    "异常处理": {
        "prompt": "把字符串安全转换为整数，非法输入返回 None。",
        "answer": "def to_int(s):\n    try:\n        return int(s)\n    except ValueError:\n        return None",
        "explain": "捕获具体异常 `ValueError` 优于裸 `except`。",
    },
    "文件与路径": {
        "prompt": "读取 `data.txt` 每一行并去掉行尾换行符。",
        "answer": "with open('data.txt', encoding='utf-8') as f:\n    lines = [line.rstrip('\\n') for line in f]",
        "explain": "`with` 自动关闭文件；显式 `encoding` 避免平台默认编码差异。",
    },
    "面向对象": {
        "prompt": "定义一个 `Rectangle` 类，含宽高属性与 `area()` 方法。",
        "answer": "class Rectangle:\n    def __init__(self, width, height):\n        self.width = width\n        self.height = height\n\n    def area(self):\n        return self.width * self.height",
        "explain": "`__init__` 初始化实例属性，`self` 指向实例本身。",
    },
    "字符串": {
        "prompt": "判断字符串是否为回文（忽略大小写与空格）。",
        "answer": "def is_palindrome(s):\n    t = ''.join(c.lower() for c in s if c.isalnum())\n    return t == t[::-1]",
        "explain": "切片 `[::-1]` 反转字符串；先归一化再比较。",
    },
    "推导式": {
        "prompt": "用列表推导式生成 1..20 中所有偶数的平方。",
        "answer": "print([x * x for x in range(1, 21) if x % 2 == 0])",
        "explain": "推导式 = 表达式 + 循环 + 条件，比显式循环更简洁。",
    },
}

# 关键词 → 知识点答疑模板
QA_TEMPLATES: list[tuple[tuple[str, ...], str]] = [
    (
        ("列表推导", "list comprehension", "推导式"),
        "列表推导式形如 `[表达式 for 变量 in 可迭代 if 条件]`。\n"
        "例：`[x*x for x in range(5) if x % 2 == 0]` → `[0, 4, 16]`。\n"
        "它比 `for` + `append` 更简洁，但嵌套三层以上建议改写为普通循环以保可读性。",
    ),
    (
        ("可变对象", "默认可变", "mutable default"),
        "不要在函数默认参数里使用可变对象（如 `def f(xs=[])`），因为默认值只创建一次，"
        "会被多次调用共享。正确写法：`def f(xs=None): xs = xs or []`。",
    ),
    (
        ("深浅拷贝", "copy", "deepcopy", "浅拷贝"),
        "`copy.copy` 是浅拷贝（只复制外层），`copy.deepcopy` 递归复制嵌套结构。\n"
        "对嵌套列表 `a = [[1], [2]]`，浅拷贝后 `a[0] is b[0]` 仍为 True，需用 deepcopy。",
    ),
    (
        ("生成器", "yield", "generator"),
        "含 `yield` 的函数是生成器，惰性产出、节省内存。\n"
        "例：`def gen(n):\n    for i in range(n):\n        yield i`。适合大数据流式处理。",
    ),
    (
        ("装饰器", "decorator", "@"),
        "装饰器是接收函数并返回新函数的高阶函数，用于增强行为（日志、计时、缓存）。\n"
        "`functools.wraps` 可保留原函数元信息。",
    ),
    (
        ("虚拟环境", "venv", "pip"),
        "用 `python -m venv .venv` 创建隔离环境，激活后 `pip install` 的包只装在该环境。\n"
        "避免污染全局 Python。",
    ),
]


@dataclass(slots=True)
class PlanStep:
    """学习计划中的一天。"""

    day: int
    focus: str
    tasks: list[str]


def generate_practice(topic: str = "", difficulty: str = "easy", count: int = 3) -> str:
    """根据知识点生成练习题（含参考答案与解析）。

    Args:
        topic: 目标知识点（可为空 → 使用通用题库）。
        difficulty: 难度标签（easy/medium/hard）。
        count: 生成题数（clamp 到 1..5）。

    Returns:
        Markdown 文本。
    """
    size = max(1, min(5, int(count or 3)))
    selected: list[tuple[str, dict[str, str]]] = []
    if topic and topic in PRACTICE_TEMPLATES:
        selected.append((topic, PRACTICE_TEMPLATES[topic]))
    for name, tpl in PRACTICE_TEMPLATES.items():
        if len(selected) >= size:
            break
        if name != topic:
            selected.append((name, tpl))

    lines = [f"### 练习（难度：{difficulty}，共 {len(selected)} 题）", ""]
    for idx, (name, tpl) in enumerate(selected, start=1):
        lines.append(f"**第 {idx} 题（{name}）**：{tpl['prompt']}")
        lines.append("")
        lines.append("<details><summary>查看参考答案</summary>")
        lines.append("")
        lines.append("```python")
        lines.append(tpl["answer"])
        lines.append("```")
        lines.append(f"解析：{tpl['explain']}")
        lines.append("</details>")
        lines.append("")
    lines.append("> 先自己动手，再展开答案对照，效果最好。")
    return "\n".join(lines)


def generate_plan(goal: str = "系统掌握 Python", days: int = 7) -> str:
    """生成学习计划。

    Args:
        goal: 学习目标。
        days: 周期天数（clamp 到 3..30）。

    Returns:
        Markdown 学习计划。
    """
    total = max(3, min(30, int(days or 7)))
    phases = [
        "语法基础（变量/类型/运算符/输入输出）",
        "流程控制（条件/循环/推导式）",
        "数据结构（列表/元组/字典/集合）",
        "函数与作用域（参数/返回/闭包）",
        "文件与异常处理",
        "面向对象（类/继承/魔术方法）",
        "标准库精要（os/json/datetime/collections）",
        "综合实战与调试技巧",
    ]
    lines = [f"### {total} 天学习计划：{goal}", ""]
    for day in range(1, total + 1):
        focus = phases[(day - 1) % len(phases)]
        lines.append(f"**第 {day} 天 · {focus}**")
        lines.append(f"- 学习：完成对应课时与示例代码（约 40 分钟）")
        lines.append(f"- 练习：完成 2~3 道相关题目（约 40 分钟）")
        lines.append(f"- 复盘：整理错题与知识点笔记（约 10 分钟）")
        lines.append("")
    lines.append("> 每天建议 90 分钟，坚持比时长更重要。")
    return "\n".join(lines)


def generate_tests(code: str) -> str:
    """基于代码中的函数签名生成 pytest 测试模板。

    Args:
        code: 源码。

    Returns:
        pytest 测试模板（Markdown 代码块）。
    """
    import re

    funcs = re.findall(r"^\s*def\s+([a-zA-Z_]\w*)\s*\(([^)]*)\)", code or "", flags=re.MULTILINE)
    if not funcs:
        return (
            "### 测试建议\n\n未在代码中识别到函数定义。请先提取出可测试的函数，再编写用例：\n\n"
            "```python\nimport pytest\n\ndef test_placeholder():\n    assert True\n```"
        )
    lines = ["### 单元测试模板（pytest）", "", "```python", "import pytest", ""]
    for name, params in funcs:
        arg_names = [p.split("=")[0].strip() for p in params.split(",") if p.strip()]
        args_repr = ", ".join("0" for _ in arg_names)
        lines.append(f"def test_{name}_basic():")
        lines.append(f"    # TODO: 用真实输入替换占位参数")
        lines.append(f"    result = {name}({args_repr})")
        lines.append(f"    assert result is not None")
        lines.append("")
    lines.append("# 建议再补充边界与异常用例：")
    lines.append("def test_edge_case():")
    lines.append("    with pytest.raises(ValueError):")
    lines.append("        raise ValueError('示例')")
    lines.append("```")
    return "\n".join(lines)


def explain_code(code: str) -> str:
    """对代码做逐段解释（含复杂度提示）。"""
    import re

    source = code or ""
    lines = source.count("\n") + 1
    funcs = re.findall(r"def\s+([a-zA-Z_]\w*)", source)
    classes = re.findall(r"class\s+([a-zA-Z_]\w*)", source)
    has_loop = ("for " in source) or ("while " in source)
    nested = source.count("for ") + source.count("while ") > 1
    parts = [
        "### 代码解释",
        f"- 规模：约 {lines} 行。",
    ]
    if classes:
        parts.append(f"- 定义了类：{'、'.join(classes)}。")
    if funcs:
        parts.append(f"- 定义了函数：{'、'.join(funcs)}。")
    parts.append("- 执行流程：按从上到下顺序执行；函数在调用时才运行。")
    if has_loop:
        parts.append("- 含循环结构；若循环体内含循环（嵌套），复杂度可能达到 O(n²)，注意优化。")
    if nested:
        parts.append("- 检测到嵌套循环，建议评估是否可用字典/集合将查找降为 O(1)。")
    parts.append("- 提示：对关键函数补充 docstring 与类型注解可提升可读性。")
    return "\n".join(parts)


def optimize_suggestions(code: str) -> str:
    """给出性能与惯用法优化建议。"""
    source = code or ""
    tips: list[str] = ["### 优化建议"]
    if "range(len(" in source:
        tips.append("- 用 `enumerate()` / `zip()` 替代 `range(len(...))`，更 Pythonic。")
    if "+=" in source and ("for " in source or "while " in source):
        tips.append('- 循环内字符串 `+=` 效率低，改为累积到列表后 `"".join(...)`。')
    if "for " in source and " in " in source and ".append(" in source:
        tips.append("- `for` + `append` 可改写为列表推导式，更简洁且更快。")
    if "== None" in source or "!= None" in source:
        tips.append("- `== None` 改为 `is None`。")
    if len(tips) == 1:
        tips.append("- 未发现明显性能问题；如需进一步优化，请提供带数据的调用场景。")
    tips.append("- 建议用 `cProfile` / `timeit` 实测后再优化，避免过早优化。")
    return "\n".join(tips)


def refactor_suggestions(code: str) -> str:
    """给出重构建议。"""
    source = code or ""
    tips: list[str] = ["### 重构建议"]
    if source.count("\n") > 30:
        tips.append("- 函数/文件较长，按职责拆分为多个小函数，每个函数只做一件事。")
    if "try:" in source and "except:" in source:
        tips.append("- 收窄 `except` 的异常类型，避免掩盖真实错误。")
    if source.count("if ") >= 3:
        tips.append("- 条件分支较多，可用早返回（guard clause）或策略字典降低嵌套。")
    tips.append("- 提取魔法数字/字符串为具名常量，提升可维护性。")
    tips.append("- 为公共函数补充类型注解与 docstring，便于协作与静态检查。")
    return "\n".join(tips)


def answer_question(question: str) -> str:
    """离线答疑：命中关键词则返回知识点讲解，否则给出通用引导。"""
    text = (question or "").lower()
    for keywords, answer in QA_TEMPLATES:
        if any(keyword in text for keyword in keywords):
            return answer
    return (
        "### 离线助手\n\n"
        "当前未配置远程模型，以下为通用引导：\n"
        "1. 先明确你想解决的具体问题（输入、期望输出、实际现象）。\n"
        "2. 贴出最小可复现代码与完整报错信息，便于精确定位。\n"
        "3. 可换个说法再问一次，或直接问我「XX 是什么」「这段代码为什么报错」。"
    )


def as_dict_analysis(result: Any) -> dict[str, Any]:  # pragma: no cover - 占位导出
    """保留扩展位（当前未使用）。"""
    return dict(result or {})


__all__ = [
    "PRACTICE_TEMPLATES",
    "QA_TEMPLATES",
    "PlanStep",
    "answer_question",
    "explain_code",
    "generate_plan",
    "generate_practice",
    "generate_tests",
    "optimize_suggestions",
    "refactor_suggestions",
]
