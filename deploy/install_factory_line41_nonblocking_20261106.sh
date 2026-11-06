#!/usr/bin/env bash
# Bounded in-place repair of the already installed single-product VPS runtime.
# No cron changes, no customer/site writes, no old factory data deletion.
set -Eeuo pipefail
umask 077

source_repo="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
base="$HOME/factory-runtime"
ops="$base/operations"
runtime="$ops/single-product-runtime"
private="$base/private/autonomous-product-cycle"
installed="$runtime/scripts/factory_vps_product_cycle.py"
candidate="$source_repo/scripts/factory_vps_product_cycle.py"
python="$base/.venv/bin/python"
db="$base/private/factory-fresh-isolated.sqlite3"
slots="$private/quality-excellence/product-flow/active-slots/current.json"
runner="$runtime/run-single-product-cycle.sh"

[[ "$(id -un)" == githubops && "$(id -u)" -ne 0 ]] || { echo LINE41_NONROOT_SERVICE_USER_REQUIRED; exit 2; }
for directory in "$base" "$ops" "$runtime" "$runtime/scripts" "$runtime/product_recipes" "$private"; do
  [[ -d "$directory" && ! -L "$directory" ]] || { echo LINE41_RUNTIME_DIRECTORY_UNSAFE; exit 3; }
done
for file in "$installed" "$candidate" "$slots" "$runner" "$db"; do
  [[ -f "$file" && ! -L "$file" ]] || { echo LINE41_REQUIRED_FILE_MISSING_OR_LINK; exit 4; }
done
[[ -x "$python" && -x "$runner" ]] || { echo LINE41_WORKER_UNAVAILABLE; exit 5; }
[[ "$(crontab -l | grep -c 'SAEIT_SINGLE_PRODUCT_FACTORY_V1' || true)" == 1 ]] || {
  echo LINE41_CRON_OWNERSHIP_NOT_VERIFIED; exit 6;
}
grep -Fq 'factory_vps_product_cycle.py' "$runner" || { echo LINE41_RUNNER_NOT_THE_EXPECTED_MODULE; exit 7; }
grep -Fq -- '--no-enable-designer' "$runner" || { echo LINE41_SINGLE_RUNNER_MODE_CHANGED; exit 7; }
for file in "$runtime/scripts/factory_product_maker.py" "$runtime/scripts/factory_verified_customer_cycle_20261021.py" \
            "$runtime/scripts/factory_product_rework.py" "$runtime/scripts/factory_master_agent_genetics_v1.py"; do
  [[ -f "$file" && ! -L "$file" ]] || { echo LINE41_DEPENDENCY_MISSING_OR_LINK; exit 8; }
done
for recipe in water_budget_economics greenhouse_crop_margin; do
  source="$source_repo/product_recipes/$recipe"
  [[ -d "$source" && ! -L "$source" && -f "$source/README.md" ]] || {
    echo LINE41_ADDITIONAL_RECIPE_UNAVAILABLE; exit 9;
  }
  [[ -z "$(find "$source" -type l -print -quit)" ]] || { echo LINE41_RECIPE_SYMLINK; exit 9; }
  destination="$runtime/product_recipes/$recipe"
  if [[ -e "$destination" || -L "$destination" ]]; then
    [[ -d "$destination" && ! -L "$destination" ]] || { echo LINE41_DESTINATION_UNSAFE; exit 9; }
  fi
done

# One small module plus two existing licensed repository recipes; no large
# rollback archive or product-cache replication on a disk with low headroom.
free_kib="$(df -Pk "$private" | awk 'NR==2 {print $4}')"
[[ "$free_kib" =~ ^[0-9]+$ ]] && (( free_kib >= 552960 )) || {
  echo LINE41_STORAGE_RESERVE_HOLD; exit 10;
}
"$python" -B -c 'import ast,sys,pathlib;ast.parse(pathlib.Path(sys.argv[1]).read_text(encoding="utf8"))' "$candidate"
"$python" -B - "$slots" <<'PY'
import json,sys
from pathlib import Path
state=json.loads(Path(sys.argv[1]).read_text(encoding="utf8"))
assert state.get("schema")=="saeit.factory.product-slots.v1"
assert isinstance(state.get("active"),list) and len(state["active"])<=1
assert isinstance(state.get("waiting"),list)
assert isinstance(state.get("exited"),dict)
print("LINE41_ORIGINAL_SLOT_STATE_COMPATIBLE")
PY

