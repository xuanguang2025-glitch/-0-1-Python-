# 阶段 2 · 流程控制

## boolean-logic

### 理论

布尔运算 `and`、`or`、`not` 采用**短路求值**：`a and b` 在 `a` 为假时直接返回 `a`，不再计算 `b`；`a or b` 在 `a` 为真时直接返回 `a`。返回值不一定是 `True`/`False`，而是参与运算的**对象本身**，因此常被用作默认值赋值的技巧。

### 代码

```python
print(0 or "默认值")        # 默认值
print("已配置" or "默认值")   # 已配置
print(1 and 2)              # 2
print(None or [] or "兜底")  # 兜底
print(not [])               # True
print(1 < 2 < 3)            # True（链式比较）
```

### 示例

```python
user_input = input("输入年龄：").strip()
age = int(user_input) if user_input else 0
is_adult = age >= 18 and age < 130
print(f"年龄={age} 是否成年={is_adult}")
```

### 练习

1. 用短路特性为函数参数设置默认值。
2. 判断年份是否在 1900–2100 之间，用链式比较一行写完。
3. 解释 `[] and 1` 与 `[] or 1` 的结果并验证。

### 注意事项

- `and` 优先级高于 `or`，复杂条件建议加括号。
- 用 `x is None` 而不是 `not x` 判断「无值」，因为 `0`、`""` 也是假值。
- 短路特性让 `if obj and obj.method()` 成为安全的空值防护写法。

### 常见错误

- 把 `and` 当成「返回布尔值」→ 实际返回操作数本身，可能得到意外类型。
- 用 `not x == y` → 解析为 `not (x == y)` 之外的含义易混，改用 `x != y`。
- `if a == 1 or 2:` → 恒为真，应为 `a in (1, 2)`。

## if-else

### 理论

`if / elif / else` 按顺序判断，命中第一个为真的分支后**不再检查后续分支**。分支体必须缩进，Python 用缩进而非 `{}` 划分代码块。`elif` 是 `else if` 的缩写。

### 代码

```python
score = 87

if score >= 90:
    grade = "A"
elif score >= 80:
    grade = "B"
elif score >= 60:
    grade = "C"
else:
    grade = "D"

print(grade)   # B
```

### 示例

```python
# 商品折扣：满 200 打 8 折，满 100 打 9 折
price = 260
if price >= 200:
    final = price * 0.8
elif price >= 100:
    final = price * 0.9
else:
    final = price
print(f"原价 {price} 实付 {final:.2f}")   # 实付 208.00
```

### 练习

1. 输入月份，输出所属季节（用 `in` 简化条件）。
2. 输入三个数，输出最大值（先不用 `max`）。
3. 实现 BMI 分级：偏瘦 / 正常 / 超重 / 肥胖。

### 注意事项

- 条件顺序会影响结果：更严格的判断要放在前面。
- 能用 `dict` 映射替代的连续 `elif` 建议换成字典查表。
- 不要把 `if` 写成 `if (a > 1):` 之外的复杂嵌套，考虑提前 `return`。

### 常见错误

- `IndentationError: expected an indented block` → 分支体没缩进。
- `SyntaxError: invalid syntax` 在 `else` 前有语句 → `else` 必须与 `if` 对齐且紧邻。
- 条件恒真：`if 1 <= x <= 10 or 100` → 后半段 `100` 恒为真。

## nested-if

### 理论

条件可以嵌套，表示「先满足大前提，再看细分条件」。嵌套超过三层会显著降低可读性，可用「早返回」（guard clause）或把条件合并用 `and` 来扁平化。

### 代码

```python
age = 25
has_ticket = True

if age >= 18:
    if has_ticket:
        print("可以入场")
    else:
        print("请先购票")
else:
    print("未满 18 岁")

# 扁平化：合并条件
if age >= 18 and has_ticket:
    print("可以入场")
```

### 示例

```python
# 三元表达式：一行完成简单分支
score = 75
level = "优秀" if score >= 90 else ("及格" if score >= 60 else "不及格")
print(level)   # 及格
```

### 练习

1. 用嵌套判断实现「登录校验」：账号存在 → 密码正确 → 未锁定。
2. 把上面的嵌套改写成早返回版本。
3. 用三元表达式实现「偶数 / 奇数」判定。

### 注意事项

- 三元表达式只适合简单逻辑，嵌套三层以上应改回 if。
- 条件嵌套深时优先考虑拆分函数。
- `a if cond else b` 的结果类型最好保持一致，便于阅读。

### 常见错误

