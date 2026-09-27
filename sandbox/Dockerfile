# PYTHON LAB 沙箱服务镜像
# 安全说明：本容器只提供「受限执行」，真正的隔离依赖容器自身
# （非 root、只读工作目录、无网络、资源上限）。详见 docs/SANDBOX.md
# 基础镜像版本与 docs/ARCHITECTURE.md §2.4、backend 运行时保持一致（Python 3.13）
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    SANDBOX_HOST=0.0.0.0 \
    SANDBOX_PORT=8081 \
    SANDBOX_WORKDIR_ROOT=/tmp/pythonlab-sandbox \
    SANDBOX_TIMEOUT_MS=5000 \
    SANDBOX_MEMORY_MB=256

# util-linux: 提供 unshare（网络命名空间隔离）
RUN apt-get update \
    && apt-get install -y --no-install-recommends util-linux \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv/sandbox

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY app ./app
COPY README.md ./

# 非 root 用户运行
RUN useradd --create-home --shell /usr/sbin/nologin runner \
    && mkdir -p /tmp/pythonlab-sandbox \
    && chown -R runner:runner /srv/sandbox /tmp/pythonlab-sandbox
USER runner

EXPOSE 8081

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8081/health', timeout=3).status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8081"]
