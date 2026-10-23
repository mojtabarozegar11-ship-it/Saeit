#!/usr/bin/env bash
# Upgrade the existing VPS-local AGRI200 loop to produce a real new v003 edition.
set -euo pipefail
umask 077
test "$(id -un)" = githubops && test "$(id -u)" -ne 0
test "$#" -eq 3
source_writer="$1"
source_qc="$2"
source_loop="$3"
for file in "$source_writer" "$source_qc" "$source_loop"; do
    test -f "$file" && test ! -L "$file"
done
base="$HOME/factory-runtime"
ops="$base/operations/production-instructions"
root="$base/private/autonomous-product-cycle"
py="$base/.venv/bin/python"
test -x "$py" && test -d "$ops" && test ! -L "$ops"
test -f "$root/production-instructions/owner-agri200-p0-index.json"
for file in stage34-autonomous-handoff.py stage5-evidence-workbook.py research-navigator.py agri200-strict-qc1000.py; do
    test -f "$ops/$file" && test ! -L "$ops/$file"
done
crontab -l | grep -Fq SAEIT_AGRI200_AUTONOMOUS_CLOSED_LOOP_V1
command -v flock >/dev/null
exec 9>"$ops/.agri200-autonomous-cron.lock"
flock -w 75 9
backup="$base/operations/backups/agri200-authorship-$(date -u +%Y%m%dT%H%M%SZ)-$$"
install -d -m 700 "$backup"
for incoming in "$source_writer" "$source_qc" "$source_loop"; do
    "$py" -B -c 'import ast,sys;ast.parse(open(sys.argv[1],encoding="utf-8").read())' "$incoming"
done
for name in agri200-source-grounded-v003.py agri200-source-grounded-v003-qc.py agri200-autonomous-closed-loop.py; do
    existing="$ops/$name"
    if test -e "$existing"; then
        test -f "$existing" && test ! -L "$existing"
        cp -p "$existing" "$backup/$name"
    fi
done
install -m 600 "$source_writer" "$ops/.agri200-v003-source.tmp"
install -m 600 "$source_qc" "$ops/.agri200-v003-qc.tmp"
install -m 600 "$source_loop" "$ops/.agri200-v003-loop.tmp"
mv -f "$ops/.agri200-v003-source.tmp" "$ops/agri200-source-grounded-v003.py"
mv -f "$ops/.agri200-v003-qc.tmp" "$ops/agri200-source-grounded-v003-qc.py"
mv -f "$ops/.agri200-v003-loop.tmp" "$ops/agri200-autonomous-closed-loop.py"
timeout 900s "$py" -B "$ops/agri200-autonomous-closed-loop.py" --factory-private "$root" --operations "$ops"
"$py" -B - "$root/production-instructions/stage-06/autonomous-closed-loop-status.json" <<'PY'
import json,sys
report=json.load(open(sys.argv[1],encoding="utf8"))
stages=report["stage_results"]
assert stages.get("source_grounded_reauthoring")=="ok",stages
assert stages.get("v003_independent_mechanical_qc")=="ok",stages
after=report["after"]
assert after["stage5_source_grounded_v003"]>0,after
assert after["stage6_source_grounded_v003_mechanical_qc"]>0,after
print("NEW_SOURCE_GROUNDED_EDITIONS="+str(after["stage5_source_grounded_v003"]))
print("V003_INDEPENDENT_MECHANICAL_QC="+str(after["stage6_source_grounded_v003_mechanical_qc"]))
print("QC1000_COMMERCIAL_APPROVAL=NOT_ATTESTED")
PY
echo AGRI200_AUTHORSHIP_BACKUP="$backup"
echo VPS_LOCAL_MINUTE_LOOP=STILL_INSTALLED
