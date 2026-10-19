#!/usr/bin/env bash
# Idempotent VPS-only warehouse extension to the existing factory product cycle.
# Never contacts, edits, needs, or publishes to any website.
set -euo pipefail
umask 077
repo="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
base="$HOME/factory-runtime"
ops="$base/operations"
private="$base/private/autonomous-product-cycle"
runtime="$ops/autonomous-product-runtime"
worker="$ops/production-warehouse"
python="$base/.venv/bin/python"
source="$repo/scripts/factory_production_warehouse.py"
cycle_script="$runtime/run-local-cycle.sh"
marker="SAEIT_PRODUCTION_WAREHOUSE_V1"

test "$(id -un)" = githubops || { echo FACTORY_WAREHOUSE_WRONG_SERVICE_USER; exit 1; }
test "$(id -u)" -ne 0
test -d "$base" && test ! -L "$base"
test -d "$ops" && test ! -L "$ops"
test -d "$base/private" && test ! -L "$base/private"
test -x "$python"
test -f "$source" && test ! -L "$source"
test -f "$repo/deploy/install_autonomous_factory_products.sh"
test -f "$repo/scripts/factory_product_maker.py"
command -v flock >/dev/null
command -v crontab >/dev/null
if ! systemctl is-active --quiet cron 2>/dev/null && ! systemctl is-active --quiet crond 2>/dev/null; then
  echo FACTORY_CRON_NOT_RUNNING
  exit 1
fi
if ! systemctl is-enabled --quiet cron 2>/dev/null && ! systemctl is-enabled --quiet crond 2>/dev/null; then
  echo FACTORY_CRON_NOT_BOOT_ENABLED
  exit 1
fi

# If production is not yet installed, use its existing reviewed *VPS-only*
# installer first. Never introduce a new factory, site adapter or downloader.
if ! test -x "$cycle_script" || ! crontab -l 2>/dev/null | grep -q 'SAEIT_AUTONOMOUS_PRODUCTS_V2'; then
  echo FACTORY_WAREHOUSE_BOOTSTRAP_EXISTING_PRODUCTION
  bash "$repo/deploy/install_autonomous_factory_products.sh"
fi
test -x "$cycle_script"
test -d "$private" && test ! -L "$private"
test -d "$private/digital-products" && test ! -L "$private/digital-products"
test "$(crontab -l | grep -c SAEIT_AUTONOMOUS_PRODUCTS_V2)" -eq 1

# Concurrent deployments and warehouse workers are serialized, but the
# independent research and manufacturing loops are deliberately left alone.
exec 8>"$ops/.production-warehouse-deploy.lock"
flock -w 35 8 || { echo FACTORY_WAREHOUSE_DEPLOY_LOCK_BUSY; exit 1; }
install -d -m 700 "$ops/backups"
if test -L "$worker" || test -L "$ops/backups"; then
  echo FACTORY_WAREHOUSE_UNSAFE_FOLDER
  exit 1
fi
install -d -m 700 "$worker"
stamp="$(date -u +%Y%m%dT%H%M%SZ)-$$"
back="$ops/backups/production-warehouse-$stamp"
install -d -m 700 "$back"
crontab -l > "$back/original.cron"
chmod 600 "$back/original.cron"
if test -f "$worker/factory_production_warehouse.py"; then
  test ! -L "$worker/factory_production_warehouse.py"
  cp -p "$worker/factory_production_warehouse.py" "$back/previous-worker.py"
  chmod 600 "$back/previous-worker.py"
fi
if test -f "$worker/run-warehouse.sh"; then
  test ! -L "$worker/run-warehouse.sh"
  cp -p "$worker/run-warehouse.sh" "$back/previous-runner.sh"
  chmod 600 "$back/previous-runner.sh"
