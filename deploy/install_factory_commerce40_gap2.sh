#!/usr/bin/env bash
# Genuine fixed-scope F24 and F35; no fake commercial release.
set -euo pipefail
umask 077
test "$(id -un)" = githubops && test "$#" -eq 1
stage="$1";test -d "$stage" && test ! -L "$stage"
base="$HOME/factory-runtime";ops="$base/operations"
root="$base/private/autonomous-product-cycle";target="$ops/forty-execution"
registry="$ops/forty-family-master/forty_families.json"
scheduler="$target/periodic-dispatch.sh";py="$base/.venv/bin/python"
test -x "$py" && test -s "$registry" && test -f "$scheduler" && test ! -L "$scheduler"
test -s "$target/factory_commerce40_admission.py" && test -s "$target/factory_build_50.py"
test "$(crontab -l|grep -c SAEIT_FACTORY_FORTY_FAMILY_OPERATIONAL_DISPATCH_V1)" -eq 1
exec 9>"$ops/.gap2-commerce-install.lock";flock -w 30 9
install -d -m 700 "$ops/backups"
backup="$ops/backups/gap2-$(date -u +%Y%m%dT%H%M%SZ)-$$"
install -d -m 700 "$backup"
files="factory_build50_f24_prompts.py factory_f24_prompt_review.py factory_build50_f35_cad.py factory_f35_cad_independent_review.py factory_commerce40_gap2_cycle.py"
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
   if test -f "$backup/$f";then cp -p "$backup/$f" "$target/$f";else rm -f "$target/$f";fi
  done
  cp -p "$backup/periodic-dispatch.sh" "$scheduler"
  rm -f "$scheduler.new"
  echo GAP2_SOURCE_ROLLBACK=APPLIED
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
for kind in F24 F35;do
 file=factory_build50_f24_prompts.py
 if test "$kind" = F35;then file=factory_build50_f35_cad.py;fi
 echo "GAP2_START=$kind"
 timeout 240s "$py" -B "$target/$file" --factory-private "$root"
done
"$py" -B - "$root" "$registry" "$target" <<'PY'
import sys,json
from pathlib import Path
root=Path(sys.argv[1]);sys.path.insert(0,sys.argv[3])
import factory_build_50 as proto
import factory_build50_family_bridge as bridge
import factory_40_family_master as master
import factory_build50_f24_prompts as f24
import factory_build50_f35_cad as f35
ledger=bridge.inventory(root,sys.argv[2],proto,master)
valid={x["family_id"] for x in ledger["families"] if x["technical_50_stage_completed"]>0}
assert {"F24","F35"}.issubset(valid)
for fid,maker in (("F24",f24),("F35",f35)):
 record=json.loads((root/"digital-products"/maker.PRODUCT/"manufacturing_manifest.json").read_text())
 assert record["family_id"]==fid and record["qa_status"]=="passed"
 assert record["public_listing_enabled"] is False and record["owner_publication_approval"] is False
print("GAP2_PROVEN_TECHNICAL_FAMILIES="+str(len(valid)))
print("GAP2_UNPROVEN_TECHNICAL_FAMILIES="+str(40-len(valid)))
PY
"$py" -B "$target/factory_commerce40_admission.py" --factory-private "$root" --registry "$registry" --module-dir "$target"
"$py" -B - "$scheduler" "$scheduler.new" <<'PY'
from pathlib import Path
import sys
src=Path(sys.argv[1]);dst=Path(sys.argv[2]);text=src.read_text()
hook='/usr/bin/timeout 75s "$HOME/factory-runtime/.venv/bin/python" -B "$HOME/factory-runtime/operations/forty-execution/factory_commerce40_gap2_cycle.py" --factory-private "$HOME/factory-runtime/private/autonomous-product-cycle" --module-dir "$HOME/factory-runtime/operations/forty-execution" || echo GAP2_REWORK_PENDING\n'
assert text.count("set -euo pipefail")==1
assert "factory_commerce40_gap2_cycle.py" not in text or hook in text
if hook not in text:text=text.replace("set -euo pipefail\n","set -euo pipefail\n"+hook,1)
assert text.count("factory_commerce40_gap2_cycle.py")==1
dst.write_text(text);dst.chmod(src.stat().st_mode&0o777)
PY
bash -n "$scheduler.new";mv -f "$scheduler.new" "$scheduler"
test "$(crontab -l|sha256sum|cut -d' ' -f1)" = "$(sha256sum "$backup/crontab"|cut -d' ' -f1)"
"$py" -B - "$root" "$scheduler" <<'PY'
import sys,json
from pathlib import Path
root=Path(sys.argv[1]);d=json.loads((root/"commercial40/dashboard.json").read_text())
assert d["private_commercial_sku_proposals"]==40
assert d["genuine_verified_product_families"]>=28
assert d["commercially_approved_families"]==0
assert d["sales_or_payments_processed"]==0
assert Path(sys.argv[2]).read_text().count("factory_commerce40_gap2_cycle.py")==1
print("GAP2_PRIVATE_SKU_COUNT="+str(d["private_commercial_sku_proposals"]))
print("GAP2_COMMERCE_TECHNICAL_FAMILIES="+str(d["genuine_verified_product_families"]))
print("GAP2_COMMERCIAL_BLOCKED_FAMILIES="+str(d["families_without_trusted_package"]))
print("GAP2_APPROVED_PRODUCTS=0")
PY
trap - EXIT
echo GAP2_REAL_CAD_AND_PROMPT_BUILDERS_INSTALLED=PASS
echo GAP2_CRON_AND_SITES_AND_PAYMENT=UNCHANGED
