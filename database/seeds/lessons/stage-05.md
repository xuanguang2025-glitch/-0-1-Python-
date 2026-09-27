# 阶段 5 · 模块与包

## import-mechanism

### 理论

`import` 让 Python 按 `sys.path` 顺序查找模块文件并执行一次，把结果放进 `sys.modules` 缓存。三种写法：`import math`、`from math import sqrt`、`import numpy as np`。首次导入执行整个模块，后续导入直接复用缓存。

### 代码

```python
import math
from math import sqrt
import json as js

print(math.pi)            # 3.141592653589793
print(sqrt(16))           # 4.0
print(js.dumps({"a": 1}))  # {"a": 1}

import sys
print(sys.path[:2])       # 查看模块搜索路径前两项
```

### 示例

```python
# 查看模块来源与是否已缓存
import sys

import math
print(math.__file__)                # .../math.py 或内置
print("math" in sys.modules)        # True
```

### 练习

1. 分别用三种写法导入 `random` 并调用 `randint`。
2. 打印 `sys.path`，解释为什么同目录文件可以直接导入。
3. 故意导入不存在的模块，观察 `ModuleNotFoundError` 信息。

### 注意事项

- 导入顺序规范：标准库 → 第三方 → 本地模块。
- 不要 `from module import *`，会污染命名空间。
- 模块顶层代码会在导入时执行，避免放重副作用逻辑。

### 常见错误

- `ModuleNotFoundError: No module named 'xxx'` → 未安装或路径不对。
- 模块名与标准库同名（如自建 `json.py`）导致覆盖。
- 循环导入 → `ImportError: cannot import name ... (most likely due to a circular import)`。

## module-package

### 理论

一个 `.py` 文件就是一个模块；包含 `__init__.py` 的目录是包，可用点号分层：`from app.utils.text import slugify`。`__init__.py` 常用来聚合导出与定义包级常量。

### 代码

```text
project/
├── app/
│   ├── __init__.py
│   ├── utils/
│   │   ├── __init__.py
│   │   └── text.py
│   └── services/
│       ├── __init__.py
│       └── user_service.py
└── main.py
```

```python
# app/utils/__init__.py：聚合导出，方便外部短路径导入
from app.utils.text import slugify

__all__ = ["slugify"]
```

### 示例

```python
# app/services/user_service.py
from app.utils import slugify

def make_slug(name: str) -> str:
    """生成用户 slug。"""
    return slugify(name)

print(make_slug("Hello World"))   # hello-world
```

### 练习

1. 创建 `mypkg/` 包含 `__init__.py` 与两个模块，互相导入。
2. 在 `__init__.py` 中只导出对外 API（用 `__all__`）。
3. 画出你项目的模块依赖图并找出可疑的双向依赖。

### 注意事项

- 包名用小写短横线之外的合法标识符（目录名不能带 `-`）。
- `__all__` 只影响 `from x import *` 与文档，不限制直接导入。
- 深层包结构要控制层级，避免 `a.b.c.d.e` 这类过深导入。

### 常见错误

- 缺少 `__init__.py` → 老版本 Python 无法识别为包（命名空间包虽可行但易踩坑）。
- 目录名与已安装包重名导致导入错乱。
- `__init__.py` 做重计算导致导入变慢。

## name-main

### 理论

模块被直接运行 `python mod.py` 时 `__name__ == "__main__"`；被导入时 `__name__` 是模块名。用 `if __name__ == "__main__":` 把「脚本入口」与「可导入库」区分开。

### 代码

```python
"""可复用模块 + 可执行脚本的双模式写法。"""

def double(n: int) -> int:
    """返回 n 的两倍。"""
    return n * 2

def main() -> None:
    """命令行入口。"""
    print(double(21))

if __name__ == "__main__":
    main()
```

### 示例

```bash
$ python double_mod.py       # 直接运行 → 42
$ python -c "import double_mod as m; print(m.double(5))"   # 导入 → 10
```

### 练习

1. 把一个纯脚本改造成「可导入 + 可运行」双模式。
2. 给模块加 `main()` 参数解析（`sys.argv`）。
3. 验证导入模块时 `main()` 不会被执行。

### 注意事项

- 顶层不要写业务代码，全部收进 `main()`。
- 测试代码也应放 `if __name__ == "__main__"` 或用 pytest。
- 特殊模块名 `__main__` 在包内相对导入时行为不同，避免在包内直接运行子模块。

### 常见错误

- 导入模块时打印了一堆日志（副作用泄漏）。
- 在 `if __name__` 块中定义函数，导致导入时函数不存在。
- 相对导入在直接运行脚本时报 `attempted relative import with no known parent package`。

