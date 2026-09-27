# 阶段 6 · 异常处理

## exception-basics

### 理论

异常是运行期错误对象，会沿调用栈向上传播，直到被 `try` 捕获或终止程序。`traceback` 要**从下往上读**：最后一行是错误类型与消息，向上的行是调用链。

### 代码

```python
def divide(a: float, b: float) -> float:
    """除法，b 为 0 时抛出异常。"""
    return a / b

try:
    divide(1, 0)
except ZeroDivisionError as exc:
    print(f"捕获到：{type(exc).__name__} - {exc}")
# 捕获到：ZeroDivisionError - division by zero
```

### 示例

```python
import traceback

try:
    int("abc")
except ValueError:
    traceback.print_exc()   # 打印完整调用栈，便于定位
```

### 练习

1. 故意触发 `IndexError`、`KeyError`、`TypeError` 各一次，记录错误信息。
2. 阅读一段 traceback，指出真正的出错行。
3. 写函数在异常时返回默认值而不是崩溃。

### 注意事项

- 不要用异常做常规流程控制（性能与可读性都差）。
- 异常消息要包含足够上下文（如 `f"解析失败: {raw!r}"`）。
- 顶层最好统一捕获并记录，避免静默失败。

### 常见错误

- 吞掉异常（`except: pass`）导致问题难排查。
- 捕获过宽的 `Exception` 掩盖真正的 bug。
- 在 `except` 中丢失原始信息（未 `raise ... from exc`）。

## try-except

### 理论

`try` 包住可能出错的代码，`except 具体异常` 精准捕获。多个 `except` 从上到下匹配，第一个匹配的执行。捕获后可用 `raise` 重新抛出。

### 代码

```python
def parse_int(text: str) -> int | None:
    """安全解析整数，失败返回 None。"""
    try:
        return int(text)
    except (TypeError, ValueError) as exc:
        print(f"解析失败：{exc}")
        return None

print(parse_int("42"), parse_int("abc"))
# 解析失败：invalid literal for int() with base 10: 'abc'
# 42 None
```

### 示例

```python
data = {"score": "九十二"}
try:
    score = int(data["score"])
except KeyError:
    print("缺少字段 score")
except ValueError as exc:
    print(f"字段格式错误：{exc}")
# 字段格式错误：invalid literal for int() with base 10: '九十二'
```

### 练习

1. 写 `safe_get(d, key)` 缺失时返回 `None`。
2. 用两个 `except` 分别处理键缺失与类型错误。
3. 在 `except` 中记录日志并重新抛出。

### 注意事项

- 只捕获你能处理的异常类型。
- 捕获顺序：具体在前、宽泛在后。
- 需要清理资源时用 `finally` 或 `with`，不要只依赖 `except`。

### 常见错误

- 裸 `except:` 会连 `KeyboardInterrupt` 一起吞掉。
- `except ValueError, TypeError:` 语法错误，应用元组。
- 在 `except` 分支里再抛同名异常导致递归报错。

## finally-else

### 理论

`else` 在 `try` 块**无异常**时执行；`finally` **无论如何**都执行，适合释放资源。执行顺序：try → else（无异常）→ finally。

### 代码

```python
def read_config(path: str) -> str | None:
    """读取配置，演示 try/except/else/finally。"""
    handle = None
    try:
        handle = open(path, encoding="utf-8")
    except FileNotFoundError:
        print(f"文件不存在：{path}")
    else:
        print("读取成功")
        return handle.read()
    finally:
        if handle:
            handle.close()
        print("清理完成")
    return None

read_config("no_such_file.txt")
# 文件不存在：no_such_file.txt
# 清理完成
```

### 示例

```python
# 用 finally 保证计数器一定还原
lock_holder = {"locked": False}

def critical_section() -> None:
    """进入临界区，异常也要解锁。"""
    lock_holder["locked"] = True
    try:
        raise RuntimeError("业务异常")
    finally:
        lock_holder["locked"] = False

try:
    critical_section()
except RuntimeError as exc:
    print(exc, lock_holder)
# 业务异常 {'locked': False}
```

### 练习

1. 用 `else` 只在成功时写日志。
2. 用 `finally` 保证文件句柄关闭（对比 `with` 写法）。
3. 解释 `return` 与 `finally` 同时存在时的执行顺序。

### 注意事项

- `finally` 中不要 `return`，会吞掉 `try` 的返回值或异常。
- 现代写法优先 `with`，`finally` 用于非上下文管理器场景。
- `else` 比「把所有代码塞进 try」更精确，能避免误捕。

### 常见错误

- `finally` 里抛异常掩盖了原异常。
- `finally` 中 `return` 导致异常被静默丢弃。
- 把无关代码放进 `try`，导致捕获到意料之外的异常。

## raise-custom

### 理论

