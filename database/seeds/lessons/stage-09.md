# 阶段 9 · 高级 Python

## iterator

### 理论

迭代器协议由 `__iter__`（返回迭代器自身）与 `__next__`（返回下一个元素，耗尽时抛 `StopIteration`）组成。`for` 底层就是不断调用 `__next__`。可迭代对象（iterable）实现了 `__iter__` 返回迭代器。

### 代码

```python
class Countdown:
    """倒计时迭代器。"""

    def __init__(self, start: int) -> None:
        self.current = start

    def __iter__(self) -> "Countdown":
        return self

    def __next__(self) -> int:
        if self.current <= 0:
            raise StopIteration
        self.current -= 1
        return self.current + 1

print(list(Countdown(3)))   # [3, 2, 1]
```

### 示例

```python
nums = [1, 2, 3]
it = iter(nums)
print(next(it), next(it), next(it))   # 1 2 3
# next(it)  -> StopIteration
```

### 练习

1. 实现一个只产出偶数的迭代器。
2. 区分「可迭代对象」与「迭代器」的差异并各写一个例子。

### 注意事项

- 迭代器是一次性的，遍历完即耗尽。
- `for` 会自动捕获 `StopIteration`。

### 常见错误

- 把可迭代对象直接 `next()`（未先 `iter()`）。
- 重复使用已耗尽的迭代器，得到空结果。

## generator

### 理论

生成器函数用 `yield` 产出值，调用时返回生成器对象，**惰性求值**、按需产生，内存占用低。`yield` 处暂停、下次 `next` 继续。

### 代码

```python
def fibonacci(n: int):
    """生成前 n 个斐波那契数。"""
    a, b = 0, 1
    for _ in range(n):
        yield a
        a, b = b, a + b

print(list(fibonacci(8)))   # [0, 1, 1, 2, 3, 5, 8, 13]
```

### 示例

```python
def read_lines(path: str):
    """逐行读取文件，避免一次性载入内存。"""
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            yield line.rstrip("\n")

# 大文件场景下内存友好
for line in read_lines("big.log"):
    if "ERROR" in line:
        print(line)
```

### 练习

1. 写生成器产出 1..N 的平方。
2. 用生成器实现「读取大文件中的非空行」。

### 注意事项

- 生成器只能遍历一次。
- 生成器内异常会在 `next` 时抛出。

### 常见错误

- 用 `list(gen)` 立即物化，失去惰性优势。
- 在生成器里做有副作用的操作却未预期暂停时机。

## generator-expression

### 理论

生成器表达式形如 `(expr for x in it)`，语法类似列表推导式，但用圆括号且**惰性**。适合只遍历一次的流水线处理，比列表推导式省内存。

### 代码

```python
nums = range(1_000_000)

# 列表推导式：立即生成全部，占用大量内存
# squares = [n * n for n in nums]

# 生成器表达式：按需产生
squares = (n * n for n in nums)
print(sum(squares))          # 求和，逐个计算，内存友好

total = sum(n * n for n in range(10))   # 直接传参可省括号
print(total)
```

### 示例

```python
data = [" 12 ", "34", "abc", "56"]

numbers = (int(x) for x in data if x.strip().isdigit())
print(list(numbers))   # [12, 34, 56]
```

### 练习

1. 用生成器表达式求 1..100 中所有 3 的倍数之和。
2. 比较列表推导式与生成器表达式的内存占用。

### 注意事项

- 只需一次遍历时优先用生成器表达式。
- 需要索引/重复遍历时用列表。

### 常见错误

- 生成器表达式写成 `[...]` 误当惰性。
- 在函数调用外多次复用生成器，第二次为空。

## map-filter-reduce

### 理论

函数式三剑客：`map(func, it)` 映射、`filter(pred, it)` 过滤、`functools.reduce(func, it)` 聚合。它们返回迭代器/结果，常与 `lambda` 搭配，可替代部分显式循环。

### 代码

```python
from functools import reduce

nums = [1, 2, 3, 4, 5]

squared = list(map(lambda n: n * n, nums))
evens = list(filter(lambda n: n % 2 == 0, nums))
total = reduce(lambda a, b: a + b, nums)

print(squared, evens, total)   # [1,4,9,16,25] [2,4] 15
```

### 示例

```python
words = ["Python", "java", "GO", "rust"]
upper = list(map(str.upper, words))
short = list(filter(lambda w: len(w) <= 3, words))
print(upper, short)
```

### 练习

1. 用 `map` + `filter` 把字符串列表转成偶数长度的大写列表。
2. 用 `reduce` 求列表最大值。

### 注意事项

- 推导式往往比 `map`/`filter` 更易读，按场景选。
- `reduce` 记得提供初始值处理空序列。

### 常见错误

- `map` 结果忘记转 `list`，直接打印看到 `<map object>`。
- `reduce` 对空列表无初始值时抛 `TypeError`。

## decorator-advanced

### 理论

装饰器是「接收函数、返回新函数」的高阶函数。`@decorator` 等价于 `func = decorator(func)`。带参数的装饰器再多包一层，常配合 `functools.wraps` 保留原函数元信息。

### 代码

```python
import functools
import time

def retry(times: int = 3, delay: float = 0.1):
    """带参数的重试装饰器。"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last: Exception | None = None
            for _ in range(times):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:   # noqa: BLE001
                    last = exc
                    time.sleep(delay)
            raise last  # type: ignore[misc]
        return wrapper
    return decorator

@retry(times=2, delay=0)
def unstable() -> str:
    raise ValueError("失败")

# unstable()  # 尝试两次后抛 ValueError
```

### 示例

