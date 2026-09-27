#!/usr/bin/env bash
# PYTHON LAB —— 一键 Docker 部署（docker compose up -d --build）
# 用法：bash scripts/docker-up.sh [--no-build] [--with-proxy] [--logs]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

command -v docker >/dev/null 2>&1 || { echo "[docker-up] 未安装 docker，本机请用 scripts/setup.sh + scripts/dev.sh" >&2; exit 1; }

COMPOSE_ARGS=()
LOGS=0
for arg in "$@"; do
  case "$arg" in
    --no-build) COMPOSE_ARGS+=("--no-build") ;;
    --with-proxy) export COMPOSE_PROFILES=proxy ;;
    --logs) LOGS=1 ;;
    *) echo "未知参数：$arg" >&2; exit 2 ;;
  esac
done

if [ ! -f .env ]; then
  cp .env.example .env
  echo "[docker-up] 已从 .env.example 生成 .env，请检查密钥后再部署"
fi

echo "[docker-up] docker compose up -d --build ${COMPOSE_ARGS[*]:-}"
docker compose up -d --build "${COMPOSE_ARGS[@]:-}"

echo "[docker-up] 等待健康检查..."
docker compose ps

echo "[docker-up] 校验完成状态：docker compose ps / docker compose logs -f backend"
if [ "$LOGS" -eq 1 ]; then
  docker compose logs -f
fi