`raise 异常实例` 主动抛出异常；自定义异常继承 `Exception`（业务异常）或更具体的基类，便于分层捕获与携带上下文。用 `raise ... from exc` 保留原始原因。

### 代码

```python
class BalanceError(Exception):
    """余额不足异常。"""

    def __init__(self, balance: float, amount: float) -> None:
        super().__init__(f"余额 {balance} 不足以支付 {amount}")
        self.balance = balance
        self.amount = amount

def pay(balance: float, amount: float) -> float:
    """扣款，余额不足时抛出自定义异常。"""
    if amount > balance:
        raise BalanceError(balance, amount)
    return balance - amount

try:
    pay(10, 20)
except BalanceError as exc:
    print(exc, exc.balance, exc.amount)
# 余额 10 不足以支付 20 10 20
```

### 示例

```python
def parse_config(raw: str) -> dict:
    """解析配置，错误时带上原始输入。"""
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"配置不是合法 JSON: {raw[:50]!r}") from exc
```

### 练习

1. 定义 `ValidationError`，携带字段名与原因。
2. 用 `raise from` 包装底层异常并保留原因链。
3. 为你的项目设计三层异常：底层、业务、接口。

### 注意事项

- 自定义异常类名以 `Error` 结尾，放在专门的模块里。
- 异常应携带结构化信息而不是只拼字符串。
- 库代码抛异常，应用层决定是否降级。

### 常见错误

- 继承 `BaseException` 导致无法被常规 `except Exception` 捕获。
- 只抛 `Exception("错误")` 丢失上下文。
- 用 `raise exc` 而非 `raise exc from origin` 丢失原因链。

## exception-hierarchy

### 理论

`BaseException` 下有 `Exception`（几乎所有业务异常）与 `SystemExit`、`KeyboardInterrupt`、`GeneratorExit`。常见内置异常都继承 `Exception`：`ValueError`、`TypeError`、`KeyError`、`OSError`（含 `FileNotFoundError`）等。

### 代码

```python
print(issubclass(ValueError, Exception))         # True
print(issubclass(FileNotFoundError, OSError))    # True
print(issubclass(KeyError, LookupError))         # True

for exc_type in (ValueError, KeyError, ZeroDivisionError):
    print(exc_type.__name__, "->", [c.__name__ for c in exc_type.__mro__[1:4]])
```

### 示例

```python
def parse(text: str) -> float:
    """按序捕获不同层级的异常。"""
    try:
        return float(text)
    except ValueError:
        return 0.0
    except Exception as exc:      # 兜底，但仍打印以便发现 bug
        print(f"未预期错误：{type(exc).__name__}: {exc}")
        raise
```

### 练习

1. 绘制 `OSError` 家族的 5 个子类。
2. 找出一个「捕获过宽」的 `except` 并收窄类型。
3. 用 `except Exception` 做兜底，同时保留日志与重抛。

### 注意事项

- 捕获 `Exception` 可以接受，但必须记录日志。
- 不要捕获 `BaseException`，会拦住退出信号。
- 自定义异常要选择合适的基类以复用捕获逻辑。

### 常见错误

- `except Exception as e: pass` 吞掉所有 bug。
- 分不清 `KeyError` 与 `IndexError`，用错类型。
- 期望 `FileNotFoundError` 却只捕 `OSError`（可捕获但过宽）。

## assertions

### 理论

`assert 条件, 消息` 在条件为假时抛 `AssertionError`。它用于**开发期不变量检查**，`python -O` 运行时会被移除，因此不能用于校验用户输入。

### 代码

```python
def average(nums: list[float]) -> float:
    """计算平均值（开发期断言保护）。"""
    assert nums, "列表不能为空"          # 开发期自检
    return sum(nums) / len(nums)

print(average([1, 2, 3]))   # 2.0
try:
    average([])
except AssertionError as exc:
    print(f"断言失败：{exc}")
```

### 示例

```python
def withdraw(balance: float, amount: float) -> float:
    """取款：用显式校验而不是 assert 处理业务规则。"""
    if amount <= 0:
        raise ValueError("取款金额必须为正数")
    if amount > balance:
        raise ValueError("余额不足")
    return balance - amount
```

### 练习

1. 用 `assert` 给函数加入参不变量检查。
2. 把 `assert` 改写为显式 `if + raise`，比较两种场景的适用性。
3. 用 `python -O` 运行代码，验证 `assert` 被跳过。

### 注意事项

- `assert` 适合内部不变量与测试，不适合外部输入校验。
- 断言消息要写清期望与实际。
- 生产环境不要依赖 `assert` 做安全校验。

### 常见错误

- 用 `assert` 校验用户输入，被 `-O` 优化掉后出现安全漏洞。
- `assert` 内写副作用表达式（如 `assert f()`），优化模式下不执行。
- 在 `assert` 中用元组语法写消息导致表达式语义变化。

## defensive-programming

### 理论