- 三元表达式写反：`a if b else c` 中 `b` 是条件不是结果。
- 嵌套缩进错误导致逻辑挂在别的分支下。
- 用 `and` 合并条件时遗漏括号，优先级出错。

## while-loop

### 理论

`while condition:` 在条件为真时反复执行循环体。必须保证循环变量最终会使条件为假，否则死循环。`while True + break` 适合「不确定次数」的循环。

### 代码

```python
total = 0
i = 1
while i <= 100:
    total += i
    i += 1
print(total)   # 5050
```

```python
# 猜数字：不确定次数，用 while True + break
import random

target = random.randint(1, 10)
while True:
    guess = int(input("猜一个 1-10 的整数："))
    if guess == target:
        print("猜对了")
        break
    print("偏大" if guess > target else "偏小")
```

### 示例

```python
# 用 while 反转整数
n, reversed_n = 12345, 0
while n > 0:
    n, digit = divmod(n, 10)
    reversed_n = reversed_n * 10 + digit
print(reversed_n)   # 54321
```

### 练习

1. 用 while 计算 n 的阶乘。
2. 用 while 求斐波那契数列前 20 项。
3. 输入若干数字，输入 `0` 时结束并输出总和与平均。

### 注意事项

- 循环体内一定要有让条件趋于假的操作（常见是自增 / 自减）。
- 浮点累加会有误差，计数类循环优先用 `for range`。
- 死循环用 `Ctrl+C` 中断；服务端逻辑务必设置最大重试次数。

### 常见错误

- 忘记 `i += 1` → 死循环。
- 条件写反：`while i >= 0` 且自增 → 立即死循环。
- `while` 条件用了赋值 `=` → `SyntaxError`。

## for-loop

### 理论

`for` 用于遍历**可迭代对象**：字符串、列表、元组、字典、文件、生成器等。`for ch in text` 依次取元素，不需要下标维护，这是 Python 的惯用写法。

### 代码

```python
for ch in "Python":
    print(ch, end="-")        # P-y-t-h-o-n-

for item in [10, 20, 30]:
    print(item * 2, end=" ")  # 20 40 60

# 字典遍历
scores = {"语文": 90, "数学": 95}
for subject, score in scores.items():
    print(f"{subject}: {score}")
```

### 示例

```python
text = "hello world"
vowels = 0
for ch in text:
    if ch in "aeiou":
        vowels += 1
print(f"元音字母数={vowels}")   # 元音字母数=3
```

### 练习

1. 统计一句话中每个字符出现的次数。
2. 遍历列表，只打印偶数。
3. 求列表中所有数字的平方和。

### 注意事项

- 不要在循环中修改正在遍历的列表，先把结果收集到新列表。
- 需要下标时用 `enumerate`，而不是自己维护计数器。
- 遍历字典默认拿到键，需要值用 `.values()`，两者都要用 `.items()`。

### 常见错误

- `RuntimeError: dictionary changed size during iteration` → 遍历字典时增删键。
- 遍历列表时 `remove` 导致漏项 → 改用列表推导式生成新列表。
- `TypeError: 'int' object is not iterable` → 对不可迭代对象使用 for。

## range-enumerate

### 理论

`range(start, stop, step)` 生成惰性整数序列（不含 `stop`）。`enumerate(seq, start=0)` 同时产出下标与元素，是「需要索引的遍历」的标准写法。`zip` 可并行遍历多个序列。

### 代码

```python
print(list(range(5)))            # [0, 1, 2, 3, 4]
print(list(range(2, 10, 3)))     # [2, 5, 8]
print(list(range(5, 0, -1)))     # [5, 4, 3, 2, 1]

names = ["语文", "数学", "英语"]
for index, name in enumerate(names, start=1):
    print(f"{index}. {name}")
# 1. 语文
# 2. 数学
# 3. 英语
```

### 示例

```python
prices = [12, 30, 8]
subtotals = []
for i, price in enumerate(prices):
    subtotals.append((i + 1) * price)
print(subtotals)   # [12, 60, 24]

# zip 并行遍历
for subject, score in zip(names, [88, 92, 79]):
    print(subject, score)
```

### 练习

1. 输出 1–20 的所有偶数。
2. 用 `enumerate` 找出列表中第一个负数及其下标。
3. 用 `zip` 把两个列表合并成 `{科目: 分数}` 字典。

### 注意事项

- `range` 返回的是惰性对象，需要列表要 `list()` 包装。
- `enumerate` 的 `start` 只影响显示，不改动原序列。
- `zip` 以最短序列为准，长出的部分被丢弃。

### 常见错误

