"""资源限额与进程树管理。

- Linux：`preexec_fn` 里用 `resource.setrlimit` 限 CPU/地址空间/文件大小/进程数/核心转储
- Windows：无 rlimit，退化为「墙钟超时 kill 进程树 + psutil 轮询 RSS 超限 kill」
- 两者共用同一套 `kill_process_tree()`
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
from typing import Any, Callable, Optional

try:  # POSIX 专有
    import resource  # type: ignore[import-not-found]
except Exception:  # noqa: BLE001 - Windows 无 resource 模块
    resource = None  # type: ignore[assignment]

try:
    import psutil  # type: ignore[import-not-found]
except Exception:  # noqa: BLE001 - psutil 缺失时退化为无内存采样
    psutil = None  # type: ignore[assignment]

IS_POSIX = os.name == "posix"
CREATE_NEW_PROCESS_GROUP = 0x00000200  # Windows


def platform_capabilities() -> dict:
    """返回当前平台的沙箱能力矩阵与 `security_level`。"""
    has_rlimit = resource is not None and hasattr(resource, "setrlimit")
    has_psutil = psutil is not None
    unshare_available = bool(shutil.which("unshare")) if IS_POSIX else False
    security_level = "hardened" if IS_POSIX else "degraded"
    return {
        "platform": sys.platform,
        "os_name": os.name,
        "python": sys.version.split()[0],
        "security_level": security_level,
        "rlimit": bool(has_rlimit),
        "psutil": bool(has_psutil),
        "network_isolation": bool(unshare_available) or IS_POSIX,
        "unshare": bool(unshare_available),
        "cpu_limit": bool(has_rlimit),
        "memory_limit": bool(has_rlimit) or bool(has_psutil),
        "process_tree_kill": True,
        "note": (
            "Linux: rlimit + 进程组隔离生效"
            if IS_POSIX
            else "Windows: 无 rlimit/cgroup，仅超时 kill + psutil 轮询 RSS（best-effort）"
        ),
    }


def build_preexec_fn(memory_mb: int, cpu_ms: int, file_size_mb: int = 16,
                     max_processes: int = 64) -> Optional[Callable[[], None]]:
    """构造 Linux 的 `preexec_fn`（Windows 返回 None）。

    子进程先 `setsid()` 脱离进程组，便于整体 kill；随后设置各项 rlimit。
    """
    if not IS_POSIX or resource is None:
        return None

    memory_bytes = int(memory_mb) * 1024 * 1024
    cpu_seconds = max(1, int(cpu_ms / 1000) + 1)
    # 地址空间给 4 倍余量（numpy/pandas 会预留大量虚拟内存），数据段才是真正限制
    address_bytes = max(memory_bytes * 4, 512 * 1024 * 1024)
    file_bytes = int(file_size_mb) * 1024 * 1024

    def _preexec() -> None:
        try:
            os.setsid()
        except OSError:
            pass
        _set_limit(resource.RLIMIT_AS, address_bytes)
        _set_limit(resource.RLIMIT_DATA, memory_bytes)
        _set_limit(resource.RLIMIT_STACK, 32 * 1024 * 1024)
        _set_limit(resource.RLIMIT_CPU, cpu_seconds)
        _set_limit(resource.RLIMIT_FSIZE, file_bytes)
        _set_limit(resource.RLIMIT_CORE, 0)
        _set_limit(resource.RLIMIT_NOFILE, 256)
        if hasattr(resource, "RLIMIT_NPROC"):
            _set_limit(resource.RLIMIT_NPROC, max_processes)

    return _preexec


def _set_limit(which: int, value: int) -> None:
    """设置单个 rlimit，失败（权限不足等）时静默忽略。"""
    try:
        resource.setrlimit(which, (value, value))
    except (ValueError, OSError):
        try:
            resource.setrlimit(which, (value, resource.getrlimit(which)[1]))
        except (ValueError, OSError):
            pass


def kill_process_tree(process: Any) -> None:
    """杀死进程树：POSIX 杀进程组，Windows 用 `taskkill /F /T`。"""
    try:
        pid = process.pid
    except Exception:  # noqa: BLE001
        return
    if process.poll() is not None:
        return
    try:
        if IS_POSIX:
            os.killpg(os.getpgid(pid), 9)
        else:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=False,
            )
    except Exception:  # noqa: BLE001 - 进程已退出或权限不足
        pass
    try:
        process.kill()
    except Exception:  # noqa: BLE001
        pass


class MemoryWatcher(threading.Thread):
    """轮询进程树 RSS，超过上限即 kill（Windows 上唯一可行的内存限制手段）。"""

    def __init__(self, process: Any, memory_mb: int, interval: float = 0.1) -> None:
        super().__init__(daemon=True, name="plab-memory-watcher")
        self._process = process
        self._limit_bytes = int(memory_mb) * 1024 * 1024
        self._interval = interval
        self._stop = threading.Event()
        self.peak_kb = 0
        self.exceeded = False

    def run(self) -> None:
        handle = None
        if psutil is not None:
            try:
                handle = psutil.Process(self._process.pid)
            except Exception:  # noqa: BLE001
                handle = None
        while not self._stop.is_set():
            if self._process.poll() is not None:
                break
            usage = self._sample_rss(handle)
            self.peak_kb = max(self.peak_kb, usage // 1024)
            if self._limit_bytes and usage > self._limit_bytes:
                self.exceeded = True
                kill_process_tree(self._process)
                break
            time.sleep(self._interval)

    def _sample_rss(self, handle: Any) -> int:
        """采样进程 + 子进程的总 RSS（字节）。"""
        if handle is None:
            return 0
        total = 0
        try:
            total += handle.memory_info().rss
            for child in handle.children(recursive=True):
                try:
                    total += child.memory_info().rss
                except Exception:  # noqa: BLE001
                    continue
        except Exception:  # noqa: BLE001 - 进程已退出
            return 0
        return total

    def stop(self) -> None:
        """结束采样线程。"""
        self._stop.set()


def max_rss_kb() -> int:
    """Linux 下取 `RUSAGE_CHILDREN` 的最大常驻集（Windows 返回 0）。"""
    if resource is None:
        return 0
    try:
        return int(resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
    except Exception:  # noqa: BLE001
        return 0


def popen_kwargs(start_new_session: bool = True) -> dict:
    """构造跨平台 `subprocess.Popen` 关键字参数。"""
    kwargs: dict = {}
    if IS_POSIX:
        kwargs["start_new_session"] = start_new_session
    else:
        kwargs["creationflags"] = CREATE_NEW_PROCESS_GROUP
    return kwargs
