#!/usr/bin/env bash
# Activate a single-product scientific repair worker without replacing old evidence.
set -euo pipefail
umask 077
test "$#" -eq 2
source_case="$1"
source_engine="$2"
root='/home/githubops/factory-runtime/private/autonomous-product-cycle'
ops='/home/githubops/factory-runtime/operations/production-instructions'
py='/home/githubops/factory-runtime/.venv/bin/python'
backups='/home/githubops/factory-runtime/operations/backups'
case_worker="$ops/sequential-scientific-casework-v1.py"
case_engine="$ops/license-safe-primary-fulltext-acquisition-sequential-v1.py"
old_marker='SAEIT_LICENSED_PRIMARY_SOURCE_ACQUISITION_20261024'
new_marker='SAEIT_SEQUENTIAL_SCIENCE_CASEWORK_20261025'
test "$(id -un)" = githubops
test -f "$source_case" && test ! -L "$source_case"
test -f "$source_engine" && test ! -L "$source_engine"
test -d "$ops" && test ! -L "$ops"
test -d "$root/production-instructions/stage-02/primary-fulltext-repair-inbox"
test -x "$py"
install -d -m 700 "$backups"

run_tag="${GITHUB_RUN_ID:-manual}-${GITHUB_RUN_ATTEMPT:-1}"
test "${#run_tag}" -le 55
[[ "$run_tag" =~ ^[A-Za-z0-9-]+$ ]]
case_backup="$backups/sequential-casework-$run_tag.previous.py"
engine_backup="$backups/sequential-engine-$run_tag.previous.py"
cron_backup="$backups/sequential-cron-$run_tag.previous.txt"
case_had=0
engine_had=0
case_changed=0
engine_changed=0
cron_changed=0
complete=0

rollback() {
  exit_code=$?
  if [ "$complete" -ne 1 ]; then
    if [ "$cron_changed" -eq 1 ]; then crontab "$cron_backup" || true; fi
    if [ "$case_changed" -eq 1 ]; then
      if [ "$case_had" -eq 1 ]; then cp -p "$case_backup" "$case_worker"; else rm -f -- "$case_worker"; fi
    fi
    if [ "$engine_changed" -eq 1 ]; then
      if [ "$engine_had" -eq 1 ]; then cp -p "$engine_backup" "$case_engine"; else rm -f -- "$case_engine"; fi
    fi
    printf '%s\n' 'SEQUENTIAL_CASEWORK_INSTALL_ROLLED_BACK' >&2
  fi
  return "$exit_code"
}
trap rollback EXIT

install_checked() {
  local source="$1" destination="$2" backup="$3" state="$4"
  local old_digest='' expected tmp
  expected="$(sha256sum "$source" | awk '{print $1}')"
  if [ -e "$destination" ]; then
    test -f "$destination" && test ! -L "$destination"
    old_digest="$(sha256sum "$destination" | awk '{print $1}')"
    if [ "$old_digest" = "$expected" ]; then return 0; fi
    test ! -e "$backup"
    cp -p "$destination" "$backup"
    test "$(sha256sum "$backup" | awk '{print $1}')" = "$old_digest"
    if [ "$state" = 'case' ]; then case_had=1; else engine_had=1; fi
  fi
  tmp="$(mktemp "$ops/.sequential-install.XXXXXX")"
  install -m 600 "$source" "$tmp"
  test "$(sha256sum "$tmp" | awk '{print $1}')" = "$expected"
  mv -f -- "$tmp" "$destination"
  if [ "$state" = 'case' ]; then case_changed=1; else engine_changed=1; fi
}

# Audit before any executable or private case is changed. This installer is
# NOT a whole-factory QC1000 orchestrator and must never create a parallel
# minute pipeline beside #866 (factory), #998 (AGRI200), or another caseworker.
command -v flock >/dev/null
command -v crontab >/dev/null
command -v systemctl >/dev/null
exec 9>"$ops/.sequential-casework-install.lock"
flock -w 20 9 || { echo CASEWORK_INSTALL_LOCK_BUSY >&2; exit 1; }
if ! systemctl is-active --quiet cron 2>/dev/null && ! systemctl is-active --quiet crond 2>/dev/null; then
  echo CASEWORK_MINUTE_CRON_INACTIVE >&2
  exit 1
fi
if ! systemctl is-enabled --quiet cron 2>/dev/null && ! systemctl is-enabled --quiet crond 2>/dev/null; then
  echo CASEWORK_MINUTE_CRON_BOOT_DISABLED >&2
  exit 1
fi
timers="$(systemctl list-timers --all --no-legend --no-pager 2>/dev/null)" || {
  echo CASEWORK_SYSTEMD_TIMER_AUDIT_FAILED >&2
  exit 1
}
if printf '%s\n' "$timers" | grep -Eiq '(factory|agri200|qc1000|sequential|production|warehouse).*\.timer'; then
  echo CASEWORK_COMPETING_SYSTEMD_TIMER >&2
  exit 1
