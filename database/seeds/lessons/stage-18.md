# 阶段 18 · 真实项目开发

## git-basics

### 理论

Git 是分布式版本控制。核心概念：工作区、暂存区、仓库；提交（commit）记录快照。常用流程：`clone` → 改代码 → `add` → `commit` → `push`。分支隔离开发，合并集成。

### 代码

```bash
git init
git add .
git commit -m "feat: 初始化项目结构"

git checkout -b feature/login        # 新建并切换分支
git add app/auth.py
git commit -m "feat(auth): 实现登录接口"

git checkout main
git merge feature/login
git push origin main
```

### 示例

```bash
# 查看状态与历史
git status
git log --oneline --graph --decorate -10

# 撤销工作区改动（危险，谨慎）
git checkout -- file.py
```

### 练习

1. 初始化仓库并完成一次提交。
2. 新建分支开发一个功能再合并。

### 注意事项

- 提交信息遵循约定（feat/fix/docs…）。
- 谨慎使用 `reset --hard`、`push --force`。

### 常见错误

- 提交了密钥或大文件。
- 提交信息含糊（“update”）。

## project-layout-pro

### 理论

工程化项目结构提升可维护性：源码、测试、配置、文档分离；用 `pyproject.toml` 管理依赖与工具；用环境变量管理配置；`README` 说明用法。

### 代码

```text
myproject/
├── src/myapp/
│   ├── __init__.py
│   ├── core/          # 配置、工具
│   ├── models/        # 数据模型
│   └── api/           # 接口层
├── tests/
├── pyproject.toml
├── .env.example
└── README.md
```

```toml
# pyproject.toml
[project]
name = "myapp"
version = "0.1.0"
dependencies = ["fastapi", "sqlalchemy"]

[tool.ruff]
line-length = 100
```

### 示例

```python
# src 布局配合安装：pip install -e .
# 分层原则：接口层只做编排，业务逻辑放 service，数据访问放 repository
```

### 练习

1. 按 src 布局组织一个项目。
2. 写 `pyproject.toml` 声明依赖与 Lint 配置。

### 注意事项

- 配置与代码分离，密钥走环境变量。
- 分层清晰，避免循环依赖。

### 常见错误

- 所有代码堆在一个 `main.py`。
- 依赖用全局安装，环境不可复现。

## code-review

### 理论

代码评审（Code Review）在合并前发现缺陷、统一风格、分享知识。关注点：正确性、可读性、可维护性、性能、安全、测试覆盖。态度就事论事、提出改进而非指责。

### 代码

```python
# Before：可读性差
def f(l):
    r=[]
    for i in l:
        if i%2==0:r.append(i*i)
    return r

# After：清晰、类型注解、docstring
def even_squares(numbers: list[int]) -> list[int]:
    """返回所有偶数的平方。"""
    return [n * n for n in numbers if n % 2 == 0]
```

### 示例

```text
评审清单：
[ ] 命名是否表意？        [ ] 是否处理边界/异常？
[ ] 是否有类型注解？      [ ] 是否有测试？
[ ] 是否有重复代码？      [ ] 是否引入安全风险？
```

### 练习

1. 评审一段代码并列出至少三条改进。
2. 把一段重复逻辑重构为函数。

### 注意事项

- 小步提交，便于评审。
- 先理解意图再提意见。

### 常见错误

- 评审只挑格式，忽略逻辑缺陷。
- 反馈情绪化，打击协作。

## unit-testing

### 理论

单元测试验证最小可测单元（通常一个函数）的行为。三要素：安排（Arrange）、执行（Act）、断言（Assert）。好的测试快速、独立、可重复、自动判定。

### 代码

```python
def add(a: int, b: int) -> int:
    """求和。"""
    return a + b

def test_add() -> None:
    """测试 add 的基本与边界情况。"""
    assert add(1, 2) == 3
    assert add(-1, 1) == 0
    assert add(0, 0) == 0
```

### 示例

```python
import pytest

def divide(a: float, b: float) -> float:
    if b == 0:
        raise ValueError("除数不能为零")
    return a / b

def test_divide_ok() -> None:
    assert divide(10, 2) == 5

def test_divide_zero() -> None:
    with pytest.raises(ValueError):
        divide(1, 0)
```

### 练习

1. 为 `add` 写覆盖边界值的测试。
2. 为会抛异常的函数写测试。

### 注意事项

- 每个测试只验证一件事。
- 测试要独立，不依赖执行顺序。

### 常见错误

- 测试依赖外部网络/数据库（不稳定）。
- 一个测试塞入过多断言，失败难定位。

## pytest-basics

### 理论

pytest 是主流测试框架：用 `assert` 断言、用 `fixture` 提供测试数据/环境、用 `parametrize` 参数化、用 `-k`/`-m` 选择用例。比 unittest 更简洁。

### 代码

```python
import pytest

@pytest.fixture
def sample_data() -> list[int]:
    """共享测试数据。"""
    return [1, 2, 3, 4, 5]

@pytest.mark.parametrize("n,expected", [(2, True), (3, False), (4, True)])
def test_is_even(n: int, expected: bool) -> None:
    assert (n % 2 == 0) == expected

def test_sum(sample_data: list[int]) -> None:
    assert sum(sample_data) == 15
```

### 示例

```bash
# 常用命令
pytest -q                     # 安静模式
pytest -k "even"              # 按名字筛选
pytest --cov=myapp tests/     # 覆盖率
```

### 练习

1. 用 fixture 提供数据库会话并测试。
2. 用 `parametrize` 覆盖多组输入。

