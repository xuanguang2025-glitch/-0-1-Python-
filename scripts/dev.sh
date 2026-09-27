#!/usr/bin/env bash
# PYTHON LAB —— 一键启动开发环境：后端(8000) + 前端(3000) [+ 沙箱(8081)]
# 用法：bash scripts/dev.sh [--no-sandbox] [--no-frontend]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

WITH_SANDBOX=1
WITH_FRONTEND=1
for arg in "$@"; do
  case "$arg" in
    --no-sandbox) WITH_SANDBOX=0 ;;
    --no-frontend) WITH_FRONTEND=0 ;;
    *) echo "未知参数：$arg" >&2; exit 2 ;;
  esac
done

PIDS=()
cleanup() {
  printf '\n[dev] 正在停止子进程...\n'
  for pid in "${PIDS[@]:-}"; do
    [ -n "${pid:-}" ] && kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  printf '[dev] 已退出\n'
}
trap cleanup EXIT INT TERM

log() { printf '\033[36m[dev]\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[dev]\033[0m %s\n' "$*"; }

# ------------------------------------------------------------- 后端
if [ -x backend/.venv/bin/python ]; then
  log "启动后端 http://127.0.0.1:8000 （uvicorn --reload）"
  ( cd backend && ./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload ) &
  PIDS+=($!)
elif [ -x backend/.venv/Scripts/python.exe ]; then
  log "启动后端 http://127.0.0.1:8000 （Windows venv 布局）"
  ( cd backend && ./.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload ) &
  PIDS+=($!)
else
  warn "未找到 backend/.venv，请先运行 scripts/setup.sh"
fi

# ------------------------------------------------------------- 沙箱（可选）
if [ "$WITH_SANDBOX" -eq 1 ]; then
  if [ -x sandbox/.venv/bin/python ]; then
    log "启动沙箱 http://127.0.0.1:8081 （security_level 见 /health）"
    ( cd sandbox && ./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8081 ) &
    PIDS+=($!)
  else
    warn "未找到 sandbox/.venv，跳过沙箱（后端将自动降级为 LocalRunner）"
  fi
fi

# ------------------------------------------------------------- 前端
if [ "$WITH_FRONTEND" -eq 1 ] && [ -f frontend/package.json ]; then
  log "启动前端 http://localhost:3000"
  ( cd frontend && npm run dev ) &
  PIDS+=($!)
else
  warn "跳过前端启动"
fi

log "全部进程已启动，Ctrl+C 结束。"
wait
