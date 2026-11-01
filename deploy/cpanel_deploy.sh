#!/bin/bash
set -euo pipefail

# cPanel executes deployment tasks from the checked-out repository root.
APPROOT="$(pwd -P)"
if [ ! -f "$APPROOT/manage.py" ] || [ ! -f "$APPROOT/passenger_wsgi.py" ]; then
    echo "ERROR: deployment must run from the Django repository root: $APPROOT" >&2
    exit 1
fi

if [ -n "${VIRTUAL_ENV:-}" ] && [ -x "$VIRTUAL_ENV/bin/python" ]; then
    PYTHON="$VIRTUAL_ENV/bin/python"
else
    PYTHON=""
    for candidate in \
        "$HOME/virtualenv/Saeit/3.11/bin/python" \
        "$HOME/virtualenv/repositories/Saeit/3.11/bin/python" \
        "/home/zomorod2/virtualenv/Saeit/3.11/bin/python" \
        "/home/zomorod2/virtualenv/repositories/Saeit/3.11/bin/python"; do
        if [ -x "$candidate" ]; then PYTHON="$candidate"; break; fi
    done
    if [ -z "$PYTHON" ]; then
        echo "ERROR: Django virtualenv not found; refusing to deploy using system Python." >&2
        exit 1
    fi
fi

"$PYTHON" --version
"$PYTHON" manage.py check --deploy
# Prevent Django's SQLite connection from creating a missing/default empty DB.
# This probe uses immutable read-only SQLite and never initializes a database.
"$PYTHON" scripts/production_db_readonly_preflight.py
# Schema migrations require a separately authorized, independently restorable release.
"$PYTHON" manage.py migrate --check
"$PYTHON" manage.py production_gate
"$PYTHON" manage.py collectstatic --noinput
touch passenger_wsgi.py
echo "Saeit Django deployment completed from $APPROOT."