cron_before="$(crontab -l | sha256sum | awk '{print $1}')"
exec 9>"$private/.single-product-cycle.lock"
flock -w 80 9 || { echo LINE41_ACTIVE_WORKER_LOCK_TIMEOUT; exit 11; }
exec 8>"$private/.production-cycle.lock"
flock -w 20 8 || { echo LINE41_PRODUCT_LOCK_TIMEOUT; exit 12; }

stamp="$(date -u +%Y%m%dT%H%M%SZ)-$$"
backup_dir="$ops/backups/line41-nonblocking-$stamp"
install -d -m 700 "$backup_dir"
install -m 600 "$installed" "$backup_dir/factory_vps_product_cycle.py.before"
original_sha="$(sha256sum "$installed" | awk '{print $1}')"
candidate_sha="$(sha256sum "$candidate" | awk '{print $1}')"
printf '%s\n' "$original_sha" > "$backup_dir/before.sha256"
printf '%s\n' "$candidate_sha" > "$backup_dir/after.sha256"
chmod 600 "$backup_dir"/*.sha256

replaced=false
verified=false
rollback_module() {
  if [[ "$replaced" == true && "$verified" != true ]]; then
    temp_restore="$(mktemp "$runtime/scripts/.line41-restore.XXXXXXXX")"
    install -m 600 "$backup_dir/factory_vps_product_cycle.py.before" "$temp_restore"
    mv -f -- "$temp_restore" "$installed"
    echo LINE41_MODULE_ROLLED_BACK_PRIOR_VERSION_RETAINED
  fi
}
trap rollback_module EXIT

for recipe in water_budget_economics greenhouse_crop_margin; do
  destination="$runtime/product_recipes/$recipe"
  if [[ ! -e "$destination" ]]; then
    install -d -m 700 "$destination"
    cp -R -- "$source_repo/product_recipes/$recipe/." "$destination/"
    find "$destination" -type d -exec chmod 700 {} +
    find "$destination" -type f -exec chmod 600 {} +
    echo "LINE41_PRIVATE_RECIPE_ADDED=$recipe"
  else
    echo "LINE41_EXISTING_RECIPE_PRESERVED=$recipe"
  fi
done

temp_module="$(mktemp "$runtime/scripts/.line41-module.XXXXXXXX")"
install -m 600 "$candidate" "$temp_module"
[[ "$(sha256sum "$temp_module" | awk '{print $1}')" == "$candidate_sha" ]]
mv -f -- "$temp_module" "$installed"
replaced=true
[[ "$(sha256sum "$installed" | awk '{print $1}')" == "$candidate_sha" ]]

# Release the private product lock before running the worker: run_cycle owns it.
flock -u 8
"$python" -B "$installed" --db "$db" --out "$private" \
  --recipes "$runtime/product_recipes" --max-products 1 --max-recipes 1 \
  --no-enable-designer --no-enable-design-intake --no-enable-invention-supply
"$python" -B - "$private/production-state.json" "$slots" <<'PY'
import json,sys
from pathlib import Path
state=json.loads(Path(sys.argv[1]).read_text(encoding="utf8"))
slots=json.loads(Path(sys.argv[2]).read_text(encoding="utf8"))
assert state.get("build_policy")=="line_41_single_active_product_technical_completion_then_next"
assert state.get("active_product_slot_capacity")==1
assert state.get("objective_quality_gates")=="technical_archive_tests_and_release_readiness_separate"
assert state.get("commercial_quality_review_completed") is False
assert state.get("publishable_product_count")==0
assert state.get("store_distribution_state")=="not_connected"
assert slots.get("commercial_release") is False
assert slots.get("quality_policy")=="objective_customer_acceptance_v1"
assert len(slots.get("active",[]))<=1
print("LINE41_VPS_PRIVATE_BUILD_RECEIPT=PASS")
print("LINE41_NEW_ARTIFACTS="+str(state.get("new_or_updated_product_count")))
print("LINE41_TECHNICALLY_FINISHED="+str(state.get("private_technical_completion_count")))
print("LINE41_ACTIVE_RECIPE_COUNT="+str(len(slots.get("active",[]))))
print("LINE41_WAITING_RECIPES="+str(len(slots.get("waiting",[]))))
print("LINE41_PUBLICATION_ENABLED=false")
PY
[[ "$(crontab -l | sha256sum | awk '{print $1}')" == "$cron_before" ]] || {
  echo LINE41_CRON_CHANGED_EXTERNALLY_DURING_DEPLOY; exit 13;
}
verified=true
trap - EXIT
echo LINE41_NONBLOCKING_PRODUCTION_REPAIR_DEPLOYED
echo LINE41_CRON_AND_EXISTING_CUSTOMER_SITES_UNCHANGED
