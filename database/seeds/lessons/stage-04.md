# 阶段 4 · 函数

## function-basics

### 理论

`def` 定义函数：函数名、参数列表、函数体与返回值。函数让逻辑可复用、可测试、可命名。没有 `return` 时函数返回 `None`。函数体第一句三引号字符串即文档字符串。

### 代码

```python
def greet(name: str, greeting: str = "你好") -> str:
    """返回问候语。"""
    return f"{greeting}，{name}！"

print(greet("小徐"))                # 你好，小徐！
print(greet("小林", "早上好"))       # 早上好，小林！
result = greet("空手")
print(result)                       # 你好，空手！
```

### 示例

```python
def is_even(n: int) -> bool:
    """判断是否为偶数。"""
    return n % 2 == 0

print([x for x in range(10) if is_even(x)])   # [0, 2, 4, 6, 8]
```

### 练习

1. 写 `area(w, h)` 返回矩形面积，并补充文档字符串。
2. 写 `normalize(text)` 去掉首尾空白并转小写。
3. 写无返回值的函数，打印其返回值验证是 `None`。

### 注意事项

- 函数名用动词短语，参数名表达含义（`timeout_seconds` 优于 `t`）。
- 一个函数只做一件事，超过 30 行考虑拆分。
- 定义在前、使用在后；模块顶层不要写副作用代码。

### 常见错误

- 忘记 `return` 导致拿到 `None`。
- `IndentationError` → 函数体未缩进。
- `TypeError: greet() missing 1 required positional argument` → 少传必填参数。

## parameters-defaults

### 理论

参数分位置参数与默认参数。默认值在**函数定义时**求值一次，因此**绝不能**用可变对象（列表/字典）作默认值——所有调用会共享同一个对象。

### 代码

```python
def add_item(item: str, bucket: list | None = None) -> list:
    """安全的可变默认参数写法。"""
    bucket = bucket if bucket is not None else []
    bucket.append(item)
    return bucket

print(add_item("a"))   # ['a']
print(add_item("b"))   # ['b']

def wrong(item: str, bucket: list = []) -> list:
    """反例：默认值是共享可变对象。"""
    bucket.append(item)
    return bucket

print(wrong("a"), wrong("b"))   # ['a', 'b'] ['a', 'b']
```

### 示例

```python
def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    """把 value 限制在 [low, high] 区间。"""
    return max(low, min(high, value))

print(clamp(1.5), clamp(-2), clamp(0.5, 0, 10))   # 1.0 0.0 0.5
```

### 练习

1. 写 `power(base, exp=2)` 并验证默认值生效。
2. 复现「可变默认参数」的坑，再用 `None` 修复它。
3. 写一个带三个默认参数的函数，并只用关键字传部分参数。

### 注意事项

- 必填参数必须在默认参数之前。
- 默认值应选「不可变且稳定」的字面量。
- 默认值表达式只求值一次，不要在默认值里调用 `datetime.now()`。

### 常见错误

- 可变默认参数被跨调用污染。
- `SyntaxError: non-default argument follows default argument` → 参数顺序错误。
- 以为默认值每次调用都重新求值。

## return-value

### 理论

`return` 结束函数并返回一个对象。需要返回多个值时，用元组解包；返回 `None` 表示「无结果」。函数要么明确返回值，要么明确只做副作用（打印/写库）。

### 代码

```python
def divide(a: float, b: float) -> tuple[float, float]:
    """返回商与余数。"""
    if b == 0:
        raise ValueError("除数不能为 0")
    return a // b, a % b

quotient, remainder = divide(17, 5)
print(quotient, remainder)   # 3.0 2.0
```

### 示例

```python
def find_max_min(nums: list[int]) -> tuple[int, int] | None:
    """返回最值；空列表返回 None。"""
    if not nums:
        return None
    return max(nums), min(nums)

print(find_max_min([3, 1, 9]))   # (9, 1)
print(find_max_min([]))          # None
```

### 练习

1. 写函数返回列表中的偶数、奇数两个列表。
2. 写函数返回字典的「键最长的一个」。
3. 写函数统计文本行数、词数、字符数并一次性返回。

### 注意事项

- 提前 `return` 可减少嵌套层级（卫语句）。
- 不要返回多种类型（有时元组有时 `None`）除非调用方明确处理。
- 返回可变对象时注意调用方可能修改它，必要时返回副本。

### 常见错误

- `return` 写在循环里，导致只处理第一项。
- 用 `print` 代替 `return`，调用方拿不到结果。
- 忘记处理 `None` 返回值 → `TypeError: cannot unpack non-sequence NoneType`。

## keyword-arguments

### 理论

调用时用 `名字=值` 传参即关键字参数，可跳过顺序、提升可读性。定义中 `*` 之后是**仅关键字参数**，只能按名字传。`/` 之前是仅位置参数。

### 代码

