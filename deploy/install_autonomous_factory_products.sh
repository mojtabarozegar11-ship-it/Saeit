#!/usr/bin/env bash
# Install offline order-independent Saeit product manufacturing on its VPS.
# Run from an authorized Saeit checkout by the VPS service user.
# No changes to cPanel, storefronts, payment systems, or main factory loop.
set -euo pipefail
umask 077

repo="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
base="$HOME/factory-runtime"
ops="$base/operations"
db="$base/private/factory-fresh-isolated.sqlite3"
python="$base/.venv/bin/python"
stage="$ops/autonomous-product-runtime"
scripts="$stage/scripts"
recipes="$stage/product_recipes"
private="$base/private/autonomous-product-cycle"

test "$(id -u)" -ne 0 || { echo "RUN_AS_SERVICE_USER_NOT_ROOT"; exit 1; }
test -f "$db"
test -x "$python"
# Match the toolchain proven by CI. Never install extra dependencies from
# inside the cron worker; deployment must provision these before cutover.
if ! "$python" -c 'import openpyxl; assert openpyxl.__version__ == "3.1.5"' >/dev/null 2>&1; then
  echo "FACTORY_F27_OPENPYXL_3_1_5_REQUIRED"; exit 1
fi
test -d "$ops"
test -d "$base/private"
# Fail closed before modifying the live runtime: a malicious or stale symlink
# must never redirect backups, manufacturing, or private buyer artifacts.
for protected_path in "$base/private" "$ops" "$ops/backups" "$stage" "$scripts" "$recipes" "$private"; do
  if [[ -L "$protected_path" ]]; then
    echo "FACTORY_PRODUCT_RUNTIME_PATH_UNSAFE"; exit 1
  fi
done
# Keep room for the compressed rollback archive plus further minute cycles.
# A full disk would otherwise strand manufacturing in a partially restored state.
free_kib="$(df -Pk "$base/private" | awk 'NR==2 {print $4}')"
if [[ ! "$free_kib" =~ ^[0-9]+$ ]] || (( free_kib < 3145728 )); then
  echo "FACTORY_PRODUCT_DEPLOY_DISK_RESERVE_HOLD"; exit 1
fi
test -f "$repo/scripts/factory_product_maker.py"
# The maker imports this mandatory, private, fail-closed personal-owner policy.
# Missing this file previously caused manufacturing/import failures after cutover.
test -f "$repo/scripts/factory_personal_owner_passport_policy_20261020.py"
test ! -L "$repo/scripts/factory_personal_owner_passport_policy_20261020.py"
test -f "$repo/scripts/factory_recipe_designer.py"
test -f "$repo/scripts/factory_specialist_pilots.py"
test -f "$repo/scripts/factory_specialist_formats.py"
test -f "$repo/scripts/factory_research_triage.py"
test -f "$repo/factory_config/design_opportunities.json"
test -f "$repo/factory_config/internal_design_supply.json"
test -f "$repo/scripts/factory_design_intake.py"
test -f "$repo/scripts/factory_customer_packager.py"
test -f "$repo/scripts/factory_continuous_invention.py"
test -f "$repo/scripts/factory_autonomous_portfolio.py"
test -f "$repo/scripts/factory_evidence_quality.py"
test -f "$repo/scripts/factory_first_product_pilot.py"
test -f "$repo/scripts/factory_vps_product_cycle.py"
# The live cycle imports genetics unconditionally; stage the exact reviewed module.
test -f "$repo/scripts/factory_master_agent_genetics_v1.py"
test ! -L "$repo/scripts/factory_master_agent_genetics_v1.py"
# The live cycle imports customer-extracted QA unconditionally. Abort cutover
# unless the exact module to execute is present in this checkout.
test -f "$repo/scripts/factory_verified_customer_cycle_20261021.py"
test ! -L "$repo/scripts/factory_verified_customer_cycle_20261021.py"
test -f "$repo/scripts/factory_product_rework.py"
test -d "$repo/product_recipes"
command -v flock >/dev/null
command -v crontab >/dev/null
if ! systemctl is-active --quiet cron 2>/dev/null &&
   ! systemctl is-active --quiet crond 2>/dev/null; then
  echo "CRON_DAEMON_NOT_ACTIVE"; exit 1
fi
if ! systemctl is-enabled --quiet cron 2>/dev/null &&
   ! systemctl is-enabled --quiet crond 2>/dev/null; then
  echo "CRON_NOT_BOOT_ENABLED"; exit 1
fi

