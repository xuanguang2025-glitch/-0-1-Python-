# 阶段 1 · Python 入门

## install-python

### 理论

Python 是解释型、动态类型的通用编程语言。代码由解释器逐行翻译执行，因此改完即可运行、无需编译。安装时请勾选 **Add Python to PATH**，这样终端里才能直接使用 `python` 命令。开发环境推荐 VS Code + Python 扩展：它能提供补全、跳转与调试能力。

### 代码

```bash
# 验证安装是否成功（Windows 用 python，macOS/Linux 多为 python3）
python --version      # 例如 Python 3.13.5
python -m pip --version
python -m pip list    # 查看已安装的第三方库
```

```python
# 进入交互式解释器（REPL）后可以直接算数，输入 exit() 退出
>>> 2 + 3 * 4
14
```

### 示例

新建 `hello.py`，内容为一行 `print("Hello, Python!")`，在终端执行：

```bash
python hello.py
# 输出：Hello, Python!
```

### 练习

1. 安装 Python 3.11 以上版本，并在终端执行 `python --version` 贴出结果。
2. 用交互式解释器计算 `(12 + 8) / 5` 与 `2 ** 10`，说出结果类型。
3. 用 `pip list` 查看已安装库数量，尝试安装 `rich` 并再次查看。

### 注意事项

- Windows 上若提示「python 不是内部或外部命令」，说明安装时未勾选 PATH，重新安装勾选即可。
- 一台机器可以装多个 Python 版本，用虚拟环境隔离可避免依赖冲突（阶段 5 详讲）。
- 文件名不要用 `1.py`、`test.py` 这类名字，可能与标准库模块重名导致导入异常。

### 常见错误

- `python: command not found` → PATH 未配置 → 重新安装并勾选 Add to PATH，或使用绝对路径调用。
- `SyntaxError: invalid syntax` 出现在文件而不是 REPL → 多半是复制了带 `>>>` 提示符的行，删掉提示符即可。
- 保存成 `hello.py.txt` → 编辑器默认加了扩展名 → 开启「显示文件扩展名」后重命名。

## first-program

### 理论

`print()` 是内置函数，把对象转换为字符串后输出到标准输出。它可以接收多个参数（默认用空格分隔），也可通过 `sep`、`end` 控制分隔符与结尾字符。

### 代码

```python
print("Hello, World!")
print("Python", "LAB", sep="-", end="!\n")
print(1, 2, 3, sep=", ")
```

### 示例

```python
name = "小徐"
print(f"欢迎来到 PYTHON LAB，{name}！")
print("第一行", end="")
print("接在第一行后面")
```

输出：

```
Hello, World!
Python-LAB!
1, 2, 3
欢迎来到 PYTHON LAB，小徐！
第一行接在第一行后面
```

### 练习

1. 输出你的姓名、年龄与城市，一行一个。
2. 用 `sep` 与 `end` 输出形如 `2026-09-26` 的日期。
3. 只用一条 `print` 输出三行内容。

### 注意事项

- `print` 输出的是「给人看」的文本，调试用可以；正式项目建议用 `logging`。
- 字符串必须配对引号，单双引号都可，嵌套时注意不要冲突。

### 常见错误

- `NameError: name 'Hello' is not defined` → 忘了给文本加引号。
- `SyntaxError: EOL while scanning string literal` → 引号没有闭合。
- 输出多了空行 → `print` 默认结尾是 `\n`，又手工写了 `\n` 就会多一行。

## variables-basics

### 理论

变量是指向对象的**名字**，Python 变量没有类型，类型属于对象。赋值语句把名字绑定到对象上；同一个名字可以先后指向不同类型的对象，这就是「动态类型」。命名规则：字母或下划线开头，只能含字母、数字、下划线，区分大小写，不能用关键字。

### 代码

```python
count = 3            # int
price = 19.9         # float
title = "Python 入门"  # str
is_ready = True      # bool

a = b = 0            # 链式赋值
x, y = 1, 2          # 解包赋值
x, y = y, x          # 交换，无需临时变量
```

### 示例

```python
name = "小徐"
score = 92
level = "优秀" if score >= 90 else "良好"
print(f"{name} 的成绩是 {score}，等级 {level}")
# 小徐 的成绩是 92，等级 优秀
```

### 练习

1. 定义三个变量分别保存书名、单价、数量，计算总价并打印。
2. 用一行代码交换两个变量的值。
3. 故意写一个不合法的变量名（如 `2name`），观察报错信息并解释原因。

### 注意事项

- 变量名用小写 + 下划线（`snake_case`），常量用全大写。
- 不要用 `l`、`O`、`I` 这类与数字易混的单字符名。
- 变量在使用前必须赋值，否则是 `NameError` 而不是「空值」。

### 常见错误

- `SyntaxError: invalid syntax` 出现在 `2name = 1` → 变量名以数字开头。
- `NameError: name 'score' is not defined` → 变量未定义或拼写错误（Python 区分大小写）。
- `TypeError: can only concatenate str (not "int") to str` → 字符串与数字直接相加，需先 `str()` 转换或用 f-string。

