#!/usr/bin/env bash
# One-pass five new *actual native* authoring pilot families, no public selling.
set -euo pipefail
umask 077
test "$(id -un)" = githubops && test "$#" -eq 1
stage="$1";test -d "$stage" && test ! -L "$stage"
base="$HOME/factory-runtime";ops="$base/operations";root="$base/private/autonomous-product-cycle"
target="$ops/forty-execution";scheduler="$target/periodic-dispatch.sh"
registry="$ops/forty-family-master/forty_families.json"
manifest="$ops/build-toolchain/toolchain-manifest.json";py="$base/.venv/bin/python"
test -x "$py" && test -s "$manifest" && test -s "$registry"
test -f "$scheduler" && test ! -L "$scheduler" && test -s "$target/factory_build_50.py"
test -s "$target/factory_commerce40_admission.py"
test "$(crontab -l|grep -c SAEIT_FACTORY_FORTY_FAMILY_OPERATIONAL_DISPATCH_V1)" -eq 1
exec 9>"$ops/.five-native-publishing-install.lock";flock -w 35 9
install -d -m 700 "$ops/backups"
backup="$ops/backups/five-authoring-$(date -u +%Y%m%dT%H%M%SZ)-$$"
install -d -m 700 "$backup"
files="factory_build50_five_publications.py factory_five_publication_review.py factory_five_publication_cycle.py"
for file in $files;do
 test -s "$stage/$file" && test ! -L "$stage/$file"
 if test -f "$target/$file";then test ! -L "$target/$file";cp -p "$target/$file" "$backup/$file";fi
done
cp -p "$scheduler" "$backup/periodic-dispatch.sh"
crontab -l > "$backup/crontab"
rollback(){
 code=$?
 if test "$code" -ne 0;then
  for file in $files;do
   if test -f "$backup/$file";then cp -p "$backup/$file" "$target/$file";else rm -f "$target/$file";fi
  done
  cp -p "$backup/periodic-dispatch.sh" "$scheduler"
  rm -f "$scheduler.new"
  echo FIVE_PUBLISHING_SOURCE_ROLLBACK=PASS
 fi
 return "$code"
}
trap rollback EXIT
for file in $files;do
 "$py" -B -m py_compile "$stage/$file"
 install -m 600 "$stage/$file" "$target/$file.new"
 test "$(sha256sum "$stage/$file"|cut -d' ' -f1)" = "$(sha256sum "$target/$file.new"|cut -d' ' -f1)"
 mv -f "$target/$file.new" "$target/$file"
done
read -r bin toolpython < <("$py" -B - "$target/factory_specialist_pilots.py" "$manifest" <<'PY'
import importlib.util,sys
spec=importlib.util.spec_from_file_location("known_toolchain",sys.argv[1])
obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj)
root,python=obj.toolchain(sys.argv[2]);print(root/"bin",python)
PY
)
test -x "$toolpython"
"$toolpython" -c 'import reportlab,docx,openpyxl'
for family in F01 F02 F03 F04 F05;do
 echo "FACTORY_FIVE_ACTUAL_NATIVE_START=$family"
 timeout 245s "$toolpython" -B "$target/factory_build50_five_publications.py" --factory-private "$root" --family "$family"
done
"$py" -B - "$root" "$registry" "$target" <<'PY'
import json,sys
from pathlib import Path
root=Path(sys.argv[1]);sys.path.insert(0,sys.argv[3])
import factory_build_50 as proto
import factory_40_family_master as master
import factory_build50_family_bridge as bridge
import factory_build50_five_publications as maker
ledger=bridge.inventory(root,sys.argv[2],proto,master)
valid={x["family_id"] for x in ledger["families"] if x["technical_50_stage_completed"]>0}
assert set(maker.PRODUCTS).issubset(valid),sorted(set(maker.PRODUCTS)-valid)
for fid,product in maker.PRODUCTS.items():
 data=json.loads((root/"digital-products"/product/"manufacturing_manifest.json").read_text())
 assert data["family_id"]==fid and data["qa_status"]=="passed"
 assert data["public_listing_enabled"] is False and data["owner_publication_approval"] is False
 assert data["independent_human_review"] is False
print("FIVE_REAL_NATIVE_50_STAGE_FAMILIES="+str(len(valid)))
print("FIVE_REMAINING_NATIVE_FAMILIES="+str(40-len(valid)))
PY
"$py" -B "$target/factory_commerce40_admission.py" --factory-private "$root" --registry "$registry" --module-dir "$target"
"$py" -B - "$scheduler" "$scheduler.new" "$toolpython" <<'PY'
from pathlib import Path
import sys
src=Path(sys.argv[1]);dst=Path(sys.argv[2]);data=src.read_text()
hook='/usr/bin/timeout 95s "'+sys.argv[3]+'" -B "$HOME/factory-runtime/operations/forty-execution/factory_five_publication_cycle.py" --factory-private "$HOME/factory-runtime/private/autonomous-product-cycle" --module-dir "$HOME/factory-runtime/operations/forty-execution" || echo FIVE_NATIVE_AUTHORING_REWORK_PENDING\n'
assert data.count('set -euo pipefail')==1
assert 'factory_five_publication_cycle.py' not in data or hook in data
if hook not in data:data=data.replace('set -euo pipefail\n','set -euo pipefail\n'+hook,1)
assert data.count('factory_five_publication_cycle.py')==1
dst.write_text(data);dst.chmod(src.stat().st_mode&0o777)
PY
bash -n "$scheduler.new";mv -f "$scheduler.new" "$scheduler"
test "$(crontab -l|sha256sum|cut -d' ' -f1)" = "$(sha256sum "$backup/crontab"|cut -d' ' -f1)"
"$py" -B - "$root" "$scheduler" <<'PY'
import json,sys
from pathlib import Path
root=Path(sys.argv[1]);doc=json.loads((root/"commercial40/dashboard.json").read_text())
assert doc["private_commercial_sku_proposals"]==40
assert doc["genuine_verified_product_families"]>=33
assert doc["commercially_approved_families"]==0
assert doc["sales_or_payments_processed"]==0
assert Path(sys.argv[2]).read_text().count("factory_five_publication_cycle.py")==1
print("VPS_FIVE_FAMILY_COMMERCE_TECHNICAL_PROOFS="+str(doc["genuine_verified_product_families"]))
print("VPS_FIVE_FAMILY_STILL_NOT_TECHNICAL="+str(doc["families_without_trusted_package"]))
print("VPS_FIVE_COMMERCIAL_SALES=0")
PY
trap - EXIT
echo VPS_FIVE_NATIVE_DOCUMENT_MAKERS_AND_EXISTING_CRON=PASS
echo VPS_FIVE_NO_UNVERIFIED_RESEARCH_AND_NO_LIVE_CHECKOUT=PASS