### 注意事项

- fixture 用 `yield` 做前置/后置清理。
- 覆盖率是参考，不等于质量。

### 常见错误

- fixture 作用域不当导致状态串扰。
- 只追求覆盖率，断言空洞。

## ci-cd

### 理论

CI（持续集成）每次提交自动跑测试与检查；CD（持续部署）自动构建发布。用 GitHub Actions 等流水线确保质量门禁，避免坏代码进主干。

### 代码

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: ruff check .
      - run: pytest -q
```

### 示例

```text
质量门禁顺序：
1) 格式/Lint   2) 类型检查   3) 单元测试   4) 构建   5) 部署
任一步失败即阻断合并。
```

### 练习

1. 写一个跑测试的 CI 配置。
2. 在 CI 中加入 Lint 与格式化检查。

### 注意事项

- 流水线要快，反馈及时。
- 密钥用 CI 的 Secrets，不入库。

### 常见错误

- CI 只跑测试不做其他检查。
- 把部署密钥明文写进配置文件。

## capstone-cli-tool

### 理论

综合项目一：命令行工具。要点：参数解析（`argparse`）、子命令、配置、错误处理、日志、打包（`pyproject.toml` 的 console_scripts）。把前面所学整合成一个可安装、可用的工具。

### 代码

```python
import argparse
import sys

def build_parser() -> argparse.ArgumentParser:
    """构建命令行解析器。"""
    parser = argparse.ArgumentParser(prog="notes", description="命令行记事本")
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="新增笔记")
    add.add_argument("text", help="笔记内容")

    sub.add_parser("list", help="列出笔记")
    return parser

def main(argv: list[str] | None = None) -> int:
    """CLI 入口，返回退出码。"""
    args = build_parser().parse_args(argv)
    if args.command == "add":
        print(f"已添加：{args.text}")
    elif args.command == "list":
        print("（暂无笔记）")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

### 示例

```toml
# pyproject.toml 中注册命令
# [project.scripts]
# notes = "myapp.cli:main"
# 安装后即可直接运行 `notes add "hello"`
```

### 练习

1. 为 CLI 增加 `delete` 子命令。
2. 把笔记持久化到本地文件。

### 注意事项

- 退出码规范（0 成功，非 0 失败）。
- 错误信息友好，别抛裸异常。

### 常见错误

- 子命令未 `required=True`，无参时静默。
- 直接在 `main` 里 `print` 调试，缺日志。

## capstone-web-api

### 理论

综合项目二：Web API 服务。整合 FastAPI + Pydantic + SQLAlchemy + 认证，提供完整 CRUD 与 JWT 鉴权，含统一响应、分页、错误处理、文档。是前后端分离项目的后端形态。

### 代码

```python
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Todo API")
_todos: dict[int, dict] = {}
_counter = 0

class TodoIn(BaseModel):
    title: str
    done: bool = False

@app.post("/api/todos", status_code=201)
async def create(todo: TodoIn) -> dict:
    """创建待办。"""
    global _counter
    _counter += 1
    _todos[_counter] = {"id": _counter, **todo.model_dump()}
    return {"success": True, "data": _todos[_counter]}

@app.get("/api/todos")
async def list_todos() -> dict:
    """列出全部待办。"""
    return {"success": True, "data": list(_todos.values())}

@app.delete("/api/todos/{todo_id}")
async def remove(todo_id: int) -> dict:
    """删除待办。"""
    if todo_id not in _todos:
        raise HTTPException(status_code=404, detail="未找到")
    _todos.pop(todo_id)
    return {"success": True, "data": {"id": todo_id}}
```

### 示例

```python
# 运行：uvicorn app:app --reload
# 文档：http://127.0.0.1:8000/docs
```

### 练习

1. 把内存存储换成 SQLite + SQLAlchemy。
2. 为接口加上 JWT 鉴权与分页。

### 注意事项

- 统一响应结构与错误码。
- 输入用 Pydantic 模型校验。

### 常见错误

- 校验缺失导致脏数据入库。
- 错误响应对前端不友好。

## capstone-data-app

### 理论

综合项目三：数据分析应用。整合 pandas + 可视化 + 报表产出：读入数据 → 清洗 → 分析 → 可视化 → 生成报表文件，并可封装为可复用脚本/函数。

### 代码

```python
from pathlib import Path
import pandas as pd

def analyze_sales(csv_path: str, out_dir: str = "reports") -> dict:
    """销售数据分析：总览、按地区聚合、导出报表。"""
    df = pd.read_csv(csv_path, encoding="utf-8")
    df = df.dropna(subset=["region", "amount"])
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)

    by_region = df.groupby("region")["amount"].agg(["sum", "mean", "count"])
    summary = {
        "total": float(df["amount"].sum()),
        "rows": int(len(df)),
        "top_region": by_region["sum"].idxmax() if not by_region.empty else None,
    }

    Path(out_dir).mkdir(exist_ok=True)
    by_region.to_csv(Path(out_dir) / "by_region.csv", encoding="utf-8")
    return summary
```

### 示例

```python
# 端口化流程：
# 1) 读入  2) 清洗  3) 聚合  4) 可视化(可选)  5) 导出
# 结果可复用为定时任务：每天生成销售日报
```

### 练习

1. 为分析结果加一张柱状图并保存。
2. 把该函数封装为可被定时任务调用的脚本。

### 注意事项

- 清洗步骤显式记录（删了多少行）。
- 报表命名带日期，便于追溯。

### 常见错误

- 未处理缺失值导致统计错误。
- 把分析逻辑与展示逻辑混在一起。
