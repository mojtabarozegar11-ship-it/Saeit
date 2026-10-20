#!/usr/bin/env bash
# Atomic private intake activation for all 40. No store, money, user-facing sites.
set -euo pipefail
umask 077
test "$(id -un)" = githubops && test "$#" -eq 1
stage="$1";test -d "$stage" && test ! -L "$stage"
base="$HOME/factory-runtime";ops="$base/operations"
root="$base/private/autonomous-product-cycle";target="$ops/forty-execution"
registry="$ops/forty-family-master/forty_families.json"
script="$target/factory_all40_private_activation.py"
scheduler="$target/periodic-dispatch.sh"
py="$base/.venv/bin/python"
test -x "$py" && test -s "$registry"
test -s "$stage/factory_all40_private_activation.py" && test ! -L "$stage/factory_all40_private_activation.py"
test -f "$scheduler" && test ! -L "$scheduler"
test -s "$target/factory_commerce40_admission.py"
test "$(crontab -l|grep -c SAEIT_FACTORY_FORTY_FAMILY_OPERATIONAL_DISPATCH_V1)" -eq 1
exec 9>"$ops/.all40-intake-release.lock";flock -w 30 9
install -d -m 700 "$ops/backups"
backup="$ops/backups/all40-private-intake-$(date -u +%Y%m%dT%H%M%SZ)-$$"
install -d -m 700 "$backup"
if test -f "$script";then test ! -L "$script";cp -p "$script" "$backup/factory_all40_private_activation.py";fi
cp -p "$scheduler" "$backup/periodic-dispatch.sh"
crontab -l > "$backup/crontab"
rollback(){
 rc=$?
 if test "$rc" -ne 0;then
  if test -f "$backup/factory_all40_private_activation.py";then cp -p "$backup/factory_all40_private_activation.py" "$script";else rm -f "$script";fi
  cp -p "$backup/periodic-dispatch.sh" "$scheduler"
  rm -f "$script.new" "$scheduler.new"
  echo ALL40_PRIVATE_INTAKE_ROLLBACK=APPLIED
 fi
 return "$rc"
}
trap rollback EXIT
"$py" -B -m py_compile "$stage/factory_all40_private_activation.py"
install -m 600 "$stage/factory_all40_private_activation.py" "$script.new"
test "$(sha256sum "$stage/factory_all40_private_activation.py"|cut -d' ' -f1)" = "$(sha256sum "$script.new"|cut -d' ' -f1)"
mv -f "$script.new" "$script"
# Independently recount exact 40 technical/catalog SKU offers from real files.
"$py" -B "$target/factory_commerce40_admission.py" --factory-private "$root" --registry "$registry" --module-dir "$target"
"$py" -B "$script" --factory-private "$root" --max-per-tick 3
# Truly drive 40 independent real queue requests through the same installed module,
# but exclusively in an isolated temporary root, never actual customers.
"$py" -B - "$root" "$script" "$ops" <<'PY'
import importlib.util,json,shutil,sys,tempfile
from pathlib import Path
source=Path(sys.argv[1])
spec=importlib.util.spec_from_file_location("private_intake_real_queue_test",sys.argv[2])
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
with tempfile.TemporaryDirectory(prefix=".all40-queue-probe-",dir=sys.argv[3]) as isolated:
    scratch=Path(isolated)
    dest=scratch/"commercial40/offers"
    dest.mkdir(parents=True,mode=0o700)
    for i in range(1,41):
        p="F%02d.json"%i
        shutil.copyfile(source/"commercial40/offers"/p,dest/p)
    requests=scratch/"activation40/requests"
    requests.mkdir(parents=True,mode=0o700)
    for i in range(1,41):
        fid="F%02d"%i
        request={"schema":module.REQUEST_SCHEMA,"request_id":"probe_realqueue_%02d"%i,
         "family_id":fid,"intent":"technical_evaluation",
         "title":"Internal isolated queue routing proof "+fid,
         "specification":"Synthetic QA-only request to verify real on-disk intake and role-specific routing with no monetary or live customer action."}
        module.save(requests/(request["request_id"]+".json"),request)
    accepted=0
    for _ in range(14):
        result=module.tick(scratch,max_per_tick=3)
        accepted+=result["queued_requests_accepted"]
    assert accepted==40,accepted
    tasks=list((scratch/"activation40/tasks").glob("*.json"))
    receipts=list((scratch/"activation40/receipts").glob("*.json"))
    assert len(tasks)==len(receipts)==40
    assert len(list(requests.glob("*.json")))==0
    for item in tasks:
        d=module.read(item)
        assert not d["payment_created"] and not d["commercial_release_authorized"]
        assert d["status"]=="queued_for_specialist_review"
        receipt=module.read(scratch/"activation40/receipts"/item.name)
        assert receipt["task_sha256"]==module.digest(d)
    print("ALL40_SYNTHETIC_ISOLATED_DISK_QUEUE_RECEIPTS=40")
    print("ALL40_SYNTHETIC_QUEUE_NO_PAYMENTS_OR_SITE_CHANGES=PASS")
