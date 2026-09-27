"""运行时守卫：在**子进程内**安装限制（第二层防线）。

通过 `python -c` 引导代码注入：
    python -I -B -c "import sys; sys.path.insert(0, WORKDIR); import _plab_guard;
                     _plab_guard.install(...); import runpy; runpy.run_path(entry, run_name='__main__')"

覆盖：
1. `open()` 路径白名单（读写分离，禁 /etc/passwd、C:\\Windows\\win.ini 等）
2. `__import__` 黑名单（subprocess / ctypes / multiprocessing / importlib ...）
3. 模块属性清洗（os.system/os.popen/os.fork/os.kill、socket.socket、subprocess.*）
4. 网络禁用（socket 构造族）
5. 递归深度上限
6. stdout/stderr 字节预算（超出后静默丢弃并写 stderr 提示）
7. `input()` 调用次数上限，避免无 stdin 时无限阻塞

⚠️ 这是**尽力而为**的守卫，不是安全边界；真正的隔离依赖容器（见 docs/SANDBOX.md）。
"""

from __future__ import annotations

import builtins as _builtins
import io as _io
import os as _os
import sys as _sys
import tempfile as _tempfile
from typing import Any, Callable, Sequence

MAX_INPUT_CALLS = 2000

# 默认黑名单（顶层模块名），与 config.Settings.blocked_imports 合并
DEFAULT_BLOCKED_IMPORTS: tuple = (
    "subprocess",
    "multiprocessing",
    "ctypes",
    "cffi",
    "pty",
    "resource",
    "mmap",
    "telnetlib",
    "ftplib",
    "smtplib",
    "poplib",
    "imaplib",
    "webbrowser",
    "tkinter",
    "turtle",
    "pdb",
    "compileall",
    "py_compile",
    "venv",
    "ensurepip",
    "pip",
    "antigravity",
)

# 读取路径黑名单前缀（POSIX）
_DENY_PREFIX_POSIX = ("/etc", "/proc", "/sys", "/dev", "/boot", "/root", "/var", "/sbin", "/usr/sbin")
# 读取路径黑名单（Windows）
_DENY_WIN = ("\\windows\\", "\\programdata\\", "\\program files", "\\$recycle.bin\\")
# 敏感文件名（任意目录）
_DENY_NAMES = {"passwd", "shadow", "sudoers", "win.ini", "id_rsa", "id_dsa", ".env", ".npmrc", ".pypirc"}


class GuardViolation(Exception):
    """守卫拦截异常：用户代码触发了被禁止的操作。"""


class OutputLimitExceeded(Exception):
    """输出超出字节预算。"""


def _violation(name: str, detail: str = "") -> GuardViolation:
    """构造统一的拦截异常。"""
    message = f"[sandbox] '{name}' 已被沙箱禁用"
    if detail:
        message = f"{message}：{detail}"
    return GuardViolation(message)


class LimitedTextStream(_io.TextIOBase):
    """带字节预算的文本输出流：超限后静默丢弃剩余内容。"""

    def __init__(self, raw: Any, limit_bytes: int) -> None:
        self._raw = raw
        self._limit = max(1, int(limit_bytes))
        self._written = 0
        self.exceeded = False

    # ---- TextIOBase 协议 ----
    def write(self, text: str) -> int:
        if self.exceeded or not text:
            return 0
        data = text.encode("utf-8", "replace")
        remaining = self._limit - self._written
        if remaining <= 0:
            self._mark_exceeded()
            return 0
        truncated = len(data) > remaining
        if truncated:
            data = data[:remaining]
        self._written += len(data)
        self._raw.write(data.decode("utf-8", "replace"))
        self._raw.flush()
        if truncated:
            self._mark_exceeded()
        return len(text)

    def writelines(self, lines: Sequence[str]) -> None:  # type: ignore[override]
        for line in lines:
            self.write(line)

    def flush(self) -> None:
        try:
            self._raw.flush()
        except Exception:  # noqa: BLE001 - 输出通道已关闭时忽略
            pass

    def isatty(self) -> bool:
        return False

    def writable(self) -> bool:
        return True

    def readable(self) -> bool:
        return False

    def seekable(self) -> bool:
        return False

    def close(self) -> None:
        self.flush()

    def _mark_exceeded(self) -> None:
        if self.exceeded:
            return
        self.exceeded = True
        try:
            self._raw.write(
                f"\n[sandbox] 输出超过 {self._limit} 字节上限，剩余输出已丢弃\n"
            )
            self._raw.flush()
        except Exception:  # noqa: BLE001
            pass


