#!/usr/bin/env bash
# Installs private production distribution planning on VPS; NO public site edits.
set -euo pipefail
umask 077
test "$(id -un)" = githubops
repo="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
base="$HOME/factory-runtime"
ops="$base/operations"
source_root="$base/private/autonomous-product-cycle"
private="$base/private/multisite-distribution"
stage="$ops/multisite-distribution"
python="$base/.venv/bin/python"
test -x "$python"
test -s "$source_root/production-state.json"
test -d "$ops" && test -d "$base/private"
test -f "$repo/scripts/factory_multisite_orchestrator.py"
test -f "$repo/config/factory_sites_seed.json"
command -v flock >/dev/null
command -v crontab >/dev/null
if ! systemctl is-active --quiet cron 2>/dev/null && ! systemctl is-active --quiet crond 2>/dev/null; then
  echo MULTISITE_CRON_DAEMON_MISSING
  exit 3
fi
for dir in "$stage" "$private" "$stage/bin" "$private/release-approvals" "$private/catalogs" "$ops/backups"; do
  test ! -L "$dir"
  mkdir -p -m 700 "$dir"
  chmod 700 "$dir"
done
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
if test -f "$stage/bin/factory_multisite_orchestrator.py"; then
  cp -p "$stage/bin/factory_multisite_orchestrator.py" "$ops/backups/factory-multisite-before-$stamp.py"
  chmod 600 "$ops/backups/factory-multisite-before-$stamp.py"
fi
"$python" -B -m py_compile "$repo/scripts/factory_multisite_orchestrator.py"
install -m 600 "$repo/scripts/factory_multisite_orchestrator.py" "$stage/bin/factory_multisite_orchestrator.py.new"
mv -f "$stage/bin/factory_multisite_orchestrator.py.new" "$stage/bin/factory_multisite_orchestrator.py"
if ! test -e "$private/site-registry.json"; then
  install -m 600 "$repo/config/factory_sites_seed.json" "$private/site-registry.json"
fi
test ! -L "$private/site-registry.json"
cat > "$stage/run-local-catalog.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
umask 077
exec 9>"$ops/multisite-catalog.lock"
flock -n 9 || exit 0
exec "$python" -B "$stage/bin/factory_multisite_orchestrator.py" \
  --registry "$private/site-registry.json" \
  --root "$source_root" \
  --approvals "$private/release-approvals" \
  --output "$private/catalogs"
EOF
chmod 700 "$stage/run-local-catalog.sh"
"$stage/run-local-catalog.sh"
test -s "$private/catalogs/distribution-state.json"
crontab -l > "$ops/backups/crontab-before-multisite-$stamp.txt" 2>/dev/null || :
chmod 600 "$ops/backups/crontab-before-multisite-$stamp.txt"
grep -v 'SAEIT_MULTISITE_CATALOG_V1' "$ops/backups/crontab-before-multisite-$stamp.txt" > "$stage/cron.new" || true
printf '52 * * * * /bin/bash %s >> %s/multisite-catalog.log 2>&1 # SAEIT_MULTISITE_CATALOG_V1\n' \
  "$stage/run-local-catalog.sh" "$ops" >> "$stage/cron.new"
chmod 600 "$stage/cron.new"
crontab "$stage/cron.new"
rm -f "$stage/cron.new"
test "$(crontab -l | grep -c SAEIT_MULTISITE_CATALOG_V1)" -eq 1
echo VPS_FACTORY_MULTISITE_PRIVATE_CATALOG_INSTALLED
echo VPS_FACTORY_DISTRIBUTION_SCHEDULE=HOURLY_MINUTE_52
echo VPS_FACTORY_PUBLIC_SITE_MODIFICATIONS=0
echo VPS_FACTORY_SITE_RELEASE_REQUIRES_REVIEW=true
echo VPS_FACTORY_NEW_SITE_REGISTRY_DYNAMIC=true

