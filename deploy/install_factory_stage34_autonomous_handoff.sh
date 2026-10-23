#!/usr/bin/env bash
# Stage-3 design + stage-4 prototype workers, private VPS only.
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
worker="$ops/stage34-autonomous-handoff.py"
marker="SAEIT_FACTORY_STAGE34_AUTONOMOUS_HANDOFF_V1"
test -x "$python_bin"
test -d "$ops" && test ! -L "$ops"
test -d "$root/production-instructions/stage-03/inbox"
command -v flock >/dev/null
exec 8>"$ops/.stage34-install.lock"
flock -w 90 8
backup="$base/operations/backups/stage34-$(date -u +%Y%m%dT%H%M%SZ)-$$"
install -d -m 700 "$backup"
crontab -l > "$backup/crontab.before"
chmod 600 "$backup/crontab.before"
if test -e "$worker"; then
    test -f "$worker" && test ! -L "$worker"
    cp -p "$worker" "$backup/stage34-worker.before.py"
fi
"$python_bin" -B -c 'import ast,sys;ast.parse(open(sys.argv[1],encoding="utf-8").read())' "$source_file"
temporary="$(mktemp "$ops/.stage34.XXXXXX")"
install -m 600 "$source_file" "$temporary"
mv -f "$temporary" "$worker"
# Existing completed research dossiers are processed immediately. This is
# original design/prototype work, not scientific review or completed manuscripts.
timeout 180s "$python_bin" -B "$worker" --factory-private "$root" --batch 500
cron='* * * * * /usr/bin/flock -n /home/githubops/factory-runtime/operations/production-instructions/.stage34-minute.lock /home/githubops/factory-runtime/.venv/bin/python -B /home/githubops/factory-runtime/operations/production-instructions/stage34-autonomous-handoff.py --factory-private /home/githubops/factory-runtime/private/autonomous-product-cycle --batch 500 >> /home/githubops/factory-runtime/operations/production-instructions/stage34-worker.log 2>&1 # SAEIT_FACTORY_STAGE34_AUTONOMOUS_HANDOFF_V1'
if grep -Fq "$marker" "$backup/crontab.before"; then
    test "$(grep -Fc "$marker" "$backup/crontab.before")" -eq 1
    if grep -Fxq "$cron" "$backup/crontab.before"; then
        echo FACTORY_STAGE34_CRON=ALREADY_PRESENT
    else
        awk -v marker="$marker" -v cron="$cron" \
            'index($0,marker) {print cron;next} {print}' "$backup/crontab.before" | crontab -
        echo FACTORY_STAGE34_CRON=UPDATED
    fi
else
    { cat "$backup/crontab.before"; printf '%s\n' "$cron"; } | crontab -
    echo FACTORY_STAGE34_CRON=INSTALLED
fi
test "$(crontab -l | grep -Fc "$marker")" -eq 1
"$python_bin" -B - "$root/production-instructions" <<'PY'
import hashlib,json,sys
from pathlib import Path
area=Path(sys.argv[1])
index=json.loads((area/"owner-agri200-p0-index.json").read_text())
assert len(index["order_ids_ranked"])==200
stage2=stage3=stage4=stage5=bad=0
for ident in index["order_ids_ranked"]:
    name=ident+"--r001.json"
    has2=(area/"stage-02/receipts"/name).is_file()
    has3=(area/"stage-03/receipts"/name).is_file()
    has4=(area/"stage-04/receipts"/name).is_file()
    has5=(area/"stage-05/inbox"/name).is_file()
    if has2: stage2+=1
    if has3: stage3+=1
    if has4: stage4+=1
    if has5: stage5+=1
    if has4 and not (has5 and has3 and has2): bad+=1
    if has3 and not has2: bad+=1
assert bad==0, "INVALID_DOWNSTREAM_TRANSITION"
assert stage4==stage5
assert stage3>=stage4
assert stage3>=3, "STAGE3_NO_REAL_P0_DESIGNS"
for name in ("stage-03/completed-designs","stage-04/completed-prototypes"):
    for file in (area/name).glob("WO-*.json"):
        doc=json.loads(file.read_text())
        assert doc.get("commercial_release") is False
        assert doc.get("public_distribution_allowed") is False
        assert doc.get("quality1000_approved") is False
        assert doc.get("full_manuscript_created") is False
status=json.loads((area/"stage-04/autonomous-status.json").read_text())
assert status["websites_modified"] is False
assert status["independent_scientific_reviews_created"]==0
assert status["public_releases"]==0
print("FACTORY_P0_STAGE2_SCIENTIFIC_SOURCE_DOSSIERS="+str(stage2))
print("FACTORY_P0_STAGE3_REAL_BILINGUAL_DESIGNS="+str(stage3))
print("FACTORY_P0_STAGE4_REAL_WORKSHEET_PROTOTYPES="+str(stage4))
print("FACTORY_P0_STAGE5_AWAITING_FULL_MANUSCRIPT_PRODUCTION="+str(stage5))
print("FACTORY_P0_RESEARCH_PENDING="+str(200-stage2))
print("FACTORY_QA1000_CERTIFICATIONS_CREATED=0")
print("FACTORY_SITES_MODIFIED=false")
PY
echo FACTORY_STAGE34_INSTALL_BACKUP="$backup"