## pip-venv

### 理论

虚拟环境把项目依赖隔离到独立目录，避免全局污染与版本冲突。流程：`python -m venv .venv` → 激活 → `pip install` → 用 `requirements.txt` 锁定版本。

### 代码

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

python -m pip install fastapi uvicorn
python -m pip freeze > requirements.txt
python -m pip install -r requirements.txt
```

### 示例

```bash
# 国内网络建议使用镜像源
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
python -m pip list --outdated
```

### 练习

1. 新建项目并创建 `.venv`，安装 `requests` 后导出 `requirements.txt`。
2. 删除 `.venv` 后按 `requirements.txt` 还原环境。
3. 在 `.gitignore` 中加入 `.venv/`、`__pycache__/`、`*.pyc`。

### 注意事项

- 始终用 `python -m pip` 而非裸 `pip`，确保装到当前解释器。
- 提交代码时提交 `requirements.txt`，不提交 `.venv`。
- 生产部署锁定精确版本，避免自动升级引入不兼容。

### 常见错误

- `'pip' 不是内部或外部命令` → 虚拟环境未激活。
- 依赖装到了全局 → 未激活环境就用 `pip install`。
- `ERROR: Could not find a version that satisfies the requirement xxx` → 包名拼错或索引不可达，需配置镜像源。

## standard-library

### 理论

「内置电池」是 Python 的优势：`os`/`sys`（系统）、`json`（序列化）、`datetime`（时间）、`collections`（专用容器）、`itertools`（迭代工具）、`pathlib`（路径）、`re`（正则）、`math`/`random`（数值）。

### 代码

```python
import json
from collections import Counter, defaultdict, namedtuple
from datetime import datetime, timedelta

print(json.dumps({"名称": "小徐"}, ensure_ascii=False))   # {"名称": "小徐"}
print(datetime(2026, 9, 26) + timedelta(days=1))          # 2026-09-27 00:00:00
print(Counter("banana").most_common(2))                    # [('a', 3), ('n', 2)]

Point = namedtuple("Point", "x y")
print(Point(1, 2).x)                                       # 1

groups = defaultdict(list)
for word in ["apple", "avocado"]:
    groups[word[0]].append(word)
print(dict(groups))                                        # {'a': ['apple', 'avocado']}
```

### 示例

```python
import itertools

print(list(itertools.islice(itertools.count(1, 2), 5)))   # [1, 3, 5, 7, 9]
print(list(itertools.combinations("ABC", 2)))              # [('A', 'B'), ('A', 'C'), ('B', 'C')]
```

### 练习

1. 用 `Counter` 统计文本词频并输出 top3。
2. 用 `datetime` 计算两个日期相差天数。
3. 用 `itertools.groupby` 把已排序列表按首字符分组。

### 注意事项

- 优先用标准库而不是自己造轮子。
- `datetime.now()` 无时区信息，涉及时区用 `datetime.now(timezone.utc)`。
- `collections` 的容器在特定场景下性能与语义更优。

### 常见错误

- `KeyError` 未用 `defaultdict` / `get`。
- `json.dumps` 中文被转义 → 加 `ensure_ascii=False`。
- `datetime` 与 `date` 混用导致 `TypeError: can't subtract offset-naive and offset-aware datetimes`。

## project-layout

### 理论

清晰的目录结构能从第一眼告诉别人项目全貌：源码、测试、文档、配置、脚本分离。推荐 `src` 布局与统一配置目录 `configs/`，敏感配置走环境变量。

### 代码

```text
pythonlab/
├── src/                 # 源码（或直接用包名目录）
├── tests/               # 测试
├── docs/                # 文档
├── scripts/             # 运维/开发脚本
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
└── pyproject.toml
```

### 示例

```text
# .gitignore 关键项
.venv/
__pycache__/
*.pyc
.env
data/
*.db
```

### 练习

1. 按上面结构整理你已有项目。
2. 写 README 的四个必填段：项目简介、安装、运行、测试。
3. 用 `.env.example` 列出全部环境变量并说明含义。

### 注意事项

- 敏感信息（密钥）只放 `.env`，提交 `.env.example`。
- 数据文件与源码分开，避免混在包内被误打包。
- README 要能让新人 5 分钟内跑起来。

### 常见错误

- 把 `.env` 提交到仓库导致密钥泄露。
- `data/`、`*.db` 混入版本库，仓库迅速膨胀。
- 目录名含空格或中文，跨平台脚本易失败。

## create-module

