#!/bin/zsh
set -e
cd -- "$(dirname -- "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "First run: install Python 3.12 and uv, then run uv sync."
  exit 1
fi
if [ ! -f frontend/dist/index.html ]; then
  echo "First run: npm --prefix frontend ci && npm --prefix frontend run build"
  exit 1
fi
exec .venv/bin/python -m wheat_assistant.launcher
