#!/usr/bin/env bash
# One-time activation of the exact reviewed farm toolkit in the native VPS factory.
# Scope: one private recipe and its private manufactured ZIP. Never publish or bill.
set -Eeuo pipefail
umask 077

stage="${1:?staged recipe directory required}"
expected_zip="${2:?expected private ZIP sha256 required}"
base="$HOME/factory-runtime"
ops="$base/operations"
runtime="$ops/single-product-runtime"
private="$base/private/autonomous-product-cycle"
recipes="$runtime/product_recipes"
recipe="farm_enterprise_economics"
installed="$recipes/$recipe"
private_product="$private/digital-products/$recipe"
maker="$runtime/scripts/factory_product_maker.py"
python="$base/.venv/bin/python"
slots="$private/quality-excellence/product-flow/active-slots/current.json"

[[ "$(id -un)" == githubops && "$(id -u)" -ne 0 ]] || { echo FARM_V2_WRONG_SERVICE_USER; exit 21; }
[[ "$expected_zip" =~ ^[a-f0-9]{64}$ ]] || { echo FARM_V2_EXPECTED_HASH_INVALID; exit 22; }
[[ "$stage" == "$ops"/.farm-v2-run-* && "${stage##*/}" =~ ^\.farm-v2-run-[0-9]+-[0-9]+$ ]] || {
  echo FARM_V2_STAGE_NAME_INVALID; exit 23;
}
for directory in "$base" "$ops" "$ops/backups" "$runtime" "$runtime/scripts" "$recipes" \
                 "$private" "$private/digital-products" "$stage" "$stage/recipes" "$stage/recipes/$recipe" "$installed" "$private_product"; do
  [[ -d "$directory" && ! -L "$directory" ]] || { echo FARM_V2_DIRECTORY_MISSING_OR_UNSAFE; exit 24; }
done
for file in "$maker" "$runtime/scripts/factory_personal_owner_passport_policy_20261020.py" \
            "$stage/recipes/$recipe/README.md" "$stage/recipes/$recipe/calculator.py" \
            "$stage/recipes/$recipe/offline_calculator.html" "$stage/recipes/$recipe/offline_engine.js" \
            "$stage/recipes/$recipe/offline_ui.js" "$installed/README.md" \
            "$private_product/manufacturing_manifest.json" "$slots"; do
  [[ -f "$file" && ! -L "$file" ]] || { echo FARM_V2_REQUIRED_FILE_MISSING_OR_UNSAFE; exit 25; }
done
[[ -z "$(find "$stage/recipes/$recipe" -type l -print -quit)" ]] || { echo FARM_V2_SYMLINK_SOURCE_REJECTED; exit 26; }
[[ -z "$(find "$installed" -type l -print -quit)" ]] || { echo FARM_V2_SYMLINK_INSTALLED_REJECTED; exit 26; }
[[ -z "$(find "$private_product" -type l -print -quit)" ]] || { echo FARM_V2_SYMLINK_PRIVATE_PRODUCT_REJECTED; exit 26; }
[[ -x "$python" && -x "$runtime/run-single-product-cycle.sh" ]] || { echo FARM_V2_NATIVE_RUNNER_MISSING; exit 27; }
grep -Fq -- '--no-enable-designer' "$runtime/run-single-product-cycle.sh" || exit 27
[[ "$(crontab -l | grep -c 'SAEIT_SINGLE_PRODUCT_FACTORY_V1' || true)" == 1 ]] || {
  echo FARM_V2_SINGLE_PRODUCT_CRON_NOT_PROVEN; exit 28;
}
free_kib="$(df -Pk "$private" | awk 'NR==2 {print $4}')"
[[ "$free_kib" =~ ^[0-9]+$ ]] && (( free_kib >= 552960 )) || {
  echo FARM_V2_LOW_STORAGE_RESERVE_HOLD; exit 29;
}

