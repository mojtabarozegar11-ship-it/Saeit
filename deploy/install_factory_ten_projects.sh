#!/usr/bin/env bash
# Private, idempotent 10-project activation; no storefront modification.
set -euo pipefail
umask 077
test "$(id -un)" = githubops && test "$(id -u)" -ne 0
test "$#" -eq 3
launcher="$1"
stage1="$2"
stage2="$3"
for src in "$launcher" "$stage1" "$stage2"; do
  test -f "$src" && test ! -L "$src"
done
base="$HOME/factory-runtime"
root="$base/private/autonomous-product-cycle"
ops="$base/operations/production-instructions"
py="$base/.venv/bin/python"
test -x "$py"
test -d "$root/production-instructions/orders"
test -d "$root/production-instructions/stage-02/inbox"
test -f "$root/production-instructions/owner-agri200-p0-index.json"
test -d "$ops" && test ! -L "$ops"
command -v flock >/dev/null
exec 8>"$ops/.ten-projects-deploy.lock"
flock -w 50 8
dest="$ops/ten-projects-launcher"
test ! -L "$dest"
mkdir -p -m 700 "$dest"
back="$base/operations/backups/ten-projects-$(date -u +%Y%m%dT%H%M%SZ)-$$"
install -d -m 700 "$back"
crontab -l > "$back/crontab.before"
chmod 600 "$back/crontab.before"
for file in factory_ten_project_launcher.py factory_stage1_handoff.py factory_stage2_research.py; do
  if test -e "$dest/$file"; then
    test ! -L "$dest/$file"
    cp -p "$dest/$file" "$back/$file"
  fi
done
for src in "$launcher" "$stage1" "$stage2"; do
  "$py" -B -c 'import ast,sys;ast.parse(open(sys.argv[1],encoding="utf8").read())' "$src"
done
install -m 600 "$launcher" "$dest/factory_ten_project_launcher.py"
install -m 600 "$stage1" "$dest/factory_stage1_handoff.py"
install -m 600 "$stage2" "$dest/factory_stage2_research.py"
timeout 180s "$py" -B "$dest/factory_ten_project_launcher.py" --factory-private "$root" --activate
cron='*/5 * * * * /usr/bin/flock -n /home/githubops/factory-runtime/operations/production-instructions/.ten-projects-minute.lock /home/githubops/factory-runtime/.venv/bin/python -B /home/githubops/factory-runtime/operations/production-instructions/ten-projects-launcher/factory_ten_project_launcher.py --factory-private /home/githubops/factory-runtime/private/autonomous-product-cycle >> /home/githubops/factory-runtime/operations/production-instructions/ten-projects-launcher.log 2>&1 # SAEIT_FACTORY_TEN_PROJECTS_V1'
marker="SAEIT_FACTORY_TEN_PROJECTS_V1"
if grep -Fq "$marker" "$back/crontab.before"; then
  test "$(grep -Fc "$marker" "$back/crontab.before")" -eq 1
  echo FACTORY_TEN_AUTOMATION=ALREADY_INSTALLED
else
  { sed -n '1,$p' "$back/crontab.before"; printf '%s\n' "$cron"; } | crontab -
  echo FACTORY_TEN_AUTOMATION=INSTALLED
fi
test "$(crontab -l | grep -Fc "$marker")" -eq 1
"$py" -B - "$root/production-instructions/ten-projects/status.json" <<'PY'
import json,sys
from pathlib import Path
r=json.loads(Path(sys.argv[1]).read_text(encoding="utf8"))
assert r["projects_kicked_off"]==10 and r["bilingual_editions_planned"]==20
assert len(r["project_ids"])==10
assert r["quality_1000_certified"]==0 and r["website_deployments"]==0
print("FACTORY_TEN_P0_START_CONFIRMED=10")
print("FACTORY_TEN_PRIVATE_MONITOR_REGISTERED=true")
print("FACTORY_TEN_REAL_SALES_PROVEN=false")
PY
echo FACTORY_TEN_BACKUP="$back"
