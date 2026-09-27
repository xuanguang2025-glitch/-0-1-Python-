# docker/ —— 编排、反代与备用镜像

## 文件

| 文件 | 说明 |
|---|---|
| `../docker-compose.yml` | **规范编排文件**（postgres + redis + backend + frontend + sandbox + 可选 nginx） |
| `docker-compose.yml` | 本目录入口，用 Compose `include` 复用根编排（保持 ARCHITECTURE.md 路径可用，需 Compose v2.20+） |
| `docker-compose.dev.yml` | 仅起 Postgres + Redis（开发者本地用，业务进程跑宿主机） |
| `nginx.conf` + `proxy_params.inc` | 反向代理（`/api` → backend，`/` → frontend，`/sandbox` → sandbox） |
| `postgres/init.sql` | 首次初始化：扩展（uuid-ossp/pg_trgm）、UTC、只读账号、模糊检索索引 |
| `backend.Dockerfile` | 备用后端镜像（若 `backend/` 内未提供 Dockerfile） |
| `frontend.Dockerfile` | 备用前端镜像（若 `frontend/` 内未提供 Dockerfile） |
| `certs/` | 放 `fullchain.pem` / `privkey.pem` 后启用 HTTPS（已加入 .gitignore） |

> 规范文件放在仓库根，是为了 `docker compose up -d` 默认就能识别；
> 架构文档里的 `docker/docker-compose.yml` 通过 `include` 指向它，避免两份配置漂移。

## init.sql 的执行时机（重要）

`postgres/init.sql` 只在**数据卷首次创建**时执行，而此时业务表还没被 Alembic 创建。
因此其中的 `pg_trgm` 索引块**首次会跳过**（表不存在），扩展、时区、只读账号已生效。
迁移建表之后如需这些索引，再执行一次：

```bash
docker compose exec -T postgres psql -U pythonlab -d pythonlab < docker/postgres/init.sql
```

## 常用命令

```bash
cp .env.example .env                 # 填密钥
docker compose up -d --build         # 起全套（本机需已安装 Docker）
docker compose ps                    # 看健康状态
docker compose logs -f backend       # 跟踪日志
docker compose --profile proxy up -d # 附带 Nginx 反代（:8080）
docker compose down                  # 停服务（保留数据卷）
docker compose down -v               # 停服务并删除数据卷（危险）
```

仅需数据库/缓存（业务跑宿主机）：

```bash
docker compose -f docker/docker-compose.dev.yml up -d
```

## 端口

| 服务 | 宿主端口 | 容器端口 |
|---|---|---|
| frontend | 3000 | 3000 |
| backend | 8000 | 8000 |
| postgres | 5432 | 5432 |
| redis | 6379 | 6379 |
| sandbox | 8081 | 8081 |
| nginx（profile=proxy） | 8080 / 8443 | 80 / 443 |

## 沙箱容器加固（compose 已内置）

`read_only: true`、`tmpfs /tmp:noexec,nosuid`、`cap_drop: ALL`、
`no-new-privileges`、`pids_limit: 256`、`mem_limit: 640m`、`cpus: 1.0`。

**注意**：容器沙箱仍建议配 `--network none` 级别隔离；当前编排让 sandbox 与
backend 在同一 bridge 网络内（backend 需调用它）。若你的环境允许，把 sandbox
单独放到一个 `internal: true` 的网络里更安全。

## 与 `SANDBOX_MODE` 的关系

- `SANDBOX_MODE=remote`：判题走 `sandbox` 容器（生产推荐）
- `SANDBOX_MODE=local`：用 backend 内置 `LocalRunner`，可去掉 `sandbox` 服务
- `SANDBOX_MODE=auto`：先探测远程 `/health`，失败自动降级 local

## 数据卷

`pythonlab-pgdata`、`pythonlab-redisdata`、`pythonlab-uploads`（具名卷，`down` 不会丢数据）。
备份见 `docs/DEPLOYMENT.md`。

本机没有 Docker 时的降级运行方式同样见 `docs/DEPLOYMENT.md`。
