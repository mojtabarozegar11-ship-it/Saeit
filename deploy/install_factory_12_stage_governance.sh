#!/usr/bin/env bash
# Sidecar control-plane only: NEVER reconfigure existing factory minute cadence,
# delete old technical goods, publish a site, or assert QA automatically.
set -euo pipefail
umask 077
test "$(id -un)" = githubops
test "$(id -u)" -ne 0
test "$#" -eq 1
source_file="$1"
test -f "$source_file" && test ! -L "$source_file"
base="$HOME/factory-runtime"
ops="$base/operations"
private="$base/private/autonomous-product-cycle"
destdir="$ops/12-stage-governance"
worker="$destdir/factory_12_stage_governance.py"
runner="$destdir/run-readonly-lifecycle-tick.sh"
identifier=SAEIT_FACTORY_LIFECYCLE_12_V1
python="$base/.venv/bin/python"
test -d "$ops" && test ! -L "$ops"
test -d "$private" && test ! -L "$private"
test -x "$python"
test -s "$private/production-warehouse/stock-register.json"
test -d "$private/production-instructions/orders"
test "$(crontab -l | grep -c SAEIT_FACTORY_EVERY_MINUTE_V1)" -eq 1
command -v flock >/dev/null
exec 7>"$ops/.factory-lifecycle-deploy.lock"
flock -w 30 7 || { echo LIFECYCLE_DEPLOY_LOCK_BUSY; exit 1; }
test ! -L "$destdir"
install -d -m 700 "$destdir" "$ops/backups"
stamp="$(date -u +%Y%m%dT%H%M%SZ)-$$"
backup="$ops/backups/12-stage-governance-$stamp"
install -d -m 700 "$backup"
crontab -l > "$backup/previous-cron.txt"
chmod 600 "$backup/previous-cron.txt"
for file in "$worker" "$runner"; do
  test ! -L "$file"
  if test -f "$file"; then cp -p "$file" "$backup/$(basename "$file").original"; fi
done
"$python" -B -c 'import ast,sys;ast.parse(open(sys.argv[1],encoding="utf8").read())' "$source_file"
tmp="$(mktemp "$destdir/.governance.XXXXXX")"
install -m 600 "$source_file" "$tmp"
mv -f -- "$tmp" "$worker"

cat > "$runner" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
umask 077
ops="$HOME/factory-runtime/operations"
private="$HOME/factory-runtime/private/autonomous-product-cycle"
exec 8>"$ops/.lifecycle-tick.lock"
flock -n 8 || exit 0
exec >> "$ops/factory-lifecycle-stages.log" 2>&1
"$HOME/factory-runtime/.venv/bin/python" -B \
 "$ops/12-stage-governance/factory_12_stage_governance.py" \
 --factory-private "$private" --tick
SH
chmod 700 "$runner"
bash -n "$runner"
if grep -Eq 'curl |wget |rsync |scp |store_sender|multisite_orchestrator|passenger|payment' "$runner"; then
  echo LIFECYCLE_NETWORK_ACTION_FORBIDDEN
  exit 1
fi
# This is a genuine 12-stage dashboard and product passport gate; does not
# move any technical goods into final commercial stock.
"$runner"
"$python" -B - "$private/product-lifecycle/dashboard.json" <<'PY'
import json,sys
from pathlib import Path
v=json.loads(Path(sys.argv[1]).read_text(encoding="utf8"))
assert v["schema"]=="saeit.factory.lifecycle.v1"
assert len(v["stages"])==12
assert v["independent_quality_gate_enforced"] is True
assert v["site_distribution_enabled"] is False and v["sites_contacted"]==0
assert v["instructions_seen"]>=1
assert v["final_commercially_verified_stock"]==0
print("FACTORY_12_STAGE_STATUS=QA_GATED")
print("FACTORY_12_STAGE_INSTRUCTIONS="+str(v["instructions_seen"]))
print("FACTORY_TECHNICAL_STOCK_AWAITING_FINAL_QA="+str(v["old_technical_QA_stock_pending_final_review"]))
print("FACTORY_FINAL_APPROVED_STOCK="+str(v["final_commercially_verified_stock"]))
print("FACTORY_12_STAGE_DISTRIBUTION_ENABLED=false")
PY

# Keep the original minute factory cron intact, and never add a duplicate.
old="$backup/previous-cron.txt"
proposed="$backup/proposed-cron.txt"
grep -v -- "$identifier" "$old" > "$proposed" || true
printf '* * * * * /bin/bash %s # %s\n' "$runner" "$identifier" >> "$proposed"
chmod 600 "$proposed"
test "$(crontab -l | sha256sum | awk '{print $1}')" = "$(sha256sum "$old" | awk '{print $1}')" || {
  echo LIFECYCLE_CRON_CONCURRENT_CHANGE
  exit 1
}
crontab - < "$proposed"
if test "$(crontab -l | grep -c "$identifier")" -ne 1 ||
   test "$(crontab -l | grep -c SAEIT_FACTORY_EVERY_MINUTE_V1)" -ne 1; then
  echo LIFECYCLE_CRON_VERIFY_FAILED
  if test "$(crontab -l | sha256sum | awk '{print $1}')" = "$(sha256sum "$proposed" | awk '{print $1}')" ; then
    crontab - < "$old" || true
  fi
  exit 1
fi
echo FACTORY_12_STAGE_VPS_INSTALLED=PASS
echo FACTORY_12_STAGE_CADENCE=EVERY_MINUTE
echo FACTORY_12_STAGE_LEGACY_STOCK_UNTOUCHED=YES
echo FACTORY_12_STAGE_SITES_CONTACTED=ZERO
echo FACTORY_12_STAGE_BACKUP="$backup"