```python
def connect(host: str, port: int, *, timeout: int = 30, retry: int = 3) -> str:
    """超时与重试必须用关键字传入，避免顺序搞错。"""
    return f"{host}:{port} timeout={timeout} retry={retry}"

print(connect("localhost", 5432, timeout=5))
print(connect("localhost", 5432, retry=1, timeout=10))
```

### 示例

```python
def create_user(name: str, *, role: str = "user", active: bool = True) -> dict:
    """创建用户字典，布尔开关必须显式写出。"""
    return {"name": name, "role": role, "active": active}

print(create_user("小徐", role="admin", active=False))
# {'name': '小徐', 'role': 'admin', 'active': False}
```

### 练习

1. 给一个布尔参数加 `*`，强制调用方写明含义。
2. 写出三种调用同一函数的方式（全位置、混合、全关键字）。
3. 解释为什么 `f(True)` 可读性差。

### 注意事项

- 关键字参数顺序可任意，但习惯上按定义顺序写。
- `*` 之后不能再有位置参数。
- 布尔参数建议强制关键字传入。

### 常见错误

- `TypeError: connect() takes 2 positional arguments but 3 were given` → 仅关键字参数用了位置方式。
- 关键字名拼错 → `TypeError: got an unexpected keyword argument`。
- 位置与关键字重复传同一参数 → `TypeError: got multiple values for argument`。

## args-kwargs

### 理论

`*args` 把多余位置参数打包为元组；`**kwargs` 把多余关键字参数打包为字典。调用时 `*seq`、`**mapping` 反向解包。常用于装饰器与通用封装。

### 代码

```python
def total(*args: float) -> float:
    """任意数量数字求和。"""
    return sum(args)

print(total(1, 2, 3), total())   # 6 0

def show(**kwargs: object) -> None:
    """打印任意关键字参数。"""
    for key, value in kwargs.items():
        print(f"{key}={value}")

show(name="小徐", level=3)
```

### 示例

```python
def wrapper(func, *args, **kwargs):
    """透传调用并打印耗时参数。"""
    print(f"调用 {func.__name__} 参数 {args} {kwargs}")
    return func(*args, **kwargs)

print(wrapper(pow, 2, 3))              # 调用 pow 参数 (2, 3) {}  -> 8
print(wrapper(pow, base=2, exp=3))     # 调用 pow 参数 () {'base': 2, 'exp': 3}
```

### 练习

1. 写 `average(*nums)` 返回平均值，空参数返回 0。
2. 写 `merge(**dicts)` 或在调用时用 `**` 展开字典。
3. 写一个 `timed(func)` 打印调用参数的通用包装器。

### 注意事项

- 参数顺序必须是：位置、默认、`*args`、仅关键字、`**kwargs`。
- `*args` 是元组，`**kwargs` 是字典。
- 过度使用会破坏签名可读性，仅在确实需要时使用。

### 常见错误

- 把 `args` 当列表使用（它是元组，不能 `append`）。
- 调用时忘记 `*` / `**` → 整个序列被当成一个参数。
- `TypeError: got multiple values for argument` → 位置与关键字冲突。

## scope-legb

### 理论

名字解析顺序 LEGB：Local（函数内）→ Enclosing（外层函数）→ Global（模块）→ Builtin（内置）。函数内赋值默认创建局部变量；要改全局用 `global`，改外层函数变量用 `nonlocal`。

### 代码

```python
counter = 0

def increase() -> None:
    """修改全局变量必须声明 global。"""
    global counter
    counter += 1

increase()
increase()
print(counter)   # 2

def make_counter():
    """闭包：用 nonlocal 修改外层变量。"""
    count = 0
    def step() -> int:
        nonlocal count
        count += 1
        return count
    return step

c = make_counter()
print(c(), c(), c())   # 1 2 3
```

### 示例

```python
# 常见坑：函数内赋值使变量变局部
x = 10

def read_only() -> int:
    """只读全局变量，无需 global。"""
    return x

def shadow() -> str:
    """这里 x 是局部变量，与全局无关。"""
    x = "local"
    return x

print(read_only(), shadow(), x)   # 10 local 10
```

### 练习

1. 用闭包实现一个「累加器」，每次调用返回累计值。
2. 复现 `UnboundLocalError` 并解释原因。
3. 用 `global` 统计函数被调用次数。

### 注意事项

- 尽量少用 `global`，它会破坏函数的可预测性。
- 闭包捕获的是变量而非值，循环中创建函数要小心延迟绑定。
- 内置名（如 `list`、`id`）不要用作变量名。

### 常见错误

- `UnboundLocalError: cannot access local variable 'x'` → 函数内赋值导致 x 变为局部。
- 闭包中不加 `nonlocal` 直接 `+=` → 同样报错。
- 把 `global` 写在赋值语句之后 → 不生效。

## lambda

### 理论

`lambda 参数: 表达式` 创建匿名函数，函数体只能是**单个表达式**，返回其求值结果。典型用途是传给 `sorted`、`max`、`filter` 的 `key` 或 `func`。