# Independent work before acquiring the two locks or changing live product bytes.
"$python" -B - "$slots" <<'PY'
import json,sys
from pathlib import Path
s=json.loads(Path(sys.argv[1]).read_text(encoding="utf8"))
assert s.get('schema')=='saeit.factory.product-slots.v1'
assert len(s.get('active',[])) <= 1
assert s.get('commercial_release') is False
assert s.get('quality_policy')=='objective_customer_acceptance_v1'
print('FARM_V2_SINGLE_ACTIVE_PRODUCT_POLICY=PASS')
PY
"$python" -B "$maker" --recipes "$stage/recipes" --out "$stage/preflight-private" --recipe "$recipe"
candidate="$stage/preflight-private/$recipe/$recipe-internal-qa.zip"
[[ -f "$candidate" && ! -L "$candidate" ]] || exit 30
[[ "$(sha256sum "$candidate" | awk '{print $1}')" == "$expected_zip" ]] || {
  echo FARM_V2_STAGED_PACKAGE_SHA_MISMATCH; exit 31;
}

cron_before="$(crontab -l | sha256sum | awk '{print $1}')"
exec 9>"$private/.single-product-cycle.lock"
flock -w 100 9 || { echo FARM_V2_SINGLE_PRODUCT_LOCK_TIMEOUT; exit 32; }
exec 8>"$private/.production-cycle.lock"
flock -w 30 8 || { echo FARM_V2_MANUFACTURER_LOCK_TIMEOUT; exit 33; }

stamp="$(date -u +%Y%m%dT%H%M%SZ)-$$"
backup="$ops/backups/farm-economics-v2-$stamp"
install -d -m 700 "$backup"
cp -a -- "$installed" "$backup/source-before"
cp -a -- "$private_product" "$backup/product-before"
new="$recipes/.farm-economics-v2-$stamp"
install -d -m 700 "$new"
cp -a -- "$stage/recipes/$recipe/." "$new/"
find "$new" -type d -exec chmod 700 {} +
find "$new" -type f -exec chmod 600 {} +

changed=false
accepted=false
restore_on_error() {
  code=$?
  if [[ "$changed" == true && "$accepted" != true ]]; then
    if [[ -d "$installed" && ! -L "$installed" ]]; then
      mv -- "$installed" "$backup/rejected-source"
    fi
    cp -a -- "$backup/source-before" "$installed"
    if [[ -d "$private_product" && ! -L "$private_product" ]]; then
      mv -- "$private_product" "$backup/rejected-product"
    fi
    cp -a -- "$backup/product-before" "$private_product"
    echo FARM_V2_ROLLBACK_RESTORED_PREVIOUS_PRODUCT
  fi
  exit "$code"
}
trap restore_on_error EXIT

changed=true
mv -- "$installed" "$backup/old-live-source"
mv -- "$new" "$installed"
"$python" -B "$maker" --recipes "$recipes" --out "$private/digital-products" --recipe "$recipe"
archive="$private_product/$recipe-internal-qa.zip"
[[ -f "$archive" && ! -L "$archive" ]] || exit 34
[[ "$(sha256sum "$archive" | awk '{print $1}')" == "$expected_zip" ]] || {
  echo FARM_V2_NATIVE_PACKAGE_SHA_MISMATCH; exit 35;
}
"$python" -B - "$private_product/manufacturing_manifest.json" "$private_product/professional_quality_release_stop.json" <<'PY'
import json,sys
from pathlib import Path
manifest=json.loads(Path(sys.argv[1]).read_text(encoding='utf8'))
gate=json.loads(Path(sys.argv[2]).read_text(encoding='utf8'))
assert manifest.get('qa_status')=='passed'
assert manifest.get('commercial_status')=='private_internal_qa_pass_not_published'
assert manifest.get('public_listing_enabled') is False
assert manifest.get('owner_publication_approval') is False
assert gate.get('commercial_release_permitted_from_manufacturing') is False
assert 'offline_ui.js' in manifest.get('files',[])
print('FARM_V2_PRIVATE_RELEASE_GATE=LOCKED')
PY
[[ "$(crontab -l | sha256sum | awk '{print $1}')" == "$cron_before" ]] || {
  echo FARM_V2_CRON_CHANGED_EXTERNALLY; exit 36;
}
accepted=true
trap - EXIT
echo FARM_V2_NATIVE_PRIVATE_ACTIVATION=PASS
echo FARM_V2_PRIVATE_ZIP_SHA256="$expected_zip"
echo FARM_V2_BACKUP_DIR="$backup"
echo FARM_V2_PUBLICATION_ENABLED=false
echo FARM_V2_CUSTOMER_SITE_AND_PAYMENTS_UNTOUCHED=true
