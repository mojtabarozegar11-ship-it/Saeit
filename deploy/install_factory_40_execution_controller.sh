#!/usr/bin/env bash
# Safe complete 40-family queue installer on an already verified factory VPS.
# Runs one bounded specialist pilot per tick where a proven toolchain exists.
# Does NOT grant commerce release to a pilot or 50-stage technically built unit.
set -euo pipefail
umask 077
test "$(id -un)" = githubops && test "$(id -u)" -ne 0 && test "$#" -eq 1
source_dir="$1"
test -d "$source_dir" && test ! -L "$source_dir"
base="$HOME/factory-runtime"
ops="$base/operations"
private="$base/private/autonomous-product-cycle"
target="$ops/forty-execution"
registry="$ops/forty-family-master/forty_families.json"
toolchain="$ops/build-toolchain/toolchain-manifest.json"
py="$base/.venv/bin/python"
marker=SAEIT_FACTORY_FORTY_FAMILY_OPERATIONAL_DISPATCH_V1
test -x "$py" && test -d "$private" && test ! -L "$private"
test -s "$registry" && test ! -L "$registry"
test -s "$toolchain" && test ! -L "$toolchain"
test -s "$ops/fifty-family-bridge/factory_build50_family_bridge.py"
test -s "$private/production-warehouse/stock-register.json"
test "$(crontab -l | grep -c SAEIT_FACTORY_EVERY_MINUTE_V1)" -eq 1
test "$(crontab -l | grep -c SAEIT_FACTORY_LIFECYCLE_12_V1)" -eq 1
test "$(crontab -l | grep -c SAEIT_FACTORY_FORTY_FAMILY_MASTER_V1)" -eq 1
test "$(crontab -l | grep -c SAEIT_FACTORY_BUILD50_FORTY_FAMILY_BRIDGE_V1)" -eq 1
test ! -L "$target"
install -d -m 700 "$target" "$ops/backups"
exec 9>"$ops/.forty-execution-deploy.lock"
/usr/bin/flock -w 20 9 || { echo FORTY_EXEC_INSTALL_ALREADY_RUNNING;exit 1; }
stamp="$(date -u +%Y%m%dT%H%M%S)-$$"
backup="$ops/backups/forty-execution-$stamp"
install -d -m 700 "$backup"
crontab -l > "$backup/crontab-before.txt"
chmod 600 "$backup/crontab-before.txt"
for name in factory_40_execution_controller.py factory_40_family_master.py factory_build50_family_bridge.py factory_build_50.py factory_specialist_pilots.py factory_specialist_formats.py;do
 test -s "$source_dir/$name" && test ! -L "$source_dir/$name"
 if test -f "$target/$name";then
  test ! -L "$target/$name"
  cp -p "$target/$name" "$backup/$name.previous"
 fi
 tmp="$(mktemp "$target/.staged-$name.XXXXXXXX")"
 install -m 600 "$source_dir/$name" "$tmp"
 mv -f "$tmp" "$target/$name"
done
"$py" -B -m py_compile "$target"/*.py
# The inspect run must never start a producer; verify exact registration first.
"$py" -B "$target/factory_40_execution_controller.py" --factory-private "$private" --registry "$registry" --module-dir "$target" --inspect-only
# Now run exactly one bounded, real, version-verified specialist pilot step.
"$py" -B "$target/factory_40_execution_controller.py" --factory-private "$private" --registry "$registry" --module-dir "$target" --toolchain-manifest "$toolchain"
"$py" -B - "$private" <<'PY'
import json,sys
from pathlib import Path
p=Path(sys.argv[1])/'production-family-management/forty-execution-dashboard.json'
d=json.loads(p.read_text('utf8'))
assert d['schema']=='saeit.factory.forty-family-operational-controller.v1'
assert d['registered_families']==40 and len(d['families'])==40
assert len({x['family_id'] for x in d['families']})==40
assert all(x['required_work_packages']==48 and not x['commercial_release_allowed'] for x in d['families'])
assert d['counts']['registered']==40
assert not d['commercial_release_enabled'] and not d['store_publication_enabled']
assert d['customer_orders_created']==0
print('FORTY_FAMILY_REAL_CONTROLLER_INITIAL_READBACK='+json.dumps(d['counts'],sort_keys=True))
print('FORTY_FAMILY_REAL_PILOT_TICK='+json.dumps(d['pilot_tick_result'],sort_keys=True))
PY
cat > "$target/periodic-dispatch.sh" <<SH
#!/usr/bin/env bash
set -euo pipefail
umask 077
exec 9>"$ops/.forty-execution-scheduler.lock"
/usr/bin/flock -n 9 || exit 0
exec >> "$ops/forty-execution.log" 2>&1
exec "$py" -B "$target/factory_40_execution_controller.py" --factory-private "$private" --registry "$registry" --module-dir "$target" --toolchain-manifest "$toolchain"
SH
chmod 700 "$target/periodic-dispatch.sh"
bash -n "$target/periodic-dispatch.sh"
entries="$(grep -c "$marker" "$backup/crontab-before.txt" || true)"
test "$entries" -le 1
if test "$entries" -eq 0;then
 cp "$backup/crontab-before.txt" "$backup/crontab-proposed.txt"
 printf '3-59/5 * * * * /bin/bash %s # %s\n' "$target/periodic-dispatch.sh" "$marker" >> "$backup/crontab-proposed.txt"
 test "$(crontab -l | sha256sum | awk '{print $1}')" = "$(sha256sum "$backup/crontab-before.txt" | awk '{print $1}')"
 crontab - < "$backup/crontab-proposed.txt"
else
 grep -Fq "$target/periodic-dispatch.sh" "$backup/crontab-before.txt"
fi
for job in "$marker" SAEIT_FACTORY_EVERY_MINUTE_V1 SAEIT_FACTORY_LIFECYCLE_12_V1 SAEIT_FACTORY_FORTY_FAMILY_MASTER_V1 SAEIT_FACTORY_BUILD50_FORTY_FAMILY_BRIDGE_V1;do
 test "$(crontab -l | grep -c "$job")" -eq 1
done
echo FORTY_FAMILY_PRIVATE_OPERATIONAL_QUEUE=ACTIVE
echo FORTY_FAMILY_PILOT_DISPATCH_EVERY_FIVE_MINUTES=ACTIVE
echo FORTY_FAMILY_OLD_PRODUCTION_AND_STORES=UNCHANGED
echo FORTY_FAMILY_AUTOMATIC_COMMERCIAL_APPROVAL=false
echo FORTY_FAMILY_BACKUP="$backup"