def install(
    *,
    workdir: str,
    import_mode: str = "blacklist",
    allowed_imports: Sequence[str] = (),
    blocked_imports: Sequence[str] = (),
    allow_network: bool = False,
    recursion_limit: int = 300,
    output_limit_bytes: int = 65536,
) -> None:
    """在子进程内安装全部守卫（应尽早调用，必须在用户代码执行前）。"""
    wd = _os.path.abspath(workdir)
    allowed = {str(name).split(".")[0] for name in allowed_imports}
    blocked = {str(name).split(".")[0] for name in blocked_imports} | set(DEFAULT_BLOCKED_IMPORTS)
    limit = max(1024, int(output_limit_bytes))

    _sys.setrecursionlimit(max(50, min(int(recursion_limit), 2000)))
    try:
        _sys.set_int_max_str_digits(5000)
    except AttributeError:  # Python < 3.11 无此接口
        pass

    real_open = _builtins.open
    real_import = _builtins.__import__
    real_compile = _builtins.compile

    def _norm(path: Any) -> str:
        try:
            return _os.path.abspath(_os.path.expanduser(str(path)))
        except Exception:  # noqa: BLE001
            return ""

    def _under(child: str, parent: str) -> bool:
        if not child or not parent:
            return False
        parent = _os.path.abspath(parent).rstrip(_os.sep)
        return child == parent or child.startswith(parent + _os.sep)

    def _is_sensitive(path: str) -> bool:
        lowered = path.lower().replace("/", "\\")
        base = _os.path.basename(path).lower()
        if base in _DENY_NAMES:
            return True
        if _os.name == "nt":
            for prefix in _DENY_WIN:
                if lowered.startswith(prefix.lstrip("\\")) or prefix in lowered:
                    return True
        else:
            for prefix in _DENY_PREFIX_POSIX:
                if path == prefix or path.startswith(prefix + _os.sep):
                    return True
        for marker in (".ssh", ".aws", ".gnupg", ".gitconfig"):
            if marker in lowered:
                return True
        return False

    def _read_allowed(path: str) -> bool:
        if not path or _is_sensitive(path):
            return False
        roots = [
            wd,
            _tempfile.gettempdir(),
            _sys.prefix,
            _sys.base_prefix,
            _os.path.dirname(_os.__file__ or ""),
        ]
        return any(_under(path, root) for root in roots if root)

    def _write_allowed(path: str) -> bool:
        return bool(path) and _under(path, wd)

    def _mutating(mode: str) -> bool:
        return any(flag in mode for flag in ("w", "a", "x", "+"))

    def guarded_open(file: Any, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        path = _norm(file)
        if path:
            if _mutating(str(mode)):
                if not _write_allowed(path):
                    raise _violation("open(write)", f"只允许写入沙箱工作目录：{path}")
            elif not _read_allowed(path):
                raise _violation("open(read)", f"禁止读取该路径：{path}")
        return real_open(file, mode, *args, **kwargs)

    def guarded_import(name: str, globals: Any = None, locals: Any = None,
                       fromlist: Sequence[str] = (), level: int = 0) -> Any:
        top = str(name).split(".")[0]
        if top in blocked:
            raise _violation(f"import {top}", "该模块在沙箱中不可用")
        if import_mode == "whitelist" and allowed and top not in allowed:
            raise _violation(f"import {top}", "不在导入白名单内")
        if import_mode == "off":
            raise _violation(f"import {top}", "沙箱已禁用全部 import")
        return real_import(name, globals, locals, fromlist, level)

    def guarded_compile(source: Any, filename: Any, mode: str, *args: Any, **kwargs: Any) -> Any:
        # 允许 importlib 机制编译真实 .py 源文件，禁止编译内存字符串后绕过检查
        if isinstance(filename, str) and filename.endswith(".py") and _os.path.exists(filename):
            return real_compile(source, filename, mode, *args, **kwargs)
        raise _violation("compile()", "禁止编译非文件源码")

    input_counter = {"calls": 0}

    def guarded_input(prompt: str = "") -> str:
        input_counter["calls"] += 1
        if input_counter["calls"] > MAX_INPUT_CALLS:
            raise EOFError("[sandbox] input() 调用次数超过上限")
        if prompt:
            _sys.stdout.write(str(prompt))
            _sys.stdout.flush()
        stdin = _sys.__stdin__
        if stdin is None:
            raise EOFError("[sandbox] 标准输入不可用")
        line = stdin.readline()
        if not line:
            raise EOFError("[sandbox] 标准输入已耗尽")
        return line.rstrip("\n")

    _builtins.open = guarded_open  # type: ignore[assignment]
    _builtins.__import__ = guarded_import  # type: ignore[assignment]
    _builtins.compile = guarded_compile  # type: ignore[assignment]
    _builtins.input = guarded_input  # type: ignore[assignment]

    _scrub_os()
    _scrub_subprocess()
    _scrub_shutil()
    _scrub_importlib()
    if not allow_network:
        _disable_network()

    _sys.stdout = LimitedTextStream(_sys.__stdout__, limit)  # type: ignore[assignment]
    _sys.stderr = LimitedTextStream(_sys.__stderr__, max(1024, limit // 2))  # type: ignore[assignment]


def _patch(module_name: str, attr: str, replacement: Callable[..., Any]) -> None:
    """尽力替换模块属性；模块不存在时静默跳过。"""
    module = _sys.modules.get(module_name)
    if module is None:
        return
    try:
        setattr(module, attr, replacement)
    except Exception:  # noqa: BLE001 - 内置模块属性不可写
        pass


def _freeze(module_name: str) -> None:
    """清除模块的 __spec__/__loader__，阻止 reload 还原被清洗的属性。"""
    module = _sys.modules.get(module_name)
    if module is None:
        return
    try:
        module.__spec__ = None  # type: ignore[union-attr]
        module.__loader__ = None  # type: ignore[union-attr]
    except Exception:  # noqa: BLE001
        pass


def _scrub_os() -> None:
    """禁用 os 中的进程/命令/删除类能力，并对路径写操作做白名单。"""
    try:
        import os as os_module  # noqa: PLC0415 - 守卫安装期允许导入
    except Exception:  # noqa: BLE001
        return

    def _deny_os(name: str) -> Callable[..., Any]:
        def _raiser(*args: Any, **kwargs: Any) -> Any:
            raise _violation(f"os.{name}", "禁止执行系统命令/进程操作")

        return _raiser

    for attr in ("system", "popen", "execv", "execve", "execvp", "execvpe", "execl", "execle",
                 "execlp", "execlpe", "fork", "forkpty", "kill", "killpg", "spawnv", "spawnve",
                 "spawnvp", "spawnvpe", "spawnl", "spawnle", "spawnlp", "spawnlpe",
                 "posix_spawn", "remove", "unlink", "rmdir", "removedirs", "truncate"):
        if hasattr(os_module, attr):
            _patch("os", attr, _deny_os(attr))

    def _check_write_path(path: Any) -> str:
        target = _os.path.abspath(_os.path.expanduser(str(path)))
        base = _os.path.abspath(_os.environ.get("PLAB_WORKDIR", _tempfile.gettempdir()))
        if not (target == base or target.startswith(base.rstrip(_os.sep) + _os.sep)):
            raise _violation("os 路径写操作", f"只允许修改沙箱工作目录：{target}")
        return str(path)

    real_rename = getattr(os_module, "rename", None)
    real_replace = getattr(os_module, "replace", None)

    if real_rename is not None:
        def guarded_rename(src: Any, dst: Any, *args: Any, **kwargs: Any) -> Any:
            _check_write_path(src)
            _check_write_path(dst)
            return real_rename(src, dst, *args, **kwargs)

        _patch("os", "rename", guarded_rename)

    if real_replace is not None:
        def guarded_replace(src: Any, dst: Any, *args: Any, **kwargs: Any) -> Any:
            _check_write_path(src)
            _check_write_path(dst)
            return real_replace(src, dst, *args, **kwargs)

        _patch("os", "replace", guarded_replace)

    _freeze("os")


def _scrub_subprocess() -> None:
    """禁用 subprocess 的全部执行入口（含已在 sys.modules 中的实例）。"""
    module = _sys.modules.get("subprocess")
    if module is None:
        return

    def _deny(name: str) -> Callable[..., Any]:
        def _raiser(*args: Any, **kwargs: Any) -> Any:
            raise _violation(f"subprocess.{name}", "禁止创建子进程")

        return _raiser

    for attr in ("run", "call", "check_call", "check_output", "Popen", "getoutput",
                 "getstatusoutput", "create_new_session"):
        if hasattr(module, attr):
            _patch("subprocess", attr, _deny(attr))
    _freeze("subprocess")


def _scrub_shutil() -> None:
    """禁止删除沙箱工作目录之外的目录树。"""
    module = _sys.modules.get("shutil")
    if module is None:
        return

    def guarded_rmtree(path: Any, *args: Any, **kwargs: Any) -> Any:
        target = _os.path.abspath(str(path))
        base = _os.path.abspath(_os.environ.get("PLAB_WORKDIR", _tempfile.gettempdir()))
        if not (target == base or target.startswith(base.rstrip(_os.sep) + _os.sep)):
            raise _violation("shutil.rmtree", f"只允许清理沙箱工作目录：{target}")
        return module.rmtree(target, *args, **kwargs)

    _patch("shutil", "rmtree", guarded_rmtree)


def _scrub_importlib() -> None:
    """禁用模块重载/动态导入，避免被清洗的模块属性被重新执行还原。

    `importlib.reload(os)` 会重新执行 `os.py`，把 `os.system` 等属性装回来，
    因此必须堵住；`importlib` 本身仍可导入（标准库引导流程依赖它）。
    """
    module = _sys.modules.get("importlib")
    if module is None:
        return

    def _deny(name: str) -> Callable[..., Any]:
        def _raiser(*args: Any, **kwargs: Any) -> Any:
            raise _violation(f"importlib.{name}", "禁止重载模块或动态导入")

        return _raiser

    for attr in ("reload", "import_module", "invalidate_caches"):
        if hasattr(module, attr):
            _patch("importlib", attr, _deny(attr))

    util = _sys.modules.get("importlib.util")
    if util is not None and hasattr(util, "reload"):
        _patch("importlib.util", "reload", _deny("util.reload"))


def _disable_network() -> None:
    """禁用 socket 构造族（import socket 仍允许，但无法建连）。"""
    try:
        import socket as socket_module  # noqa: PLC0415
    except Exception:  # noqa: BLE001
        return

    def _deny_socket(name: str) -> Callable[..., Any]:
        def _raiser(*args: Any, **kwargs: Any) -> Any:
            raise _violation(f"socket.{name}", "沙箱已禁用网络")

        return _raiser

    for attr in ("socket", "create_connection", "socketpair", "create_server", "fromfd", "dup"):
        if hasattr(socket_module, attr):
            _patch("socket", attr, _deny_socket(attr))
    _freeze("socket")
