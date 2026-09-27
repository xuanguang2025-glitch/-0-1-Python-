#!/usr/bin/env bash
# PYTHON LAB —— 导入种子数据（18 阶段课程 / 题库 / 项目 / 知识点 / 成就 ...）
# 用法：bash scripts/seed.sh [--only courses,problems]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/backend"

if [ -x .venv/bin/python ]; then
  PY="./.venv/bin/python"
elif [ -x .venv/Scripts/python.exe ]; then
  PY="./.venv/Scripts/python.exe"
else
  echo "[seed] 未找到 backend/.venv，请先运行 scripts/setup.sh" >&2
  exit 1
fi

if [ -f scripts/seed_data.py ]; then
  echo "[seed] python scripts/seed_data.py $*"
  "$PY" scripts/seed_data.py "$@"
elif [ -f app/db/seed/loader.py ]; then
  echo "[seed] python -m app.db.seed.loader $*"
  "$PY" -m app.db.seed.loader "$@"
else
  echo "[seed] 未找到种子导入脚本（scripts/seed_data.py 或 app/db/seed/loader.py）" >&2
  exit 1
fi

echo "[seed] 完成"