mkdir -p "$ops/backups"
# Exclude the scheduled runner while replacing code and recipe inventory.
exec 8>"$ops/autonomous-product-cycle.lock"
flock -w 120 8 || { echo "INSTALL_LOCK_TIMEOUT"; exit 1; }
# A failed backup stops installation before replacing runtime files.
stamp="$(date -u +%Y%m%dT%H%M%SZ)-$$"
if [[ -d "$stage" ]]; then
  backup="$ops/backups/autonomous-product-runtime-before-$stamp.tar.gz"
  tar -czf "$backup" -C "$ops" autonomous-product-runtime
  tar -tzf "$backup" >/dev/null
  chmod 600 "$backup"
fi
rollback_runtime() {
  rc="$?"
  if [[ "$rc" -ne 0 && -n "${backup:-}" && -s "$backup" ]]; then
    # Quarantine the failed deployment and restore the verified runtime archive.
    mv "$stage" "$ops/backups/failed-runtime-$stamp"
    tar -xzf "$backup" -C "$ops"
    echo "FACTORY_RUNTIME_ROLLED_BACK"
  fi
  exit "$rc"
}
trap rollback_runtime EXIT
mkdir -p "$scripts" "$recipes" "$private"
chmod 700 "$stage" "$scripts" "$recipes" "$private"


for f in factory_product_maker.py factory_personal_owner_passport_policy_20261020.py factory_autonomous_portfolio.py \
         factory_evidence_quality.py factory_first_product_pilot.py factory_vps_product_cycle.py factory_master_agent_genetics_v1.py \
         factory_verified_customer_cycle_20261021.py \
         factory_product_rework.py factory_recipe_designer.py factory_specialist_pilots.py factory_specialist_formats.py factory_research_triage.py factory_build_50.py factory_build50_workbook.py factory_design_intake.py factory_continuous_invention.py factory_customer_packager.py; do
  install -m 600 "$repo/scripts/$f" "$scripts/$f"
done
install -d -m 700 "$stage/factory_config"
install -m 600 "$repo/factory_config/design_opportunities.json" "$stage/factory_config/design_opportunities.json"
install -m 600 "$repo/factory_config/internal_design_supply.json" "$stage/factory_config/internal_design_supply.json"
# Build a complete replacement inventory. Preserve retired recipes privately;
# never remove artifacts, defect ledgers, or locally retained previous sources.
incoming="$(mktemp -d "$stage/.recipes-incoming.XXXXXX")"
"$python" -B -c 'import runpy,sys; m=runpy.run_path(sys.argv[1]); m["discover_recipes"](sys.argv[2])' \
  "$scripts/factory_product_maker.py" "$repo/product_recipes"
# Reject symlinks even when they point to files outside the checkout.
if [[ -n "$(find "$repo/product_recipes" -type l -print -quit)" ]]; then
  echo "UNSAFE_PRODUCT_RECIPE_SYMLINK"; exit 1
fi
cp -R "$repo/product_recipes/." "$incoming/"
find "$incoming" -type d -exec chmod 700 {} +
find "$incoming" -type f -exec chmod 600 {} +
retired="$ops/backups/product-recipes-before-$stamp"
mv "$recipes" "$retired"
if ! mv "$incoming" "$recipes"; then
  mv "$retired" "$recipes"
  echo "RECIPE_ACTIVATION_FAILED"; exit 1
fi
incoming=""

# Verify the exact reviewed flagship calculator reached the active inventory.
# This is a source-integrity assertion, not an independent quality certificate.
if ! cmp -s "$repo/product_recipes/farm_enterprise_economics/calculator.py" \
            "$recipes/farm_enterprise_economics/calculator.py"; then
  echo "FACTORY_FLAGSHIP_SOURCE_ACTIVATION_MISMATCH"; exit 1
fi
echo "FACTORY_FLAGSHIP_SOURCE_INSTALLED_BYTE_FOR_BYTE=PASS"

# Quality gate must exist and compile BEFORE any production cycle or cron change.
"$python" -B -c 'import ast, pathlib, sys; [ast.parse(pathlib.Path(x).read_text(encoding="utf-8")) for x in sys.argv[1:]]' \
  "$scripts/factory_personal_owner_passport_policy_20261020.py" "$scripts/factory_master_agent_genetics_v1.py" "$scripts/factory_recipe_designer.py" "$scripts/factory_evidence_quality.py" "$scripts/factory_autonomous_portfolio.py" "$scripts/factory_vps_product_cycle.py" "$scripts/factory_verified_customer_cycle_20261021.py" "$scripts/factory_product_rework.py" "$scripts/factory_specialist_pilots.py" "$scripts/factory_specialist_formats.py" "$scripts/factory_research_triage.py" "$scripts/factory_continuous_invention.py" "$scripts/factory_customer_packager.py"