- `range(1, 10)` 少遍历了 10 → `stop` 是开区间。
- `for i in range(len(lst))` 后又 `lst[i]` → 可读性差，优先 `enumerate`。
- 用 `zip` 期望保留最长序列 → 要用 `itertools.zip_longest`。

## break-continue

### 理论

`break` 立即结束**当前所在的那一层**循环；`continue` 跳过本轮剩余语句，进入下一轮。二者只影响最近的一层循环，嵌套时需注意作用范围。

### 代码

```python
for n in range(1, 10):
    if n == 5:
        break
    print(n, end=" ")      # 1 2 3 4

print()

for n in range(1, 10):
    if n % 2 == 0:
        continue
    print(n, end=" ")      # 1 3 5 7 9
```

### 示例

```python
# 在列表中找到第一个能被 7 整除的数
numbers = [3, 11, 14, 21, 25]
for n in numbers:
    if n % 7 == 0:
        print(f"找到 {n}")
        break
else:
    print("没有找到")
# 找到 14
```

### 练习

1. 遍历 1–100，跳过所有含数字 7 的数，求和。
2. 逐行读取列表，遇到空字符串停止。
3. 在嵌套循环中跳出外层（提示：用标志变量或封装成函数 `return`）。

### 注意事项

- `break` 不会跳出外层循环，嵌套时容易误解。
- 循环内大量 `continue` 会降低可读性，可考虑提前继续条件判断。
- 与 `for/else` 联用时，`break` 会跳过 `else`。

### 常见错误

- 以为 `break` 能一次跳出多层循环。
- `continue` 写在循环变量自增之前（while 中）导致死循环。
- 用 `break` 替代函数 `return`，逻辑变得难以复用。

## nested-loops

### 理论

嵌套循环常用于二维结构（矩阵、表格、图形）。总执行次数是各层次数之积，因此双层 1000×1000 就是一百万次，性能敏感场景要评估复杂度。

### 代码

```python
# 打印 5 行三角形
for i in range(1, 6):
    print("*" * i)

# 九九乘法表（只打下半三角）
for i in range(1, 10):
    row = [f"{i}×{j}={i * j}" for j in range(1, i + 1)]
    print("  ".join(row))
```

### 示例

```python
matrix = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
total = 0
for row in matrix:
    for value in row:
        total += value
print(f"元素和={total}")           # 元素和=45

# 转置
transposed = [[row[i] for row in matrix] for i in range(3)]
print(transposed)                  # [[1, 4, 7], [2, 5, 8], [3, 6, 9]]
```

### 练习

1. 打印 5 行倒三角形。
2. 求 3×3 矩阵的主对角线之和。
3. 判断一个 3×3 列表是否为对称矩阵。

### 注意事项

- 内层循环变量名不要与外层重名（如都叫 `i`），容易出坑。
- 二维列表不能用 `[[0] * 3] * 3` 创建（行是同一对象）。
- 能用推导式或 `zip` 表达的场景，优先用更简洁的写法。

### 常见错误

- 用 `*` 复制二维列表导致「改一行全变」。
- 内外层变量混淆，逻辑判断用了错误的层级变量。
- 复杂度失控：三层嵌套遍历大列表导致超时。

## loop-else

### 理论

`for ... else` / `while ... else` 中的 `else` 在循环**正常结束**（未被 `break` 打断）时执行。它天然表达「找遍都没有」的语义，比手动标志变量更清晰。

### 代码

```python
numbers = [4, 6, 8, 9]
for n in numbers:
    if n % 2 == 1:
        print(f"存在奇数：{n}")
        break
else:
    print("全是偶数")
# 存在奇数：9
```

### 示例

```python
# 质数判断
def is_prime(n: int) -> bool:
    """判断 n 是否为质数。"""
    if n < 2:
        return False
    for divisor in range(2, int(n ** 0.5) + 1):
        if n % divisor == 0:
            return False
    return True


print([x for x in range(2, 20) if is_prime(x)])
# [2, 3, 5, 7, 11, 13, 17, 19]
```

### 练习

1. 用 `for/else` 判断列表中是否存在重复元素。
2. 用 `for/else` 实现「查找不到返回 -1」的搜索函数。
3. 把本节的质数判断改写成 `for/else` 版本。

### 注意事项

- `else` 容易被误读为「否则」，记住它的语义是「循环没有被 break 打断」。
- 循环体内出现 `return` 会直接结束函数，`else` 不会执行。
- 与 `continue` 无关：`continue` 不影响 `else` 是否执行。

### 常见错误

- 以为 `else` 在循环条件为假时才作为「否则分支」执行。
- 忘记 `break` 导致 `else` 永远执行。
- 在 `while/else` 中条件本身为假就进入 `else`，导致逻辑误判。
