#!/usr/bin/env bash
# Install an autonomous, VPS-local, reversible P0 repair->package->QC loop.
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
target="$ops/agri200-autonomous-closed-loop.py"
marker=SAEIT_AGRI200_AUTONOMOUS_CLOSED_LOOP_V1
test -x "$py" && test -d "$ops" && test ! -L "$ops"
test -f "$root/production-instructions/owner-agri200-p0-index.json"
for required in stage2-literature-scout.py stage2-research.py stage34-autonomous-handoff.py stage5-evidence-workbook.py stage6-preflight-rework.py stage5-substantive-rework.py research-navigator.py agri200-strict-qc1000.py agri200-strict-qc-catalog.json; do
    test -f "$ops/$required" && test ! -L "$ops/$required"
done
command -v flock >/dev/null
command -v crontab >/dev/null
exec 8>"$ops/.agri200-autonomous-install.lock"
flock -w 75 8
backup="$base/operations/backups/agri200-autonomous-$(date -u +%Y%m%dT%H%M%SZ)-$$"
install -d -m 700 "$backup"
crontab -l > "$backup/crontab.before" 2>/dev/null || true
chmod 600 "$backup/crontab.before"
if test -e "$target"; then
    test -f "$target" && test ! -L "$target"
    cp -p "$target" "$backup/worker.before.py"
fi
"$py" -B -c 'import ast,sys;ast.parse(open(sys.argv[1],encoding="utf-8").read())' "$incoming"
tmp="$(mktemp "$ops/.autonomous-loop.XXXXXX")"
install -m 600 "$incoming" "$tmp"
mv -f "$tmp" "$target"
"$py" -B "$target" --factory-private "$root" --operations "$ops" --audit-only >/dev/null
cron='* * * * * /usr/bin/flock -n /home/githubops/factory-runtime/operations/production-instructions/.agri200-autonomous-cron.lock /usr/bin/timeout 900s /home/githubops/factory-runtime/.venv/bin/python -B /home/githubops/factory-runtime/operations/production-instructions/agri200-autonomous-closed-loop.py --factory-private /home/githubops/factory-runtime/private/autonomous-product-cycle --operations /home/githubops/factory-runtime/operations/production-instructions > /dev/null 2>> /home/githubops/factory-runtime/operations/production-instructions/agri200-autonomous-errors.log # SAEIT_AGRI200_AUTONOMOUS_CLOSED_LOOP_V1'
if grep -Fq "$marker" "$backup/crontab.before"; then
    test "$(grep -Fc "$marker" "$backup/crontab.before")" -eq 1
    if ! grep -Fxq "$cron" "$backup/crontab.before"; then
        awk -v marker="$marker" -v cron="$cron" 'index($0,marker) {print cron;next} {print}' "$backup/crontab.before" | crontab -
    fi
else
    { sed -n 'p' "$backup/crontab.before"; printf '%s\n' "$cron"; } | crontab -
fi
test "$(crontab -l | grep -Fc "$marker")" -eq 1
# Run the whole chain once immediately; cron continues after this invocation.
timeout 900s "$py" -B "$target" --factory-private "$root" --operations "$ops"
echo AUTONOMOUS_CLOSED_LOOP_BACKUP="$backup"
echo AUTONOMOUS_CLOSED_LOOP_CRON=INSTALLED_ON_VPS
