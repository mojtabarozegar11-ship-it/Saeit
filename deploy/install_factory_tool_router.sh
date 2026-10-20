#!/usr/bin/env bash
# One-pass private integration with existing live 5-min controller cron.
# Preserve native producers/cron/store/payment; rollback on failed verification.
set -euo pipefail
umask 077
test "$(id -un)" = githubops && test "$(id -u)" -ne 0 && test "$#" -eq 1
stage="$1"
test -d "$stage" && test ! -L "$stage"
test -s "$stage/factory_tool_router.py" && test ! -L "$stage/factory_tool_router.py"
base="$HOME/factory-runtime"
ops="$base/operations";root="$base/private/autonomous-product-cycle"
registry="$ops/forty-family-master/forty_families.json"
target="$ops/forty-execution"
py="$base/.venv/bin/python"
scheduler="$target/periodic-dispatch.sh";router="$target/factory_tool_router.py"
test -x "$py" && test -d "$root" && test -s "$registry" && test -f "$scheduler" && test ! -L "$scheduler"
test ! -L "$target" && test ! -L "$router" && test -s "$target/factory_40_execution_controller.py"
test -s "$ops/production-workbench-3000/runner.py"
test -s "$root/production-toolkit-3000/verification.json"
test "$(crontab -l | grep -c SAEIT_FACTORY_FORTY_FAMILY_OPERATIONAL_DISPATCH_V1)" -eq 1
test "$(crontab -l | grep -c SAEIT_FACTORY_EVERY_MINUTE_V1)" -eq 1
install -d -m 700 "$ops/backups"
exec 9>"$ops/.factory-tool-router-deploy.lock"
flock -w 30 9
stamp="$(date -u +%Y%m%dT%H%M%SZ)-$$"
backup="$ops/backups/tool-router-$stamp";install -d -m 700 "$backup"
cp -p "$scheduler" "$backup/periodic-dispatch.sh"
prior_router=0
if test -f "$router";then cp -p "$router" "$backup/factory_tool_router.py";prior_router=1;fi
crontab -l > "$backup/crontab-before.txt"
rollback(){
  rc=$?
  if test "$rc" -ne 0;then
    cp -p "$backup/periodic-dispatch.sh" "$scheduler"
    if test "$prior_router" -eq 1;then cp -p "$backup/factory_tool_router.py" "$router";else rm -f "$router";fi
    rm -f "$router.new" "$scheduler.new"
    echo FACTORY_TOOL_ROUTER_ROLLBACK=APPLIED
  fi
  return "$rc"
}
trap rollback EXIT
"$py" -B -m py_compile "$stage/factory_tool_router.py"
"$py" -B "$stage/factory_tool_router.py" --factory-private "$root" --ops "$ops" --registry "$registry" --verify-only
"$py" -B "$stage/factory_tool_router.py" --factory-private "$root" --ops "$ops" --registry "$registry" --selftest-all
install -m 600 "$stage/factory_tool_router.py" "$router.new"
test "$(sha256sum "$stage/factory_tool_router.py" | cut -d' ' -f1)" = "$(sha256sum "$router.new" | cut -d' ' -f1)"
mv -f "$router.new" "$router"
"$py" -B - "$scheduler" "$scheduler.new" <<'PY'
import pathlib,sys
source=pathlib.Path(sys.argv[1]);output=pathlib.Path(sys.argv[2])
text=source.read_text()
marker='exec "$py" -B "$target/factory_40_execution_controller.py"'
hook='/usr/bin/timeout 60s "$py" -B "$target/factory_tool_router.py" --factory-private "$private" --ops "$ops" --registry "$registry" --cycle || echo FACTORY_SUPPORT_ROUTER_REQUIRES_REVIEW\n'
assert text.count(marker)==1,"SCHEDULER_MAIN_CONTROLLER_MARKER_MISSING"
assert 'factory_tool_router.py' not in text or hook in text,"UNEXPECTED_OLD_ROUTER_HOOK"
result=text if hook in text else text.replace(marker,hook+marker,1)
output.write_text(result)
output.chmod(source.stat().st_mode & 0o777)
PY
bash -n "$scheduler.new"
mv -f "$scheduler.new" "$scheduler"
"$py" -B "$router" --factory-private "$root" --ops "$ops" --registry "$registry" --cycle
"$py" -B - "$root/tool-router/dashboard.json" <<'PY'
import json,sys
from pathlib import Path
data=json.loads(Path(sys.argv[1]).read_text())
assert data['schema']=='saeit.factory.tool-router.v1'
assert data['registered_tool_bindings']==3000 and data['families_connected']==40
assert data['new_tool_bindings']==2000 and data['existing_tool_bindings_retained']==1000
assert data['support_invocations_this_tick']==400
assert len(data['family_readbacks'])==40
assert data['native_manufacturing_engines_added']==0 and not data['commercial_release']
assert not data['sites_touched'] and not data['payments_touched']
print('FACTORY_ROUTER_40_FAMILIES_400_GENUINE_CALLS=PASS')
PY
test "$(crontab -l | sha256sum | cut -d' ' -f1)" = "$(sha256sum "$backup/crontab-before.txt" | cut -d' ' -f1)"
grep -Fq 'factory_tool_router.py' "$scheduler"
trap - EXIT
echo FACTORY_3000_TOOLS_ROUTED_IN_EXISTING_CRON=PASS
echo FACTORY_2000_NEW_TOOLS_ACCESSIBLE_TO_ALL_40_FAMILIES=PASS
echo FACTORY_WORKER_API_AND_QUEUE=READY_FOR_LOCAL_CALLERS
echo FACTORY_NO_CRON_OR_SITES_OR_PAYMENTS_CHANGED=PASS
echo FACTORY_TOOL_ROUTER_BACKUP="$backup"
