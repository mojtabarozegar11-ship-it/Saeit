#!/usr/bin/env bash
# Private VPS-only Stage-5 draft producer and independent Stage-6 review handoff.
set -euo pipefail
umask 077
test "$(id -un)" = githubops && test "$(id -u)" -ne 0
test "$#" -eq 1
source_file="$1"
test -f "$source_file" && test ! -L "$source_file"
base="$HOME/factory-runtime"
root="$base/private/autonomous-product-cycle"
ops="$base/operations/production-instructions"
python_bin="$base/.venv/bin/python"
worker="$ops/stage5-evidence-workbook.py"
dependency="$ops/stage34-autonomous-handoff.py"
marker=SAEIT_FACTORY_STAGE5_EVIDENCE_WORKBOOK_V1
test -x "$python_bin"
test -d "$ops" && test ! -L "$ops"
test -d "$root/production-instructions/stage-05/inbox"
test -f "$dependency" && test ! -L "$dependency"
command -v flock >/dev/null
exec 8>"$ops/.stage5-install.lock"
flock -w 75 8
backup="$base/operations/backups/stage5-$(date -u +%Y%m%dT%H%M%SZ)-$$"
install -d -m 700 "$backup"
crontab -l > "$backup/crontab.before"
chmod 600 "$backup/crontab.before"
if test -e "$worker"; then
    test -f "$worker" && test ! -L "$worker"
    cp -p "$worker" "$backup/stage5-worker.before.py"
fi
"$python_bin" -B -c 'import ast,sys;ast.parse(open(sys.argv[1],encoding="utf-8").read())' "$source_file"
temporary="$(mktemp "$ops/.stage5.XXXXXX")"
install -m 600 "$source_file" "$temporary"
mv -f "$temporary" "$worker"
# Existing stage-5 handoffs are processed immediately; reviews remain pending,
# and all existing published websites, prices and credentials are unchanged.
timeout 230s "$python_bin" -B "$worker" \
    --factory-private "$root" --stage34-worker "$dependency" --batch 300
cron='* * * * * /usr/bin/flock -n /home/githubops/factory-runtime/operations/production-instructions/.stage5-minute.lock /home/githubops/factory-runtime/.venv/bin/python -B /home/githubops/factory-runtime/operations/production-instructions/stage5-evidence-workbook.py --factory-private /home/githubops/factory-runtime/private/autonomous-product-cycle --stage34-worker /home/githubops/factory-runtime/operations/production-instructions/stage34-autonomous-handoff.py --batch 300 >> /home/githubops/factory-runtime/operations/production-instructions/stage5-worker.log 2>&1 # SAEIT_FACTORY_STAGE5_EVIDENCE_WORKBOOK_V1'
if grep -Fq "$marker" "$backup/crontab.before"; then
    test "$(grep -Fc "$marker" "$backup/crontab.before")" -eq 1
    if grep -Fxq "$cron" "$backup/crontab.before"; then
        echo FACTORY_STAGE5_CRON=ALREADY_PRESENT
    else
        awk -v marker="$marker" -v cron="$cron" \
            'index($0,marker) {print cron;next} {print}' "$backup/crontab.before" | crontab -
        echo FACTORY_STAGE5_CRON=UPDATED
    fi
else
    { cat "$backup/crontab.before"; printf '%s\n' "$cron"; } | crontab -
    echo FACTORY_STAGE5_CRON=INSTALLED
fi
test "$(crontab -l | grep -Fc "$marker")" -eq 1
"$python_bin" -B - "$root/production-instructions" <<'PY'
import json
import sys
from pathlib import Path
area=Path(sys.argv[1])
state=json.loads((area/'stage-05/autonomous-status.json').read_text(encoding='utf-8'))
print('FACTORY_P0_STAGE5_DRAFTS='+str(state['stage5_drafts_total']))
print('FACTORY_P0_STAGE6_REVIEW_TICKETS='+str(state['stage6_review_queue']))
print('FACTORY_P0_STAGE5_BLOCKED_THIS_TICK='+str(state['stage5_blocked_this_tick']))
print('FACTORY_STAGE5_QA1000_APPROVED_CREATED='+str(state['quality1000_certifications_created']))
print('FACTORY_STAGE5_PUBLIC_RELEASES_CREATED='+str(state['public_releases_created']))
PY
echo FACTORY_STAGE5_SITES_MODIFIED=false
echo FACTORY_STAGE5_INSTALL_BACKUP="$backup"