# Product QA is mandatory BEFORE changes to the local scheduler.
# The cycle discovers the complete catalog and runs each recipe's test_*.py suite.
"$python" "$scripts/factory_vps_product_cycle.py" \
  --db "$db" --out "$private" --recipes "$recipes" \
  --max-products 25 --enable-designer --enable-design-intake --enable-invention-supply
test -s "$private/production-state.json"
test "$(find "$private/digital-products" -type f -name "*-internal-qa.zip" -print -quit | wc -l)" -ge 1
# Finish the buyer-use package only after real source and holdout QA.
"$python" -B "$scripts/factory_customer_packager.py" --factory-private "$private" --max-new 2
test -s "$private/customer-packs/status.json"

cat > "$stage/run-local-cycle.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
umask 077
exec 9>"$ops/autonomous-product-cycle.lock"
flock -n 9 || exit 0
exec >> "$ops/autonomous-product-cycle.log" 2>&1
"$python" "$scripts/factory_vps_product_cycle.py" \\
  --db "$db" --out "$private" --recipes "$recipes" \\
  --max-products 25 --enable-designer --enable-design-intake --enable-invention-supply
# A malformed product enters a durable editorial/rework report; other
# independently tested products remain eligible next minute.
if ! "$python" -B "$scripts/factory_customer_packager.py" \\
  --factory-private "$private" --max-new 2; then
  echo FACTORY_CUSTOMER_PACKAGE_NEEDS_REWORK
fi
# A broken specialist cannot stop core product manufacturing. Its private
# rework receipt persists for the following minute; publication stays locked.
if ! "$python" "$scripts/factory_specialist_pilots.py" \\
  --out "$private" --manifest "$ops/build-toolchain/toolchain-manifest.json"; then
  echo FACTORY_SPECIALIST_PILOT_NEEDS_REWORK
fi
if ! "$python" "$scripts/factory_build50_workbook.py" --factory-private "$private" --toolchain "$ops/build-toolchain/toolchain-manifest.json"; then
  echo FACTORY_BUILD50_WORKBOOK_NEEDS_REWORK
fi
"$python" "$scripts/factory_build_50.py" --factory-private "$private"
if ! "$python" "$scripts/factory_research_triage.py" --out "$private"; then
  echo FACTORY_RESEARCH_TRIAGE_NEEDS_REWORK
fi
EOF
chmod 700 "$stage/run-local-cycle.sh"

# Do not regress an already-installed every-minute synchronized warehouse loop.
if crontab -l 2>/dev/null | grep -q SAEIT_FACTORY_EVERY_MINUTE_V1; then
  test "$(crontab -l | grep -c SAEIT_AUTONOMOUS_PRODUCTS_V2)" -eq 1
  test "$(crontab -l | grep -c SAEIT_PRODUCTION_WAREHOUSE_V1)" -eq 1
  echo AUTONOMOUS_SCHEDULE=VPS_LOCAL_EVERY_MINUTE_PRESERVED
  echo PUBLISHING_ENABLED=false
  exit 0
fi

# All unrelated cron entries are preserved.
crontab -l > "$ops/backups/crontab-before-autonomous-product-$stamp.txt" 2>/dev/null ||
  : > "$ops/backups/crontab-before-autonomous-product-$stamp.txt"
chmod 600 "$ops/backups/crontab-before-autonomous-product-$stamp.txt"
grep -v -e 'SAEIT_FIRST_PRODUCT_PILOT' -e 'SAEIT_AUTONOMOUS_PORTFOLIO' \
  -e 'SAEIT_AUTONOMOUS_PRODUCTS_V2' \
  "$ops/backups/crontab-before-autonomous-product-$stamp.txt" \
  > "$ops/autonomous-product-crontab.tmp" || true
printf '23 * * * * /bin/bash %s # SAEIT_AUTONOMOUS_PRODUCTS_V2\n' \
  "$stage/run-local-cycle.sh" >> "$ops/autonomous-product-crontab.tmp"
chmod 600 "$ops/autonomous-product-crontab.tmp"
crontab "$ops/autonomous-product-crontab.tmp"
rm -f "$ops/autonomous-product-crontab.tmp"
test "$(crontab -l | grep -c SAEIT_AUTONOMOUS_PRODUCTS_V2)" -eq 1
echo "SAEIT_VPS_PRODUCT_MANUFACTURING_INSTALLED"
echo "AUTONOMOUS_SCHEDULE=VPS_LOCAL_HOURLY"
echo "ORDER_REQUIRED=false"
echo "PUBLISHING_ENABLED=false"
echo "EXISTING_FACTORY_LOOP_UNMODIFIED=true"
