#!/usr/bin/env bash
# VPS-only correction, bounded shadow evolution; pin current file SHA.
set -euo pipefail
umask 077
test "$(id -un)" = githubops
test "$#" -eq 1
stage="$1"
test -d "$stage" && test ! -L "$stage"
ops="$HOME/factory-runtime/operations"
private="$HOME/factory-runtime/private/autonomous-product-cycle"
py="$HOME/factory-runtime/.venv/bin/python"
test -x "$py"
test "$(crontab -l | grep -c SAEIT_FACTORY_EVERY_MINUTE_V1)" -eq 1
test "$(crontab -l | grep -c SAEIT_FACTORY_LIFECYCLE_12_V1)" -eq 1
test "$(crontab -l | grep -c SAEIT_FACTORY_FORTY_FAMILY_MASTER_V1)" -eq 1
names=(factory_vps_product_cycle.py factory_12_stage_governance.py factory_40_family_master.py)
files=(
 "$ops/autonomous-product-runtime/scripts/factory_vps_product_cycle.py"
 "$ops/12-stage-governance/factory_12_stage_governance.py"
 "$ops/forty-family-master/factory_40_family_master.py"
)
for name in "${names[@]}" factory_evolution_50.py; do
  test -f "$stage/new-$name" && test ! -L "$stage/new-$name"
  "$py" -B -c 'import ast,sys;ast.parse(open(sys.argv[1],encoding="utf8").read())' "$stage/new-$name"
done
exec 6>"$ops/.factory-agent-hardening-deploy.lock"
flock -w 40 6
exec 7>"$ops/.factory-minute-cycle.lock"
exec 8>"$ops/.lifecycle-tick.lock"
exec 9>"$ops/.factory-forty-minute-master.lock"
flock -w 80 7
flock -w 80 8
flock -w 80 9
for i in 0 1 2; do
  file="${files[$i]}"; name="${names[$i]}"
  test -f "$file" && test ! -L "$file"
  test -f "$stage/old-$name"
  expected="$(sha256sum "$stage/old-$name" | awk '{print $1}')"
  live="$(sha256sum "$file" | awk '{print $1}')"
  if test "$live" != "$expected"; then
    echo "FACTORY_CORE_REFUSED_CHANGED_FILE=$name"
    exit 1
  fi
done
test ! -L "$ops/backups"
test ! -L "$ops/factory-evolution-50"
install -d -m 700 "$ops/backups" "$ops/factory-evolution-50"
backup="$ops/backups/factory-hardening-$(date -u +%Y%m%dT%H%M%SZ)-$$"
install -d -m 700 "$backup"
crontab -l > "$backup/crontab-original"
for i in 0 1 2; do
  cp -p "${files[$i]}" "$backup/${names[$i]}"
done
evo="$ops/factory-evolution-50/factory_evolution_50.py"
runner="$ops/factory-evolution-50/run-shadow.sh"
for p in "$evo" "$runner"; do
  test ! -L "$p"
  if test -f "$p"; then cp -p "$p" "$backup/$(basename "$p").old"; fi
done
changed=0
cron_changed=0
restore(){
  code=$?
  if test "$changed" -eq 1; then
    for i in 0 1 2; do cp -p "$backup/${names[$i]}" "${files[$i]}" || true; done
    for p in "$evo" "$runner"; do
      if test -f "$backup/$(basename "$p").old"; then
        cp -p "$backup/$(basename "$p").old" "$p" || true
      else
        rm -f -- "$p"
      fi
    done
    echo FACTORY_HARDENING_RESTORED_OLD_CODE
  fi
  if test "$cron_changed" -eq 1; then
    crontab - < "$backup/crontab-original" || true
    echo FACTORY_HARDENING_RESTORED_CRON
  fi
  exit "$code"
}
trap restore EXIT
changed=1
for i in 0 1 2; do
  dest="${files[$i]}";name="${names[$i]}"
  tmp="$(mktemp "$(dirname "$dest")/.factory-agent.XXXXXXXX")"
  install -m 600 "$stage/new-$name" "$tmp"
  mv -f -- "$tmp" "$dest"
done
install -m 600 "$stage/new-factory_evolution_50.py" "$evo"
cat > "$runner" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
umask 077
ops="$HOME/factory-runtime/operations"
private="$HOME/factory-runtime/private/autonomous-product-cycle"
exec 5>"$ops/.factory-evolution-50.lock"
flock -n 5 || exit 0
exec >> "$ops/factory-evolution-50.log" 2>&1
"$HOME/factory-runtime/.venv/bin/python" -B \
 "$ops/factory-evolution-50/factory_evolution_50.py" --factory-private "$private"
SH
chmod 700 "$runner"
bash -n "$runner"
"$py" -B "$ops/12-stage-governance/factory_12_stage_governance.py" --factory-private "$private" --tick > "$backup/qa-validation"
"$py" -B "$ops/forty-family-master/factory_40_family_master.py" --factory-private "$private" --registry "$ops/forty-family-master/forty_families.json" > "$backup/master-validation"
"$runner"
"$py" -B - "$private" <<'PY'
from pathlib import Path
import json,sys
p=Path(sys.argv[1])
qa=json.loads((p/"product-lifecycle/dashboard.json").read_text())
stock=json.loads((p/"production-warehouse/stock-register.json").read_text())
master=json.loads((p/"production-family-management/family-dashboard.json").read_text())
evo=json.loads((p/"factory-evolution-50/evolution-status.json").read_text())
assert qa["site_distribution_enabled"] is False
assert stock["sites_contacted"]==0 and stock["finished_goods_versions"]>=2
assert master["registered_families"]==40 and master["distribution_enabled"] is False
assert evo["verified_promoted_generation"]==0
assert evo["generation_limit"]==50 and evo["source_mutation_performed"] is False
print("FACTORY_GENES_HARDENING_VPS_SMOKE=PASS")
print("FACTORY_50_GENERATION_SHADOW_ACTIVE=true")
print("FACTORY_GENETIC_REAL_PROMOTIONS=0")
print("FACTORY_FINISHED_APPROVED="+str(qa["final_commercially_verified_stock"]))
PY
marker=SAEIT_FACTORY_EVOLUTION_50_SHADOW_V1
grep -v "$marker" "$backup/crontab-original" > "$backup/crontab-proposed" || true
printf '* * * * * /bin/bash %s # %s\n' "$runner" "$marker" >> "$backup/crontab-proposed"
test "$(crontab -l | sha256sum | awk '{print $1}')" = "$(sha256sum "$backup/crontab-original" | awk '{print $1}')"
cron_changed=1
crontab - < "$backup/crontab-proposed"
test "$(crontab -l | grep -c "$marker")" -eq 1
test "$(crontab -l | grep -c SAEIT_FACTORY_EVERY_MINUTE_V1)" -eq 1
test "$(crontab -l | grep -c SAEIT_FACTORY_LIFECYCLE_12_V1)" -eq 1
test "$(crontab -l | grep -c SAEIT_FACTORY_FORTY_FAMILY_MASTER_V1)" -eq 1
changed=0
cron_changed=0
trap - EXIT
echo FACTORY_CORE_MODULES_PATCHED=3
echo FACTORY_CODE_STATUS=VPS_VERIFIED
echo FACTORY_GENOTYPE_MAX_GENERATIONS=50
echo FACTORY_WEBSITE_TRANSFER=false
echo FACTORY_ROLLBACK_BACKUP="$backup"