```python
import functools
import time

def timed(func):
    """统计函数耗时。"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        print(f"{func.__name__} 耗时 {time.perf_counter() - start:.4f}s")
        return result
    return wrapper

@timed
def work() -> int:
    return sum(range(1000))

work()
```

### 练习

1. 写一个 `@memoize` 装饰器缓存函数结果。
2. 实现 `@log_calls` 打印每次调用的参数。

### 注意事项

- 始终用 `functools.wraps` 保留元数据。
- 装饰器会增加调用开销，热路径慎用。

### 常见错误

- 忘记 `functools.wraps`，导致 `func.__name__` 变成 `wrapper`。
- 带参装饰器忘写最外层 `return decorator`。

## closures

### 理论

闭包是「函数 + 其捕获的外部变量」。内层函数引用外层作用域变量，即使外层已返回，变量仍被保留。`nonlocal` 用于在内层修改外层变量。

### 代码

```python
def counter():
    """返回一个带状态的计数函数。"""
    count = 0

    def increment() -> int:
        nonlocal count
        count += 1
        return count

    return increment

c = counter()
print(c(), c(), c())   # 1 2 3
```

### 示例

```python
def multiply_by(factor: int):
    """生成乘法函数。"""
    def mul(x: int) -> int:
        return x * factor
    return mul

double = multiply_by(2)
triple = multiply_by(3)
print(double(5), triple(5))   # 10 15
```

### 练习

1. 用闭包实现一个「累加器」。
2. 用闭包实现可配置的问候函数。

### 注意事项

- 捕获的是变量本身而非值，注意循环中的延迟绑定。
- 需要修改外层变量时用 `nonlocal`。

### 常见错误

- 循环里创建闭包，全部捕获最后一个变量值。
- 误在闭包里直接赋值（会被当作局部变量，抛 `UnboundLocalError`）。

## contextmanager

### 理论

`contextlib.contextmanager` 让「生成器函数」一键变成上下文管理器：`yield` 前是 `__enter__`，`yield` 后是 `__exit__`。适合管理锁、临时文件、事务、计时等。

### 代码

```python
import time
from contextlib import contextmanager

@contextmanager
def timer(label: str):
    """统计代码块耗时。"""
    start = time.perf_counter()
    try:
        yield
    finally:
        print(f"{label}: {time.perf_counter() - start:.4f}s")

with timer("计算"):
    sum(range(100_000))
```

### 示例

```python
from contextlib import contextmanager

@contextmanager
def open_write(path: str):
    """打开文件写入，出错自动关闭。"""
    f = open(path, "w", encoding="utf-8")
    try:
        yield f
    finally:
        f.close()

with open_write("x.txt") as f:
    f.write("hello")
```

### 练习

1. 写一个「临时切换目录」的上下文管理器。
2. 写一个「打印开始/结束」的上下文管理器。

### 注意事项

- 用 `try/finally` 保证资源一定释放。
- `yield` 只能出现一次。

### 常见错误

- `yield` 后忘记清理逻辑。
- 把必须成对的操作写在 `finally` 之外。

## functools-tools

### 理论

`functools` 工具箱：`lru_cache`（缓存）、`partial`（偏函数）、`reduce`、`wraps`、`total_ordering`、`cached_property`。能显著简化常见模式。

### 代码

```python
from functools import lru_cache, partial

@lru_cache(maxsize=128)
def fib(n: int) -> int:
    """带缓存的递归斐波那契。"""
    return n if n < 2 else fib(n - 1) + fib(n - 2)

print(fib(30))    # 快速返回 832040

add = lambda a, b: a + b
add10 = partial(add, 10)
print(add10(5))   # 15
```

### 示例

```python
from functools import cached_property

class DataSet:
    """示例：开销大的属性只算一次。"""

    def __init__(self, nums: list[int]) -> None:
        self.nums = nums

    @cached_property
    def total(self) -> int:
        print("计算中...")
        return sum(self.nums)

print(DataSet([1, 2, 3]).total)
```

### 练习

1. 用 `lru_cache` 优化耗时纯函数。
2. 用 `partial` 定制一个固定参数的日志函数。

### 注意事项

- `lru_cache` 只适合纯函数（相同输入相同输出）。
- 缓存参数必须可哈希。

### 常见错误

- 对含可变参数的函数用 `lru_cache`，抛 `TypeError`。
- 忘记缓存会持续占用内存（设 `maxsize`）。

## typing-generics

### 理论

类型注解提升可读性并支持静态检查。泛型用 `TypeVar`/`Generic` 表达「类型参数」，`Protocol` 表达结构化接口，`Optional`/`Union`/`Literal` 表达联合类型。运行时不影响执行，但能提前发现错误。

### 代码

```python
from typing import TypeVar, Generic

T = TypeVar("T")

class Stack(Generic[T]):
    """类型安全的栈。"""

    def __init__(self) -> None:
        self._items: list[T] = []

    def push(self, item: T) -> None:
        self._items.append(item)

    def pop(self) -> T:
        return self._items.pop()

s: Stack[int] = Stack()
s.push(1)
print(s.pop())
```

### 示例

```python
from typing import Literal, Optional

def greet(name: Optional[str] = None) -> str:
    return f"你好, {name or '访客'}"

def move(direction: Literal["up", "down"]) -> None:
    print(f"向 {direction}")

greet()
move("up")
```

### 注意事项

- 用 `mypy`/`pyright` 做静态检查才能真正受益。
- 尽量精确注解，避免滥用 `Any`。

### 常见错误

- 注解与实际返回不符，检查工具报错。
- 循环引用类型时未用字符串注解或 `from __future__ import annotations`。
