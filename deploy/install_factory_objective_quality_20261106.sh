#!/usr/bin/env bash
# One-shot, bounded VPS policy migration: no numeric score, no publication.
# Preserves all historical manifests, customer ZIPs, receipts and cron entries.
set -Eeuo pipefail
umask 077

source_repo="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
base="$HOME/factory-runtime"
runtime="$base/operations/single-product-runtime"
private="$base/private/autonomous-product-cycle"
db="$base/private/factory-fresh-isolated.sqlite3"
python="$base/.venv/bin/python"
runner="$runtime/run-single-product-cycle.sh"

[[ "$(id -un)" == githubops && "$(id -u)" -ne 0 ]] || exit 21
for directory in "$base" "$base/operations" "$base/operations/backups" "$runtime" \
                 "$runtime/scripts" "$runtime/product_recipes" "$private"; do
  [[ -d "$directory" && ! -L "$directory" ]] || exit 22
done
[[ -x "$python" && -x "$runner" && -f "$db" && ! -L "$db" ]] || exit 23
grep -Fq 'factory_vps_product_cycle.py' "$runner" || exit 24
files=(factory_product_maker.py factory_verified_customer_cycle_20261021.py factory_vps_product_cycle.py)
# Some installed native variants have the finished-goods warehouse module.
if [[ -f "$runtime/scripts/factory_production_warehouse.py" ]]; then
  files+=(factory_production_warehouse.py)
fi
for name in "${files[@]}"; do
  [[ -f "$source_repo/scripts/$name" && ! -L "$source_repo/scripts/$name" ]] || exit 25
  [[ -f "$runtime/scripts/$name" && ! -L "$runtime/scripts/$name" ]] || exit 26
  "$python" -B -c 'import ast,sys,pathlib; ast.parse(pathlib.Path(sys.argv[1]).read_text(encoding="utf8"))' "$source_repo/scripts/$name"
done

before_cron="$(crontab -l | sha256sum | awk '{print $1}')"
[[ "$(crontab -l | grep -c 'SAEIT_SINGLE_PRODUCT_FACTORY_V1' || true)" == 1 ]] || exit 27
free_kib="$(df -Pk "$private" | awk 'NR==2 {print $4}')"
[[ "$free_kib" =~ ^[0-9]+$ ]] && (( free_kib >= 552960 )) || exit 28

exec 9>"$private/.single-product-cycle.lock"
flock -w 100 9 || exit 29
exec 8>"$private/.production-cycle.lock"
flock -w 30 8 || exit 30

backup="$base/operations/backups/objective-quality-$(date -u +%Y%m%dT%H%M%SZ)-$$"
install -d -m 700 "$backup"
for name in "${files[@]}"; do
  install -m 600 "$runtime/scripts/$name" "$backup/$name.before"
  sha256sum "$backup/$name.before" >> "$backup/installed-before.sha256"
done
chmod 600 "$backup/installed-before.sha256"
changed=false
accepted=false
restore_on_failure() {
  code=$?
  if [[ "$changed" == true && "$accepted" != true ]]; then
    flock -w 100 9 || true
    flock -w 30 8 || true
    for name in "${files[@]}"; do
      recovery="$(mktemp "$runtime/scripts/.quality-restore.XXXXXXXX")"
      install -m 600 "$backup/$name.before" "$recovery"
      mv -f -- "$recovery" "$runtime/scripts/$name"
    done
    echo FACTORY_OBJECTIVE_QUALITY_ROLLBACK=RESTORED
  fi
  exit "$code"
}
trap restore_on_failure EXIT

for name in "${files[@]}"; do
  source="$source_repo/scripts/$name"
  candidate="$(mktemp "$runtime/scripts/.quality-candidate.XXXXXXXX")"
  install -m 600 "$source" "$candidate"
  [[ "$(sha256sum "$candidate" | awk '{print $1}')" == "$(sha256sum "$source" | awk '{print $1}')" ]]
  changed=true
  mv -f -- "$candidate" "$runtime/scripts/$name"
done

for name in "${files[@]}"; do
  [[ "$(sha256sum "$runtime/scripts/$name" | awk '{print $1}')" == "$(sha256sum "$source_repo/scripts/$name" | awk '{print $1}')" ]]
done
flock -u 8
flock -u 9

# Exercise one real private cycle with the native Python; never call a shop.
timeout 180s "$python" -B "$runtime/scripts/factory_vps_product_cycle.py" \
  --db "$db" --out "$private" --recipes "$runtime/product_recipes" \
  --max-products 1 --max-recipes 1 \
  --no-enable-designer --no-enable-design-intake --no-enable-invention-supply

"$python" -B - "$private" <<'PY'
import json,sys
from pathlib import Path
root=Path(sys.argv[1])
state=json.loads((root/'production-state.json').read_text(encoding='utf8'))
slots=json.loads((root/'quality-excellence/product-flow/active-slots/current.json').read_text(encoding='utf8'))
assert state['objective_quality_gates']=='technical_archive_tests_and_release_readiness_separate'
assert state['customer_zip_tests_cannot_authorize_commercial_publication'] is True
assert state['publishable_product_count']==0
assert state['store_distribution_state']=='not_connected'
assert slots['quality_policy']=='objective_customer_acceptance_v1'
assert slots['commercial_release'] is False
assert len(slots['active'])<=1
print('FACTORY_OBJECTIVE_QUALITY_NATIVE_RECEIPT=PASS')
print('FACTORY_TECHNICAL_FINISHED='+str(len(slots['technical_exited'])))
print('FACTORY_ACTIVE='+str(len(slots['active'])))
print('FACTORY_WAITING='+str(len(slots['waiting'])))
print('FACTORY_NUMERIC_SCORE_REQUIREMENT=REMOVED')
print('FACTORY_COMMERCE_AUTOPUBLISH=DISABLED')
PY
[[ "$(crontab -l | sha256sum | awk '{print $1}')" == "$before_cron" ]] || exit 31
accepted=true
echo FACTORY_OBJECTIVE_QUALITY_BACKUP="$backup"
