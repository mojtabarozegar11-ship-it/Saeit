#!/usr/bin/env bash
# Replace two HOURLY production/warehouse cron entries, or safely restore an
# absent scheduler, with one coordinated EVERY-MINUTE cron. Never site transfer.
set -euo pipefail
umask 077
test "$(id -un)" = githubops
test "$(id -u)" -ne 0
base="$HOME/factory-runtime"
ops="$base/operations"
runtime="$ops/autonomous-product-runtime"
stock="$ops/production-warehouse"
maker="$runtime/run-local-cycle.sh"
ware="$stock/run-warehouse.sh"
runner="$stock/run-minute-cycle.sh"
marker="SAEIT_FACTORY_EVERY_MINUTE_V1"
mfgmarker="SAEIT_AUTONOMOUS_PRODUCTS_V2"
stockmarker="SAEIT_PRODUCTION_WAREHOUSE_V1"
test -d "$base" && test ! -L "$base"
test -d "$ops" && test ! -L "$ops"
test -d "$runtime" && test ! -L "$runtime"
test -d "$stock" && test ! -L "$stock"
test -x "$maker" && test -f "$maker" && test ! -L "$maker"
test -x "$ware" && test -f "$ware" && test ! -L "$ware"
test -d "$base/private/autonomous-product-cycle/production-warehouse/finished"
test -s "$base/private/autonomous-product-cycle/production-warehouse/stock-register.json"
command -v crontab >/dev/null
command -v flock >/dev/null
if ! systemctl is-active --quiet cron 2>/dev/null && ! systemctl is-active --quiet crond 2>/dev/null; then
  echo FACTORY_MINUTE_CRON_INACTIVE
  exit 1
fi
if ! systemctl is-enabled --quiet cron 2>/dev/null && ! systemctl is-enabled --quiet crond 2>/dev/null; then
  echo FACTORY_MINUTE_CRON_BOOT_DISABLED
  exit 1
fi

exec 7>"$ops/.factory-minute-scheduler-deploy.lock"
flock -w 20 7 || { echo FACTORY_MINUTE_DEPLOY_LOCK_BUSY; exit 1; }
test ! -L "$ops/backups"
install -d -m 700 "$ops/backups"
stamp="$(date -u +%Y%m%dT%H%M%SZ)-$$"
backup="$ops/backups/factory-minute-$stamp"
install -d -m 700 "$backup"
crontab -l > "$backup/previous.cron"
chmod 600 "$backup/previous.cron"

python3 - "$backup/previous.cron" "$maker" "$ware" "$runner" "$mfgmarker" "$stockmarker" "$marker" <<'PY'
from pathlib import Path
import sys
p,maker,ware,runner,mfg,stock,newmark=sys.argv[1:]
lines=Path(p).read_text().splitlines()
active=[line for line in lines if line.strip() and not line.lstrip().startswith("#")]
factory=[line for line in active if mfg in line]
warehouse=[line for line in active if stock in line]
expected_new="* * * * * /bin/bash "+runner+" # "+mfg+" "+stock+" "+newmark
old_mfg="23 * * * * /bin/bash "+maker+" # "+mfg
old_wh="31 * * * * /bin/bash "+ware+" # "+stock
if factory==[expected_new] and warehouse==[expected_new]:
    print("FACTORY_MINUTE_SCHEDULE_ALREADY_CORRECT")
elif factory==[old_mfg] and warehouse==[old_wh]:
    print("FACTORY_MINUTE_OLD_SCHEDULE_VALIDATED")
elif not factory and not warehouse:
    # The live owner500 canary identified a VPS with no original minute marker.
    # Never add a second driver if an unmarked or differently named cron calls
    # any of these executables; preserve all unrelated specialist schedules.
    if any(any(token in line for token in (maker,ware,runner,newmark)) for line in active):
        raise SystemExit("FACTORY_MINUTE_UNMARKED_COMPETING_SCHEDULE")
    print("FACTORY_MINUTE_ABSENT_SCHEDULE_VERIFIED_FOR_RESTORE")
else:
    raise SystemExit("FACTORY_MINUTE_UNEXPECTED_OR_DUPLICATE_CRON")
PY