### 理论

把自己的函数按职责拆到不同模块：文本处理进 `text.py`、时间处理进 `time.py`。每个模块只暴露必要的公开函数，私有助手函数用下划线前缀。

### 代码

```python
"""app/utils/text.py —— 文本工具模块。"""

def _normalize(text: str) -> str:
    """私有助手：统一空白。"""
    return " ".join(text.split())

def slugify(text: str) -> str:
    """把标题转成 URL 友好的 slug。"""
    return "-".join(_normalize(text).lower().split())

__all__ = ["slugify"]
```

```python
from app.utils.text import slugify

print(slugify("  Hello   Python  "))   # hello-python
```

### 示例

```python
"""职责拆分示例：一个模块一件事。"""

# time_utils.py
from datetime import datetime, timezone

def now_utc() -> datetime:
    """当前 UTC 时间。"""
    return datetime.now(timezone.utc)
```

### 练习

1. 把一段 200 行的脚本按职责拆成 3 个模块。
2. 给每个模块写模块级 docstring 与 `__all__`。
3. 用下划线前缀隐藏不该被外部调用的函数。

### 注意事项

- 模块名不要与标准库冲突（如 `time.py` 放在包内可接受，但顶层要与内置区分）。
- 一个模块只负责一类职责；工具模块不要反向依赖业务模块。
- 模块间尽量单向依赖，避免网状结构。

### 常见错误

- 模块顶层 import 时就连接数据库 → 导入即副作用。
- 把配置写死在模块里 → 无法在不同环境复用。
- 私有函数被外部调用 → 约定被破坏，重构时易挂。

## package-init

### 理论

`__init__.py` 是包的入口：可以留空、可以聚合导出、可以做版本声明。但应保持轻量，避免在导入时执行重逻辑。懒加载可借助模块级 `__getattr__`。

### 代码

```python
"""app/utils/__init__.py —— 聚合导出，保持轻量。"""

from app.utils.ids import new_uuid
from app.utils.text import slugify

__version__ = "1.0.0"
__all__ = ["new_uuid", "slugify", "__version__"]
```

```python
# 使用方：短路径导入
from app.utils import slugify, new_uuid
print(slugify("Hello World"), new_uuid()[:8])
```

### 示例

```python
"""惰性导出：首次访问属性时才导入重模块。"""

__all__ = ["heavy_client"]

def __getattr__(name: str):
    """按需导入，避免包导入即加载重依赖。"""
    if name == "heavy_client":
        from app.services.heavy import client
        return client
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

### 练习

1. 给已有包补一个 `__init__.py`，只导出 3 个核心函数。
2. 观察「导入包但不导入子模块」的启动耗时差异。
3. 用 `__getattr__` 实现一个惰性导出并验证。

### 注意事项

- 聚合导出让调用方更简洁，但要避免 `__init__` 形成环。
- `__version__` 建议单一来源（从 `pyproject.toml` 或常量模块读取）。
- 循环导入常由 `__init__.py` 的聚合导出引入，注意拆分。

### 常见错误

- `__init__.py` 导入子模块，子模块又导入包 → 循环导入。
- 在 `__init__.py` 里写 `print` 或初始化连接 → 每次导入都执行。
- `from pkg import *` 未定义 `__all__` → 导出不可控。

## relative-import

### 理论

相对导入用点号表示层级：`.sibling` 同级，`..parent` 上一级。它只能在**包内**使用，直接运行子模块会失败。循环导入发生时，把导入移到函数内部或抽取共用模块是常用解法。

### 代码

```python
"""app/services/user_service.py —— 相对导入写法。"""
from ..utils.text import slugify          # 上一级包的 utils
from .auth_service import hash_password   # 同级模块
```

```python
# 推荐：包内统一用绝对导入（更易读、重构友好）
from app.services.auth_service import hash_password
from app.utils.text import slugify
```

### 示例

```python
"""破解循环导入：把导入延迟到函数内部。"""

def process():
    """运行时才导入，避免模块级循环依赖。"""
    from app.services.report_service import build_report
    return build_report()
```

### 练习

1. 故意制造循环导入，观察报错信息。
2. 用三种方式修复循环导入（延迟导入 / 抽公共模块 / 改单向依赖）。
3. 把项目内所有 `from ..` 改成绝对导入并对比可读性。

### 常见错误

- `ImportError: attempted relative import with no known parent package` → 直接运行了包内子模块。
- `ImportError: cannot import name 'X' from partially initialized module` → 循环导入。
- 相对导入层级数写错（`..` 数量与目录深度不匹配）。
