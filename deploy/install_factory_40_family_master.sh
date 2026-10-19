#!/usr/bin/env bash
# Install a *read-only with respect to products* 40-family capacity planner
# on the existing VPS; never modify live production, inventory or child sites.
set -euo pipefail
umask 077
test "$(id -un)" = githubops
test "$(id -u)" -ne 0
test "$#" -eq 2
source_python="$1"; source_registry="$2"
test -f "$source_python" && test ! -L "$source_python"
test -f "$source_registry" && test ! -L "$source_registry"
base="$HOME/factory-runtime"
ops="$base/operations"
private="$base/private/autonomous-product-cycle"
target="$ops/forty-family-master"
py="$target/factory_40_family_master.py"
registry="$target/forty_families.json"
run="$target/run-minute-master.sh"
marker=SAEIT_FACTORY_FORTY_FAMILY_MASTER_V1
python="$base/.venv/bin/python"
test -x "$python"
test -d "$ops" && test ! -L "$ops"
test -d "$private" && test ! -L "$private"
test -d "$private/product-lifecycle" && test ! -L "$private/product-lifecycle"
test -d "$private/production-instructions/orders" && test ! -L "$private/production-instructions/orders"
test -s "$private/production-warehouse/stock-register.json"
test "$(crontab -l | grep -c SAEIT_FACTORY_EVERY_MINUTE_V1)" -eq 1
test "$(crontab -l | grep -c SAEIT_FACTORY_LIFECYCLE_12_V1)" -eq 1
command -v flock >/dev/null
exec 7>"$ops/.factory-forty-master-install.lock"
flock -w 30 7 || { echo FACTORY_FORTY_MASTER_INSTALL_BUSY; exit 1; }
test ! -L "$target"
test ! -L "$ops/backups"
install -d -m 700 "$target" "$ops/backups"
stamp="$(date -u +%Y%m%dT%H%M%SZ)-$$"
backup="$ops/backups/forty-master-$stamp"
install -d -m 700 "$backup"
crontab -l > "$backup/previous-cron"
chmod 600 "$backup/previous-cron"
for item in "$py" "$registry" "$run"; do
  test ! -L "$item"
  if test -f "$item"; then cp -p "$item" "$backup/$(basename "$item").old"; fi
done
"$python" -B -c 'import ast,sys;ast.parse(open(sys.argv[1],encoding="utf8").read())' "$source_python"
"$python" -B - "$source_registry" <<'PY'
import importlib.util,json,sys
from pathlib import Path
path=Path(sys.argv[1])
registry=json.loads(path.read_text(encoding='utf8'))
assert registry["schema"]=="saeit.factory.family-registry.v1"
assert len(registry["profiles"])==40
assert registry["distribution_enabled"] is False
print("FORTY_MASTER_FAMILIES_SOURCE=40")
PY
stagepy="$(mktemp "$target/.master-script.XXXXXXXX")"
stagereg="$(mktemp "$target/.master-profiles.XXXXXXXX")"
install -m 600 "$source_python" "$stagepy"
install -m 600 "$source_registry" "$stagereg"
mv -f -- "$stagepy" "$py"
mv -f -- "$stagereg" "$registry"
chmod 600 "$py" "$registry"
cat > "$run" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
umask 077
ops="$HOME/factory-runtime/operations"
private="$HOME/factory-runtime/private/autonomous-product-cycle"
exec 8>"$ops/.factory-forty-minute-master.lock"
flock -n 8 || exit 0
exec >> "$ops/factory-forty-family-master.log" 2>&1
"$HOME/factory-runtime/.venv/bin/python" -B \
  "$ops/forty-family-master/factory_40_family_master.py" \
  --factory-private "$private" --registry "$ops/forty-family-master/forty_families.json"
SH
chmod 700 "$run"
bash -n "$run"
if grep -Eq 'curl |wget |rsync |scp |publish|store_sender|multisite_orchestrator|payment' "$run"; then
  echo FACTORY_FORTY_MASTER_SITE_DEPENDENCY_DENIED
  exit 1
fi
"$run"
"$python" -B - "$private/production-family-management/family-dashboard.json" <<'PY'
import json,sys
from pathlib import Path
p=Path(sys.argv[1])
v=json.loads(p.read_text(encoding='utf8'))
assert v["schema"]=="saeit.factory.family-master-dashboard.v1"
assert v["registered_families"]==40
assert v["fully_verified_active_producer_families"]==0
assert v["max_total_simultaneous_jobs_authorized"]==0
assert v["distribution_enabled"] is False and v["sites_contacted"]==0
assert len(v["families"])==40
print("FACTORY_40_REGISTERED_FAMILIES=40")
print("FACTORY_40_VERIFIED_PRODUCER_LINES="+str(v["fully_verified_active_producer_families"]))
print("FACTORY_40_TOTAL_UNASSIGNED_ORDERS="+str(sum(v["unassigned_work_orders"].values())))
print("FACTORY_40_VPS_MEASURED_CAPACITY="+str(v["measured_vps_capacity"]["worker_slots_theoretical"]))
PY

# Append only this independent reporting sidecar, preserve all factory cron.
old="$backup/previous-cron"
proposed="$backup/proposed-cron"
grep -v "$marker" "$old" > "$proposed" || true
printf '* * * * * /bin/bash %s # %s\n' "$run" "$marker" >> "$proposed"
chmod 600 "$proposed"
test "$(crontab -l | sha256sum | awk '{print $1}')" = "$(sha256sum "$old" | awk '{print $1}')" || {
  echo FACTORY_FORTY_CONCURRENT_CRON_CHANGE
  exit 1
}
crontab - < "$proposed"
if test "$(crontab -l | grep -c "$marker")" -ne 1 ||
   test "$(crontab -l | grep -c SAEIT_FACTORY_EVERY_MINUTE_V1)" -ne 1 ||
   test "$(crontab -l | grep -c SAEIT_FACTORY_LIFECYCLE_12_V1)" -ne 1; then
  echo FACTORY_FORTY_CRON_VERIFY_FAILED
  if test "$(crontab -l | sha256sum | awk '{print $1}')" = "$(sha256sum "$proposed" | awk '{print $1}')" ; then
    crontab - < "$old" || true
  fi
  exit 1
fi
echo FACTORY_40_FAMILY_MASTER_INSTALLED=PASS
echo FACTORY_40_FAMILY_MASTER_INTERVAL_SECONDS=60
echo FACTORY_40_FAMILY_PRODUCT_EXECUTION=NOT_AUTOMATICALLY_AUTHORIZED
echo FACTORY_40_FAMILY_EXISTING_PRODUCTION_UNTOUCHED=true
echo FACTORY_40_FAMILY_EXISTING_STOCK_UNTOUCHED=true
echo FACTORY_40_FAMILY_SITE_TRANSFER_ENABLED=false
echo FACTORY_40_FAMILY_ROLLBACK_BACKUP="$backup"
