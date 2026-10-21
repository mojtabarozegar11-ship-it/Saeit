#!/usr/bin/env bash
# F23 offline evidence retrieval: verified private technical factory, no sales.
set -euo pipefail
umask 077
test "$(id -un)" = githubops && test "$#" -eq 1
stage="$1"
test -d "$stage" && test ! -L "$stage"
base="$HOME/factory-runtime";ops="$base/operations"
root="$base/private/autonomous-product-cycle"
target="$ops/forty-execution"
scheduler="$target/periodic-dispatch.sh"
registry="$ops/forty-family-master/forty_families.json"
py="$base/.venv/bin/python"
test -x "$py" && test -s "$registry" && test -s "$target/factory_build_50.py"
test -s "$scheduler" && test ! -L "$scheduler"
test "$(crontab -l|grep -c SAEIT_FACTORY_FORTY_FAMILY_OPERATIONAL_DISPATCH_V1)" -eq 1

exec 9>"$ops/.f23-assistant-install.lock";flock -w 50 9
exec 8>"$ops/.forty-execution-shared-installer.lock";flock -w 240 8
install -d -m 700 "$ops/backups"
backup="$ops/backups/f23-offline-assistant-$(date -u +%Y%m%dT%H%M%SZ)-$$"
install -d -m 700 "$backup"
files="factory_build50_f23_assistant.py factory_f23_assistant_independent_review.py factory_f23_offline_assistant_runtime.py"
for f in $files;do
 test -s "$stage/$f" && test ! -L "$stage/$f"
 if test -f "$target/$f";then test ! -L "$target/$f";cp -p "$target/$f" "$backup/$f";fi
done
cp -p "$scheduler" "$backup/periodic-dispatch.sh"
crontab -l > "$backup/crontab"
rollback(){
 rc=$?
 if test "$rc" -ne 0;then
  for f in $files;do
   if test -f "$backup/$f";then cp -p "$backup/$f" "$target/$f";else rm -f -- "$target/$f";fi
  done
  cp -p "$backup/periodic-dispatch.sh" "$scheduler"
  rm -f "$scheduler.new"
  echo F23_INSTALL_CODE_ROLLBACK=PASS
 fi
 return "$rc"
}
trap rollback EXIT
for f in $files;do
 "$py" -B -m py_compile "$stage/$f"
 install -m 600 "$stage/$f" "$target/$f.new"
 test "$(sha256sum "$stage/$f"|cut -d' ' -f1)" = "$(sha256sum "$target/$f.new"|cut -d' ' -f1)"
 mv -f "$target/$f.new" "$target/$f"
done

timeout 210s "$py" -B "$target/factory_build50_f23_assistant.py" --factory-private "$root"
"$py" -B - "$root" "$registry" "$target" <<'PY'
import importlib,json,sys,zipfile
from pathlib import Path
root=Path(sys.argv[1]);sys.path.insert(0,sys.argv[3])
import factory_build_50 as proto
import factory_build50_family_bridge as bridge
import factory_40_family_master as master
import factory_build50_f23_assistant as maker
import factory_f23_offline_assistant_runtime as runtime
import factory_f23_assistant_independent_review as inspector
ledger=bridge.inventory(root,sys.argv[2],proto,master)
valid={x["family_id"] for x in ledger["families"] if x["technical_50_stage_completed"]>0}
assert "F23" in valid
folder=root/"digital-products"/maker.PRODUCT
manifest=json.loads((folder/"manufacturing_manifest.json").read_text(encoding="utf8"))
archive=folder/(maker.PRODUCT+"-internal-qa.zip")
assert manifest["family_id"]=="F23" and manifest["qa_status"]=="passed"
assert manifest["public_listing_enabled"] is False and manifest["owner_publication_approval"] is False
assert manifest["professional_quality_1000_passed"] is False
with zipfile.ZipFile(archive) as z:
    entries=z.namelist()
    assert len(entries)==51 and z.testzip() is None
    records=json.loads(z.read(maker.PRODUCT+"/knowledge.json"))
    runtime.check_cards(records)
    for case in records:
        result=runtime.answer(case["question"],records)
        assert result["status"]=="retrieved" and result["source_ids"]==[case["id"]]
assert runtime.answer("Tell me the secret live banking credential",records)["status"]=="insufficient_evidence"
print("VPS_F23_REAL_OFFLINE_48_CARD_ASSISTANT_50STAGES=PASS")
print("VPS_F23_TECHNICAL_FAMILY_COUNT="+str(len(valid)))
print("VPS_F23_COMMERCIAL_RELEASE=DENIED")
PY

"$py" -B - "$scheduler" "$scheduler.new" <<'PY'
from pathlib import Path
import sys
source=Path(sys.argv[1]);dest=Path(sys.argv[2]);body=source.read_text()
hook='/usr/bin/flock -n "$HOME/factory-runtime/operations/.f23-assistant-rebuild.lock" /usr/bin/timeout 75s "$HOME/factory-runtime/.venv/bin/python" -B "$HOME/factory-runtime/operations/forty-execution/factory_build50_f23_assistant.py" --factory-private "$HOME/factory-runtime/private/autonomous-product-cycle" || echo F23_NATIVE_ASSISTANT_REWORK_PENDING\n'
assert body.count("set -euo pipefail")==1
assert "factory_build50_f23_assistant.py" not in body or hook in body
if hook not in body:body=body.replace("set -euo pipefail\n","set -euo pipefail\n"+hook,1)
assert body.count("factory_build50_f23_assistant.py")==1
dest.write_text(body);dest.chmod(source.stat().st_mode&0o777)
PY
bash -n "$scheduler.new";mv -f "$scheduler.new" "$scheduler"
test "$(crontab -l|sha256sum|cut -d' ' -f1)" = "$(sha256sum "$backup/crontab"|cut -d' ' -f1)"
test "$(grep -c factory_build50_f23_assistant.py "$scheduler")" -eq 1
trap - EXIT
echo F23_OFFLINE_ASSISTANT_INSTALLED_WITH_BACKUP_AND_EXCLUSIVE_SCHEDULE=PASS
echo F23_FACTORY_ORIGINAL_STOCK_AND_PUBLIC_SITES=UNCHANGED
