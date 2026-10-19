#!/usr/bin/env bash
# Extend the real factory with strict 50-stage evidence coverage across 40 families.
# Never silently approve products, change stock or call an external website.
set -euo pipefail
umask 077
test "$(id -un)" = githubops
test "$(id -u)" -ne 0
test "$#" -eq 1
source_dir="$1"
test -d "$source_dir" && test ! -L "$source_dir"
base="$HOME/factory-runtime"
ops="$base/operations"
private="$base/private/autonomous-product-cycle"
dest="$ops/fifty-family-bridge"
registry="$ops/forty-family-master/forty_families.json"
py="$base/.venv/bin/python"
marker=SAEIT_FACTORY_BUILD50_FORTY_FAMILY_BRIDGE_V1
test -x "$py" && test -d "$private" && test ! -L "$private"
test -s "$registry" && test ! -L "$registry"
test -s "$private/production-warehouse/stock-register.json"
test "$(crontab -l | grep -c SAEIT_FACTORY_EVERY_MINUTE_V1)" -eq 1
test "$(crontab -l | grep -c SAEIT_FACTORY_LIFECYCLE_12_V1)" -eq 1
test "$(crontab -l | grep -c SAEIT_FACTORY_FORTY_FAMILY_MASTER_V1)" -eq 1
test ! -L "$dest"
command -v flock >/dev/null
install -d -m 700 "$dest" "$ops/backups"
exec 8>"$ops/.fifty-bridge-install.lock"
flock -w 20 8 || { echo BUILD50_INSTALL_BUSY; exit 1; }
stamp="$(date -u +%Y%m%dT%H%M%S)-$$"
backup="$ops/backups/fifty-bridge-$stamp"
install -d -m 700 "$backup"
crontab -l > "$backup/previous.cron"
chmod 600 "$backup/previous.cron"
for name in factory_build50_family_bridge.py factory_build_50.py factory_40_family_master.py; do
  test -s "$source_dir/$name" && test ! -L "$source_dir/$name"
  if test -f "$dest/$name"; then
    test ! -L "$dest/$name"
    cp -p "$dest/$name" "$backup/$name.old"
  fi
done
if test -f "$dest/run-five-minute-bridge.sh"; then
  test ! -L "$dest/run-five-minute-bridge.sh"
  cp -p "$dest/run-five-minute-bridge.sh" "$backup/run-five-minute-bridge.sh.old"
fi
count="$(grep -c "$marker" "$backup/previous.cron" || true)"
test "$count" -le 1
for name in factory_build50_family_bridge.py factory_build_50.py factory_40_family_master.py; do
  temp="$(mktemp "$dest/.new-$name.XXXXXXXX")"
  install -m 600 "$source_dir/$name" "$temp"
  mv -f "$temp" "$dest/$name"
  chmod 600 "$dest/$name"
done
"$py" -B -m py_compile "$dest/factory_build50_family_bridge.py" "$dest/factory_build_50.py" "$dest/factory_40_family_master.py"
ledger="$private/production-family-management/build50-family-dashboard.json"
"$py" -B "$dest/factory_build50_family_bridge.py" --factory-private "$private" --registry "$registry" --output "$ledger"
"$py" -B - "$ledger" <<'PY'
import json,sys
d=json.load(open(sys.argv[1],encoding='utf8'))
assert d['schema']=='saeit.factory.build50-family-bridge.v1'
assert d['counts']['registered_families']==40 and len(d['families'])==40
assert all(x['required_stages']==50 and x['worker_packages_required']==48 for x in d['families'])
assert not d['commercial_release_allowed'] and not d['sites_contacted']
assert d['payment_or_orders_created'] is False
print('BUILD50_FORTY_FAMILY_FIRST_LEDGER='+json.dumps(d['counts'],sort_keys=True))
PY
cat > "$dest/run-five-minute-bridge.sh" <<SH
#!/usr/bin/env bash
set -euo pipefail
umask 077
exec 9>"$ops/.fifty-family-bridge-run.lock"
/usr/bin/flock -n 9 || exit 0
exec >> "$ops/fifty-family-bridge.log" 2>&1
exec "$py" -B "$dest/factory_build50_family_bridge.py" --factory-private "$private" --registry "$registry" --output "$ledger"
SH
chmod 700 "$dest/run-five-minute-bridge.sh"
bash -n "$dest/run-five-minute-bridge.sh"
"$dest/run-five-minute-bridge.sh"
if test "$count" -eq 0; then
  cp "$backup/previous.cron" "$backup/proposed.cron"
  printf '*/5 * * * * /bin/bash %s # %s\n' "$dest/run-five-minute-bridge.sh" "$marker" >> "$backup/proposed.cron"
  test "$(crontab -l | sha256sum | awk '{print $1}')" = "$(sha256sum "$backup/previous.cron" | awk '{print $1}')"
  crontab - < "$backup/proposed.cron"
else
  grep -Fq "$dest/run-five-minute-bridge.sh" "$backup/previous.cron"
fi
test "$(crontab -l | grep -c "$marker")" -eq 1
test "$(crontab -l | grep -c SAEIT_FACTORY_EVERY_MINUTE_V1)" -eq 1
test "$(crontab -l | grep -c SAEIT_FACTORY_LIFECYCLE_12_V1)" -eq 1
test "$(crontab -l | grep -c SAEIT_FACTORY_FORTY_FAMILY_MASTER_V1)" -eq 1
echo FACTORY_BUILD50_FORTY_BRIDGE_LIVE=PASS
echo FACTORY_BUILD50_FORTY_CRON_EVERY_FIVE_MINUTES=1
echo FACTORY_BUILD50_FORTY_OLD_PRODUCTION_UNCHANGED=true
echo FACTORY_BUILD50_FORTY_COMMERCIAL_AUTO_APPROVAL=false
echo FACTORY_BUILD50_FORTY_BACKUP="$backup"
