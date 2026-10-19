#!/usr/bin/env bash
# Install code self-edit proposals to an isolated VPS runtime. Never edit live workers.
set -euo pipefail
umask 077
test "$(id -un)" = githubops
test "$(id -u)" -ne 0
test "$#" -eq 1
source="$1"
test -d "$source" && test ! -L "$source"
test -d "$source/scripts" && test ! -L "$source/scripts"
test -f "$source/scripts/factory_code_self_upgrade.py"
test -f "$source/scripts/factory_research_triage.py"
test -f "$source/scripts/factory_specialist_pilots.py"
base="$HOME/factory-runtime"
ops="$base/operations"
private="$base/private/autonomous-product-cycle"
target="$ops/factory-code-self-upgrade"
runner="$target/run-scan-and-edit.sh"
py="$base/.venv/bin/python"
marker=SAEIT_FACTORY_CODE_SELF_EDIT_HOURLY_V1
test -x "$py"
test -d "$ops" && test -d "$private"
command -v flock >/dev/null
command -v crontab >/dev/null
if find "$source/scripts" -type l -print -quit | grep -q .; then
  echo FACTORY_SELF_EDIT_SOURCE_SYMLINK_REFUSED; exit 2
fi
"$py" -B -m py_compile "$source/scripts/factory_code_self_upgrade.py" \
  "$source/scripts/factory_research_triage.py" "$source/scripts/factory_specialist_pilots.py"
exec 8>"$ops/.code-self-upgrade-install.lock"
flock -w 70 8
test ! -L "$target"
mkdir -p "$target" "$ops/backups"
chmod 700 "$target"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)-$$"
backup="$ops/backups/code-self-upgrade-$timestamp"
mkdir -m 700 "$backup"
crontab -l > "$backup/previous-crontab" || :
chmod 600 "$backup/previous-crontab"
if [[ -d "$target/source" ]]; then
  test ! -L "$target/source"
  cp -a "$target/source" "$backup/source"
fi
if [[ -f "$runner" ]]; then
  test ! -L "$runner"
  cp -p "$runner" "$backup/old-runner"
fi
incoming="$(mktemp -d "$target/.candidate-source.XXXXXX")"
mkdir -p "$incoming/scripts"
find "$source/scripts" -maxdepth 1 -type f -name 'factory_*.py' \
  -exec cp -- {} "$incoming/scripts/" \;
if [[ -f "$source/scripts/vps_master_evolution_cycle.py" ]]; then
  cp "$source/scripts/vps_master_evolution_cycle.py" "$incoming/scripts/"
fi
test -s "$incoming/scripts/factory_code_self_upgrade.py"
find "$incoming" -type d -exec chmod 700 {} +
find "$incoming" -type f -exec chmod 600 {} +
old="$target/source"
if [[ -d "$old" ]]; then
  mv "$old" "$backup/previous-source"
fi
mv "$incoming" "$old"
cat > "$runner" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
umask 077
ops="$HOME/factory-runtime/operations"
exec 7>"$ops/.code-self-upgrade-cycle.lock"
flock -n 7 || exit 0
exec >> "$ops/factory-code-self-upgrade.log" 2>&1
exec "$HOME/factory-runtime/.venv/bin/python" -B \
  "$ops/factory-code-self-upgrade/source/scripts/factory_code_self_upgrade.py" \
  --repo "$ops/factory-code-self-upgrade/source" \
  --out "$HOME/factory-runtime/private/autonomous-product-cycle/code-self-upgrade"
SH
chmod 700 "$runner"
bash -n "$runner"
if ! "$runner"; then
  rm -rf -- "$old"
  if [[ -d "$backup/previous-source" ]]; then
    mv "$backup/previous-source" "$old"
  fi
  if [[ -f "$backup/old-runner" ]]; then
    cp -p "$backup/old-runner" "$runner"
  else
    rm -f "$runner"
  fi
  echo FACTORY_SELF_EDIT_INSTALL_ROLLED_BACK
  exit 4
fi
"$py" -B - "$private/code-self-upgrade/evolution-proof.json" <<'PY'
import json,sys
from pathlib import Path
p=Path(sys.argv[1])
a=json.loads(p.read_text(encoding="utf8"))
assert a["schema"]=="saeit.factory.code-self-upgrade.v1"
assert a["candidate_count"]>=0
assert a["candidate_count"]+a["preexisting_verified_repairs"]==4
assert a["candidates_with_measured_improvement"]==a["candidate_count"]
assert a["validated_repair_rule_coverage"]==4
assert a["factory_python_files_scanned"]>=15
assert a["production_code_promotions"]==0
assert not a["whole_code_autonomous_evolution_complete"]
print("FACTORY_SELF_EDIT_REAL_STAGED_UPGRADES="+str(a["candidate_count"]))
print("FACTORY_SELF_EDIT_FACTORY_MODULES_INVENTORIED="+str(a["factory_python_files_scanned"]))
print("FACTORY_SELF_EDIT_AUTO_PRODUCTION_RELEASE=false")
PY
proposed="$backup/proposed-crontab"
grep -v "$marker" "$backup/previous-crontab" > "$proposed" || true
printf '17 * * * * /bin/bash %s # %s\n' "$runner" "$marker" >> "$proposed"
chmod 600 "$proposed"
# No unrelated scheduled jobs are deleted.
crontab - < "$proposed"
test "$(crontab -l | grep -c "$marker")" -eq 1
test "$(crontab -l | grep -c SAEIT_FACTORY_EVERY_MINUTE_V1)" -eq 1
test "$(crontab -l | grep -c SAEIT_FACTORY_LIFECYCLE_12_V1)" -eq 1
test "$(crontab -l | grep -c SAEIT_FACTORY_FORTY_FAMILY_MASTER_V1)" -eq 1
echo FACTORY_CODE_SELF_EDIT_PRIVATE_INSTALL=PASS
echo FACTORY_CODE_SELF_EDIT_PRODUCTION_MUTATIONS=0
echo FACTORY_CODE_SELF_EDIT_HOURLY_SCAN=PASS
echo FACTORY_CODE_SELF_EDIT_SITE_RELEASE=false
echo FACTORY_CODE_SELF_EDIT_BACKUP="$backup"
