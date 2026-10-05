#!/bin/sh
set -eu
ROOT="${1:-.}"
OUT="${2:-zomorod-staging-transfer.tar.gz}"
cd "$ROOT"
test -f manage.py
test -f deploy/staging/.env.staging.example
# Source-only handoff: never package local secrets, databases, caches, VCS metadata or runtime artifacts.
tar --exclude='.git' --exclude='.env' --exclude='.env.*' --exclude='*.sqlite3' --exclude='__pycache__' --exclude='.pytest_cache' --exclude='.venv' --exclude='venv' --exclude='virtualenv' --exclude='media' --exclude='var' -czf "$OUT" .
sha256sum "$OUT" > "$OUT.sha256"
printf 'PACKAGE=%s\n' "$OUT"
cat "$OUT.sha256"
