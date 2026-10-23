#!/usr/bin/env bash
# Private QC1000 agricultural inspector: never certifies or publishes.
set -euo pipefail
umask 077
test "$(id -un)" = githubops && test "$(id -u)" -ne 0
test "$#" -eq 2
incoming="$1"
incoming_catalog="$2"
test -f "$incoming" && test ! -L "$incoming"
test -f "$incoming_catalog" && test ! -L "$incoming_catalog"
base="$HOME/factory-runtime"
ops="$base/operations/production-instructions"
root="$base/private/autonomous-product-cycle"
py="$base/.venv/bin/python"
worker="$ops/agri200-strict-qc1000.py"
catalog="$ops/agri200-strict-qc-catalog.json"
stage34="$ops/stage34-autonomous-handoff.py"
stage5="$ops/stage5-evidence-workbook.py"
marker=SAEIT_AGRI200_STRICT_QC1000_V1
test -x "$py" && test -d "$root/production-instructions/stage-05/completed-drafts"
for dependency in "$stage34" "$stage5"; do
    test -f "$dependency" && test ! -L "$dependency"
done
test -d "$ops" && test ! -L "$ops"
command -v flock >/dev/null
exec 8>"$ops/.agri200-strict-qc-install.lock"
flock -w 75 8
backup="$base/operations/backups/agri200-strict-qc-$(date -u +%Y%m%dT%H%M%SZ)-$$"
install -d -m 700 "$backup"
crontab -l > "$backup/crontab.before"
chmod 600 "$backup/crontab.before"
if test -e "$worker"; then
    test -f "$worker" && test ! -L "$worker"
    cp -p "$worker" "$backup/worker.before.py"
fi
if test -e "$catalog"; then
    test -f "$catalog" && test ! -L "$catalog"
    cp -p "$catalog" "$backup/catalog.before.json"
fi
"$py" -B -c 'import ast,sys;ast.parse(open(sys.argv[1],encoding="utf-8").read())' "$incoming"
"$py" -B - "$incoming_catalog" <<'PY'
import json,sys
data=json.load(open(sys.argv[1],encoding="utf-8"))
assert data["schema"]=="saeit.factory.quality-100-groups.v2"
assert data["total_points"]==1000 and len(data["groups"])==100
PY
tmp_worker="$(mktemp "$ops/.strict-qc-worker.XXXXXX")"
tmp_catalog="$(mktemp "$ops/.strict-qc-catalog.XXXXXX")"
install -m 600 "$incoming" "$tmp_worker"
install -m 600 "$incoming_catalog" "$tmp_catalog"
mv -f "$tmp_worker" "$worker"
mv -f "$tmp_catalog" "$catalog"
timeout 230s "$py" -B "$worker" \
    --factory-private "$root" \
    --stage34-worker "$stage34" \
    --stage5-worker "$stage5" \
    --criteria "$catalog" --batch 250
cron='* * * * * /usr/bin/flock -n /home/githubops/factory-runtime/operations/production-instructions/.agri200-strict-qc-cron.lock /home/githubops/factory-runtime/.venv/bin/python -B /home/githubops/factory-runtime/operations/production-instructions/agri200-strict-qc1000.py --factory-private /home/githubops/factory-runtime/private/autonomous-product-cycle --stage34-worker /home/githubops/factory-runtime/operations/production-instructions/stage34-autonomous-handoff.py --stage5-worker /home/githubops/factory-runtime/operations/production-instructions/stage5-evidence-workbook.py --criteria /home/githubops/factory-runtime/operations/production-instructions/agri200-strict-qc-catalog.json --batch 250 >> /home/githubops/factory-runtime/operations/production-instructions/agri200-strict-qc.log 2>&1 # SAEIT_AGRI200_STRICT_QC1000_V1'
if grep -Fq "$marker" "$backup/crontab.before"; then
    test "$(grep -Fc "$marker" "$backup/crontab.before")" -eq 1
    if ! grep -Fxq "$cron" "$backup/crontab.before"; then
        awk -v marker="$marker" -v cron="$cron" 'index($0,marker) {print cron;next} {print}' "$backup/crontab.before" | crontab -
    fi
else
    { cat "$backup/crontab.before"; printf '%s\n' "$cron"; } | crontab -
fi
test "$(crontab -l | grep -Fc "$marker")" -eq 1
"$py" -B - "$root/production-instructions" <<'PY'
import json,sys
from pathlib import Path
area=Path(sys.argv[1])
state=json.loads((area/"stage-06/strict-qc-status.json").read_text(encoding="utf-8"))
for a,b in (
    ("PRODUCTS_IN_STAGE5","stage5_products_seen"),
    ("STRICT_QC_INSPECTED","inspected_this_run"),
    ("STRICT_QC_AUDITED_TOTAL","strict_qc1000_audits_total"),
    ("PRODUCTS_RETURNED_TO_PRODUCTION","returned_to_rework_total"),
    ("QUARANTINED_THIS_RUN","quarantined_during_this_run"),
    ("QA1000_INDEPENDENT_APPROVALS","independent_quality1000_approvals_created"),
):
    print("FACTORY_"+a+"="+str(state[b]))
print("FACTORY_SITES_CHANGED=false")
PY
echo FACTORY_STRICT_QC_BACKUP="$backup"
