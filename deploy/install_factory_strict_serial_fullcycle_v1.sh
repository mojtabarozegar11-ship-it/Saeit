#!/usr/bin/env bash
# One agricultural product at a time; preserve old cron and private data.
set -euo pipefail
umask 077
test "$#" -eq 1
# Explicit environment authorization is required before any private file,
# crontab, or executable is modified. A CI green check is not authorization.
if [ "${SAEIT_QC1000_INSTALL_APPROVED:-}" != "1" ]; then
  echo STRICT_SERIAL_INSTALL_APPROVAL_REQUIRED >&2
  exit 1
fi
source_root="$1"
base='/home/githubops/factory-runtime'
ops="$base/operations/production-instructions"
private="$base/private/autonomous-product-cycle"
python="$base/.venv/bin/python"
backup_root="$base/operations/backups"
new_marker='SAEIT_STRICT_SERIAL_PRODUCT_TO_QC1000_20261025'
test "$(id -un)" = githubops
test -d "$source_root/scripts" && test ! -L "$source_root"
test -d "$ops" && test ! -L "$ops" && test -d "$private" && test ! -L "$private"
test -x "$python"
test -f "$ops/license-safe-primary-fulltext-acquisition-sequential-v1.py"
test -f "$ops/agri200-strict-qc-catalog.json"
test -f "$base/operations/12-stage-governance/factory_12_stage_governance.py"

# Pause only dedicated AGRI200 producers. Shared stage workers stay scheduled
# with a verified exclusion of this specific owner-owned cohort.
legacy_markers=(
  SAEIT_SEQUENTIAL_SCIENCE_CASEWORK_20261025
  SAEIT_AGRI200_AUTONOMOUS_CLOSED_LOOP_V1
  SAEIT_AGRI200_STRICT_QC1000_V1
  SAEIT_FACTORY_STAGE2_SOURCE_DISCOVERY_V1
  SAEIT_QC184_LICENSED_ALTERNATIVE_DISCOVERY_20261024
  SAEIT_QC_V003_DOCTORAL_DEPTH_GATE_20261024
  SAEIT_QC_V003_SCIENTIFIC_REVIEW_HANDOFF_20261024
)
shared_markers=(
  SAEIT_FACTORY_STAGE2_RESEARCH_V1
  SAEIT_FACTORY_STAGE34_AUTONOMOUS_HANDOFF_V1
  SAEIT_FACTORY_STAGE5_EVIDENCE_WORKBOOK_V1
  SAEIT_FACTORY_STAGE5_SUBSTANTIVE_REWORK_V1
  SAEIT_FACTORY_STAGE6_PREFLIGHT_REWORK_V1
  SAEIT_SCIENCE_REWORK_ALL_20261024
)
files=(
  'factory_strict_serial_fullcycle_v1.py:strict-serial-fullcycle-v1.py'
  'factory_strict_serial_scope_v1.py:factory_strict_serial_scope_v1.py'
  'factory_sequential_scientific_casework_v1.py:sequential-scientific-casework-v1.py'
  'factory_stage2_literature_scout.py:stage2-literature-scout-serial.py'
  'factory_stage2_research.py:stage2-research-serial.py'
  'factory_stage34_autonomous_handoff_20261023.py:stage34-autonomous-handoff-serial.py'
  'factory_stage5_evidence_workbook_20261023.py:stage5-evidence-workbook-serial.py'
  'factory_stage6_preflight_rework_20261023.py:stage6-preflight-rework-serial.py'
  'factory_agri200_downloadable_20261023.py:research-navigator-serial.py'
  'factory_agri200_strict_qc_20261023.py:agri200-strict-qc1000-serial.py'
  'factory_stage5_substantive_rework_20261023.py:stage5-substantive-rework-serial.py'
  'factory_agri200_source_grounded_v003_20261023.py:agri200-source-grounded-v003-serial.py'
  'factory_agri200_source_grounded_v003_qc_20261023.py:agri200-source-grounded-v003-qc-serial.py'
  'factory_systemwide_science_rework_20261024.py:systemwide-scientific-source-rework-serial.py'
)
# Read-only scheduler inventory MUST precede backups, worker replacements, and
# crontab edits. The existing installer previously rewrote 14 executable files
# before checking whether another minute producer already owned this cohort.
command -v crontab >/dev/null
command -v systemctl >/dev/null
command -v flock >/dev/null
cron_snapshot="$(crontab -l)" || {
  echo STRICT_SERIAL_CRON_INVENTORY_UNREADABLE >&2
  exit 1
}
if ! systemctl is-active --quiet cron 2>/dev/null && ! systemctl is-active --quiet crond 2>/dev/null; then
  echo STRICT_SERIAL_CRON_SERVICE_INACTIVE >&2
  exit 1
