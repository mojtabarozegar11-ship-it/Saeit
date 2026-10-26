#!/usr/bin/env bash
# Protected factory-only replacement of BUILD50 audit in BOTH live workers.
# No cron, sites, product inventory, order or quality-gate mutations.
set -euo pipefail
umask 077
test "$#" -eq 2
staged="$1"
revision="$2"
[[ "$revision" =~ ^[0-9a-f]{40}$ ]] || exit 64
test "$(id -un)" = githubops
base="$HOME/factory-runtime"
ops="$base/operations"
target_main="$ops/autonomous-product-runtime/scripts/factory_build_50.py"
target_warehouse="$ops/production-warehouse/factory_build_50.py"
source="$staged/scripts/factory_build_50.py"
test -d "$ops" && test ! -L "$ops"
test -d "$staged" && test ! -L "$staged"
test -f "$source" && test ! -L "$source"
for path in "$target_main" "$target_warehouse"; do
  test -f "$path" && test ! -L "$path"
  test -d "$(dirname "$path")" && test ! -L "$(dirname "$path")"
done
exec 8>"$ops/.factory-minute-cycle.lock"
flock -w 480 8 || { echo FACTORY_BUILD50_OUTER_LOCK_BUSY; exit 2; }
exec 9>"$ops/autonomous-product-cycle.lock"
flock -w 60 9 || { echo FACTORY_BUILD50_INNER_LOCK_BUSY; exit 2; }
exec 7>"$ops/production-warehouse-worker.lock"
flock -w 60 7 || { echo FACTORY_BUILD50_WAREHOUSE_LOCK_BUSY; exit 2; }
test ! -L "$ops/backups"
backup="$ops/backups/build50-io-$revision"
test ! -e "$backup"
install -d -m 700 "$ops/backups" "$backup"
cp -p -- "$target_main" "$backup/factory-build50-main.py"
cp -p -- "$target_warehouse" "$backup/factory-build50-warehouse.py"
armed=true
rollback() {
  result=$?
  if test "$armed" = true; then
    cp -p -- "$backup/factory-build50-main.py" "$target_main" || true
    cp -p -- "$backup/factory-build50-warehouse.py" "$target_warehouse" || true
    echo FACTORY_BUILD50_IO_ROLLED_BACK >&2
  fi
  exit "$result"
}
trap rollback EXIT
python3 -B - "$source" <<'PY'
import ast,pathlib,sys
ast.parse(pathlib.Path(sys.argv[1]).read_text(encoding="utf8"))
PY
expected="$(sha256sum "$source" | awk '{print $1}')"
for path in "$target_main" "$target_warehouse"; do
  temp="$(mktemp "$(dirname "$path")/.build50-io-XXXXXXXX")"
  install -m 600 -- "$source" "$temp"
  mv -f -- "$temp" "$path"
  test "$(sha256sum "$path" | awk '{print $1}')" = "$expected"
done
armed=false
trap - EXIT
echo FACTORY_BUILD50_IO_TWO_RUNTIME_COPIES_DEPLOYED=true
echo FACTORY_BUILD50_IO_BACKUP_RETAINED="$backup"
echo FACTORY_BUILD50_IO_SITE_CHANGES=false
