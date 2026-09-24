#!/usr/bin/env bash
set -u

# Read-only cPanel preflight. It does not migrate, write files, restart Passenger,
# expose secrets, or modify the database.

ROOT="${1:-/home/zomorodm/repositories/Saeit}"
cd "$ROOT" || { echo "ERROR: project root not found: $ROOT"; exit 1; }

echo "== SAEIT CPANEL PREFLIGHT =="
echo "root=$PWD"

echo
echo "== Python =="
if command -v python >/dev/null 2>&1; then
  python --version
  python -c 'import sys; print("executable="+sys.executable)'
else
  echo "ERROR: python command not found"
fi

echo
echo "== Django import =="
python -c 'import django; print("django="+django.get_version())' 2>&1 || true

echo
echo "== Required files =="
for f in manage.py passenger_wsgi.py requirements.txt .env; do
  if [ -f "$f" ]; then
    echo "OK  $f"
  else
    if [ "$f" = ".env" ]; then
      echo "MISSING $f (expected server-side; do not create it from this script)"
    else
      echo "ERROR $f"
    fi
  fi
done

echo
echo "== Django read-only checks =="
python manage.py check 2>&1 || true

echo
echo "== Migration state (read-only) =="
python manage.py showmigrations --plan 2>&1 || true

echo
echo "== Passenger entrypoint =="
python -c 'import passenger_wsgi; print("WSGI import: OK")' 2>&1 || true

echo
echo "== Preflight complete =="
echo "No production mutation was performed."
