#!/usr/bin/env bash
# Install a standalone minute stage-1 intake worker on the existing private VPS.
# Never edits sites, stock, product QA, the minute manufacturing runner or its cron.
set -euo pipefail
umask 077
test "$(id -un)" = githubops && test "$(id -u)" -ne 0
test "$#" -eq 1
src="$1"
test -f "$src" && test ! -L "$src"
base="$HOME/factory-runtime"
ops="$base/operations/production-instructions"
root="$base/private/autonomous-product-cycle"
py="$base/.venv/bin/python"
dest="$ops/stage1-handoff.py"
marker="SAEIT_FACTORY_STAGE1_INDEPENDENT_V1"
test -d "$ops" && test ! -L "$ops"
test -d "$root" && test ! -L "$root"
test -d "$root/production-instructions/orders"
test -x "$py"
command -v flock >/dev/null
exec 8>"$ops/.stage1-deploy.lock"
flock -w 40 8
back="$base/operations/backups/stage1-$(date -u +%Y%m%dT%H%M%SZ)-$$"
install -d -m 700 "$back"
crontab -l > "$back/crontab.before"
chmod 600 "$back/crontab.before"
if test -e "$dest"; then
    test ! -L "$dest"
    cp -p "$dest" "$back/stage1-handoff.before.py"
fi
"$py" -B -c 'import ast,sys;ast.parse(open(sys.argv[1],encoding="utf8").read())' "$src"
temp="$(mktemp "$ops/.stage1.XXXXXX")"
install -m 600 "$src" "$temp"
mv -f "$temp" "$dest"
# Process all currently issued inputs before enabling the independent minutely consumer.
timeout 150s "$py" -B "$dest" --factory-private "$root" --batch 2000
cron='* * * * * /usr/bin/flock -n /home/githubops/factory-runtime/operations/production-instructions/.stage1-minute.lock /home/githubops/factory-runtime/.venv/bin/python -B /home/githubops/factory-runtime/operations/production-instructions/stage1-handoff.py --factory-private /home/githubops/factory-runtime/private/autonomous-product-cycle --batch 1000 >> /home/githubops/factory-runtime/operations/production-instructions/stage1-handoff.log 2>&1 # SAEIT_FACTORY_STAGE1_INDEPENDENT_V1'
if grep -Fq "$marker" "$back/crontab.before"; then
    test "$(grep -Fc "$marker" "$back/crontab.before")" -eq 1
    echo FACTORY_STAGE1_CRON=ALREADY_PRESENT
else
    { cat "$back/crontab.before"; printf '%s\n' "$cron"; } | crontab -
    echo FACTORY_STAGE1_CRON=INSTALLED
fi
test "$(crontab -l | grep -Fc "$marker")" -eq 1
"$py" -B - "$root/production-instructions" <<'PY'
import json,sys
from pathlib import Path
p=Path(sys.argv[1])
r=json.loads((p/"stage-01/status.json").read_text())
assert r["stage"]==1 and r["sites_modified"] is False
assert r["stage_2_worker_verified"] is False
receipts=list((p/"stage-01/receipts").glob("WO-*.json"))
inbox=list((p/"stage-02/inbox").glob("WO-*.json"))
assert len(receipts)>=200
assert len(inbox)>=200
p0=set(json.loads((p/"owner-agri200-p0-index.json").read_text())["order_ids_ranked"])
assert len(p0)==200
for ident in p0:
    file=p/"stage-01/receipts"/(ident+"--r001.json")
    assert file.is_file(), "P0_STAGE1_MISSING:"+ident
    proof=json.loads(file.read_text())
    assert proof["stage_1_completed"] is True and proof["research_completed"] is False
print("FACTORY_STAGE1_P0_COMPLETED=200")
print("FACTORY_STAGE1_TOTAL_DURABLE_RECEIPTS="+str(len(receipts)))
print("FACTORY_STAGE2_INBOX_RECORDS="+str(len(inbox)))
print("FACTORY_STAGE2_RESEARCH_STARTED=NOT_VERIFIED")
print("FACTORY_STAGE1_SITE_CHANGES=0")
PY
echo FACTORY_STAGE1_DEPLOY_BACKUP="$back"
