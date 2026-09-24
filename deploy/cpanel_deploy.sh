#!/bin/bash
set -e

APPROOT="/home/zomorodm/repositories/Saeit"
cd "$APPROOT"

if [ -n "${VIRTUAL_ENV:-}" ] && [ -x "$VIRTUAL_ENV/bin/python" ]; then
    PYTHON="$VIRTUAL_ENV/bin/python"
elif [ -x "/home/zomorodm/virtualenv/repositories/Saeit/3.11/bin/python" ]; then
    PYTHON="/home/zomorodm/virtualenv/repositories/Saeit/3.11/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
    PYTHON="$(command -v python)"
else
    echo "ERROR: Python executable not found."
    exit 1
fi

echo "Using Python: $PYTHON"
"$PYTHON" --version

"$PYTHON" manage.py check --deploy
"$PYTHON" manage.py migrate --noinput
"$PYTHON" manage.py collectstatic --noinput

# Passenger reload: touching the WSGI entrypoint requests a graceful reload.
touch passenger_wsgi.py

echo "Saeit Django deployment completed."
