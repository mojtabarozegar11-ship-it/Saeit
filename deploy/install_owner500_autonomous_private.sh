#!/usr/bin/env bash
# Safely extend the existing minute factory without altering its runner or site deployments.
set -Eeuo pipefail
trap 'echo "OWNER500_AUTONOMY_INSTALL_FAIL_LINE=$LINENO" >&2' ERR
umask 077
test "$(id -un)" = githubops
test "$(id -u)" -ne 0
test "$#" -eq 1
source_stage="$1"
base="$HOME/factory-runtime"
ops="$base/operations"
private="$base/private/autonomous-product-cycle"
dest="$ops/owner500-autonomous-scheduler"
marker=SAEIT_OWNER500_AUTONOMOUS_F28_V1
python="$base/.venv/bin/python"
for dir in "$source_stage" "$base" "$ops" "$private"; do
  test -d "$dir" && test ! -L "$dir" || { echo "AUTONOMY_REQUIRED_SAFE_DIRECTORY_MISSING:$dir"; exit 1; }
done
test -x "$python"
test -d "$private/generated-product-recipes"
test -s "$private/production-order-inputs/factory-invention-snapshot.json"
test -f "$ops/production-warehouse/run-minute-cycle.sh"
command -v flock
command -v crontab
command -v sha256sum
if ! systemctl is-active --quiet cron 2>/dev/null && ! systemctl is-active --quiet crond 2>/dev/null; then
  echo OWNER500_AUTONOMY_CRON_SERVICE_INACTIVE
  exit 1
fi
if test -L "$dest"; then
  echo OWNER500_AUTONOMY_DEST_SYMLINK_BLOCKED
  exit 1