PY
# Attach intake to current five-minute family dispatch, preserving cron entirely.
"$py" -B - "$scheduler" "$scheduler.new" <<'PY'
from pathlib import Path
import sys
src=Path(sys.argv[1]);dest=Path(sys.argv[2]);source=src.read_text()
hook='/usr/bin/timeout 75s "$HOME/factory-runtime/.venv/bin/python" -B "$HOME/factory-runtime/operations/forty-execution/factory_all40_private_activation.py" --factory-private "$HOME/factory-runtime/private/autonomous-product-cycle" --max-per-tick 3 || echo ALL40_PRIVATE_INTAKE_RECHECK_REQUIRED\n'
assert source.count('set -euo pipefail')==1
assert "factory_all40_private_activation.py" not in source or hook in source
if hook not in source:
    source=source.replace('set -euo pipefail\n','set -euo pipefail\n'+hook,1)
assert source.count('factory_all40_private_activation.py')==1
dest.write_text(source);dest.chmod(src.stat().st_mode&0o777)
PY
bash -n "$scheduler.new";mv -f "$scheduler.new" "$scheduler"
test "$(crontab -l|sha256sum|cut -d' ' -f1)" = "$(sha256sum "$backup/crontab"|cut -d' ' -f1)"
"$py" -B - "$root" "$scheduler" <<'PY'
import json,sys
from pathlib import Path
root=Path(sys.argv[1]);scheduler=Path(sys.argv[2])
d=json.loads((root/"activation40/dashboard.json").read_text())
assert d["registered_intake_families"]==40
assert d["families_available_for_private_intake"]==40
assert len(d["families"])==40
assert d["synthetic_local_route_probes_verified"]==40
assert d["commercial_families_sellable"]==0 and d["sales_and_payments_processed"]==0
assert scheduler.read_text().count("factory_all40_private_activation.py")==1
print("VPS_ALL40_PRIVATE_INTAKE_ACTIVATED=40")
print("VPS_ALL40_TECHNICAL_PORTFOLIO_FAMILIES="+str(d["technical_product_families"]))
print("VPS_ALL40_MISSING_SPECIALIST_NATIVE_MAKER="+str(d["families_needing_a_native_maker"]))
print("VPS_ALL40_PUBLIC_SALE_AND_PAYMENT=0")
print("VPS_ALL40_GENUINE_WORKER_CONSUMPTION_UNPROVEN=true")
PY
trap - EXIT
echo VPS_ALL40_PRIVATE_QUEUE_RUNTIME_AND_SCHEDULER=PASS
echo VPS_ALL40_CRON_LIVE_SITES_PAYMENT_CHECKOUT_UNCHANGED=PASS