### 代码

```python
square = lambda x: x * x
print(square(5))                     # 25

students = [("小徐", 92), ("小林", 88), ("小周", 95)]
print(sorted(students, key=lambda item: item[1], reverse=True))
# [('小周', 95), ('小徐', 92), ('小林', 88)]

print(list(map(lambda x: x * 2, [1, 2, 3])))   # [2, 4, 6]
```

### 示例

```python
records = [
    {"name": "A", "score": 88, "age": 20},
    {"name": "B", "score": 95, "age": 19},
]
top = max(records, key=lambda r: (r["score"], -r["age"]))
print(top["name"])   # B
```

### 练习

1. 用 `lambda` 按字符串长度排序一组单词。
2. 用 `filter` + `lambda` 取出所有正数。
3. 把 `lambda` 改写为普通 `def`，比较可读性。

### 注意事项

- 复杂逻辑用 `def` 更清晰，`lambda` 只适合一行。
- `lambda` 不能包含语句（`print`、`return`、赋值）。
- 变量名遮蔽：`lambda x: x` 中的 `x` 不会影响外部 `x`。

### 常见错误

- 在 `lambda` 中写赋值表达式 → `SyntaxError`。
- `sorted(key=lambda x: x[1])` 但元素不是序列 → `TypeError`。
- 晚绑定：循环中生成多个 `lambda` 都返回最后一个值。

## list-comprehension

### 理论

`[表达式 for 变量 in 可迭代 if 条件]` 一行生成列表，比「循环 + append」更快也更清晰。也支持嵌套循环与多条件，但超过两层就该拆函数。

### 代码

```python
squares = [x * x for x in range(10)]
evens = [x for x in range(10) if x % 2 == 0]
labels = ["偶" if x % 2 == 0 else "奇" for x in range(5)]
pairs = [(i, j) for i in range(2) for j in range(2)]
print(squares)   # [0, 1, 4, 9, 16, 25, 36, 49, 64, 81]
print(evens)     # [0, 2, 4, 6, 8]
print(labels)    # ['偶', '奇', '偶', '奇', '偶']
print(pairs)     # [(0, 0), (0, 1), (1, 0), (1, 1)]
```

### 示例

```python
raw = [" 12 ", "abc", "34", ""]
numbers = [int(item) for item in (s.strip() for s in raw) if item.strip().isdigit()]
print(numbers)                 # [12, 34]

matrix = [[1, 2], [3, 4]]
flat = [value for row in matrix for value in row]
print(flat)                    # [1, 2, 3, 4]
```

### 练习

1. 生成 1–50 中所有能被 3 整除的数的平方。
2. 把二维列表展平并去掉负数。
3. 用推导式把 `{科目: 分数}` 字典转成「科目-分数」字符串列表。

### 注意事项

- 推导式只用于「生成列表」，不要塞入副作用（打印、写文件）。
- 条件放在 `for` 之后是过滤，放在表达式位置是三元选择。
- 内存敏感时用生成器表达式 `(...)`。

### 常见错误

- `[... if ... for ...]` 顺序写错 → `SyntaxError`。
- 推导式中使用外层同名变量，造成覆盖困惑。
- 嵌套推导式读不懂却硬写，应改回双重循环。

## recursion

### 理论

递归函数调用自身，必须包含**基线条件**（终止）与**递归条件**（向基线靠拢）。Python 默认递归深度约 1000，深度过大会 `RecursionError`。可用 `functools.lru_cache` 记忆化加速。

### 代码

```python
def factorial(n: int) -> int:
    """计算 n 的阶乘。"""
    if n <= 1:
        return 1
    return n * factorial(n - 1)

print(factorial(5))   # 120

from functools import lru_cache

@lru_cache(maxsize=None)
def fib(n: int) -> int:
    """带记忆化的斐波那契。"""
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)

print([fib(i) for i in range(10)])   # [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]
```

### 示例

```python
def flatten(nested: list) -> list:
    """递归展平任意深度的嵌套列表。"""
    result = []
    for item in nested:
        if isinstance(item, list):
            result.extend(flatten(item))
        else:
            result.append(item)
    return result

print(flatten([1, [2, [3, [4]]]]))   # [1, 2, 3, 4]
```

### 练习

1. 用递归实现二分查找。
2. 用递归计算列表元素之和（不用 `sum`）。
3. 用递归解汉诺塔，输出移动步骤数。

### 注意事项

- 递归可读性好但栈开销大，深度大时改迭代。
- 斐波那契朴素递归是指数复杂度，必须记忆化。
- 递归函数要么返回结果，要么明确只做副作用，不要混用。

### 常见错误

- 缺少基线条件 → `RecursionError: maximum recursion depth exceeded`。
- 基线条件写错（如 `n == 0` 却传入负数）导致无限递归。
- 修改可变默认参数或全局状态导致重复计算错误。
