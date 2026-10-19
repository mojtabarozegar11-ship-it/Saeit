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

# Back up existing code if present; source control remains the source of truth.
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
tar -czf "$ops/backups/autonomous-product-runtime-before-$stamp.tar.gz" \
  -C "$ops" autonomous-product-runtime || true
chmod 600 "$ops/backups/autonomous-product-runtime-before-$stamp.tar.gz" 2>/dev/null || true

for f in factory_product_maker.py factory_autonomous_portfolio.py \
         factory_evidence_quality.py factory_first_product_pilot.py factory_vps_product_cycle.py \
         factory_product_rework.py; do
  install -m 600 "$repo/scripts/$f" "$scripts/$f"
done
# Every valid recipe folder is deployed automatically; new products need no installer edit.
shopt -s nullglob
recipe_sources=("$repo"/product_recipes/*)
(("${#recipe_sources[@]}" > 0)) || { echo "NO_PRODUCT_RECIPE_DIRECTORIES"; exit 1; }
for recipe_source in "${recipe_sources[@]}"; do
  [[ -d "$recipe_source" && ! -L "$recipe_source" ]] || { echo "UNSAFE_PRODUCT_RECIPE_DIRECTORY"; exit 1; }
  recipe="$(basename "$recipe_source")"
  mkdir -p "$recipes/$recipe"
  chmod 700 "$recipes/$recipe"
  while IFS= read -r -d '' file; do
    relative="${file#"$recipe_source"/}"
    mkdir -p "$recipes/$recipe/$(dirname "$relative")"
    install -m 600 "$file" "$recipes/$recipe/$relative"
  done < <(find "$recipe_source" -type f -print0)
done

# Quality gate must exist and compile BEFORE any production cycle or cron change.
"$python" -B -c 'import ast, pathlib, sys; [ast.parse(pathlib.Path(x).read_text(encoding="utf-8")) for x in sys.argv[1:]]' \
  "$scripts/factory_evidence_quality.py" "$scripts/factory_autonomous_portfolio.py" "$scripts/factory_vps_product_cycle.py" "$scripts/factory_product_rework.py"

# Product QA is mandatory BEFORE changes to the local scheduler.
# The cycle discovers the complete catalog and runs each recipe's test_*.py suite.
"$python" "$scripts/factory_vps_product_cycle.py" \
  --db "$db" --out "$private" --recipes "$recipes" \
  --max-products 25
test -s "$private/production-state.json"
test "$(find "$private/digital-products" -type f -name "*-internal-qa.zip" -print -quit | wc -l)" -ge 1

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