fi
if ! systemctl is-enabled --quiet cron 2>/dev/null && ! systemctl is-enabled --quiet crond 2>/dev/null; then
  echo STRICT_SERIAL_CRON_SERVICE_NOT_ENABLED >&2
  exit 1
fi
timer_inventory="$(systemctl list-timers --all --no-legend --no-pager)" || {
  echo STRICT_SERIAL_SYSTEMD_TIMER_INVENTORY_UNREADABLE >&2
  exit 1
}
if printf '%s\n' "$timer_inventory" | grep -Eiq '(factory|agri200|qc1000|strict[-_]?serial|owner500).*\.timer'; then
  echo STRICT_SERIAL_COMPETING_SYSTEMD_TIMER >&2
  exit 1
fi
printf '%s\n' "$cron_snapshot" | python3 -B -c '
import re
import sys
new = sys.argv[1]
parts = sys.argv[2:]
sep = parts.index("--SHARED-MARKERS--")
legacy = set(parts[:sep])
shared = set(parts[sep + 1:])
allowed = legacy | shared | {new}
active = [row.strip() for row in sys.stdin.read().splitlines()
          if row.strip() and not row.lstrip().startswith("#")]
serial = [row for row in active if new in row]
if len(serial) > 1:
    raise SystemExit("STRICT_SERIAL_DUPLICATE_MINUTE_MARKER")
for row in serial:
    if not row.startswith("* * * * * ") or "strict-serial-fullcycle-v1.py" not in row:
        raise SystemExit("STRICT_SERIAL_UNRECOGNIZED_EXISTING_SCHEDULE")
for row in active:
    if re.search(r"(agri200|qc1000|factory[-_]?minute|strict[-_]?serial|sequential[-_]?scientific|owner500)", row, re.I):
        if not any(marker in row for marker in allowed):
            raise SystemExit("STRICT_SERIAL_UNMARKED_COMPETING_PRODUCER")
' "$new_marker" "${legacy_markers[@]}" '--SHARED-MARKERS--' "${shared_markers[@]}"
# After read-only audit, serialize installers and reject concurrent cron edits.
# This lock is an installer-only private operations file, not a product write.
exec 8>"$ops/.strict-serial-installer.lock"
flock -n 8 || { echo STRICT_SERIAL_INSTALLER_ALREADY_RUNNING >&2; exit 1; }
if [ "$(crontab -l)" != "$cron_snapshot" ]; then
  echo STRICT_SERIAL_CRON_CHANGED_DURING_PREFLIGHT >&2
  exit 1
fi

