# 阶段 12 · 网络编程

## http-basics

### 理论

HTTP 是请求-响应协议。请求含方法（GET/POST/PUT/DELETE）、URL、头（headers）、体（body）；响应含状态码、头、体。常见状态码：200 成功、301 重定向、400 客户端错误、401 未认证、403 禁止、404 未找到、500 服务端错误。

### 代码

```http
GET /api/users?page=1 HTTP/1.1
Host: example.com
Accept: application/json
Authorization: Bearer <token>

HTTP/1.1 200 OK
Content-Type: application/json; charset=utf-8

{"success": true, "data": {"items": []}}
```

```python
# 用 requests 发送同类请求
import requests
resp = requests.get("https://example.com/api/users", params={"page": 1})
print(resp.status_code, resp.headers.get("Content-Type"))
```

### 示例

```python
import requests

resp = requests.post(
    "https://example.com/api/users",
    json={"name": "张三"},
    headers={"Authorization": "Bearer token"},
    timeout=10,
)
print(resp.status_code)
```

### 练习

1. 用 `requests` 发送 GET 与 POST 请求并打印状态码。
2. 解读 4xx 与 5xx 状态码的差异。

### 注意事项

- 校验 `status_code`，不要假设一定成功。
- 敏感头（Authorization）不要打日志。

### 常见错误

- 只看响应体不检查状态码。
- GET 请求带 body（语义错误，很多服务忽略）。

## requests-library

### 理论

`requests` 是事实标准的 HTTP 客户端：`get`/`post`/`put`/`delete`，自动处理编码、cookie、会话。`Session` 复用连接与头，`params`/`json` 传参，`timeout` 设置超时。

### 代码

```python
import requests

session = requests.Session()
session.headers.update({"User-Agent": "pythonlab/1.0"})

resp = session.get("https://httpbin.org/get", params={"q": "python"}, timeout=10)
resp.raise_for_status()          # 非 2xx 抛 HTTPError
data = resp.json()
print(data.get("args"))
```

### 示例

```python
import requests

def fetch_json(url: str, **params) -> dict:
    """获取 JSON，失败抛异常。"""
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()
```

### 练习

1. 用 `Session` 连续请求并保持登录态。
2. 用 `raise_for_status` 处理错误响应。

### 注意事项

- 始终设 `timeout`，否则可能永久阻塞。
- 复用一个 `Session` 提升性能。

### 常见错误

- 不设超时，程序卡死。
- 忘记 `raise_for_status()`，错误被静默忽略。

## json-api

### 理论

现代 API 多用 JSON 交换数据。请求用 `Content-Type: application/json`，响应用 JSON 体。解析用 `resp.json()`，构造用 `json=` 参数。要注意嵌套结构与错误约定（如统一响应壳）。

### 代码

```python
import requests

# 提交 JSON
resp = requests.post(
    "https://api.example.com/items",
    json={"name": "笔记本", "price": 5999},
    timeout=10,
)
resp.raise_for_status()
created = resp.json()

# 解析嵌套结构
items = created.get("data", {}).get("items", [])
for item in items:
    print(item["name"], item["price"])
```

### 示例

```python
import requests

def safe_parse(resp: requests.Response) -> dict:
    """安全解析 JSON，失败返回空字典。"""
    try:
        return resp.json()
    except ValueError:
        return {}
```

### 练习

1. 调用一个公开 JSON API 并提取字段。
2. 处理 API 返回的错误码字段。

### 注意事项

- 用 `resp.json()` 而非手动 `json.loads(resp.text)`。
- 字段可能缺失，用 `.get()` 有默认值。

### 常见错误

- 假定字段一定存在，`KeyError`。
- 把响应当字符串处理导致解析错误。

## socket-basics

### 理论

Socket 是网络通信的编程接口。TCP 流程：服务端 `socket` → `bind` → `listen` → `accept`；客户端 `socket` → `connect`；之后双方 `send`/`recv`。

### 代码

```python
# 服务端
import socket

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(("127.0.0.1", 9999))
server.listen(1)
conn, addr = server.accept()
data = conn.recv(1024)
conn.sendall(b"pong")
conn.close()
server.close()
```

```python
# 客户端
import socket

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect(("127.0.0.1", 9999))
client.sendall(b"ping")
print(client.recv(1024).decode())
client.close()
```

### 示例

```python
import socket

def port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    """检测端口是否可连接。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex((host, port)) == 0
```

### 练习

1. 写一个回声（echo）服务端与客户端。
2. 检测本机某端口是否开放。

### 注意事项

- 用 `with` 或 `try/finally` 关闭 socket。
- `recv` 返回的是字节，需 `decode`。

### 常见错误

- 忘记关闭连接，端口占用。
- 以为一次 `recv` 能收到完整消息（需循环/约定长度）。

## tcp-udp

### 理论

TCP 面向连接、可靠、有序（三次握手），适合文件/网页；UDP 无连接、不可靠、快（不保证到达/顺序），适合视频流、DNS。选择取决于对可靠性的需求。

### 代码

```python
# UDP 服务端
import socket

server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server.bind(("127.0.0.1", 9998))
data, addr = server.recvfrom(1024)
server.sendto(b"ack", addr)
server.close()
```

