# PYTHON LAB Sandbox（独立代码沙箱服务）

FastAPI 实现的受限 Python 执行服务，供 backend 的 `RemoteRunner` 调用；
backend 不可用时可用 backend 内置 `LocalRunner` 降级。

> ⚠️ **本服务不是安全边界。** 本地（尤其 Windows）模式只提供「超时 kill +
> 输出截断 + 运行时守卫」的尽力而为限制，**禁止直接暴露公网**。生产必须运行
> 本目录的 Docker 镜像（非 root、无网络、资源上限）。详见 `docs/SANDBOX.md`。

## 路由

| Method | Path | 说明 |
|---|---|---|
| GET | `/health` | 健康检查，含 `security_level`（`hardened` / `degraded`）与平台能力 |
| GET | `/limits` | 当前限额与静态检查规则 |
| POST | `/execute` | 规范执行入口（`mode=run\|judge`） |
| POST | `/run` | 单次运行别名 |
| POST | `/judge` | 批量判题别名 |

## 请求协议

```jsonc
{
  "request_id": "uuid",
  "language": "python",
  "mode": "run",                      // run | judge
  "files": [{"path": "main.py", "content": "print('hi')"}],
  "code": "print('hi')",              // 简写：等价于 entry 单文件
  "entry": "main.py",
  "stdin": "",
  "test_cases": [{"id": "tc1", "input": "1\n", "expected": "1", "comparison": "trimmed"}],
  "timeout_ms": 5000,                 // 别名：timeout
  "memory_limit_mb": 256,             // 别名：memory_mb
  "cpu_limit_ms": 4000,
  "max_output_bytes": 65536,
  "allow_network": false,
  "env": {"PLAB_FLAG": "1"}
}
```

## 响应协议

```jsonc
{
  "request_id": "uuid",
  "status": "success",     // success|compile_error|runtime_error|timeout|memory_exceeded|
                           // output_exceeded|security_error|wrong_answer|internal_error
  "exit_code": 0,
  "stdout": "hi\n", "stderr": "",
  "truncated": false,
  "time_ms": 31, "duration_ms": 31,
  "memory_kb": 20123,
  "timed_out": false,
  "results": [], "passed_cases": 0, "total_cases": 0,
  "error": null,
  "runner": "sandbox",
  "degraded": true,
  "security_level": "degraded"
}
```

## 本地运行（Windows，受限模式）

```bash
cd sandbox
C:/Users/徐浩然/.workbuddy/binaries/python/versions/3.13.12/python.exe -m venv .venv
.venv/Scripts/python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
    fastapi "uvicorn[standard]" psutil httpx pytest
.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8081
curl -s http://127.0.0.1:8081/health
```

自测：`sandbox/tests/test_executor.py`（`pytest -q`），或 `scripts/healthcheck.py`。

## Docker 运行

```bash
docker build -t pythonlab/sandbox:1.0.0 sandbox
docker run --rm -p 8081:8081 --read-only --tmpfs /tmp \
    --memory 640m --cpus 1 --network none pythonlab/sandbox:1.0.0
```

## 安全层级

1. 静态源码检查（`app/security.py`）：命中危险调用直接拒绝（`security_error`）
2. 资源限额：Linux `setrlimit(AS/DATA/CPU/FSIZE/NPROC)`；Windows 无 rlimit，
   退化为 psutil 轮询 RSS 超限 kill
3. 墙钟超时：超时立即 kill 整个进程树（POSIX 杀进程组 / Windows `taskkill /F /T`）
4. 输出截断：单用例默认 64KB，超限丢弃剩余输出并置 `truncated=true`
5. 运行时守卫（`app/guard.py`，`-c` 注入）：`open()` 路径白名单、`__import__`
   黑名单、`os.system/os.popen/os.fork` 等清洗、禁用 socket、递归深度上限
6. 可选网络命名空间隔离：Linux 探测到可用 `unshare -n` 时自动启用

详见 `docs/SANDBOX.md`。
