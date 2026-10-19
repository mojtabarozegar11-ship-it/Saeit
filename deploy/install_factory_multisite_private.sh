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