```python
# UDP 客户端
import socket

client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
client.sendto(b"hello", ("127.0.0.1", 9998))
data, _ = client.recvfrom(1024)
print(data.decode())
client.close()
```

### 示例

```python
# TCP: SOCK_STREAM  |  UDP: SOCK_DGRAM
import socket
print(socket.SOCK_STREAM, socket.SOCK_DGRAM)
```

### 练习

1. 用 UDP 实现一个简单的时间查询服务。
2. 对比 TCP 与 UDP 的适用场景各举两例。

### 注意事项

- UDP 需自行处理丢包/重传。
- TCP 有连接开销，短小请求 UDP 更快。

### 常见错误

- 用 UDP 却假设消息一定到达。
- 混用 `recv` 与 `recvfrom`。

## urllib-basics

### 理论

`urllib` 是标准库网络模块，无需第三方依赖。`urllib.request` 发请求，`urllib.parse` 处理 URL 编码/解析。功能不如 `requests` 友好，但零依赖。

### 代码

```python
from urllib import request, parse

params = parse.urlencode({"q": "python 教程"})
url = f"https://httpbin.org/get?{params}"
with request.urlopen(url, timeout=10) as resp:
    print(resp.status, resp.read(100))
```

### 示例

```python
from urllib.parse import urlparse, parse_qs

u = urlparse("https://a.com/path?x=1&y=2")
print(u.scheme, u.netloc, u.path, parse_qs(u.query))
```

### 练习

1. 用 `urllib` 下载一个网页并保存。
2. 解析 URL 提取查询参数。

### 注意事项

- `urllib` 不自动处理重定向 cookie 细节，复杂场景用 `requests`。
- URL 中文参数必须编码。

### 常见错误

- 未编码中文参数导致请求失败。
- 忘记 `with` 关闭响应。

## api-client

### 理论

封装 API 客户端把「鉴权、基址、序列化、错误处理」集中起来，业务层只调用方法。常见模式：类持有 `base_url` 与 `session`，方法返回结构化数据。

### 代码

```python
import requests

class ApiClient:
    """通用 API 客户端。"""

    def __init__(self, base_url: str, token: str | None = None, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"

    def get(self, path: str, **params) -> dict:
        resp = self.session.get(f"{self.base_url}{path}", params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

client = ApiClient("https://jsonplaceholder.typicode.com")
print(client.get("/todos/1").get("title"))
```

### 示例

```python
class TodoClient(ApiClient):
    """针对待办资源的专用客户端。"""

    def list_todos(self, limit: int = 10) -> list[dict]:
        return self.get("/todos", _limit=limit)  # type: ignore[return-value]
```

### 练习

1. 为一个公开 API 封装至少三个方法。
2. 给客户端加统一错误处理与重试。

### 注意事项

- 基址、超时、鉴权集中管理。
- 返回结构化数据而非原始响应。

### 常见错误

- 每个请求散落各处，难以维护。
- 把 token 硬编码在代码里。

## retry-timeout

### 理论

网络请求可能超时或瞬时失败，健壮客户端需「超时 + 重试 + 退避」。指数退避（每次等待翻倍）避免雪崩。只对可重试错误（超时、5xx）重试，不对 4xx 重试。

### 代码

```python
import time
import requests

def get_with_retry(url: str, retries: int = 3, base_delay: float = 0.5) -> requests.Response:
    """带指数退避的 GET。"""
    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code < 500:
                return resp
        except requests.RequestException:
            pass
        time.sleep(base_delay * (2 ** attempt))
    raise RuntimeError(f"重试 {retries} 次仍失败: {url}")
```

### 示例

```python
# requests 内置适配器重试（urlopen）
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

session = requests.Session()
retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
session.mount("https://", HTTPAdapter(max_retries=retry))
```

### 练习

1. 实现带最大重试次数与超时的请求函数。
2. 让重试仅针对 5xx 与超时错误。

### 注意事项

- 重试要有上限和退避，避免放大故障。
- 幂等操作才适合自动重试。

### 常见错误

- 无限重试拖垮服务。
- 对 4xx（如 401）也重试，无意义。

## rate-limit

### 理论

限流保护服务端与自身：客户端主动限速（礼貌爬取），服务端按 IP/用户限制频次（429 Too Many Requests）。常用「令牌桶」「固定窗口」。

### 代码

```python
import time

class RateLimiter:
    """简单固定间隔限流器。"""

    def __init__(self, min_interval: float = 1.0) -> None:
        self.min_interval = min_interval
        self._last = 0.0

    def wait(self) -> None:
        elapsed = time.perf_counter() - self._last
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last = time.perf_counter()

limiter = RateLimiter(0.5)
for _ in range(3):
    limiter.wait()
    # 发起请求...
```

### 示例

```python
# 服务端返回 429 时应读取 Retry-After
# resp.status_code == 429 -> delay = int(resp.headers.get("Retry-After", "1"))
```

### 练习

1. 用限流器实现每秒最多 2 次请求。
2. 处理 429 响应并按 `Retry-After` 退避。

### 注意事项

- 遵守目标站点的 robots 与频率要求。
- 服务端限流返回 429 并给出重试时间。

### 常见错误

- 高频请求被封 IP。
- 忽略 429 继续猛刷。
