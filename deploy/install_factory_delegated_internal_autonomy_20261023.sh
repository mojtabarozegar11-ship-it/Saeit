#!/usr/bin/env bash
# Install owner-delegated private internal coordination. No site or shop writes.
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
worker="$ops/delegated-internal-autonomy.py"
marker=SAEIT_FACTORY_OWNER_DELEGATE_COORDINATION_V1
test -x "$python_bin"
test -d "$ops" && test ! -L "$ops"
test -d "$root/production-instructions" && test ! -L "$root/production-instructions"
for dependency in stage1-handoff.py stage2-literature-scout.py stage2-research.py stage34-autonomous-handoff.py stage5-evidence-workbook.py stage6-preflight-rework.py stage5-substantive-rework.py; do
    test -f "$ops/$dependency" && test ! -L "$ops/$dependency"
done
command -v flock >/dev/null
exec 8>"$ops/.delegated-internal-autonomy-install.lock"
flock -w 90 8
backup="$base/operations/backups/delegated-internal-autonomy-$(date -u +%Y%m%dT%H%M%SZ)-$$"
install -d -m 700 "$backup"
crontab -l > "$backup/crontab.before"
chmod 600 "$backup/crontab.before"
if test -e "$worker"; then
    test -f "$worker" && test ! -L "$worker"
    cp -p "$worker" "$backup/delegated-worker.before.py"
fi
"$python_bin" -B -c 'import ast,sys;ast.parse(open(sys.argv[1],encoding="utf-8").read())' "$source_file"
temporary="$(mktemp "$ops/.delegated-internal-autonomy.XXXXXX")"
install -m 600 "$source_file" "$temporary"
mv -f "$temporary" "$worker"
# Prove private stage workers can run without pausing for owner confirmation.
timeout 660s "$python_bin" -B "$worker" \
    --factory-private "$root" \
    --operations "$ops" \
    --python "$python_bin" \
    --batch 200 --worker-timeout 75
cron='*/5 * * * * /usr/bin/flock -n /home/githubops/factory-runtime/operations/production-instructions/.delegated-internal-autonomy-minute.lock /home/githubops/factory-runtime/.venv/bin/python -B /home/githubops/factory-runtime/operations/production-instructions/delegated-internal-autonomy.py --factory-private /home/githubops/factory-runtime/private/autonomous-product-cycle --operations /home/githubops/factory-runtime/operations/production-instructions --python /home/githubops/factory-runtime/.venv/bin/python --batch 50 --worker-timeout 75 >> /home/githubops/factory-runtime/operations/production-instructions/delegated-internal-autonomy.log 2>&1 # SAEIT_FACTORY_OWNER_DELEGATE_COORDINATION_V1'
if grep -Fq "$marker" "$backup/crontab.before"; then
    test "$(grep -Fc "$marker" "$backup/crontab.before")" -eq 1
    if grep -Fxq "$cron" "$backup/crontab.before"; then
        echo FACTORY_OWNER_DELEGATE_CRON=ALREADY_PRESENT
    else
        awk -v marker="$marker" -v cron="$cron" \
            'index($0,marker) {print cron;next} {print}' "$backup/crontab.before" | crontab -
        echo FACTORY_OWNER_DELEGATE_CRON=UPDATED
    fi
else
    { cat "$backup/crontab.before"; printf '%s\n' "$cron"; } | crontab -
    echo FACTORY_OWNER_DELEGATE_CRON=INSTALLED
fi
test "$(crontab -l | grep -Fc "$marker")" -eq 1
"$python_bin" -B - "$root/production-instructions/delegated-internal-autonomy-status.json" <<'PY'
import json,sys
from pathlib import Path
data=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
for key in ("status","new_private_receipts","verified_receipt_counts","failed_workers"):
    print("FACTORY_OWNER_DELEGATE_"+key.upper()+"="+json.dumps(data[key],sort_keys=True))
assert data["operating_authority"]["repeat_owner_confirmation_required_for_internal_work"] is False
assert data["commercial_quality1000_certified"] is False
assert data["public_distribution_authorized"] is False
PY
echo FACTORY_OWNER_DELEGATE_EXTERNAL_PUBLICATION=false
echo FACTORY_OWNER_DELEGATE_INSTALL_BACKUP="$backup"
