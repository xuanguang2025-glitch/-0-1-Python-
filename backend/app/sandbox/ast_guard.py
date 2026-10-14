r"""用户代码 AST 白名单校验（替代字符串黑名单）。

背景：`docs/SANDBOX.md` 声明本机 LocalRunner 只是「尽力而为」的降级执行，
但**字符串黑名单在 Python 上必然可绕过**（QA 已实测绕过）：

    __import__("os").system("echo PWNED")     # 双引号不匹配黑名单
    getattr(os, "system")("echo PWNED")       # 反射拿函数再调用
    p = "C:/Windows/win.ini"; open(p).read()  # 间接路径
    os.listdir("C:/")                         # 枚举任意目录

因此本模块改为**结构化校验**：把源码解析成 AST，只按「节点类型 + 属性名 +
导入模块」判断，不依赖任何字符串书写形式（单双引号、f-string、变量拼接都无法绕过）。

校验项（命中即 `security_error`，不执行）：

| 规则 | 判定依据 |
|---|---|
| `syntax_error` | `ast.parse` 失败（解析失败必须拒绝，否则 `compile` 类技巧可绕过） |
| `import_not_allowed` | `Import` / `ImportFrom` 的模块根不在白名单（复用 `SANDBOX_ALLOWED_IMPORTS`） |
| `import_dangerous_name` | `from os import system` / `from os import chdir` 这类「白名单模块 + 危险名」 |
| `dangerous_call` | 调用 `eval/exec/compile/__import__/globals/locals/getattr/setattr/delattr/vars/breakpoint` |
| `dangerous_attribute` | 属性名命中全局黑名单（`system/popen/fork/exec*/kill*/spawn*/listdir/walk/scandir/rmtree/chmod/chown/putenv/...`） |
| `dangerous_module_attribute` | 模块感知的属性黑名单（`os.remove`、`os.chdir`、`os.makedirs`、`shutil.rmtree`、`Path.unlink`…），避免误杀 `str.replace` / `list.remove` / `dict.get` |
| `dunder_attribute` | 访问 `__class__` / `__globals__` / `__subclasses__` / `__code__` 等 dunder（仅放行 `__name__`） |
| `open_absolute_path` | `open()` 首参是绝对路径（`C:\`、`\\server\share`、`/etc/...`）或含 `..` |
| `open_dynamic_path` | `open()` 首参不是字面量（无法静态判定 → 失败关闭） |
| `path_literal` | 敏感绝对路径字面量出现在 `open()` / `Path()` **实参位置**（不全局检查，避免误杀 `print('/usr')`） |
| `path_constructor_escape` | `Path()` 构造参数含 `..`（`Path('../x').write_text()` 逃逸） |
| `shell_injection` | 字符串常量含 `rm -rf` / `cmd.exe` / `powershell` / `:(){` 等命令注入特征 |

**有意不拦的**（避免误杀正常教学代码，附理由）：

- 多文件项目里**本次提交自带**的模块（`from utils.helper import add`）：
  按提交范围局部放行，见 `local_module_names()`；
- `input()`：OJ 判题与交互式练习**必须**能用（`name = input()`），沙箱内 stdin 由
  父进程写入且无 stdin 时抛 `EOFError`，不构成逃逸；QA 的绕过手法里不含 `input`。
- `sys.exit(0)` / `exit()` / `quit()`：OJ 标准写法（stage-16 课程正文即用到），
  最坏只是退出当前子进程，而子进程本来就会被超时 kill / rlimit 收口。
- `os.path.*` / `dict.get` / `str.replace` / `list.remove`：通过「模块感知黑名单 +
  精确属性名」而非「子串黑名单」实现，天然不误伤（见 `test_sandbox_security.py` 正向用例）。
- `os.environ.get(...)`：只读环境变量是合法教学内容（stage-07 课程正文即用到），
  写环境变量（`putenv`）才禁止。
- 纯展示用途的路径字符串（`print("path:", "/usr", "/tmp")`）：`path_literal` 只在
  `open()` / `Path()` 实参位置检查，不扫描所有字符串常量。
- `Path(变量)`：`Path(filename)` 是文件处理练习的常见写法，非字面量参数不做静态
  判定（失败关闭会误杀）；绝对路径 / `..` 的**字面量**参数仍被拦截。
- 工作目录内建目录：`os.mkdir` / `os.makedirs` 被整体拦截（可任意建目录，QA 实测），
  正当需求用 `pathlib.Path('sub').mkdir()`（相对路径，未拦截）。
- `os.remove`：保留拦截（可删工作目录外文件的前提是路径已逃逸，而逃逸路径本身
  会被 `open` / `Path` / `chdir` 规则拦下；删自己刚建的文件用 `Path(...).unlink()`
  同样被拦，属可接受的权衡 —— QA 复核 8 已记录该误杀场景）。
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from app.sandbox.protocol import DEFAULT_ALLOWED_MODULES

#: 允许导入的模块根（Settings 不可用时的兜底白名单，与 config 默认值保持一致）
FALLBACK_ALLOWED_IMPORTS: frozenset[str] = frozenset(DEFAULT_ALLOWED_MODULES) | frozenset(
    {
        "os",
        "io",
        "csv",
        "pathlib",
        "time",
        "copy",
        "operator",
        "enum",
        "dataclasses",
        "abc",
        "textwrap",
        "unicodedata",
        "statistics",
        "decimal",
        "fractions",
        "hashlib",
        "base64",
        "secrets",
        "calendar",
        "uuid",
        "keyword",
        "argparse",
        "pprint",
        "numbers",
        "array",
        "queue",
        "struct",
        "zlib",
        "string",
    }
)

#: 全局危险属性名：这些名字在任何对象上都没有正当教学用途，命中即拒。
#: 刻意**不含** `remove` / `replace` / `rename` / `get` —— 那是 `list.remove`、
#: `str.replace` 等常用方法的合法名字，改由 `MODULE_ATTR_BLOCKLIST` 按模块精确拦截。
BLOCKED_ATTRS: frozenset[str] = frozenset(
    {
        # 进程 / 命令执行
        "system",
        "popen",
        "fork",
        "forkpty",
        "kill",
        "killpg",
        "posix_spawn",
        "startfile",
        "spawnl",
        "spawnle",
        "spawnlp",
        "spawnlpe",
        "spawnv",
        "spawnve",
        "spawnvp",
        "spawnvpe",
        "execl",
        "execle",
        "execlp",
        "execlpe",
        "execv",
        "execve",
        "execvp",
        "execvpe",
        # 环境变量写入
        "putenv",
        "unsetenv",
        # 文件系统破坏
        "rmtree",
        "chmod",
        "chown",
        "chroot",
        "truncate",
        "removedirs",
        "scandir",
        "listdir",
        "walk",
        # 反射 / 动态执行（作为属性名出现时同样危险，如 `builtins.eval`）
        "eval",
        "exec",
        "compile",
        "__import__",
        "globals",
        "locals",
        "getattr",
        "setattr",
        "delattr",
        "vars",
        "breakpoint",
        "memoryview",
    }
)

#: 模块感知的属性黑名单：`(模块根, 属性名)` 命中即拒。
#: 这样 `os.remove` 被拦，而 `mylist.remove(x)` / `"a-b".replace("-", "_")` 不受影响。
#:
#: 收录原则（按 QA 实测的影响证明，而非名字听起来危险）：
#: - 破坏 / 越出工作目录：`chdir`（`os.chdir('..')` 之后所有相对路径读写都落在
#:   沙箱外，QA 用父目录可写证明文件复现）、`mkdir` / `makedirs`（可任意建目录）、
#:   `remove` / `unlink` / `rmdir` / `rmtree`（删文件）；
#: - 目录内建目录的正当需求用 `pathlib.Path.mkdir()`（相对路径，未被拦截）。
MODULE_ATTR_BLOCKLIST: Mapping[str, frozenset[str]] = {
    "os": frozenset(
        {
            "remove",
            "unlink",
            "rmdir",
            "rename",
            "replace",
            "symlink",
            "link",
            "removeprefix",
            "removesuffix",
            "chdir",
            "mkdir",
            "makedirs",
        }
    ),
    "shutil": frozenset({"rmtree", "move", "disk_usage"}),
    "pathlib": frozenset(
        {"unlink", "rmtree", "chmod", "rename", "replace", "symlink_to", "hardlink_to", "touch"}
    ),
    "io": frozenset({"unlink", "remove", "rmdir"}),
}

#: 危险函数名（作为 `Name` 被调用时命中即拒）。
#: **不含 `input`**：判题与交互练习必须可用，理由见模块 docstring。
#: **不含 `exit` / `quit`**：OJ 标准写法 `sys.exit(0)`（stage-16 课程正文即用到）
#: 必须放行 —— 它们最坏只是退出当前子进程，而子进程本来就会被超时 kill /
#: rlimit 收口，不构成逃逸；早期把两者列入黑名单属于误杀（QA 复核 8 复现）。
BLOCKED_CALL_NAMES: frozenset[str] = frozenset(
    {
        "__import__",
        "eval",
        "exec",
        "compile",
        "globals",
        "locals",
        "vars",
        "getattr",
        "setattr",
        "delattr",
        "breakpoint",
    }
)

#: `from <白名单模块> import <危险名>` 的危险名（模块本身合法，但名字致命）
DANGEROUS_IMPORTED_NAMES: frozenset[str] = BLOCKED_ATTRS | BLOCKED_CALL_NAMES | frozenset(
    {"system", "popen", "fork", "spawn", "exec", "eval", "compile"}
)

#: 命令注入特征（字符串常量内出现即拒）
SHELL_INJECTION_MARKERS: tuple[str, ...] = (
    "rm -rf",
    "rm -fr",
    "cmd.exe",
    "cmd /c",
    "powershell",
    "pwsh",
    ":(){",
    "chmod 777",
    "curl ",
    "wget ",
    "bash -c",
    "sh -c",
    "net user",
    "reg add",
    "invoke-expression",
    "nc -e",
)

#: 敏感绝对路径前缀（POSIX）。出现在字符串常量里即拒（覆盖 `open(p)` 间接引用）。
_SENSITIVE_POSIX_PREFIXES: tuple[str, ...] = (
    "/etc",
    "/proc",
    "/sys",
    "/dev",
    "/boot",
    "/root",
    "/home",
    "/usr",
    "/bin",
    "/sbin",
    "/lib",
    "/opt",
    "/srv",
    "/var",
    "/tmp",
    "/private",
    "/Users",
)

#: Windows 盘符 / UNC 路径（任意盘符都算敏感：工作目录由沙箱分配，不可能是绝对盘符）
_WINDOWS_ABS_RE = re.compile(r"^[A-Za-z]:[\\/]")

#: 仅放行的 dunder（`if __name__ == "__main__"` 是标准写法）
_ALLOWED_DUNDERS: frozenset[str] = frozenset({"__name__", "__doc__", "__file__"})


class GuardViolation(Exception):
    """AST 校验失败：携带命中的规则名、说明与行号。"""

    def __init__(self, rule: str, message: str, line: int = 0, filename: str = "") -> None:
        super().__init__(message)
        self.rule = rule
        self.message = message
        self.line = int(line or 0)
        self.filename = filename

    def describe(self) -> str:
        """生成可直接展示给用户的说明（含规则名与位置）。"""
        location = f"{self.filename}:{self.line}" if self.filename and self.line else ""
        suffix = f"（{location}）" if location else ""
        return f"AST 校验拒绝 [{self.rule}]：{self.message}{suffix}"

    def __str__(self) -> str:  # pragma: no cover - 交由 describe() 输出
        return self.describe()


def _is_sensitive_absolute_path(text: str) -> bool:
    """判断字符串常量是否为敏感绝对路径。"""
    candidate = text.strip().strip('"').strip("'")
    if not candidate:
        return False
    if _WINDOWS_ABS_RE.match(candidate) or candidate.startswith("\\\\"):
        return True
    if candidate.startswith("~"):
        return True
    lowered = candidate.replace("\\", "/").lower()
    return any(lowered == prefix or lowered.startswith(prefix + "/") for prefix in _SENSITIVE_POSIX_PREFIXES)


def _has_traversal(text: str) -> bool:
    """判断路径是否包含 `..` 片段。"""
    normalized = text.replace("\\", "/")
    return any(part == ".." for part in normalized.split("/"))


def _dotted_name(node: ast.AST) -> str:
    """把 `a.b.c` 形式的节点还原为字符串（无法还原时返回空串）。"""
    parts: list[str] = []
    current: ast.AST = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
        return ".".join(reversed(parts))
    return ""


def _root_name(dotted: str) -> str:
    """取点分表达式的根名（`shutil.rmtree` → `shutil`）。"""
    return dotted.split(".", 1)[0] if dotted else ""


@dataclass
class _ImportCollector(ast.NodeVisitor):
    """预扫描：收集「本地名 → 模块名」的导入映射（用于模块感知判定）。"""

    aliases: dict[str, str]

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802 - ast 命名
        for item in node.names:
            self.aliases[item.asname or item.name.split(".")[0]] = item.name

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802 - ast 命名
        module = node.module or ""
        for item in node.names:
            self.aliases[item.asname or item.name] = f"{module}.{item.name}" if module else item.name


class _SecurityVisitor(ast.NodeVisitor):
    """AST 白名单校验主体。"""

    def __init__(self, allowed_imports: frozenset[str], filename: str) -> None:
        self.allowed = allowed_imports
        self.filename = filename
        self.module_aliases: dict[str, str] = {}

    # -------------------------------------------------------------- 违规构造
    def _violation(self, rule: str, message: str, node: ast.AST) -> GuardViolation:
        """构造带行号的违规对象。"""
        return GuardViolation(rule, message, getattr(node, "lineno", 0), self.filename)

    # ------------------------------------------------------------------ import
    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802 - ast 命名
        """`import x` / `import x as y`：模块根必须在白名单内。"""
        for item in node.names:
            root = item.name.split(".")[0]
            if root not in self.allowed:
                raise self._violation(
                    "import_not_allowed",
                    f"模块 {item.name!r} 不在允许导入的白名单内（允许：{_preview(self.allowed)}）",
                    node,
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802 - ast 命名
        """`from x import y`：模块根须在白名单内，且不能导入危险名。"""
        module = node.module or ""
        root = module.split(".")[0]
        if root not in self.allowed:
            raise self._violation(
                "import_not_allowed",
                f"模块 {module!r} 不在允许导入的白名单内（允许：{_preview(self.allowed)}）",
                node,
            )
        module_blocked = MODULE_ATTR_BLOCKLIST.get(root, frozenset())
        for item in node.names:
            if item.name == "*":
                continue
            if item.name in DANGEROUS_IMPORTED_NAMES:
                raise self._violation(
                    "import_dangerous_name",
                    f"禁止导入 {module}.{item.name}",
                    node,
                )
            # `from os import chdir` 与 `os.chdir` 等效，必须同样拦截
            if item.name in module_blocked:
                raise self._violation(
                    "import_dangerous_name",
                    f"禁止导入 {module}.{item.name}（可越出工作目录）",
                    node,
                )
        self.generic_visit(node)

    # ------------------------------------------------------------------ 调用
    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802 - ast 命名
        """函数调用：危险函数名、`open()`/`Path()` 路径规则、模块感知黑名单。"""
        func = node.func
        qualified = self._qualified_call_name(func)
        if isinstance(func, ast.Name):
            if func.id in BLOCKED_CALL_NAMES:
                raise self._violation("dangerous_call", f"禁止调用 {func.id}()", node)
            if func.id == "open":
                self._check_open_call(node)
        else:
            dotted = _dotted_name(func)
            tail = dotted.rsplit(".", 1)[-1] if dotted else ""
            root = _root_name(dotted)
            if tail in BLOCKED_CALL_NAMES and root in self.module_aliases:
                raise self._violation("dangerous_call", f"禁止调用 {dotted}()", node)
            if tail == "open":
                self._check_open_call(node)
        # 模块感知黑名单的调用形态：`os.chdir('..')`、`from os import chdir as c; c('..')`
        self._check_blocked_module_call(qualified, node)
        # `Path('../x').write_text()`：构造参数上跳即逃逸，与 chdir 同理
        if qualified == "pathlib.Path":
            self._check_path_constructor(node)
        self.generic_visit(node)

    def _qualified_call_name(self, func: ast.AST) -> str:
        """解析调用目标的限定名（结合导入别名），无法静态解析时返回点分名或空串。

        - `from pathlib import Path` 后的 `Path(...)` → `pathlib.Path`；
        - `import pathlib as pl` 后的 `pl.Path(...)` → `pathlib.Path`；
        - `import os` 后的 `os.remove(...)` → `os.remove`；
        - 未导入就直接写的 `os.remove(...)` → `os.remove`（失败关闭，照样拦）。
        """
        if isinstance(func, ast.Name):
            return self.module_aliases.get(func.id, "")
        dotted = _dotted_name(func)
        if not dotted:
            return ""
        root, _, rest = dotted.partition(".")
        alias = self.module_aliases.get(root)
        if alias is None:
            return dotted
        return f"{alias}.{rest}" if rest else alias

    def _check_blocked_module_call(self, qualified: str, node: ast.Call) -> None:
        """调用模块黑名单内的函数（覆盖 `from x import y` / `import x as z` 的别名形态）。"""
        if not qualified or "." not in qualified:
            return
        module_root, _, attr = qualified.rpartition(".")
        blocked = MODULE_ATTR_BLOCKLIST.get(module_root)
        if blocked and attr in blocked:
            raise self._violation(
                "dangerous_module_attribute",
                f"禁止调用 {qualified}()",
                node,
            )

    def _check_path_constructor(self, node: ast.Call) -> None:
        """`Path(...)` 构造参数：字面量不得是绝对路径或含 `..`（防目录逃逸）。

        `Path('../x').write_text(...)` 与 `os.chdir('..')` 等效：逃逸后相对路径
        读写都落在沙箱工作目录之外（QA 已用父目录证明文件复现）。

        非字面量参数（变量 / 函数返回值）不做静态判定：`Path(filename)` 是文件
        处理练习的常见写法，失败关闭会误杀教学代码；残留风险由「本机执行器只是
        降级模式」的定位消化（远程沙箱另有 rlimit / unshare 边界）。
        """
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                if _is_sensitive_absolute_path(arg.value):
                    raise self._violation(
                        "path_literal", f"禁止在 Path() 中引用绝对路径 {arg.value!r}", node
                    )
                if _has_traversal(arg.value):
                    raise self._violation(
                        "path_constructor_escape",
                        f"禁止在 Path() 中使用包含 '..' 的路径 {arg.value!r}",
                        node,
                    )

    def _check_open_call(self, node: ast.Call) -> None:
        """`open(...)` 第一个实参必须是**相对字面量路径**（失败关闭）。"""
        if not node.args:
            raise self._violation("open_dynamic_path", "open() 缺少路径参数，无法静态校验", node)
        first = node.args[0]
        if not isinstance(first, ast.Constant) or not isinstance(first.value, str):
            raise self._violation(
                "open_dynamic_path",
                "open() 的路径必须是字符串字面量（沙箱只允许打开工作目录内的相对路径）",
                node,
            )
        raw = first.value
        if _is_sensitive_absolute_path(raw):
            raise self._violation("open_absolute_path", f"禁止访问绝对路径 {raw!r}", node)
        if _has_traversal(raw):
            raise self._violation("open_absolute_path", f"禁止使用包含 '..' 的路径 {raw!r}", node)
        # 收窄后的 `path_literal`：仅当敏感绝对路径字面量出现在 open() 实参位置才拒绝
        # （纯展示用法如 `print("path:", "/usr")` 放行，见 visit_Constant 注释）。
        for arg in node.args:
            if (
                isinstance(arg, ast.Constant)
                and isinstance(arg.value, str)
                and _is_sensitive_absolute_path(arg.value)
            ):
                raise self._violation(
                    "path_literal", f"禁止在 open() 中引用绝对路径 {arg.value!r}", node
                )

    # ------------------------------------------------------------------ 属性
    def visit_Attribute(self, node: ast.Attribute) -> None:  # noqa: N802 - ast 命名
        """属性访问：全局黑名单 + 模块感知黑名单 + dunder 白名单。"""
        attr = node.attr
        if attr.startswith("__") and attr.endswith("__") and attr not in _ALLOWED_DUNDERS:
            raise self._violation("dunder_attribute", f"禁止访问 {attr}", node)
        if attr in BLOCKED_ATTRS:
            raise self._violation("dangerous_attribute", f"禁止访问属性 {attr}", node)

        dotted = _dotted_name(node)
        root = _root_name(dotted)
        if dotted and root in self.module_aliases:
            module_root = _root_name(self.module_aliases[root])
            blocked = MODULE_ATTR_BLOCKLIST.get(module_root)
            if blocked and attr in blocked:
                raise self._violation(
                    "dangerous_module_attribute",
                    f"禁止访问 {self.module_aliases[root]}.{attr}",
                    node,
                )
        self.generic_visit(node)

    # -------------------------------------------------------------- 字符串常量
    def visit_Constant(self, node: ast.Constant) -> None:  # noqa: N802 - ast 命名
        """字符串常量：仅全局检查命令注入特征。

        `path_literal`（敏感绝对路径）**不在这里全局检查**：那会把
        `print("path example:", "/usr", "/tmp")` 这类纯展示用法一并误杀
        （QA 复核 8 复现，误伤面覆盖课程正文里的路径示例）。路径语义位置
        （`open()` / `Path()` 实参）的检查见 `_check_open_call` 与
        `_check_path_constructor` —— 那里才是「字符串真的被当作路径用」的地方。
        """
        if isinstance(node.value, str):
            lowered = node.value.lower()
            for marker in SHELL_INJECTION_MARKERS:
                if marker in lowered:
                    raise self._violation(
                        "shell_injection", f"字符串包含命令注入特征 {marker!r}", node
                    )
        self.generic_visit(node)


def _preview(items: Iterable[str], limit: int = 12) -> str:
    """白名单预览（避免错误信息过长）。"""
    ordered = sorted(items)
    head = ", ".join(ordered[:limit])
    return head + ("…" if len(ordered) > limit else "")


def resolve_allowed_imports(allowed_imports: Sequence[str] | None = None) -> frozenset[str]:
    """解析最终生效的导入白名单：显式参数 > Settings > 内置兜底。"""
    if allowed_imports:
        return frozenset(str(item).split(".")[0].strip() for item in allowed_imports if str(item).strip())
    try:
        from app.core.config import get_settings

        configured = get_settings().allowed_imports
    except Exception:  # noqa: BLE001 - 配置不可用时用兜底白名单
        configured = []
    if configured:
        return frozenset(str(item).split(".")[0].strip() for item in configured if str(item).strip())
    return FALLBACK_ALLOWED_IMPORTS


def check_source(
    source: str,
    *,
    filename: str = "main.py",
    allowed_imports: Sequence[str] | None = None,
) -> GuardViolation | None:
    """校验单份源码；通过返回 `None`，否则返回 `GuardViolation`。"""
    text = source or ""
    if not text.strip():
        return None

    # 预扫描导入映射（模块感知判定需要先知道哪些名字是模块）
    collector = _ImportCollector(aliases={})
    try:
        tree = ast.parse(text, filename=filename or "main.py")
    except SyntaxError as exc:
        return GuardViolation("syntax_error", f"代码语法错误，无法通过安全校验：{exc.msg}", exc.lineno or 0, filename)
    except (ValueError, MemoryError, RecursionError) as exc:  # 空字节 / 超深嵌套等
        return GuardViolation("syntax_error", f"代码无法解析，已拒绝执行：{exc}", 0, filename)
    collector.visit(tree)

    visitor = _SecurityVisitor(resolve_allowed_imports(allowed_imports), filename)
    visitor.module_aliases = collector.aliases
    try:
        visitor.visit(tree)
    except GuardViolation as violation:
        return violation
    except RecursionError:
        return GuardViolation("syntax_error", "代码嵌套过深，无法通过安全校验", 0, filename)
    return None


def local_module_names(files: Mapping[str, str], *, skip_paths: Iterable[str] = ()) -> frozenset[str]:
    """从提交的文件列表推导「本次提交自带的模块名」。

    多文件项目（`docs/API.md` §2.8 `/api/projects/{id}/run`）需要 `main.py` 互相
    import，例如 `from utils.helper import add`。这些模块名不属于
    `SANDBOX_ALLOWED_IMPORTS`，但它们是**用户自己刚提交的文件**，因此按提交范围
    局部放行（而不是把白名单整体放宽）。

    注意：放行范围仅限本次 `files` 里出现过的模块路径，用户并不能借此 import
    未提交的系统模块（例如提交 `os.py` 只能 import 到他自己的 `os.py`）。
    """
    skip = {str(item).replace("\\", "/").split("/")[-1] for item in skip_paths}
    names: set[str] = set()
    for path in files:
        normalized = str(path).replace("\\", "/").strip("/")
        if not normalized:
            continue
        parts = normalized.split("/")
        if parts[-1] in skip or not parts[-1].endswith(".py"):
            continue
        module_parts = parts[:-1] if parts[-1] == "__init__.py" else parts
        module_parts = [item[: -len(".py")] if item.endswith(".py") else item for item in module_parts]
        # 逐级加入包名与子模块名：utils → utils.helper
        for index in range(1, len(module_parts) + 1):
            candidate = ".".join(module_parts[:index])
            if candidate:
                names.add(candidate)
                names.add(candidate.split(".")[0])
    return frozenset(names)


def check_files(
    files: Mapping[str, str],
    *,
    allowed_imports: Sequence[str] | None = None,
    skip_paths: Iterable[str] = (),
) -> GuardViolation | None:
    """校验一组文件；`skip_paths` 中的文件（系统生成的引导文件）不参与校验。"""
    skip = {str(item) for item in skip_paths}
    skip_names = {item.replace("\\", "/").split("/")[-1] for item in skip}
    allowed = resolve_allowed_imports(allowed_imports) | local_module_names(
        files, skip_paths=skip_names
    )
    for path, content in files.items():
        name = str(path).replace("\\", "/").split("/")[-1]
        if path in skip or name in skip:
            continue
        violation = check_source(content, filename=str(path), allowed_imports=sorted(allowed))
        if violation is not None:
            return violation
    return None


__all__ = [
    "BLOCKED_ATTRS",
    "BLOCKED_CALL_NAMES",
    "DANGEROUS_IMPORTED_NAMES",
    "FALLBACK_ALLOWED_IMPORTS",
    "GuardViolation",
    "MODULE_ATTR_BLOCKLIST",
    "SHELL_INJECTION_MARKERS",
    "check_files",
    "check_source",
    "local_module_names",
    "resolve_allowed_imports",
]