fi
install -d -m 700 "$dest" "$ops/backups"
exec 8>"$ops/.owner500-autonomous-install.lock"
flock -w 40 8
old_cron="$(mktemp "$ops/backups/owner500-cron-before.XXXXXXXX")"
crontab -l > "$old_cron"
chmod 600 "$old_cron"
minute_count="$(grep -Ec '^[^#]*SAEIT_FACTORY_EVERY_MINUTE_V1' "$old_cron" || true)"
owner_count="$(grep -Ec "^[^#]*$marker" "$old_cron" || true)"
echo "OWNER500_AUTONOMY_EXISTING_MINUTE_CRON_ENTRIES=$minute_count"
echo "OWNER500_AUTONOMY_EXISTING_OWNER_CRON_ENTRIES=$owner_count"
# Existing factory main cron is a separate subsystem; do not rewrite it here.
# Only block ambiguous duplicate markers. The dedicated owner500 runner can
# be installed even when main's marker is missing (a separately reported gap).
test "$minute_count" -le 1
if test "$minute_count" -eq 0; then
  echo OWNER500_AUTONOMY_MAIN_MINUTE_SCHEDULE_NOT_VERIFIED=YES
fi
test "$owner_count" -le 1
backup="$ops/backups/owner500-autonomy-$(date -u +%Y%m%dT%H%M%SZ)-$$"
install -d -m 700 "$backup"
cp -p "$old_cron" "$backup/previous.cron"
for f in factory_owner500_autonomous_engine.py factory_design_intake.py factory_recipe_designer.py factory_product_maker.py factory_verified_customer_cycle_20261021.py factory_personal_owner_passport_policy_20261020.py owner_demand_500_20261022.json owner500_autonomous_f28_formulas.json; do
  test -s "$source_stage/$f" && test ! -L "$source_stage/$f"
  if test -e "$dest/$f"; then
    test -f "$dest/$f" && test ! -L "$dest/$f"
    cp -p "$dest/$f" "$backup/$f"
  fi
  install -m 600 "$source_stage/$f" "$dest/$f"
  test "$(sha256sum "$source_stage/$f" | awk '{print $1}')" = "$(sha256sum "$dest/$f" | awk '{print $1}')"
done
runner="$dest/run.sh"
if test -e "$runner"; then
  test -f "$runner" && test ! -L "$runner"
  cp -p "$runner" "$backup/previous-runner.sh"
fi
stage_runner="$(mktemp "$dest/.runner.XXXXXXXX")"
cat > "$stage_runner" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
umask 077
ops="$HOME/factory-runtime/operations"
base="$HOME/factory-runtime"
private="$base/private/autonomous-product-cycle"
scheduler="$ops/owner500-autonomous-scheduler"
exec 7>"$ops/.factory-minute-cycle.lock"
flock -w 50 7 || { echo OWNER500_AUTONOMY_FACTORY_BUSY_SKIPPED; exit 0; }
exec 9>"$scheduler/.cron-run.lock"
flock -n 9 || exit 0
exec >> "$scheduler/autonomous-cycle.log" 2>&1
echo "OWNER500_AUTONOMY_START_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
timeout 160s "$base/.venv/bin/python" -B "$scheduler/factory_owner500_autonomous_engine.py" \
  --factory-private "$private" --owner-catalog "$scheduler/owner_demand_500_20261022.json" \
  --formula-queue "$scheduler/owner500_autonomous_f28_formulas.json" \
  --scripts-dir "$scheduler" --limit 1
result=$?
echo "OWNER500_AUTONOMY_END_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
exit "$result"
SH
bash -n "$stage_runner"
chmod 700 "$stage_runner"
mv -f "$stage_runner" "$runner"
# Run one real canary BEFORE installing the recurring schedule.
if ! timeout 215s /bin/bash "$runner"; then
  echo OWNER500_AUTONOMY_CANARY_FAILED_NOT_SCHEDULED
  exit 1
fi
log="$dest/autonomous-cycle.log"
test -s "$log"
grep -q 'FACTORY_OWNER500_AUTONOMOUS_CYCLE=' "$log"
# The private state is real and checked by SHA-bound receipt.
"$python" -B - "$private" <<'PY'
import json,sys
from pathlib import Path
root=Path(sys.argv[1])
state=root/'owner500-autonomous-production/state.json'
report=json.loads(state.read_text())
assert report["schema"]=="saeit.factory.autonomous-owner500-f28.v1"
assert report["quality1000_certified"]==0
assert report["website_deployments"]==0
assert report["payments_touched"]==0
assert report["verified_private_products"]>=1
assert report["supported_formula_briefs"]==20
print("OWNER500_AUTONOMY_VPS_REAL_CANARY_VERIFIED="+str(report["verified_private_products"]))
print("OWNER500_AUTONOMY_VPS_NEW_THIS_CANARY="+str(report["new_private_products_this_tick"]))
PY
entry="*/5 * * * * /bin/bash $runner # $marker"
next="$(mktemp "$ops/backups/owner500-proposed-cron.XXXXXXXX")"
"$python" - "$old_cron" "$next" "$entry" "$marker" <<'PY'
from pathlib import Path
import sys
before,after,entry,marker=sys.argv[1:]
rows=Path(before).read_text().splitlines()
active=[row for row in rows if marker in row and not row.lstrip().startswith("#")]
if active and active!=[entry]:
    raise SystemExit("OWNER500_AUTONOMY_EXISTING_SCHEDULE_CONFLICT")
if not active: rows.append(entry)
Path(after).write_text("\n".join(rows)+"\n")
PY
chmod 600 "$next"
# Do not overwrite concurrent edits by administrators or other workflows.
test "$(sha256sum "$old_cron" | cut -d' ' -f1)" = "$(crontab -l | sha256sum | cut -d' ' -f1)" || {
  echo OWNER500_AUTONOMY_CRONTAB_CHANGED_CONCURRENTLY
  exit 1
}
crontab "$next"
actual="$(crontab -l | grep -F "$marker" | grep -vE '^[[:space:]]*#' || true)"
if test "$actual" != "$entry"; then
  echo OWNER500_AUTONOMY_SCHEDULE_VERIFY_FAILED
  if test "$(crontab -l | sha256sum | cut -d' ' -f1)" = "$(sha256sum "$next" | cut -d' ' -f1)"; then
    crontab "$old_cron"
  fi
  exit 1
fi
echo "OWNER500_AUTONOMY_VPS_INSTALLED=PASS"
echo "OWNER500_AUTONOMY_CADENCE=EVERY_5_MINUTES"
echo "OWNER500_AUTONOMY_CRON_MARKER=$marker"
echo "OWNER500_AUTONOMY_BACKUP=$backup"
echo OWNER500_AUTONOMY_SITES_UNMODIFIED=YES