## data-types-intro

### 理论

四种最常用的内置类型：`int`（任意精度整数）、`float`（双精度浮点）、`str`（不可变文本序列）、`bool`（只有 `True`/`False`）。此外还有 `NoneType`（表示「无值」）。用 `type()` 可以随时查看对象的类型。

### 代码

```python
print(type(10))        # <class 'int'>
print(type(3.14))      # <class 'float'>
print(type("hi"))      # <class 'str'>
print(type(True))      # <class 'bool'>
print(type(None))      # <class 'NoneType'>

big = 10 ** 100        # Python 整数无溢出
print(0.1 + 0.2)       # 0.30000000000000004
```

### 示例

```python
quantity = 3
unit_price = 9.9
total = quantity * unit_price
print(f"数量 {quantity}（{type(quantity).__name__}），总价 {total:.2f}")
# 数量 3（int），总价 29.70
```

### 练习

1. 打印 `True + True` 与 `True * 5`，解释结果。
2. 判断 `7 / 2`、`7 // 2`、`7 % 2` 的结果与类型。
3. 用 `type()` 验证 `len("abc")` 的返回类型。

### 注意事项

- 浮点数存在精度误差，涉及金额时用 `decimal.Decimal` 或换算成整数分。
- `bool` 是 `int` 的子类，可以参与算术运算。
- `None` 表示「没有值」，`None == 0` 为 `False`，判断应使用 `is None`。

### 常见错误

- 误以为整数会溢出 → Python 整数自动扩展，不会溢出，但超大整数运算会变慢。
- `TypeError: unsupported operand type(s) for +: 'int' and 'str'` → 未做类型转换。
- 用 `==` 判断 `None` → 语义上应使用 `is` / `is not`。

## type-conversion

### 理论

显式转换由内置构造函数完成：`int()`、`float()`、`str()`、`bool()`。隐式转换只发生在数值之间（如 `int + float → float`）。字符串转数字时必须是合法字面量，否则抛 `ValueError`。

### 代码

```python
print(int("42"))       # 42
print(float("3.14"))   # 3.14
print(str(42) + "b")   # 42b
print(bool(""))        # False
print(bool("0"))       # True（非空字符串都为 True）
print(int(3.99))       # 3（向零截断，不是四舍五入）
```

### 示例

```python
raw = " 128 "
try:
    number = int(raw.strip())
    print(f"解析成功：{number}，加 1 得 {number + 1}")
except ValueError:
    print("输入不是合法整数")
# 解析成功：128，加 1 得 129
```

### 练习

1. 把用户输入的字符串 `"19.5"` 转成浮点并保留一位小数输出。
2. 分别转换 `""`、`"0"`、`"False"`，打印 `bool()` 结果并解释。
3. 写一个安全转换函数，解析失败时返回默认值 0。

### 注意事项

- `int("3.5")` 会报错，需先 `float("3.5")`。
- `bool([])`、`bool({})`、`bool(None)`、`bool(0)` 都是 `False`，其余大多为 `True`。
- 转换前先 `strip()` 去掉空白，避免用户输入带空格导致失败。

### 常见错误

- `ValueError: invalid literal for int() with base 10: '3.5'` → 字符串不是整数格式。
- `ValueError: invalid literal for int() with base 10: ''` → 空字符串无法转数字。
- `TypeError: int() can't convert non-string with explicit base` → 给 `int()` 传了非法类型。

## operators-intro

### 理论

运算符按优先级执行：算术 → 比较 → `not` → `and` → `or`。常见算术运算符：`+ - * / // % **`；比较运算符返回布尔值。赋值类运算符（`+=`、`-=`）是语法糖。括号可以改变优先级，`()` 是最有效的可读性工具。

### 代码

```python
print(7 / 2)     # 3.5  真除法
print(7 // 2)    # 3    向下取整
print(-7 // 2)   # -4   向下取整（不是向零）
print(7 % 3)     # 1
print(2 ** 10)   # 1024
print(3 > 2 and 1 < 2)  # True
print(1 == 1.0)  # True（值相等）
```

### 示例

```python
seconds = 3725
hours, remainder = divmod(seconds, 3600)
minutes, secs = divmod(remainder, 60)
print(f"{hours} 小时 {minutes} 分 {secs} 秒")
# 1 小时 2 分 5 秒
```

### 练习

1. 给定秒数，输出「x 天 y 小时 z 分」。
2. 判断一个整数是否为偶数、是否为 3 的倍数。
3. 计算 2 的 20 次方并说明与 `1 << 20` 的关系。

### 注意事项

- `//` 是向下取整（`floor`），负数结果与直觉不同；取余结果的符号跟除数一致。
- 浮点比较不要直接用 `==`，应判断差值是否小于极小值。
- `a += 1` 与 `a = a + 1` 等价，但对可变对象可能语义不同。

### 常见错误

