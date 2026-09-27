#!/usr/bin/env bash
# PYTHON LAB —— 数据库迁移（alembic upgrade head）
# 用法：bash scripts/migrate.sh [revision]（默认 head）
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/backend"

REVISION="${1:-head}"

if [ -x .venv/bin/python ]; then
  PY="./.venv/bin/python"
elif [ -x .venv/Scripts/python.exe ]; then
  PY="./.venv/Scripts/python.exe"
else
  echo "[migrate] 未找到 backend/.venv，请先运行 scripts/setup.sh" >&2
  exit 1
fi

if [ ! -f alembic.ini ]; then
  echo "[migrate] backend/alembic.ini 不存在，跳过迁移（数据库可能由 seed 直接建表）" >&2
  exit 0
fi

echo "[migrate] alembic upgrade $REVISION"
"$PY" -m alembic upgrade "$REVISION"
echo "[migrate] 完成"
