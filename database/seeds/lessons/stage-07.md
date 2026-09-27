# 阶段 7 · 文件操作

## file-read-write

### 理论

文件是持久化数据最简单的方式。读写三步走：`open()` 打开 → 读/写 → `close()` 关闭。`open(path, mode, encoding)` 的 `mode` 决定行为：`r` 读、`w` 覆盖写、`a` 追加、`x` 独占创建、`+` 读写；`b` 表示二进制。

### 代码

```python
# 读
with open("data.txt", "r", encoding="utf-8") as f:
    text = f.read()          # 一次性读全部
    f.seek(0)
    lines = f.readlines()    # 读成行列表

# 写（w 会清空原文件）
with open("out.txt", "w", encoding="utf-8") as f:
    f.write("hello\n")
    f.writelines(["a\n", "b\n"])

# 追加
with open("out.txt", "a", encoding="utf-8") as f:
    f.write("c\n")
```

### 示例

```python
def count_lines(path: str) -> int:
    """统计文本文件行数（大文件用迭代避免一次性载入）。"""
    with open(path, "r", encoding="utf-8") as f:
        return sum(1 for _ in f)

print(count_lines("data.txt"))
```

### 练习

1. 把一个列表逐行写入文件，再读回来还原为列表。
2. 用 `a` 模式给日志文件追加时间戳记录。
3. 实现 `tail(path, n)` 返回文件最后 n 行。

### 注意事项

- 生产代码优先用 `with`，避免忘记 `close()`。
- `w` 模式会立即清空文件，误用可能丢数据。
- 文本模式务必显式声明 `encoding="utf-8"`。

### 常见错误

- 忘记 `encoding`，在 Windows 上默认 GBK 导致中文乱码。
- 用 `f.read()` 读超大文件导致内存爆掉。
- 用 `w` 当 `a` 使用，覆盖了已有内容。

## with-statement

### 理论

`with` 是上下文管理器语法，进入时调用 `__enter__`，退出时（无论是否异常）调用 `__exit__`，用于可靠地释放资源。文件对象、锁、数据库连接都实现了该协议。

### 代码

```python
# 同时打开多个文件，减少嵌套
with open("in.txt", "r", encoding="utf-8") as src, \
     open("out.txt", "w", encoding="utf-8") as dst:
    for line in src:
        dst.write(line.rstrip() + "\n")
```

### 示例

```python
from contextlib import contextmanager

@contextmanager
def open_read(path: str):
    """简化版打开上下文，演示底层协议。"""
    handle = open(path, "r", encoding="utf-8")
    try:
        yield handle
    finally:
        handle.close()
```

### 练习

1. 用 `with` 同时打开读写两个文件做内容替换。
2. 写一个自定义上下文管理器，统计代码块耗时。

### 注意事项

- `with` 块退出即关闭，块外不要再使用文件对象。
- `__exit__` 返回 `True` 会吞掉异常，需谨慎。

### 常见错误

- 在 `with` 外继续读写已关闭的文件，抛 `ValueError: I/O operation on closed file`。
- 嵌套 `with` 过深时忘记资源释放顺序。

## encoding-issues

### 理论

计算机存储字节，文本是人类可读字符，二者靠「编码」映射。常见编码：UTF-8（推荐）、GBK/GB2312（中文 Windows 默认）、Latin-1。读写两端编码不一致就会出现 `UnicodeDecodeError` 或「乱码」。

### 代码

```python
text = "你好，Python"

data = text.encode("utf-8")     # 字符 -> 字节
print(data)                     # b'\xe4\xbd\xa0\xe5\xa5\xbd...'
print(data.decode("utf-8"))     # 你好，Python

# 容错读取
with open("gbk.txt", "r", encoding="gbk", errors="replace") as f:
    print(f.read())
```

### 示例

```python
def safe_read(path: str, encodings=("utf-8", "gbk", "latin-1")) -> str:
    """依次尝试多种编码读取，避免直接崩溃。"""
    for enc in encodings:
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("utf-8", b"", 0, 1, f"无法识别编码: {path}")
```

### 练习

1. 用 GBK 写入中文，再用 UTF-8 读，观察乱码并修复。
2. 写函数自动探测文件编码并正确读取。

### 注意事项

- 全项目统一 UTF-8 是最省心的策略。
- `errors="ignore"`/`"replace"` 会静默丢字符，仅作兜底。
- BOM（`utf-8-sig`）在跨平台 CSV 中很常见。

