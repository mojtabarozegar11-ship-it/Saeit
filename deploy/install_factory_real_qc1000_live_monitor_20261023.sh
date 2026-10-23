#!/usr/bin/env bash
# Install only the private QC1000 evidence monitor. No product, site or payment write.
set -euo pipefail
umask 077
test "$(id -un)" = githubops && test "$(id -u)" -ne 0
test "$#" -eq 1
incoming="$1"
test -f "$incoming" && test ! -L "$incoming"
base="/home/githubops/factory-runtime"
ops="$base/operations/production-instructions"
root="$base/private/autonomous-product-cycle"
py="$base/.venv/bin/python"
dest="$ops/real-qc1000-live-monitor.py"
key="$ops/real-qc1000-trusted-runner.pub"
marker="SAEIT_PRIVATE_REAL_QC1000_MONITOR_20261023"
test -x "$py" && test -d "$ops" && test ! -L "$ops"
test -d "$root/production-instructions/stage-05/downloadable-receipts"
test -d "$root/production-instructions/stage-06"
command -v flock >/dev/null
command -v openssl >/dev/null
exec 8>"$ops/.real-qc1000-install.lock"
flock -w 70 8
backup="$base/operations/backups/real-qc1000-$(date -u +%Y%m%dT%H%M%SZ)-$$"
install -d -m 700 "$backup"
crontab -l > "$backup/crontab.before"
chmod 600 "$backup/crontab.before"
previous=0
if test -e "$dest"; then
  test -f "$dest" && test ! -L "$dest"
  cp -p "$dest" "$backup/monitor.before.py"
  previous=1
fi
rollback() {
  rc=$?
  trap - ERR
  crontab "$backup/crontab.before" || true
  if test "$previous" -eq 1; then
    cp -p "$backup/monitor.before.py" "$dest" || true
  else
    rm -f -- "$dest"
  fi
  echo "PRIVATE_QC1000_INSTALL_ROLLED_BACK=1"
  exit "$rc"
}
trap rollback ERR
"$py" -B -c 'import ast,sys;ast.parse(open(sys.argv[1],encoding="utf8").read())' "$incoming"
stage="$(mktemp "$ops/.real-qc1000-monitor.XXXXXX")"
install -m 600 "$incoming" "$stage"
mv -f "$stage" "$dest"
test "$(sha256sum "$incoming" | cut -d' ' -f1)" = "$(sha256sum "$dest" | cut -d' ' -f1)"
# A missing trust key is safe: all products remain blocked from QC1000 clearance.
timeout 40s "$py" -B "$dest" --factory-private "$root" \
  --trusted-runner-pubkey "$key" --batch 10
cron='* * * * * /usr/bin/flock -n /home/githubops/factory-runtime/operations/production-instructions/.real-qc1000-minute.lock /usr/bin/timeout 45s /home/githubops/factory-runtime/.venv/bin/python -B /home/githubops/factory-runtime/operations/production-instructions/real-qc1000-live-monitor.py --factory-private /home/githubops/factory-runtime/private/autonomous-product-cycle --trusted-runner-pubkey /home/githubops/factory-runtime/operations/production-instructions/real-qc1000-trusted-runner.pub --batch 10 >> /home/githubops/factory-runtime/operations/production-instructions/real-qc1000-live-monitor.log 2>&1 # SAEIT_PRIVATE_REAL_QC1000_MONITOR_20261023'
if grep -Fq "$marker" "$backup/crontab.before"; then
  test "$(grep -Fc "$marker" "$backup/crontab.before")" -eq 1
  if ! grep -Fxq "$cron" "$backup/crontab.before"; then
    awk -v marker="$marker" -v cron="$cron" 'index($0,marker) {print cron;next} {print}' "$backup/crontab.before" | crontab -
  fi
else
  { cat "$backup/crontab.before"; printf '%s\n' "$cron"; } | crontab -
fi
test "$(crontab -l | grep -Fc "$marker")" -eq 1
"$py" -B - "$root/production-instructions/stage-06/real-qc1000-health.json" "$key" <<'PY'
import json,sys
from pathlib import Path
status=json.loads(Path(sys.argv[1]).read_text(encoding="utf8"))
assert status["scanner_health"]=="RUNNING"
assert status["professional_quality_1000_certifications_created"]==0
assert status["public_products_released"]==0
print("PRIVATE_QC1000_HEALTH=RUNNING")
print("PRIVATE_QC1000_CANDIDATES="+str(status["indexed_candidates"]))
print("PRIVATE_QC1000_SCENARIO_RECEIPTS_VERIFIED="+str(status["actual_execution_scenarios_evidence_verified_this_tick"]))
print("PRIVATE_QC1000_TRUSTED_RUNNER_ENROLLED="+str(Path(sys.argv[2]).is_file()).lower())
print("PRIVATE_QC1000_NO_FALSE_CERTIFICATIONS=PASS")
PY
echo "PRIVATE_QC1000_MINUTE_CRON=INSTALLED"
echo "PRIVATE_QC1000_VERSION_BACKUP=$backup"
trap - ERR
