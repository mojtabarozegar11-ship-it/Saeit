#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APPROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
cd "$APPROOT"

if [ ! -f manage.py ]; then
    echo "ERROR: manage.py not found in resolved app root: $APPROOT" >&2
    exit 1
fi

if [ -n "${VIRTUAL_ENV:-}" ] && [ -x "$VIRTUAL_ENV/bin/python" ]; then
    PYTHON="$VIRTUAL_ENV/bin/python"
elif [ -x "$APPROOT/venv/bin/python" ]; then
    PYTHON="$APPROOT/venv/bin/python"
elif [ -x "$APPROOT/.venv/bin/python" ]; then
    PYTHON="$APPROOT/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
    PYTHON="$(command -v python)"
else
    echo "ERROR: Python executable not found." >&2
    exit 1
fi

echo "Deploy root: $APPROOT"
echo "Using Python: $PYTHON"
"$PYTHON" --version

"$PYTHON" manage.py check --deploy
"$PYTHON" manage.py migrate --noinput
"$PYTHON" manage.py production_gate
"$PYTHON" manage.py collectstatic --noinput

touch passenger_wsgi.py

echo "Saeit Django deployment completed."
