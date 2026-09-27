"""离线规则引擎测试：≥12 种异常的真实 traceback 输入 → 行号与知识点提取（全离线）。"""

from __future__ import annotations

import asyncio
import json

from app.services.ai.base import ChatMessage
from app.services.ai.error_analysis import analyze_error, detect_exception, locate_line
from app.services.ai.rule_based import RuleBasedProvider

# (期望异常类型, traceback, 期望行号, 报错行)
TRACEBACK_CASES: list[tuple[str, str, int, str]] = [
    (
        "SyntaxError",
        '  File "main.py", line 1\n    print(\'hello\'\n         ^\nSyntaxError: \'(\' was never closed',
        1,
        "SyntaxError: '(' was never closed",
    ),
    (
        "IndentationError",
        '  File "main.py", line 2\n    print("x")\n    ^\nIndentationError: unexpected indent',
        2,
        "IndentationError: unexpected indent",
    ),
    (
        "NameError",
        'Traceback (most recent call last):\n  File "main.py", line 3, in <module>\n    print(total)\nNameError: name \'total\' is not defined',
        3,
        "NameError: name 'total' is not defined",
    ),
    (
        "TypeError",
        'Traceback (most recent call last):\n  File "main.py", line 2, in <module>\n    print("age: " + 18)\nTypeError: can only concatenate str (not "int") to str',
        2,
        'TypeError: can only concatenate str (not "int") to str',
    ),
    (
        "ValueError",
        'Traceback (most recent call last):\n  File "main.py", line 1, in <module>\n    n = int("abc")\nValueError: invalid literal for int() with base 10: \'abc\'',
        1,
        "ValueError: invalid literal for int() with base 10: 'abc'",
    ),
    (
        "IndexError",
        'Traceback (most recent call last):\n  File "main.py", line 5, in <module>\n    print(nums[5])\nIndexError: list index out of range',
        5,
        "IndexError: list index out of range",
    ),
    (
        "KeyError",
        'Traceback (most recent call last):\n  File "main.py", line 2, in <module>\n    print(cfg["b"])\nKeyError: \'b\'',
        2,
        "KeyError: 'b'",
    ),
    (
        "AttributeError",
        'Traceback (most recent call last):\n  File "main.py", line 4, in <module>\n    s.upper()\nAttributeError: \'NoneType\' object has no attribute \'upper\'',
        4,
        "AttributeError: 'NoneType' object has no attribute 'upper'",
    ),
    (
        "ZeroDivisionError",
        'Traceback (most recent call last):\n  File "main.py", line 1, in <module>\n    print(10 / 0)\nZeroDivisionError: division by zero',
        1,
        "ZeroDivisionError: division by zero",
    ),
    (
        "RecursionError",
        'Traceback (most recent call last):\n  File "main.py", line 2, in f\n    return f(n - 1)\nRecursionError: maximum recursion depth exceeded',
        2,
        "RecursionError: maximum recursion depth exceeded",
    ),
    (
        "ImportError",  # ModuleNotFoundError 归一化为 ImportError
        'Traceback (most recent call last):\n  File "main.py", line 1, in <module>\n    import pandas\nModuleNotFoundError: No module named \'pandas\'',
        1,
        "ModuleNotFoundError: No module named 'pandas'",
    ),
    (
        "FileNotFoundError",
        'Traceback (most recent call last):\n  File "main.py", line 1, in <module>\n    open("data.txt")\nFileNotFoundError: [Errno 2] No such file or directory: \'data.txt\'',
        1,
        "FileNotFoundError: [Errno 2] No such file or directory: 'data.txt'",
    ),
]


def test_exception_cases_extract_type_and_location() -> None:
    """12 种异常均能识别类型、定位行号并映射知识点。"""
    rows: list[str] = []
    for expected_type, traceback_text, expected_line, error_line in TRACEBACK_CASES:
        analysis = analyze_error("", error_line, traceback_text)
        assert analysis.error_type == expected_type, (expected_type, analysis.error_type)
        assert analysis.matched is True, expected_type
        assert analysis.location == f"main.py:{expected_line}", analysis.location
        assert analysis.fix_steps, expected_type
        assert analysis.related_topics, expected_type
        assert analysis.minimal_example, expected_type
        rows.append(
            f"| {expected_type} | main.py:{expected_line} | {analysis.related_topics[0]} | {analysis.fix_steps[0][:24]}... |"
        )
    print("\n异常处理对照表：\n| 异常 | 定位 | 知识点 | 首条修改建议 |\n|---|---|---|---|")
    print("\n".join(rows))


def test_detect_exception_and_locate_line() -> None:
    """底层解析函数行为正确。"""
    assert detect_exception("ValueError: bad value")[0] == "ValueError"
    location, line = locate_line('  File "app.py", line 7, in run\n    boom()')
    assert location == "app.py:7"
    assert line == 7


def test_rule_based_error_task_json() -> None:
    """RuleBasedProvider 的 error 任务在 json_mode 下返回可解析 JSON。"""
    provider = RuleBasedProvider()
    messages = [ChatMessage(role="user", content="IndexError: list index out of range")]
    response = asyncio.run(
        provider.chat(
            messages,
            task="error",
            json_mode=True,
            error_message="IndexError: list index out of range",
            traceback='Traceback (most recent call last):\n  File "main.py", line 5, in <module>\n    print(nums[5])\nIndexError: list index out of range',
        )
    )
    assert response.degraded is True
    data = json.loads(response.content)
    assert data["error_type"] == "IndexError"
    assert data["location"] == "main.py:5"
    assert data["related_topics"]


def test_rule_based_error_task_markdown() -> None:
    """非 JSON 模式下输出中文 Markdown，含「修改方法」。"""
    provider = RuleBasedProvider()
    response = asyncio.run(
        provider.chat(
            [ChatMessage(role="user", content="KeyError: 'b'")],
            task="error",
            error_message="KeyError: 'b'",
        )
    )
    assert "修改方法" in response.content
    assert "KeyError" in response.content