防御式编程：对外部输入永不信任，入口处集中校验（fail fast）；对内保持不变量，用类型注解与断言辅助。校验通过后函数内部可以「乐观」编写，避免层层嵌套。

### 代码

```python
def create_user(name: str, age: int) -> dict:
    """入口集中校验，之后乐观执行。"""
    if not name or not name.strip():
        raise ValueError("name 不能为空")
    if not 0 <= age <= 150:
        raise ValueError("age 必须在 0-150 之间")
    return {"name": name.strip(), "age": age}

try:
    create_user("  ", 20)
except ValueError as exc:
    print(f"参数错误：{exc}")
```

### 示例

```python
def get_page(items: list, page: int = 1, size: int = 10) -> list:
    """容错分页：非法参数自动收敛。"""
    page = max(1, page)
    size = max(1, min(100, size))
    start = (page - 1) * size
    return items[start:start + size]

print(get_page(list(range(25)), page=0, size=999))
```

### 练习

1. 为一个函数设计「非法输入清单」并逐条写校验。
2. 用卫语句（早返回）替代 3 层嵌套。
3. 为分页函数补充大小与页数上限。

### 注意事项

- 校验失败要给出可操作的错误信息。
- 参数收敛（clamp）比报错更适合展示层。
- 校验逻辑集中，避免散落各处。

### 常见错误

- 依赖调用方「应该」传对参数而不校验。
- 校验写在深层逻辑里，错误信息难以定位。
- 过度防御导致正常路径被包在多层 `if` 中。

## logging-basics

### 理论

`logging` 比 `print` 更适合生产：有级别（DEBUG/INFO/WARNING/ERROR/CRITICAL）、可配置输出目标与格式、可携带时间与模块名。库代码获取 logger 用 `logging.getLogger(__name__)`。

### 代码

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
)

logger = logging.getLogger(__name__)
logger.debug("调试细节，默认不输出")
logger.info("服务已启动")
logger.warning("缓存不可用，已降级")
try:
    int("abc")
except ValueError:
    logger.exception("解析失败")     # 自动带上 traceback
```

### 示例

```python
import logging

logger = logging.getLogger("pythonlab.task")

def run_task(name: str) -> bool:
    """执行任务并记录结果。"""
    logger.info("任务开始 name=%s", name)
    try:
        # 任务主体
        return True
    except Exception:
        logger.exception("任务失败 name=%s", name)
        return False
```

### 练习

1. 把项目中的 `print` 按级别替换为 `logger`。
2. 配置日志同时输出到文件与控制台。
3. 用 `logger.exception` 记录一次真实异常。

### 注意事项

- 日志用占位符 `%s` 而不是 f-string，避免无谓字符串拼接。
- 日志中不要输出密码、Token 等敏感信息。
- 生产环境默认 INFO，排查问题时临时开 DEBUG。

### 常见错误

- 直接 `print` 导致生产无法按级别过滤。
- 重复 `basicConfig` 不生效（只有首次调用有效）。
- 混淆 `logger.error` 与 `logger.exception`，后者才自动带堆栈。

## error-recovery

### 理论

错误分可恢复（网络抖动、限流）与不可恢复（参数错误、数据损坏）。可恢复错误用「有限重试 + 退避」，不可恢复错误应快速失败并给出明确提示。降级（fallback）能让核心功能在依赖不可用时继续可用。

### 代码

```python
import random
import time

def retry(times: int = 3, base_delay: float = 0.2):
    """带指数退避的重试装饰器。"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(1, times + 1):
                try:
                    return func(*args, **kwargs)
                except (TimeoutError, ConnectionError) as exc:
                    if attempt == times:
                        raise
                    delay = base_delay * (2 ** (attempt - 1))
                    print(f"第 {attempt} 次失败（{exc}），{delay:.1f}s 后重试")
                    time.sleep(delay)
        return wrapper
    return decorator

@retry(times=3)
def flaky() -> str:
    """30% 概率成功的模拟调用。"""
    if random.random() < 0.7:
        raise TimeoutError("上游超时")
    return "ok"

print(flaky())
```

### 示例

```python
def load_config(primary: str) -> dict:
    """主路径失败时降级到默认配置。"""
    try:
        with open(primary, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError) as exc:
        print(f"配置加载失败，使用默认值：{exc}")
        return {"debug": False, "timeout": 30}
```

### 练习

1. 给一个网络请求函数加重试与退避。
2. 实现「主缓存 → 备用缓存 → 内存」三级降级。
3. 区分哪些异常应该重试、哪些应立即失败。

### 注意事项

- 重试必须限定次数并加退避，避免放大故障。
- 重试要求幂等，非幂等操作需去重键。
- 降级要打印 WARNING 日志，便于发现长期异常。

### 常见错误

- 无限重试导致线程耗尽。
- 对不可恢复错误（如参数非法）也重试。
- 降级后不记录日志，问题被长期掩盖。