- `ZeroDivisionError: division by zero` → 除数或模数为 0。
- 把 `=` 当成比较写进条件 → `SyntaxError`，比较应用 `==`。
- `TypeError: unsupported operand type(s) for **` → 指数运算用于不支持的类型（如对字符串做乘方）。

## input-output

### 理论

`input(prompt)` 从标准输入读一行，**返回值恒为字符串**，需要数字时必须自行转换。`print()` 支持 `sep`、`end`、`file` 等参数；格式化输出推荐 f-string。

### 代码

```python
name = input("请输入姓名：")
age = int(input("请输入年龄："))     # 必须转换
print(f"{name} 明年 {age + 1} 岁")
```

```python
# 读取一行空格分隔的多个整数
values = list(map(int, input().split()))
print(sum(values))
```

### 示例

```python
# 输入：3 5
a, b = map(int, input().split())
print(f"和={a + b} 差={a - b} 积={a * b}")
# 和=8 差=-2 积=15
```

### 练习

1. 读取三个浮点数并输出平均值（保留两位小数）。
2. 读取一行若干整数，输出最大值、最小值与平均值。
3. 模拟收银：输入单价与数量，输出总价并四舍五入到分。

### 注意事项

- 一律把 `input()` 的结果当成字符串处理，不要假设它已转换。
- `input()` 会去掉行尾换行符，但保留行首尾其它空白。
- 判题系统通常用标准输入喂数据，因此不要打印任何多余提示语到 stdout。

### 常见错误

- `ValueError: invalid literal for int()` → 用户输入了非数字或多输出了空格以外内容。
- 把提示语和答案写在同一行 → 判题按行比对会失败。
- `EOFError: EOF when reading a line` → 输入已结束却还在读，说明读的行数多于数据行数。

## comments-docstring

### 理论

`#` 开头的注释到行尾结束，用于解释「为什么」。三引号字符串放在模块、函数、类的第一句时是**文档字符串**（docstring），可被 `help()` 与工具读取。优质注释解释意图与约束，而不是复述代码。

### 代码

```python
"""模块级文档字符串：说明本模块职责。"""


def area(width: float, height: float) -> float:
    """计算矩形面积。

    Args:
        width: 宽度，必须为非负数。
        height: 高度，必须为非负数。

    Returns:
        面积 = 宽 × 高。
    """
    # 负尺寸没有业务意义，直接拒绝比返回错误结果更安全
    if width < 0 or height < 0:
        raise ValueError("尺寸不能为负数")
    return width * height
```

### 示例

```python
print(area.__doc__.splitlines()[0])  # 计算矩形面积。
print(area(3, 4))                    # 12
help(area)                           # 打印完整文档
```

### 练习

1. 为一个「判断闰年」的函数写完整 docstring（含 Args/Returns）。
2. 找出你写过的代码里最需要注释的三处并补上说明理由的注释。
3. 用 `help()` 查看 `str.split` 的文档并总结参数含义。

### 注意事项

- 注释要与代码同步更新，过期注释比没有注释更危险。
- 不要用注释掉大段代码代替版本控制，用 Git。
- 行内注释至少空两格再写 `#`。

### 常见错误

- docstring 写在函数体内部但不在第一行 → 不会被识别为文档。
- 中英文混排未加空格 → 可读性差，建议中英文之间留空格。
- 用 `'''` 与 `"""` 混用导致缩进错乱 → 统一使用 `"""`。

## pep8-style

### 理论

PEP 8 是 Python 官方风格指南：4 空格缩进、行长 ≤ 79/99、`snake_case` 命名函数与变量、`PascalCase` 命名类、常量全大写、导入分三段（标准库 / 第三方 / 本地）。统一风格能让代码评审聚焦逻辑而非格式。

### 代码

```python
# 导入：标准库 → 第三方 → 本地，各自成组
import json
import os
from datetime import datetime

import requests

from app.utils import slugify

MAX_RETRY = 3                     # 常量全大写
DEFAULT_TIMEOUT = 30


class PageLoader:
    """按页抓取数据。"""

    def fetch_page(self, page_no: int) -> dict:
        """抓取指定页并返回解析后的字典。"""
        return {"page": page_no}
```

### 示例

```bash
# 自动格式化与检查（需先安装）
python -m pip install ruff
ruff check .
ruff format .
```

### 练习

1. 用 `ruff` 或 `flake8` 检查你写过的任意一个文件，修掉全部告警。
2. 把一段超过 100 行的紧凑代码按 PEP 8 重排（加空行、改命名）。
3. 写一份 5 条的团队编码约定（命名 / 注释 / 导入 / 行长 / docstring）。

### 注意事项

- 保持 4 空格缩进，不要用 Tab 混排。
- 二元运算符两侧留空，但函数默认值的 `=` 两侧不留空。
- 顶层定义之间空 2 行，类内方法之间空 1 行。

### 常见错误

- `TabError: inconsistent use of tabs and spaces in indentation` → 缩进混用。
- `IndentationError: expected an indented block` → 忘记缩进函数体。
- 导入顺序混乱导致循环依赖 → 按三段分组并放到文件顶部。