# Activate only the imported read-only QA logic on the factory VPS.
# No site worker, private cPanel source, external API, store, or payment is run.
for item in \
  scripts/factory_cross_site_capabilities.py \
  scripts/factory_cross_site_cycle.py \
  content/zomorod-v11/site_agents.php \
  content/zomorod-v11/site_agent_workforce.php \
  command_center/mpw_private_telemetry.py \
  ops/factory-site-capabilities/zomorod/site_agents.php \
  ops/factory-site-capabilities/zomorod/site_agent_workforce.php \
  ops/factory-site-capabilities/mojplaywin/mpw_private_telemetry.py; do
  test -s "$repo/$item" && test ! -L "$repo/$item"
done
"$python" -B "$repo/scripts/factory_cross_site_capabilities.py" --repo "$repo" >/dev/null
cross="$ops/cross-site-factory-qa"
test ! -L "$cross"
install -d -m 700 "$cross"
runner="$cross/run-hourly.sh"
test ! -L "$runner"
if test -f "$runner"; then
  cp -p "$runner" "$ops/backups/cross-site-factory-runner-before-$stamp.sh"
fi
cat > "$runner" <<'CROSS_RUN'
#!/usr/bin/env bash
set -euo pipefail
umask 077
base="$HOME/factory-runtime"
repo="$base/operations/multisite-deploy-source"
private="$base/private/autonomous-product-cycle"
ops="$base/operations"
exec 7>"$ops/cross-site-factory-qa/.cycle.lock"
flock -n 7 || exit 0
"$base/.venv/bin/python" -B "$repo/scripts/factory_cross_site_cycle.py" \
  --repo "$repo" --factory-private "$private" \
  --output "$private/cross-site-capabilities/last-report.json" \
  >> "$ops/cross-site-factory-qa/private-cycle.log" 2>&1
CROSS_RUN
chmod 700 "$runner"
bash -n "$runner"
"$runner"
"$python" -B - "$source_root/cross-site-capabilities/last-report.json" <<'PY'
import json,sys
from pathlib import Path
data=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert data["schema"]=="saeit.factory.cross-site-live-cycle.v1"
assert data["source_files_hash_verified"]==3
assert data["source_copy_integrity"] is True
assert data["roles_zomorod"]==11 and data["roles_mojplaywin_robots"]==11
assert data["quality_or_commercial_release_granted"] is False
assert data["website_files_modified"] is False
print("CROSS_SITE_FACTORY_VPS_PRIVATE_SMOKE=PASS")
print("CROSS_SITE_FACTORY_LOCAL_PREVIEWS_CHECKED="+str(data["html_previews_scanned"]))
PY
marker=SAEIT_CROSS_SITE_FACTORY_QA_V1
crontab -l > "$cross/crontab-before-$stamp" 
grep -v "$marker" "$cross/crontab-before-$stamp" > "$cross/crontab-after-$stamp" || true
printf '41 * * * * /bin/bash %s # %s\n' "$runner" "$marker" >> "$cross/crontab-after-$stamp"
chmod 600 "$cross/crontab-before-$stamp" "$cross/crontab-after-$stamp"
test "$(crontab -l | sha256sum | awk '{print $1}')" = "$(sha256sum "$cross/crontab-before-$stamp" | awk '{print $1}')"
crontab < "$cross/crontab-after-$stamp"
test "$(crontab -l | grep -c "$marker")" -eq 1
test "$(crontab -l | grep -c SAEIT_MULTISITE_CATALOG_V1)" -eq 1
echo CROSS_SITE_FACTORY_IMPORTED_QA_ACTIVATED=TRUE
echo CROSS_SITE_FACTORY_PRIVATE_HOURLY_CRON=ACTIVE
echo CROSS_SITE_FACTORY_SITE_SERVICES_UNCHANGED=TRUE
echo CROSS_SITE_FACTORY_ORIGINAL_CPANEL_MODULES_NOT_COPIED=true