### 常见错误

- Windows 上用 `w` 默认 GBK 写、Linux 上用 UTF-8 读导致乱码。
- 二进制内容当文本打开触发解码错误。

## pathlib

### 理论

`pathlib.Path` 用面向对象方式操作路径，比字符串拼接更安全、跨平台。常用属性/方法：`name`、`suffix`、`stem`、`parent`、`/` 拼接、`exists()`、`mkdir()`、`glob()`、`read_text()`、`write_text()`。

### 代码

```python
from pathlib import Path

p = Path("logs") / "app.log"
print(p.name, p.suffix, p.parent)   # app.log .log logs

p.parent.mkdir(parents=True, exist_ok=True)
p.write_text("启动成功\n", encoding="utf-8")
print(p.read_text(encoding="utf-8"))

for py in Path(".").glob("**/*.py"):
    print(py)
```

### 示例

```python
from pathlib import Path

def total_size(root: str) -> int:
    """递归统计目录下所有文件总字节数。"""
    base = Path(root)
    return sum(f.stat().st_size for f in base.rglob("*") if f.is_file())
```

### 练习

1. 用 `pathlib` 重写一段基于字符串拼接的路径代码。
2. 找出目录下所有 `.txt` 文件并打印字节数。

### 注意事项

- 优先 `Path` 而非 `os.path`，可读性与跨平台性更好。
- `glob("**/*")` 递归较慢，大目录慎用。

### 常见错误

- 用 `+` 拼路径，在 Windows 上混用 `/` 与 `\`。
- `mkdir()` 不加 `parents=True` 时父目录不存在报错。

## csv-json

### 理论

CSV 适合表格数据，JSON 适合嵌套结构。Python 标准库 `csv` 与 `json` 提供读写支持；JSON 与 Python 字典/列表几乎一一对应。

### 代码

```python
import csv, json

# CSV 写
with open("scores.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["name", "score"])
    writer.writeheader()
    writer.writerow({"name": "张三", "score": 95})

# CSV 读
with open("scores.csv", "r", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))
print(rows)