run_id="${GITHUB_RUN_ID:-manual}-${GITHUB_RUN_ATTEMPT:-1}"
[[ "$run_id" =~ ^[a-zA-Z0-9-]{1,55}$ ]]
backup="$backup_root/strict-serial-$run_id"
test ! -e "$backup"
install -d -m 700 "$backup"
crontab -l > "$backup/crontab.before"
chmod 600 "$backup/crontab.before"
changed=()
cron_changed=0
complete=0
restore() {
  local code=$?
  if [ "$complete" -ne 1 ]; then
    if [ "$cron_changed" -eq 1 ]; then crontab "$backup/crontab.before" || true; fi
    for entry in "${changed[@]}"; do
      local destination="$ops/$entry"
      if [ -f "$backup/$entry.original" ]; then
        cp -p "$backup/$entry.original" "$destination"
      else
        rm -f -- "$destination"
      fi
    done
    echo STRICT_SERIAL_INSTALL_ROLLED_BACK >&2
  fi
  return "$code"
}
trap restore EXIT

for mapping in "${files[@]}"; do
  filename="${mapping%%:*}"
  dest="${mapping#*:}"
  source="$source_root/scripts/$filename"
  target="$ops/$dest"
  test -f "$source" && test ! -L "$source" && test ! -L "$target"
  "$python" -B -c 'import ast,sys;ast.parse(open(sys.argv[1],encoding="utf8").read())' "$source"
  if [ -e "$target" ]; then
    test -f "$target"
    cp -p "$target" "$backup/$dest.original"
  fi
  before_sha="$(sha256sum "$source" | awk '{print $1}')"
  temp="$(mktemp "$ops/.strict-serial-worker.XXXXXX")"
  install -m 600 "$source" "$temp"
  test "$(sha256sum "$temp" | awk '{print $1}')" = "$before_sha"
  mv -- "$temp" "$target"
  changed+=("$dest")
done

"$python" -B "$ops/strict-serial-fullcycle-v1.py" --factory-private "$private" \
  --operations "$ops" --dry-run
temp_cron="$(mktemp "$ops/.strict-serial-cron.XXXXXX")"
python3 -B - "$backup/crontab.before" "$temp_cron" "$new_marker" "${legacy_markers[@]}" '--SHARED-MARKERS--' "${shared_markers[@]}" <<'PY'
import sys
from pathlib import Path
before,after,new,*all_markers=sys.argv[1:]
separator=all_markers.index('--SHARED-MARKERS--')
legacy=all_markers[:separator]
shared=all_markers[separator+1:]
shared_paths={
    'SAEIT_FACTORY_STAGE2_RESEARCH_V1':('stage2-research.py','stage2-research-serial.py'),
    'SAEIT_FACTORY_STAGE34_AUTONOMOUS_HANDOFF_V1':('stage34-autonomous-handoff.py','stage34-autonomous-handoff-serial.py'),
    'SAEIT_FACTORY_STAGE5_EVIDENCE_WORKBOOK_V1':('stage5-evidence-workbook.py','stage5-evidence-workbook-serial.py'),
    'SAEIT_FACTORY_STAGE5_SUBSTANTIVE_REWORK_V1':('stage5-substantive-rework.py','stage5-substantive-rework-serial.py'),
    'SAEIT_FACTORY_STAGE6_PREFLIGHT_REWORK_V1':('stage6-preflight-rework.py','stage6-preflight-rework-serial.py'),
    'SAEIT_SCIENCE_REWORK_ALL_20261024':('systemwide-scientific-source-rework.py','systemwide-scientific-source-rework-serial.py')
}
if set(shared)!=set(shared_paths) or set(shared).intersection(legacy):
    raise SystemExit('STRICT_SERIAL_INVALID_SHARED_SCOPE')
rows=Path(before).read_text().splitlines()
for marker in legacy+shared+[new]:
    if sum(marker in row and not row.lstrip().startswith("#") for row in rows)>1:
        raise SystemExit("DUPLICATE_FACTORY_CRON:"+marker)