fi
test ! -e "$cron_backup"
cron_error="$backups/.sequential-cron-$run_tag.stderr"
test ! -e "$cron_error"
if crontab -l > "$cron_backup" 2> "$cron_error"; then
  :
elif grep -Eqi '^no crontab for ' "$cron_error"; then
  :
else
  echo CASEWORK_CRONTAB_READ_FAILED >&2
  exit 1
fi
rm -f -- "$cron_error"
chmod 600 "$cron_backup"
python3 - "$cron_backup" "$old_marker" "$new_marker" "$case_worker" <<'PY'
import sys
from pathlib import Path

path, old, new, worker = sys.argv[1:]
lines = Path(path).read_text(encoding="utf-8").splitlines()
active = [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]
old_rows = [line for line in active if old in line]
new_rows = [line for line in active if new in line]
if len(old_rows) > 1 or len(new_rows) > 1 or (old_rows and new_rows):
    raise SystemExit("CASEWORK_DUPLICATE_OR_CONFLICTING_MARKERS")
for line in active:
    minute = line.split()[:5] == ["*"] * 5
    if line in old_rows:
        if not minute or "license-safe-primary-fulltext-acquisition.py" not in line:
            raise SystemExit("CASEWORK_UNRECOGNIZED_OLD_SCHEDULER")
    elif line in new_rows:
        if not minute or worker not in line:
            raise SystemExit("CASEWORK_UNRECOGNIZED_NEW_SCHEDULER")
    elif ("SAEIT_FACTORY_EVERY_MINUTE_V1" in line
          or "SAEIT_AGRI200_AUTONOMOUS_CLOSED_LOOP_V1" in line
          or (minute and any(word in line.lower() for word in
              ("factory", "agri200", "qc1000", "product", "production",
               "warehouse", "sequential", "run-minute-cycle.sh")))):
        raise SystemExit("CASEWORK_COMPETING_MINUTE_PIPELINE")
print("CASEWORK_CRON_PREFLIGHT_PASS_ONLY_NO_FULL_QC1000_CLAIM")
PY

# Preserve the existing global worker and cron until the isolated pair passes.
install_checked "$source_engine" "$case_engine" "$engine_backup" engine
install_checked "$source_case" "$case_worker" "$case_backup" case
timeout 30s "$py" -B "$case_worker" --factory-private "$root" --dry-run
# No real product is touched during installation; the protected VPS cron owns ticks.

# Replace only the known previous scientific-source cron; preserve every other
# factory scheduler and keep a complete rollback copy of the crontab.
# Detect any concurrent crontab modification since the read-only preflight.
test "$(crontab -l 2>/dev/null | sha256sum | awk '{print $1}')" = "$(sha256sum "$cron_backup" | awk '{print $1}')" || {
  echo CASEWORK_CONCURRENT_CRON_EDIT >&2
  exit 1
}
new_count="$(grep -Fc "$new_marker" "$cron_backup" || true)"
old_count="$(grep -Fc "$old_marker" "$cron_backup" || true)"
test "$new_count" -le 1 && test "$old_count" -le 1
if [ "$old_count" -eq 1 ]; then
  grep -F "$old_marker" "$cron_backup" | grep -Fq 'license-safe-primary-fulltext-acquisition.py'
fi
if [ "$new_count" -eq 1 ]; then
  grep -F "$new_marker" "$cron_backup" | grep -Fq "$case_worker"
fi
expected_cron="* * * * * /usr/bin/flock -n '$ops/.sequential-science-casework-cron.lock' /usr/bin/timeout 90s '$py' -B '$case_worker' --factory-private '$root' --max-source-attempts 2 >> '$ops/sequential-scientific-casework.log' 2>&1 # $new_marker"
if [ "$new_count" -eq 1 ] && [ "$old_count" -eq 0 ] && grep -Fxq "$expected_cron" "$cron_backup"; then
  :
else
  temp_cron="$(mktemp "$ops/.sequential-cron.XXXXXX")"
  awk -v old="$old_marker" -v new="$new_marker" \
    'index($0, "# " old) == 0 && index($0, "# " new) == 0 {print}' "$cron_backup" > "$temp_cron"
  printf '%s\n' "$expected_cron" >> "$temp_cron"
  crontab "$temp_cron"
  cron_changed=1
  rm -f -- "$temp_cron"
fi
crontab -l | grep -F "$new_marker"
complete=1
printf '%s\n' 'SEQUENTIAL_SCIENTIFIC_SOURCE_ONLY=CRON_CONFIGURED_NOT_QC1000' \
  'INDEPENDENT_SCIENTIFIC_REVIEW=MANDATORY' \
  'QC1000_AUTO_APPROVALS=0' 'PUBLIC_RELEASES=0' \
  "CRON_ROLLBACK_BACKUP=$cron_backup"
