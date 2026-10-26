#!/usr/bin/env bash
# Deploy only the already-CI-verified factory customer QA cadence into the
# canonical private VPS manufacturer. Never touch sites, cron, orders or goods.
set -euo pipefail
umask 077
test "$#" -eq 2
staged="$1"
revision="$2"
[[ "$revision" =~ ^[0-9a-f]{40}$ ]] || exit 64
test "$(id -un)" = "githubops"
base="$HOME/factory-runtime"
ops="$base/operations"
target="$ops/autonomous-product-runtime/scripts"
test -d "$target" && test ! -L "$target"
test -d "$staged" && test ! -L "$staged"
names=(factory_verified_customer_cycle_20261021.py factory_vps_product_cycle.py)
for name in "${names[@]}"; do
  test -f "$staged/scripts/$name" && test ! -L "$staged/scripts/$name"
  test -f "$target/$name" && test ! -L "$target/$name"
done
exec 8>"$ops/.factory-minute-cycle.lock"
flock -w 480 8 || { echo FACTORY_CADENCE_OUTER_LOCK_BUSY; exit 2; }
exec 9>"$ops/autonomous-product-cycle.lock"
flock -w 60 9 || { echo FACTORY_CADENCE_INNER_LOCK_BUSY; exit 2; }
backup="$ops/backups/customer-qa-cadence-$revision"
test ! -e "$backup"
install -d -m 700 "$ops/backups" "$backup"
for name in "${names[@]}"; do
  cp -p -- "$target/$name" "$backup/$name"
done
armed=true
rollback() {
  result=$?
  if test "$armed" = true; then
    for name in "${names[@]}"; do
      cp -p -- "$backup/$name" "$target/$name" || true
    done
    echo FACTORY_CADENCE_RUNTIME_ROLLED_BACK >&2
  fi
  exit "$result"
}
trap rollback EXIT
for name in "${names[@]}"; do
  temp="$(mktemp "$target/.cadence-$name.XXXXXXXX")"
  install -m 600 -- "$staged/scripts/$name" "$temp"
  python3 -B - "$temp" <<'PY'
import ast, pathlib, sys
ast.parse(pathlib.Path(sys.argv[1]).read_text(encoding="utf8"))
PY
  mv -f -- "$temp" "$target/$name"
  test "$(sha256sum "$target/$name" | awk '{print $1}')" = "$(sha256sum "$staged/scripts/$name" | awk '{print $1}')"
done
armed=false
trap - EXIT
echo FACTORY_CADENCE_TWO_CANONICAL_SCRIPTS_DEPLOYED=true
echo FACTORY_CADENCE_BACKUP_RETAINED="$backup"
echo FACTORY_CADENCE_SITES_MODIFIED=false
