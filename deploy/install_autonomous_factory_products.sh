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
test -d "$ops"
test -d "$base/private"
test -f "$repo/scripts/factory_product_maker.py"
test -f "$repo/scripts/factory_autonomous_portfolio.py"
test -f "$repo/scripts/factory_evidence_quality.py"
test -f "$repo/scripts/factory_first_product_pilot.py"
test -f "$repo/scripts/factory_vps_product_cycle.py"
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

mkdir -p "$ops/backups" "$scripts" "$recipes" "$private"
chmod 700 "$stage" "$scripts" "$recipes" "$private"
# Serialize catalog replacement against the scheduled VPS cycle.
exec 9>"$ops/autonomous-product-cycle.lock"
flock 9

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
tar -czf "$ops/backups/autonomous-product-runtime-before-$stamp.tar.gz" \
  -C "$ops" autonomous-product-runtime
tar -tzf "$ops/backups/autonomous-product-runtime-before-$stamp.tar.gz" >/dev/null
chmod 600 "$ops/backups/autonomous-product-runtime-before-$stamp.tar.gz"

for f in factory_product_maker.py factory_autonomous_portfolio.py \
         factory_evidence_quality.py factory_first_product_pilot.py factory_vps_product_cycle.py \
         factory_product_rework.py; do
  install -m 600 "$repo/scripts/$f" "$scripts/$f"
done
# Stage an exact source catalog. QA runs before the live catalog is changed.
shopt -s nullglob
recipe_sources=("$repo"/product_recipes/*)
(("${#recipe_sources[@]}" > 0)) || { echo "NO_PRODUCT_RECIPE_DIRECTORIES"; exit 1; }
catalog_stage="$ops/.product-recipes-stage-$stamp"
old_catalog="$ops/.product-recipes-old-$stamp"
desired_catalog="$ops/.product-recipes-desired-$stamp.txt"
retired="$private/retired-recipes"
cleanup_staging() {
  if [[ -n "${catalog_stage:-}" && "$catalog_stage" == "$ops"/.product-recipes-stage-* && -d "$catalog_stage" ]]; then
    rm -rf -- "$catalog_stage"
  fi
  if [[ -n "${desired_catalog:-}" && "$desired_catalog" == "$ops"/.product-recipes-desired-* && -f "$desired_catalog" ]]; then
    rm -f -- "$desired_catalog"
  fi
}
trap cleanup_staging EXIT
mkdir -m 700 "$catalog_stage"
: > "$desired_catalog"
chmod 600 "$desired_catalog"
for recipe_source in "${recipe_sources[@]}"; do
  [[ -d "$recipe_source" && ! -L "$recipe_source" ]] || { echo "UNSAFE_PRODUCT_RECIPE_DIRECTORY"; exit 1; }
  recipe="$(basename "$recipe_source")"
  [[ "$recipe" =~ ^[a-z0-9]+(_[a-z0-9]+)*$ ]] || { echo "INVALID_PRODUCT_RECIPE_SLUG"; exit 1; }
  if find "$recipe_source" -type l -print -quit | grep -q .; then
    echo "UNSAFE_PRODUCT_RECIPE_SYMLINK"; exit 1
  fi
  printf '%s\\n' "$recipe" >> "$desired_catalog"
  mkdir -m 700 "$catalog_stage/$recipe"
  while IFS= read -r -d '' file; do
    relative="${file#"$recipe_source"/}"
    mkdir -p "$catalog_stage/$recipe/$(dirname "$relative")"
    install -m 600 "$file" "$catalog_stage/$recipe/$relative"
  done < <(find "$recipe_source" -type f -print0)
done
"$python" "$repo/scripts/factory_product_maker.py" \
  --recipes "$catalog_stage" --verify-only

# Swap only the dedicated recipe catalog. The prior VPS runtime has a verified backup.
if [[ -e "$recipes" ]]; then
  [[ -d "$recipes" && ! -L "$recipes" ]] || { echo "UNSAFE_ACTIVE_RECIPE_CATALOG"; exit 1; }
  mv -- "$recipes" "$old_catalog"
fi
mv -- "$catalog_stage" "$recipes"

# Quality gate must exist and compile BEFORE any production cycle or cron change.
"$python" -B -c 'import ast, pathlib, sys; [ast.parse(pathlib.Path(x).read_text(encoding="utf-8")) for x in sys.argv[1:]]' \
  "$scripts/factory_evidence_quality.py" "$scripts/factory_autonomous_portfolio.py" "$scripts/factory_vps_product_cycle.py" "$scripts/factory_product_rework.py"

# Build the staged catalog before changing the scheduler. Restore the previous active
# catalog if the production cycle cannot complete; the failed source stays in backups.
if ! "$python" "$scripts/factory_vps_product_cycle.py" \
  --db "$db" --out "$private" --recipes "$recipes" --max-products 25; then
  failed_catalog="$ops/backups/failed-product-recipes-$stamp"
  mv -- "$recipes" "$failed_catalog"
  if [[ -d "$old_catalog" ]]; then mv -- "$old_catalog" "$recipes"; fi
  exit 1
fi
test -s "$private/production-state.json"
test "$(find "$private/digital-products" -type f -name "*-internal-qa.zip" -print -quit | wc -l)" -ge 1

# Retire removed recipe directories out of the active catalog; keep a private archive
# of only recipes absent from the source. Existing packages and QA history stay intact.
mkdir -p "$retired"
chmod 700 "$retired"
if [[ -d "$old_catalog" ]]; then
  for old_recipe in "$old_catalog"/*; do
    [[ -e "$old_recipe" ]] || continue
    old_name="$(basename "$old_recipe")"
    [[ "$old_name" =~ ^[a-z0-9]+(_[a-z0-9]+)*$ ]] || { echo "INVALID_OLD_RECIPE_SLUG"; exit 1; }
    [[ -d "$old_recipe" && ! -L "$old_recipe" ]] || { echo "UNSAFE_OLD_RECIPE_PATH"; exit 1; }
    if ! grep -Fxq "$old_name" "$desired_catalog"; then
      mv -- "$old_recipe" "$retired/$old_name-$stamp"
      echo "RETIRED_RECIPE=$old_name"
    fi
  done
  [[ "$old_catalog" == "$ops"/.product-recipes-old-* ]] || { echo "UNSAFE_OLD_CATALOG_PATH"; exit 1; }
  rm -rf -- "$old_catalog"
fi
install -m 600 "$desired_catalog" "$stage/installed-recipes.txt"
rm -f -- "$desired_catalog"

cat > "$stage/run-local-cycle.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
umask 077
exec 9>"$ops/autonomous-product-cycle.lock"
flock -n 9 || exit 0
exec >> "$ops/autonomous-product-cycle.log" 2>&1
exec "$python" "$scripts/factory_vps_product_cycle.py" \\
  --db "$db" --out "$private" --recipes "$recipes" \\
  --max-products 25
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
