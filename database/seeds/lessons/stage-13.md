# 阶段 13 · Web 开发

## flask-basics

### 理论

Flask 是轻量 Web 框架：用装饰器把 URL 映射到视图函数。一个应用实例 + 路由 + 请求处理即可跑起来，适合入门与小型服务。

### 代码

```python
from flask import Flask, jsonify, request

app = Flask(__name__)

@app.get("/")
def index():
    """首页。"""
    return jsonify({"message": "hello"})

@app.post("/echo")
def echo():
    """回显 JSON。"""
    data = request.get_json(silent=True) or {}
    return jsonify({"received": data}), 201

if __name__ == "__main__":
    app.run(debug=True, port=5000)
```

### 示例

```python
from flask import Flask, abort

app = Flask(__name__)

@app.get("/items/<int:item_id>")
def get_item(item_id: int):
    if item_id <= 0:
        abort(404)
    return {"id": item_id}
```

### 练习

1. 用 Flask 写一个返回当前时间的 `/now` 接口。
2. 实现带路径参数的 `/users/<name>` 接口。

### 注意事项

- 生产环境不要用 `debug=True` 与内置服务器。
- 用 `jsonify` 返回 JSON。

### 常见错误

- 视图函数返回后忘记 `return`。
- 在视图外访问 `request`（无请求上下文）。

## fastapi-basics

### 理论

FastAPI 基于 ASGI，默认异步、自动生成 OpenAPI 文档（`/docs`），用 Pydantic 做请求/响应校验。类型注解即契约，非常适合现代 API。

### 代码

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Demo")

class Item(BaseModel):
    name: str
    price: float

@app.get("/health")
async def health() -> dict:
    """健康检查。"""
    return {"status": "ok"}

@app.post("/items", status_code=201)
async def create_item(item: Item) -> Item:
    """创建商品（示例，不落库）。"""
    return item
```

### 示例

```python
from fastapi import FastAPI, HTTPException

app = FastAPI()

@app.get("/items/{item_id}")
async def read_item(item_id: int, q: str | None = None) -> dict:
    if item_id != 1:
        raise HTTPException(status_code=404, detail="未找到")
    return {"item_id": item_id, "q": q}
```

### 练习

1. 用 FastAPI 写 `/add?a=1&b=2` 返回和。
2. 定义 Pydantic 模型校验请求体。

### 注意事项

- 路径/查询参数靠类型注解自动解析与校验。
- 用 `HTTPException` 返回标准错误。

### 常见错误

- 同步阻塞函数直接写在 `async def` 里（应改同步 `def` 或用线程池）。
- 响应模型与返回对象字段不匹配。

## routing-rest

### 理论

RESTful 用「资源 + HTTP 方法」表达操作：`GET` 查询、`POST` 创建、`PUT/PATCH` 更新、`DELETE` 删除。URL 用名词复数，避免动词。

### 代码

```python
from fastapi import APIRouter, FastAPI

router = APIRouter(prefix="/api/v1/items", tags=["items"])

@router.get("")            # 列表
async def list_items() -> list[dict]:
    return []

@router.post("")           # 创建
async def create_item(payload: dict) -> dict:
    return payload

@router.get("/{item_id}")  # 详情
async def get_item(item_id: int) -> dict:
    return {"id": item_id}

@router.delete("/{item_id}")  # 删除
async def delete_item(item_id: int) -> dict:
    return {"deleted": item_id}

app = FastAPI()
app.include_router(router)
```

### 示例

```python
# 好：GET /api/v1/users/  坏：GET /api/v1/getUsers
# 好：DELETE /api/v1/users/1  坏：POST /api/v1/deleteUser?id=1
```

### 练习

1. 为一组资源设计 RESTful 路由。
2. 用 `APIRouter` 组织模块化路由。

### 注意事项

- 版本化前缀（`/v1`）便于演进。
- 状态码语义正确（创建返回 201）。

### 常见错误

- URL 里塞动词（`/createUser`）。
- 用 GET 做有副作用的操作。

## request-response

### 理论

请求处理三要素：路径/查询参数、请求体、请求头。响应含状态码、头、体。Pydantic 模型既能校验请求，也能规范响应（`response_model` 过滤多余字段）。

### 代码

```python
from fastapi import FastAPI, Header, Request
from pydantic import BaseModel

app = FastAPI()

class UserIn(BaseModel):
    name: str
    age: int

class UserOut(BaseModel):
    name: str

@app.post("/users", response_model=UserOut, status_code=201)
async def create_user(user: UserIn, request: Request, x_token: str = Header(...)) -> UserOut:
    """创建用户，返回时只暴露 name。"""
    return UserOut(name=user.name)
```

### 示例

```python
from fastapi import FastAPI, Query

app = FastAPI()

@app.get("/search")
async def search(q: str = Query(..., min_length=1), limit: int = 10) -> dict:
    return {"q": q, "limit": limit}
```

### 练习

1. 用 `response_model` 隐藏敏感字段。
2. 用 `Header` 读取自定义请求头。

### 注意事项

- 区分输入模型与输出模型。
- 用 `Query`/`Path` 给参数加校验。

### 常见错误

- 输入输出共用一个模型，误暴露内部字段。
- 忽略请求头鉴权。

## template-render

### 理论

服务端渲染用模板引擎（Jinja2）把数据填入 HTML。FastAPI/Flask 都可集成 Jinja2。前后端分离项目可能只在个别页面（如邮件、管理后台）使用。

### 代码

```python
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="templates")

@app.get("/hello/{name}", response_class=HTMLResponse)
async def hello(request: Request, name: str):
    return templates.TemplateResponse("hello.html", {"request": request, "name": name})