out=[]
for line in rows:
    if line.lstrip().startswith("#"):
        out.append(line)
        continue
    if new in line:
        # Existing serial command can only be replaced by an audited installer.
        if "strict-serial-fullcycle-v1.py" not in line:
            raise SystemExit("FOREIGN_SERIAL_CRON")
        continue
    markers=[marker for marker in legacy if marker in line]
    shared_matches=[marker for marker in shared if marker in line]
    if shared_matches:
        if len(shared_matches)!=1 or markers:
            raise SystemExit('AMBIGUOUS_SHARED_CRON')
        marker=shared_matches[0]
        old,new_file=shared_paths[marker]
        prefix='/home/githubops/factory-runtime/operations/production-instructions/'
        old_worker=prefix+old
        new_worker=prefix+new_file
        if (line.count(new_worker)==1 and line.count(old_worker)==0
                and line.count('--exclude-owner-agri200')==1
                and line.rstrip().endswith('# '+marker)):
            out.append(line)
            continue
        if (line.count(old_worker)!=1 or ' >> ' not in line
                or '--exclude-owner-agri200' in line
                or not line.rstrip().endswith('# '+marker)):
            raise SystemExit('UNRECOGNIZED_SHARED_WORKER_CRON:'+marker)
        updated=line.replace(old_worker,new_worker,1)
        updated=updated.replace(' >> ',' --exclude-owner-agri200 >> ',1)
        out.append(updated)
        continue
    if markers:
        if ("factory-runtime/operations/production-instructions/" not in line
                or "githubops" in line and "/home/githubops/" not in line):
            raise SystemExit("UNKNOWN_AGRICULTURAL_CRON_PATH")
        out.append("# PAUSED_BY_STRICT_SERIAL_20261025 "+line)
    else:
        out.append(line)
out.append("* * * * * /usr/bin/flock -n /home/githubops/factory-runtime/operations/production-instructions/.strict-serial-cron.lock /usr/bin/timeout 58s /home/githubops/factory-runtime/.venv/bin/python -B /home/githubops/factory-runtime/operations/production-instructions/strict-serial-fullcycle-v1.py --factory-private /home/githubops/factory-runtime/private/autonomous-product-cycle --operations /home/githubops/factory-runtime/operations/production-instructions --require-scheduler-scope >> /home/githubops/factory-runtime/operations/production-instructions/strict-serial-fullcycle.log 2>&1 # SAEIT_STRICT_SERIAL_PRODUCT_TO_QC1000_20261025")
Path(after).write_text("\n".join(out)+"\n")
PY
test "$(crontab -l | sha256sum | awk '{print $1}')" = "$(sha256sum "$backup/crontab.before" | awk '{print $1}')"
crontab "$temp_cron"
cron_changed=1
test "$(crontab -l | grep -Fc "$new_marker")" -eq 1
for marker in "${legacy_markers[@]}"; do
  test "$(crontab -l | grep -F "$marker" | grep -vc '^#' || true)" -eq 0
done
for marker in "${shared_markers[@]}"; do
  existing_count="$(grep -F "$marker" "$backup/crontab.before" | grep -vc '^#' || true)"
  if [ "$existing_count" -gt 0 ]; then
    test "$(crontab -l | grep -F "$marker" | grep -Fc -- '--exclude-owner-agri200')" -eq 1
  fi
done
command -v pgrep >/dev/null
if pgrep -u githubops -f '/(agri200-autonomous-closed-loop|stage2-literature-scout|stage2-research|stage34-autonomous-handoff|stage5-evidence-workbook|stage5-substantive-rework|stage6-preflight-rework|agri200-strict-qc1000)\.py' >/dev/null; then
  echo LEGACY_AGRI_WORKER_STILL_RUNNING_RETRY_WHEN_QUIESCENT >&2
  exit 1
fi
# Installation configures the protected VPS-local minute scheduler only.
# A real product tick must happen through cron, not the installer. Neither
# crontab presence nor a successful installer proves the next tick executed.
rm -f -- "$temp_cron"
complete=1
echo STRICT_SERIAL_CRON_CONFIGURED_RUNTIME_NOT_VERIFIED
echo PRIVATE_WAREHOUSE_ONLY_NO_UNVERIFIED_SITE_RELEASE
echo "ROLLBACK_CRON=$backup/crontab.before"
