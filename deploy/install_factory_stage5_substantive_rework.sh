#!/usr/bin/env bash
# VPS-only source-specific Stage5 revision builder. Does not attest experts or publish.
set -euo pipefail
umask 077
test "$(id -un)" = githubops && test "$(id -u)" -ne 0
test "$#" -eq 1
incoming="$1"
test -f "$incoming" && test ! -L "$incoming"
base="$HOME/factory-runtime"
ops="$base/operations/production-instructions"
root="$base/private/autonomous-product-cycle"
py="$base/.venv/bin/python"
target="$ops/stage5-substantive-rework.py"
stage34="$ops/stage34-autonomous-handoff.py"
stage5="$ops/stage5-evidence-workbook.py"
stage6="$ops/stage6-preflight-rework.py"
marker=SAEIT_FACTORY_STAGE5_SUBSTANTIVE_REWORK_V1
test -x "$py" && test -d "$root/production-instructions/stage-05/substantive-rework-inbox"
for dependency in "$stage34" "$stage5" "$stage6"; do
    test -f "$dependency" && test ! -L "$dependency"
done
test -d "$ops" && test ! -L "$ops"
command -v flock >/dev/null
exec 8>"$ops/.stage5-substantive-install.lock"
flock -w 75 8
backup="$base/operations/backups/substantive-$(date -u +%Y%m%dT%H%M%SZ)-$$"
install -d -m 700 "$backup"
crontab -l > "$backup/crontab.before"
chmod 600 "$backup/crontab.before"
if test -e "$target"; then
    test -f "$target" && test ! -L "$target"
    cp -p "$target" "$backup/stage5-substantive.before.py"
fi
"$py" -B -c 'import ast,sys;ast.parse(open(sys.argv[1],encoding="utf8").read())' "$incoming"
tmp="$(mktemp "$ops/.stage5-substantive.XXXXXX")"
install -m 600 "$incoming" "$tmp"
mv -f "$tmp" "$target"
timeout 300s "$py" -B "$target" --factory-private "$root" --stage34-worker "$stage34" --stage5-worker "$stage5" --stage6-worker "$stage6" --batch 200
cron='* * * * * /usr/bin/flock -n /home/githubops/factory-runtime/operations/production-instructions/.stage5-substantive-minute.lock /home/githubops/factory-runtime/.venv/bin/python -B /home/githubops/factory-runtime/operations/production-instructions/stage5-substantive-rework.py --factory-private /home/githubops/factory-runtime/private/autonomous-product-cycle --stage34-worker /home/githubops/factory-runtime/operations/production-instructions/stage34-autonomous-handoff.py --stage5-worker /home/githubops/factory-runtime/operations/production-instructions/stage5-evidence-workbook.py --stage6-worker /home/githubops/factory-runtime/operations/production-instructions/stage6-preflight-rework.py --batch 200 >> /home/githubops/factory-runtime/operations/production-instructions/stage5-substantive-rework.log 2>&1 # SAEIT_FACTORY_STAGE5_SUBSTANTIVE_REWORK_V1'
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
data=json.loads((Path(sys.argv[1])/"stage-05/substantive-revision-status.json").read_text())
for source,dest in [
    ("rework_orders","REWORK_REQUESTS"),
    ("source_specific_revision_briefs_total","SOURCE_SPECIFIC_REVISIONS"),
    ("blocked_this_run","REVISION_BLOCKED_THIS_RUN"),
    ("independent_specialist_approvals","INDEPENDENT_SPECIALIST_APPROVALS"),
    ("stage7_handoffs","STAGE7_HANDOFFS"),
    ("qa1000_approvals","QA1000_APPROVALS")]:
    print("FACTORY_STAGE5_"+dest+"="+str(data[source]))
print("FACTORY_WEBSITES_CHANGED=false")
PY
echo FACTORY_STAGE5_SUBSTANTIVE_BACKUP="$backup"