fi
rollback() {
  local rc="$?"
  if test "$rc" -ne 0; then
    echo "FACTORY_WAREHOUSE_INSTALL_FAILED_RESTORING_CRON"
    # Retain all unrelated jobs, undo only this add-on after a failed install.
    if crontab -l 2>/dev/null | grep -q "$marker"; then
      (crontab -l 2>/dev/null | grep -v -- "$marker" || true) | crontab - || true
    fi
    if test -f "$back/previous-worker.py"; then
      install -m 600 "$back/previous-worker.py" "$worker/factory_production_warehouse.py"
    fi
    if test -f "$back/previous-runner.sh"; then
      install -m 700 "$back/previous-runner.sh" "$worker/run-warehouse.sh"
    fi
  fi
  exit "$rc"
}
trap rollback EXIT

"$python" -B -m py_compile "$source"
install -m 600 "$source" "$worker/factory_production_warehouse.py"
cat > "$worker/run-warehouse.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
umask 077
exec 9>"$ops/production-warehouse-worker.lock"
flock -n 9 || exit 0
exec >> "$ops/production-warehouse.log" 2>&1
exec "$python" -B "$worker/factory_production_warehouse.py" \\
  --factory-private "$private"
EOF
chmod 700 "$worker/run-warehouse.sh"

# Immediately place any previously manufactured and QA-passed products into
# the new stockroom. Existing failed/rework inputs remain intact.
"$worker/run-warehouse.sh"
"$python" -B "$worker/factory_production_warehouse.py" \
  --factory-private "$private" --verify-only
test -s "$private/production-warehouse/stock-register.json"
"$python" -B - "$private/production-warehouse/stock-register.json" <<'PY'
import json,sys
from pathlib import Path
info=json.loads(Path(sys.argv[1]).read_text(encoding='utf8'))
assert info['schema']=='saeit.factory.production-warehouse.v1'
assert info['factory_site_dependency'] is False
assert info['customer_order_dependency'] is False
assert info['distribution_enabled'] is False
assert info['sites_contacted']==0
print("FACTORY_WAREHOUSE_PRIVATE_STOCK_VERSIONS="+str(info['finished_goods_versions']))
print("FACTORY_WAREHOUSE_SITE_TRANSFERS=0")
PY

# Preserve a verified synchronized one-minute factory run during upgrades.
if crontab -l 2>/dev/null | grep -q SAEIT_FACTORY_EVERY_MINUTE_V1; then
  test "$(crontab -l | grep -c SAEIT_AUTONOMOUS_PRODUCTS_V2)" -eq 1
  test "$(crontab -l | grep -c SAEIT_PRODUCTION_WAREHOUSE_V1)" -eq 1
  trap - EXIT
  echo FACTORY_WAREHOUSE_SCHEDULE=VPS_LOCAL_EVERY_MINUTE_PRESERVED
  echo FACTORY_WAREHOUSE_SITE_PUBLISHING=false
  exit 0
fi

# Existing factory production runs at minute 23; warehouse stock scan is 31.
# It also runs immediately at installation and can be invoked manually.
# Submit directly via stdin to avoid remote temporary crontab file-path issues.
{
  crontab -l 2>/dev/null | grep -v -- "$marker" || true
  printf '31 * * * * /bin/bash %s # %s\n' "$worker/run-warehouse.sh" "$marker"
} | crontab -
test "$(crontab -l | grep -c "$marker")" -eq 1
test "$(crontab -l | grep -c SAEIT_AUTONOMOUS_PRODUCTS_V2)" -eq 1
trap - EXIT

echo FACTORY_WAREHOUSE_VPS_INSTALLED=true
echo FACTORY_WAREHOUSE_MODE=PRODUCE_THEN_STOCK
echo FACTORY_WAREHOUSE_SCHEDULE=VPS_LOCAL_HOURLY_31
echo FACTORY_WAREHOUSE_SITES_REQUIRED=false
echo FACTORY_WAREHOUSE_SITE_PUBLISHING=false
echo FACTORY_WAREHOUSE_NO_WEBSITE_MODIFICATIONS=true
echo FACTORY_WAREHOUSE_BACKUP="$back"