# Quarantined, historical source-only capability evaluation.
# This never launches site robots, generations or privileged factory agents.
test -s "$repo/scripts/factory_legacy_77_benchmark.py"
test -s "$repo/scripts/factory_legacy_77_cycle.py"
test ! -L "$repo/ops/factory-site-capabilities/legacy-candidates"
test ! -L "$repo/ops/factory-site-capabilities/legacy-candidates/mpw_v91_port/ORIGIN.json"
"$python" -B "$repo/scripts/factory_legacy_77_benchmark.py" --syntax-only > /dev/null
legacy="$ops/factory-heritage-77"
test ! -L "$legacy"
install -d -m 700 "$legacy"
legacyrunner="$legacy/run-hourly.sh"
test ! -L "$legacyrunner"
if test -f "$legacyrunner"; then
  cp -p "$legacyrunner" "$ops/backups/legacy77-runner-before-$stamp.sh"
fi
cat > "$legacyrunner" <<'HERITAGE_RUN'
#!/usr/bin/env bash
set -euo pipefail
umask 077
base="$HOME/factory-runtime"
ops="$base/operations"
exec 7>"$ops/factory-heritage-77/.cycle.lock"
flock -n 7 || exit 0
"$base/.venv/bin/python" -B "$ops/multisite-deploy-source/scripts/factory_legacy_77_cycle.py" \
  --repo "$ops/multisite-deploy-source" \
  --output "$base/private/autonomous-product-cycle/cross-site-capabilities/legacy-77-last-report.json" \
  >> "$ops/factory-heritage-77/last-cycle.log" 2>&1
HERITAGE_RUN
chmod 700 "$legacyrunner"
bash -n "$legacyrunner"
"$legacyrunner"
"$python" -B - "$source_root/cross-site-capabilities/legacy-77-last-report.json" <<'PY'
import json,sys
from pathlib import Path
d=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert d["schema"]=="saeit.factory.heritage-evaluation-cycle.v1"
assert d["real_read_only_imports"]==77
assert d["real_pure_function_probes"]>=14
assert d["robot_source_roles_verified"]==11
assert d["separate_agents_executed"]==0
assert d["customer_product_published"] is False
assert d["factory_prod_agents_replaced"] is False
print("FACTORY_77_HISTORICAL_MODULES_REAL_VPS_SAFE_IMPORT=77")
print("FACTORY_77_HISTORICAL_MODULE_FUNCTIONAL_PROBES="+str(d["real_pure_function_probes"]))
print("FACTORY_11_ROBOT_SOURCE_ROLE_REGISTRY=VERIFIED")
PY
marker=SAEIT_FACTORY_HERITAGE_77_V1
crontab -l > "$legacy/crontab-before-$stamp"
grep -v "$marker" "$legacy/crontab-before-$stamp" > "$legacy/crontab-after-$stamp" || true
printf '46 * * * * /bin/bash %s # %s\n' "$legacyrunner" "$marker" >> "$legacy/crontab-after-$stamp"
chmod 600 "$legacy/crontab-before-$stamp" "$legacy/crontab-after-$stamp"
test "$(crontab -l | sha256sum | awk '{print $1}')" = "$(sha256sum "$legacy/crontab-before-$stamp" | awk '{print $1}')"
crontab < "$legacy/crontab-after-$stamp"
test "$(crontab -l | grep -c "$marker")" -eq 1
test "$(crontab -l | grep -c SAEIT_MULTISITE_CATALOG_V1)" -eq 1
test "$(crontab -l | grep -c SAEIT_CROSS_SITE_FACTORY_QA_V1)" -eq 1
echo FACTORY_77_HISTORICAL_MODULES_HOURLY_EVALUATION=ACTIVE
echo FACTORY_77_SITE_ROBOT_PRODUCTION_ACTIVATION=false
echo FACTORY_77_EXTERNAL_SITE_CONTENT_MODIFIED=false
