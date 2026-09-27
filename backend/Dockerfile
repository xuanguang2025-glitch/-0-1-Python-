# PYTHON LAB —— 后端镜像（生产用；本机无 Docker 时直接跑 uvicorn 即可）
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 依赖先行，利用 Docker 层缓存
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts

# 数据与上传目录
RUN mkdir -p /app/data/uploads
VOLUME ["/app/data"]

EXPOSE 8000

# 生产建议使用外部 Postgres/Redis；此处仅以环境变量占位，实际由 compose 注入
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