if test -L "$runner"; then
  echo FACTORY_MINUTE_UNSAFE_EXISTING_RUNNER
  exit 1
fi
if test -f "$runner"; then
  cp -p "$runner" "$backup/previous-runner.sh"
  chmod 600 "$backup/previous-runner.sh"
fi

# Single runner owns a minute-level nonblocking flock across both stages.
temp="$(mktemp "$stock/.factory-minute-runner.XXXXXXXX")"
chmod 700 "$temp"
cat > "$temp" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
umask 077
ops="$HOME/factory-runtime/operations"
exec 8>"$ops/.factory-minute-cycle.lock"
flock -n 8 || exit 0
exec >> "$ops/factory-minute-cycle.log" 2>&1
echo "FACTORY_MINUTE_START_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
mfg_rc=0
/bin/bash "$ops/autonomous-product-runtime/run-local-cycle.sh" || mfg_rc=$?
if test "$mfg_rc" -ne 0; then
  echo "FACTORY_MINUTE_MANUFACTURING_FAILED=$mfg_rc"
else
  echo FACTORY_MINUTE_MANUFACTURING_FINISHED=true
fi
# Stock existing valid goods even if the current manufacturing cycle fails.
wh_rc=0
/bin/bash "$ops/production-warehouse/run-warehouse.sh" || wh_rc=$?
if test "$wh_rc" -ne 0; then
  echo "FACTORY_MINUTE_WAREHOUSE_FAILED=$wh_rc"
else
  echo FACTORY_MINUTE_WAREHOUSE_FINISHED=true
fi
echo "FACTORY_MINUTE_END_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
test "$mfg_rc" -eq 0 && test "$wh_rc" -eq 0
SH
bash -n "$temp"
if grep -Eq 'curl |wget |factory_store_sender|multisite_orchestrator|rsync |scp ' "$temp"; then
  rm -f "$temp"
  echo FACTORY_MINUTE_SITE_DEPENDENCY_FOUND
  exit 1
fi
mv -f -- "$temp" "$runner"
chmod 700 "$runner"

python3 - "$backup/previous.cron" "$backup/proposed.cron" "$runner" "$mfgmarker" "$stockmarker" "$marker" <<'PY'
from pathlib import Path
import sys
source,out,runner,mfg,stock,mark=sys.argv[1:]
lines=Path(source).read_text().splitlines()
expected_new="* * * * * /bin/bash "+runner+" # "+mfg+" "+stock+" "+mark
filtered=[line for line in lines if mfg not in line and stock not in line]
filtered.append(expected_new)
Path(out).write_text("\n".join(filtered)+"\n")
PY
chmod 600 "$backup/proposed.cron"
test "$(crontab -l | sha256sum | awk '{print $1}')" = "$(sha256sum "$backup/previous.cron" | awk '{print $1}')" || {
  echo FACTORY_MINUTE_CONCURRENT_CRON_EDIT
  exit 1
}
crontab - < "$backup/proposed.cron"
if ! test "$(crontab -l | grep -c "$mfgmarker")" -eq 1 || \
   ! test "$(crontab -l | grep -c "$stockmarker")" -eq 1 || \
   ! crontab -l | grep -qF "* * * * * /bin/bash $runner # $mfgmarker $stockmarker $marker"; then
  echo FACTORY_MINUTE_SCHEDULE_VERIFY_FAILED
  if test "$(crontab -l | sha256sum | awk '{print $1}')" = "$(sha256sum "$backup/proposed.cron" | awk '{print $1}')" ; then
    crontab - < "$backup/previous.cron" || true
  fi
  if test -f "$backup/previous-runner.sh"; then
    install -m 700 "$backup/previous-runner.sh" "$runner"
  fi
  exit 1
fi
echo FACTORY_MINUTE_SCHEDULE=EVERY_MINUTE
echo FACTORY_MINUTE_PRODUCE_THEN_WAREHOUSE=SEQUENTIAL
echo FACTORY_MINUTE_NO_OVERLAP=FLOCK
echo FACTORY_MINUTE_SITE_TRANSFER=DISABLED
echo FACTORY_MINUTE_CRON_INDEPENDENT_OF_GITHUB=true
echo FACTORY_MINUTE_BACKUP="$backup"
