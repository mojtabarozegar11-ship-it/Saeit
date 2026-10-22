#!/usr/bin/env bash
# Safe private stage-2 installer; dedicated worker and cron, no storefront changes.
set -euo pipefail
umask 077
test "$(id -un)" = githubops && test "$(id -u)" -ne 0
test "$#" -eq 2
src="$1"
curated="$2"
test -f "$src" && test ! -L "$src"
test -f "$curated" && test ! -L "$curated"
base="$HOME/factory-runtime"
ops="$base/operations/production-instructions"
root="$base/private/autonomous-product-cycle"
py="$base/.venv/bin/python"
dest="$ops/stage2-research.py"
marker="SAEIT_FACTORY_STAGE2_RESEARCH_V1"
test -d "$ops" && test ! -L "$ops"
test -d "$root/production-instructions/stage-02/inbox"
test -x "$py"
command -v flock >/dev/null
exec 8>"$ops/.stage2-deploy.lock"
flock -w 40 8
back="$base/operations/backups/stage2-$(date -u +%Y%m%dT%H%M%SZ)-$$"
install -d -m 700 "$back"
crontab -l > "$back/crontab.before"
chmod 600 "$back/crontab.before"
if test -e "$dest"; then
    test ! -L "$dest"
    cp -p "$dest" "$back/stage2-research.before.py"
fi
"$py" -B -c 'import ast,sys;ast.parse(open(sys.argv[1],encoding="utf8").read())' "$src"
"$py" -B -c 'import json,sys;v=json.load(open(sys.argv[1],encoding="utf8"));assert 3<=len(v["bundles"])<=200' "$curated"
temp="$(mktemp "$ops/.stage2.XXXXXX")"
install -m 600 "$src" "$temp"
mv -f "$temp" "$dest"
# Register reviewed public scientific/extension sources for the first three P0
# briefs. Stage 2 alone checks citation structure, not source factual truth.
timeout 180s "$py" -B "$dest" --factory-private "$root" --seed-research "$curated" --batch 220
cron='* * * * * /usr/bin/flock -n /home/githubops/factory-runtime/operations/production-instructions/.stage2-minute.lock /home/githubops/factory-runtime/.venv/bin/python -B /home/githubops/factory-runtime/operations/production-instructions/stage2-research.py --factory-private /home/githubops/factory-runtime/private/autonomous-product-cycle --batch 250 >> /home/githubops/factory-runtime/operations/production-instructions/stage2-research.log 2>&1 # SAEIT_FACTORY_STAGE2_RESEARCH_V1'
if grep -Fq "$marker" "$back/crontab.before"; then
    test "$(grep -Fc "$marker" "$back/crontab.before")" -eq 1
    echo FACTORY_STAGE2_CRON=ALREADY_PRESENT
else
    { cat "$back/crontab.before"; printf '%s\n' "$cron"; } | crontab -
    echo FACTORY_STAGE2_CRON=INSTALLED
fi
test "$(crontab -l | grep -Fc "$marker")" -eq 1
"$py" -B - "$root/production-instructions" <<'PY'
import json,sys
from pathlib import Path
p=Path(sys.argv[1])
i=json.loads((p/"owner-agri200-p0-index.json").read_text())
assert i["topic_count"]==200
stage3=0
missing=0
for work in i["order_ids_ranked"]:
    name=work+"--r001.json"
    if (p/"stage-02/receipts"/name).is_file():
        receipt=json.loads((p/"stage-02/receipts"/name).read_text())
        assert receipt["stage_2_completed"] is True
        assert receipt["scientific_review_completed"] is False
        stage3+=1
    elif (p/"stage-02/research-needed"/name).is_file():
        brief=json.loads((p/"stage-02/research-needed"/name).read_text())
        assert brief["stage_2_research_completed"] is False
        missing+=1
    else:
        raise RuntimeError("STAGE2_P0_NOT_PROCESSED:"+work)
assert stage3>=3 and stage3+missing==200
assert not (p.parent/"production-warehouse"/"stage2-commercial-release.json").exists()
print("FACTORY_STAGE2_P0_RESEARCH_DOCUMENTED="+str(stage3))
print("FACTORY_STAGE2_P0_MISSING_SOURCE_WORKPAPERS="+str(missing))
print("FACTORY_STAGE2_P0_ACCOUNTED="+str(stage3+missing))
print("FACTORY_STAGE2_INDEPENDENT_REVIEW=NOT_CLAIMED")
print("FACTORY_STAGE2_SITE_DEPLOYMENTS=0")
PY
echo FACTORY_STAGE2_DEPLOY_BACKUP="$back"
