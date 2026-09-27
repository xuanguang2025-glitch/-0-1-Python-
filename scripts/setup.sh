#!/usr/bin/env bash
# PYTHON LAB —— 一键初始化（Unix / macOS / WSL）
# 用法：bash scripts/setup.sh [--skip-frontend] [--with-migrate] [--with-seed]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON_BIN="${PYTHON:-python3}"
PIP_INDEX="${PIP_INDEX:-https://pypi.tuna.tsinghua.edu.cn/simple}"
NPM_REGISTRY="${NPM_REGISTRY:-https://registry.npmmirror.com}"

SKIP_FRONTEND=0
WITH_MIGRATE=0
WITH_SEED=0
for arg in "$@"; do
  case "$arg" in
    --skip-frontend) SKIP_FRONTEND=1 ;;
    --with-migrate) WITH_MIGRATE=1 ;;
    --with-seed) WITH_SEED=1 ;;
    *) echo "未知参数：$arg" >&2; exit 2 ;;
  esac
done

log() { printf '\033[36m[setup]\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[setup]\033[0m %s\n' "$*"; }
die() { printf '\033[31m[setup]\033[0m %s\n' "$*" >&2; exit 1; }

command -v "$PYTHON_BIN" >/dev/null 2>&1 || die "找不到 $PYTHON_BIN，请先安装 Python 3.13+ 或设置环境变量 PYTHON"

# ---------------------------------------------------------------- 1. .env
if [ ! -f .env ]; then
  cp .env.example .env
  log "已生成 .env（来自 .env.example）—— 请按需修改密钥与 AI Key"
else
  log ".env 已存在，跳过"
fi

# ---------------------------------------------------------- 2. 后端 venv
if [ -f backend/requirements.txt ]; then
  if [ ! -d backend/.venv ]; then
    log "创建 backend/.venv"
    "$PYTHON_BIN" -m venv backend/.venv
  fi
  VENV_PY="$(pwd)/backend/.venv/bin/python"
  log "升级 pip 并安装后端依赖（国内源 ${PIP_INDEX}）"
  "$VENV_PY" -m pip install --upgrade pip -i "$PIP_INDEX"
  "$VENV_PY" -m pip install -r backend/requirements.txt -i "$PIP_INDEX"
  if [ -f backend/requirements-dev.txt ]; then
    "$VENV_PY" -m pip install -r backend/requirements-dev.txt -i "$PIP_INDEX"
  fi
else
  warn "backend/requirements.txt 不存在，跳过后端依赖安装"
fi

# -------------------------------------------------------- 3. 数据目录
mkdir -p data/uploads logs 2>/dev/null || true

# ---------------------------------------------------------- 4. 前端依赖
if [ "$SKIP_FRONTEND" -eq 0 ] && [ -f frontend/package.json ]; then
  log "安装前端依赖（registry=${NPM_REGISTRY}）"
  ( cd frontend && npm install --registry="$NPM_REGISTRY" )
else
  warn "跳过前端依赖安装"
fi

# ------------------------------------------------- 5. 可选：迁移与种子
if [ "$WITH_MIGRATE" -eq 1 ]; then
  log "执行数据库迁移"
  bash scripts/migrate.sh
fi
if [ "$WITH_SEED" -eq 1 ]; then
  log "导入种子数据"
  bash scripts/seed.sh
fi

log "完成。下一步：bash scripts/dev.sh 然后打开 http://localhost:3000"