# JSON
data = {"name": "李四", "tags": ["python", "ai"], "score": 88}
with open("user.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print(json.load(open("user.json", encoding="utf-8")))
```

### 示例

```python
import json

def load_config(path: str) -> dict:
    """读取 JSON 配置，失败时返回空字典。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
```

### 练习

1. 把字典列表导出为 CSV，再读回为列表。
2. 用 JSON 保存/加载一个嵌套的配置对象。

### 注意事项

- CSV 写文件建议 `newline=""`，避免多空行。
- JSON 用 `ensure_ascii=False` 保留中文。

### 常见错误

- CSV 数字列读进来全是字符串，未做类型转换。
- 手拼 JSON 字符串而非 `json.dumps`，容易转义出错。

## os-path

### 理论

`os` 与 `os.path` 提供操作系统交互：环境变量、目录操作、路径判断与拼接。虽被 `pathlib` 部分替代，但遍历目录、读取环境变量仍常用。

### 代码

```python
import os

print(os.getcwd())
print(os.environ.get("PATH", "")[:40])
print(os.path.join("a", "b", "c.txt"))
print(os.path.exists("data.txt"), os.path.isdir("logs"))

for root, dirs, files in os.walk("."):
    for name in files:
        print(os.path.join(root, name))
```

### 示例

```python
import os

def safe_getenv(key: str, default: str = "") -> str:
    """读取环境变量，缺失时返回默认值。"""
    value = os.environ.get(key)
    return value if value is not None else default
```

### 练习

1. 遍历项目目录，打印所有 `.py` 文件的相对路径。
2. 读取环境变量并给默认值。

### 注意事项

- 敏感信息（密钥）从环境变量读取，切忌硬编码。
- `os.walk` 返回的是生成器，可边遍历边处理。

### 常见错误

- 直接 `os.environ["KEY"]` 在变量缺失时抛 `KeyError`。
- 修改 `dirs` 列表会影响遍历，但易误用。

## file-batch-rename

### 理论

批量重命名是典型的自动化任务：遍历目录 → 按规则生成新名字 → `Path.rename()`。关键在「先规划、后执行」，并能预览与回滚。

### 代码

```python
from pathlib import Path

def batch_rename(folder: str, prefix: str, dry_run: bool = True) -> list[tuple[str, str]]:
    """给目录下所有文件加前缀，dry_run 时只预览。"""
    plans: list[tuple[str, str]] = []
    for index, path in enumerate(sorted(Path(folder).iterdir()), start=1):
        if not path.is_file():
            continue
        new_name = f"{prefix}{index:03d}{path.suffix}"
        plans.append((path.name, new_name))
        if not dry_run:
            path.rename(path.with_name(new_name))
    return plans

for old, new in batch_rename("photos", "img_", dry_run=True):
    print(f"{old} -> {new}")
```

### 示例

```python
from pathlib import Path

def rename_suffix(folder: str, old: str, new: str) -> int:
    """把某后缀统一改名为另一种后缀，返回修改数量。"""
    count = 0
    for path in Path(folder).glob(f"*{old}"):
        path.rename(path.with_suffix(new))
        count += 1
    return count
```

### 练习

1. 实现按拍摄日期重命名的批处理（先用文件名占位）。
2. 加一个 `--dry-run` 开关，先预览再执行。

### 注意事项

- 永远先 dry-run 再真正执行，避免不可逆。
- 目标名冲突时要处理（跳过或加序号）。

### 常见错误

- 边遍历边改名，导致遍历器混乱或重复处理。
- 覆盖了已存在的同名文件造成数据丢失。

## log-parsing-basics

### 理论

日志解析即把非结构化文本转成结构化数据。常见手段：字符串 `split()`、`startswith()`、正则 `re`。解析前先抽样观察格式，再写规则。

### 代码

```python
import re
from collections import Counter

LINE_RE = re.compile(r"^(?P<ts>\S+ \S+) \[(?P<level>\w+)\] (?P<msg>.*)$")

def parse_line(line: str) -> dict | None:
    """解析单行日志，返回结构化字典或 None。"""
    m = LINE_RE.match(line.strip())
    return m.groupdict() if m else None

text = """2026-01-01 08:00:01 [INFO] 启动
2026-01-01 08:00:02 [ERROR] 连接超时
2026-01-01 08:00:03 [ERROR] 重试失败"""
levels = Counter(r["level"] for line in text.splitlines() if (r := parse_line(line)))
print(levels)  # Counter({'ERROR': 2, 'INFO': 1})
```

### 示例

```python
from pathlib import Path
from collections import Counter

def count_levels(path: str) -> Counter:
    """统计日志文件中各等级出现次数。"""
    counter: Counter = Counter()
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if "[" in line and "]" in line:
            level = line.split("[", 1)[1].split("]", 1)[0]
            counter[level] += 1
    return counter
```

### 练习

1. 从日志中提取所有错误消息并去重统计。
2. 统计每分钟的日志条数。

### 注意事项

- 正则要加 `^$` 锚点，避免部分匹配错行。
- 大日志逐行读，不要一次性 `read()`。

### 常见错误

- 正则不加锚点，导致匹配到无关行。
- 时间格式多样时直接字符串比较，排序错误。

## config-file

### 理论

配置与代码分离是好工程习惯。常见格式：`.ini`（`configparser`）、`.json`、`.yaml`、`.env`。原则：环境相关配置走环境变量，结构化配置走文件并给默认值。

### 代码

```python
import configparser

cfg = configparser.ConfigParser()
cfg["db"] = {"host": "localhost", "port": "5432", "user": "app"}
cfg["log"] = {"level": "INFO"}

with open("app.ini", "w", encoding="utf-8") as f:
    cfg.write(f)

read = configparser.ConfigParser()
read.read("app.ini", encoding="utf-8")
print(read["db"]["host"], read.getint("db", "port"))
```

### 示例

```python
import json
from pathlib import Path

DEFAULTS = {"debug": False, "page_size": 20}

def load_settings(path: str = "settings.json") -> dict:
    """读取 JSON 配置并与默认值合并。"""
    merged = dict(DEFAULTS)
    if Path(path).exists():
        merged.update(json.loads(Path(path).read_text(encoding="utf-8")))
    return merged
```

### 练习

1. 用 `configparser` 读写多段配置。
2. 实现「环境变量覆盖配置文件」的优先级逻辑。

### 注意事项

- 配置里不要存明文密码，用环境变量或密钥管理。
- 提供 `DEFAULTS` 保证缺配置也能运行。

### 常见错误

- INI 值都是字符串，忘记 `getint`/`getboolean`。
- 配置文件缺失时直接崩溃，未做兜底。
