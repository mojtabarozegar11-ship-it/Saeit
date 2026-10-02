#!/bin/bash
set -euo pipefail

APPROOT="${SAEIT_APPROOT:-/home/zomorodm/repositories/Saeit}"
cd "$APPROOT"

if [ -n "${VIRTUAL_ENV:-}" ] && [ -x "$VIRTUAL_ENV/bin/python" ]; then
  PYTHON="$VIRTUAL_ENV/bin/python"
elif [ -x "/home/zomorodm/virtualenv/repositories/Saeit/3.11/bin/python" ]; then
  PYTHON="/home/zomorodm/virtualenv/repositories/Saeit/3.11/bin/python"
else
  PYTHON="$(command -v python3 || command -v python)"
fi

exec "$PYTHON" manage.py economic_autorun
