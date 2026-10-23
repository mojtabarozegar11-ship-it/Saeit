#!/usr/bin/env bash
# VPS-private Stage 6 integrity audit + stage 5 scientific rework feedback.
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
worker="$ops/stage6-preflight-rework.py"
dependency34="$ops/stage34-autonomous-handoff.py"
dependency5="$ops/stage5-evidence-workbook.py"
marker=SAEIT_FACTORY_STAGE6_PREFLIGHT_REWORK_V1
test -x "$python_bin"
test -d "$ops" && test ! -L "$ops"
test -d "$root/production-instructions/stage-06/inbox"
test -f "$dependency34" && test ! -L "$dependency34"
test -f "$dependency5" && test ! -L "$dependency5"
command -v flock >/dev/null
exec 8>"$ops/.stage6-install.lock"
flock -w 75 8
backup="$base/operations/backups/stage6-$(date -u +%Y%m%dT%H%M%SZ)-$$"
install -d -m 700 "$backup"
crontab -l > "$backup/crontab.before"
chmod 600 "$backup/crontab.before"
if test -e "$worker"; then
    test -f "$worker" && test ! -L "$worker"
    cp -p "$worker" "$backup/stage6-worker.before.py"
fi
"$python_bin" -B -c 'import ast,sys;ast.parse(open(sys.argv[1],encoding="utf-8").read())' "$source_file"
temporary="$(mktemp "$ops/.stage6.XXXXXX")"
install -m 600 "$source_file" "$temporary"
mv -f "$temporary" "$worker"
timeout 230s "$python_bin" -B "$worker" \
    --factory-private "$root" --stage34-worker "$dependency34" \
    --stage5-worker "$dependency5" --batch 300
cron='* * * * * /usr/bin/flock -n /home/githubops/factory-runtime/operations/production-instructions/.stage6-minute.lock /home/githubops/factory-runtime/.venv/bin/python -B /home/githubops/factory-runtime/operations/production-instructions/stage6-preflight-rework.py --factory-private /home/githubops/factory-runtime/private/autonomous-product-cycle --stage34-worker /home/githubops/factory-runtime/operations/production-instructions/stage34-autonomous-handoff.py --stage5-worker /home/githubops/factory-runtime/operations/production-instructions/stage5-evidence-workbook.py --batch 300 >> /home/githubops/factory-runtime/operations/production-instructions/stage6-worker.log 2>&1 # SAEIT_FACTORY_STAGE6_PREFLIGHT_REWORK_V1'
if grep -Fq "$marker" "$backup/crontab.before"; then
    test "$(grep -Fc "$marker" "$backup/crontab.before")" -eq 1
    if grep -Fxq "$cron" "$backup/crontab.before"; then
        echo FACTORY_STAGE6_CRON=ALREADY_PRESENT
    else
        awk -v marker="$marker" -v cron="$cron" \
            'index($0,marker) {print cron;next} {print}' "$backup/crontab.before" | crontab -
        echo FACTORY_STAGE6_CRON=UPDATED
    fi
else
    { cat "$backup/crontab.before"; printf '%s\n' "$cron"; } | crontab -
    echo FACTORY_STAGE6_CRON=INSTALLED
fi
test "$(crontab -l | grep -Fc "$marker")" -eq 1
"$python_bin" -B - "$root/production-instructions" <<'PY'
import json
import sys
from pathlib import Path
area=Path(sys.argv[1])
state=json.loads((area/'stage-06/autonomous-status.json').read_text(encoding='utf-8'))
for label,key in (
    ('STAGE6_INBOX','stage6_inbox'),
    ('STAGE6_TECHNICAL_PREFLIGHTS','stage6_technical_preflights_total'),
    ('STAGE6_INTEGRITY_BLOCKED_THIS_TICK','stage6_integrity_blocked_this_tick'),
    ('STAGE5_SUBSTANTIVE_REWORK_REQUESTS','stage5_substantive_rework_requests_total'),
    ('STAGE6_INDEPENDENT_SCIENTIFIC_APPROVALS','stage6_independent_scientific_reviews_completed_by_worker'),
    ('STAGE7_APPROVED_HANDOFFS','stage7_approved_handoffs_created'),
    ('QC1000_CERTIFICATIONS','quality1000_certifications_created')):
    print('FACTORY_'+label+'='+str(state[key]))
PY
echo FACTORY_STAGE6_SITES_MODIFIED=false
echo FACTORY_STAGE6_INSTALL_BACKUP="$backup"