```

```html
<!-- templates/hello.html -->
<h1>你好，{{ name }}</h1>
{#
    Jinja2 支持 {{ 变量 }}、{% if %}、{% for %}，默认自动转义防 XSS
#}
```

### 示例

```python
# Flask 版本
from flask import Flask, render_template
app = Flask(__name__)

@app.get("/profile")
def profile():
    return render_template("profile.html", user={"name": "张三"})
```

### 练习

1. 用 Jinja2 渲染一个含循环的列表页。
2. 演示变量自动转义的作用。

### 注意事项

- 默认自动转义；输出 HTML 需显式 `|safe` 并确保可信。
- 模板目录与静态资源路径要配置正确。

### 常见错误

- 关闭自动转义导致 XSS。
- 模板变量名与传入不符，渲染为空白。

## validation-pydantic

### 理论

Pydantic 用类型注解做数据校验与转换：自动把字符串转成 int/float，校验范围与格式，返回结构化错误。是 FastAPI 的核心依赖。

### 代码

```python
from pydantic import BaseModel, Field, field_validator

class Signup(BaseModel):
    username: str = Field(min_length=3, max_length=20)
    age: int = Field(ge=0, le=150)
    email: str

    @field_validator("email")
    @classmethod
    def check_email(cls, value: str) -> str:
        if "@" not in value:
            raise ValueError("邮箱格式不正确")
        return value.lower()

data = Signup(username="abc", age=20, email="A@X.com")
print(data.email)   # a@x.com（已规范化）
```

### 示例

```python
from pydantic import BaseModel, ValidationError

class M(BaseModel):
    n: int

try:
    M(n="not-a-number")
except ValidationError as exc:
    print(exc.error_count())    # 1
```

### 练习

1. 用 Pydantic 校验一个含手机号的注册模型。
2. 自定义校验器实现密码强度检查。

### 注意事项

- 用 `Field` 声明约束，用 `field_validator` 自定义规则。
- v2 中校验器用 `@field_validator`（非 v1 的 `validator`）。

### 常见错误

- 混用 Pydantic v1/v2 API。
- 校验器返回 `None` 覆盖了字段值。

## auth-token

### 理论

无状态鉴权常用 JWT：服务端签发含用户标识与过期时间的 token，客户端在 `Authorization: Bearer <token>` 携带。服务端验签与过期即确认身份。刷新令牌用于免频繁登录。

### 代码

```python
import jwt          # PyJWT
from datetime import datetime, timedelta, timezone

SECRET = "从环境变量读取，切勿硬编码"

def create_token(user_id: int, minutes: int = 15) -> str:
    """签发访问令牌。"""
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=minutes),
        "type": "access",
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")

def decode_token(token: str) -> dict:
    """校验并解析令牌，失败抛异常。"""
    return jwt.decode(token, SECRET, algorithms=["HS256"])
```

### 示例

```python
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

app = FastAPI()
bearer = HTTPBearer()

@app.get("/me")
async def me(cred: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    try:
        payload = decode_token(cred.credentials)
    except Exception:
        raise HTTPException(status_code=401, detail="令牌无效")
    return {"user_id": payload["sub"]}
```

### 练习

1. 构造带过期时间的 JWT 并验证过期报错。
2. 用刷新令牌换取新的访问令牌。

### 注意事项

- 密钥只从环境变量读，绝不硬编码。
- 密码用哈希（bcrypt）存储，不存明文。

### 常见错误

- 密钥写死在代码里泄露。
- 不校验 `exp`，令牌永不过期。

## api-design

### 理论

好 API：一致（命名、响应结构统一）、可读（文档清晰）、健壮（校验、错误明确）、可演进（版本化、兼容）。统一响应壳（如 `{success, data, message, error}`）便于前端处理。

### 代码

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="PythonLab API", version="1.0.0")

class ApiResponse(BaseModel):
    success: bool = True
    data: dict | None = None
    message: str = ""

@app.get("/api/health", response_model=ApiResponse, tags=["system"])
async def health() -> ApiResponse:
    """健康检查接口。"""
    return ApiResponse(data={"status": "ok"})
```

### 示例

```python
# 错误响应保持一致
# {"success": false, "error": {"code": "NOT_FOUND", "details": {}}}
# 分页统一：{"items": [...], "total": 100, "page": 1, "page_size": 20}
```

### 练习

1. 为你的 API 设计统一响应与错误结构。
2. 用 tags 给接口分组并补全文档。

### 注意事项

- 错误码用常量枚举，前后端共享约定。
- 分页参数命名一致（page/page_size）。

### 常见错误

- 各接口响应结构五花八门。
- 错误信息含糊，难定位。

## deploy-basics

### 理论

部署把服务跑在服务器上：用生产级 ASGI 服务器（uvicorn/gunicorn）替代开发服务器，用环境变量注入配置，前置反向代理（Nginx）。容器化（Docker）保证环境一致。

### 代码

```bash
# 开发
uvicorn app.main:app --reload --port 8000

# 生产（多进程）
gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 4 -b 0.0.0.0:8000
```

```dockerfile
FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 示例

```bash
# 健康检查
curl -f http://localhost:8000/api/health || exit 1
```

### 练习

1. 写出从源码到运行的部署步骤。
2. 用 Dockerfile 构建并运行服务。

### 注意事项

- 密钥用环境变量/密钥管理，不进镜像。
- 生产关闭 `--reload` 与 debug。

### 常见错误

- 生产用 `--reload`，性能差且不稳。
- 把 `.env` 或密钥打进镜像。
