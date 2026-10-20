#!/usr/bin/env bash
# Safely deploy real F29/F30/F33 makers and 40-family admission QA in one pass.
set -euo pipefail
umask 077
test "$(id -un)" = githubops && test "$#" -eq 1
stage="$1";test -d "$stage" && test ! -L "$stage"
base="$HOME/factory-runtime";ops="$base/operations"
root="$base/private/autonomous-product-cycle"
target="$ops/forty-execution"
scheduler="$target/periodic-dispatch.sh"
manifest="$ops/build-toolchain/toolchain-manifest.json"
registry="$ops/forty-family-master/forty_families.json"
py="$base/.venv/bin/python"
test -x "$py" && test -s "$manifest" && test -s "$registry" && test -f "$scheduler" && test ! -L "$scheduler"
test ! -L "$target" && test -s "$target/factory_build_50.py" && test -s "$target/factory_build50_family_bridge.py"
test "$(crontab -l|grep -c SAEIT_FACTORY_FORTY_FAMILY_OPERATIONAL_DISPATCH_V1)" -eq 1
exec 9>"$ops/.family-producer-gap-onepass.lock"
flock -w 30 9
install -d -m 700 "$ops/backups"
stamp="$(date -u +%Y%m%dT%H%M%SZ)-$$";back="$ops/backups/gap-onepass-$stamp"
install -d -m 700 "$back"
files=(factory_build50_creative_kits.py factory_creative_independent_review.py factory_30_gap_preflight.py factory_product_routes.py)
for f in "${files[@]}";do
 test -s "$stage/$f" && test ! -L "$stage/$f"
 if test -f "$target/$f";then test ! -L "$target/$f";cp -p "$target/$f" "$back/$f";fi
done
cp -p "$scheduler" "$back/periodic-dispatch.sh"
crontab -l > "$back/crontab"
rollback() {
 rc=$?
 if test "$rc" -ne 0;then
   for f in "${files[@]}";do
     if test -f "$back/$f";then cp -p "$back/$f" "$target/$f";else rm -f "$target/$f";fi
   done
   cp -p "$back/periodic-dispatch.sh" "$scheduler"
   echo GAP_ONEPASS_CODE_ROLLBACK=APPLIED
 fi
 return "$rc"
}
trap rollback EXIT
for f in "${files[@]}";do
 "$py" -m py_compile "$stage/$f"
 install -m 600 "$stage/$f" "$target/$f.new"
 test "$(sha256sum "$stage/$f"|cut -d' ' -f1)" = "$(sha256sum "$target/$f.new"|cut -d' ' -f1)"
 mv -f "$target/$f.new" "$target/$f"
done
# The pinned toolchain is required for actual DOCX/PPTX/PIL production.
pythonbin="$("$py" -B - "$target/factory_specialist_pilots.py" "$manifest" <<'PY'
import importlib.util,sys
sp=importlib.util.spec_from_file_location('pilot',sys.argv[1])
m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
_,python=m.toolchain(sys.argv[2]);print(python)
PY
)"
test -x "$pythonbin"
# Avoid source mutation and unbounded materialization. BUILD50 itself locks attempts.
for fid in F29 F30 F33;do
 echo "CREATIVE_FAMILY_START=$fid"
 timeout 300s "$pythonbin" -B "$target/factory_build50_creative_kits.py" --factory-private "$root" --family "$fid"
done
# Compile actual family routes and technical gap states only after producers finish.
"$py" -B "$target/factory_30_gap_preflight.py" --factory-private "$root" --ops "$ops" --registry "$registry" --module-dir "$target"
"$py" -B - "$scheduler" "$scheduler.new" <<'PY'
from pathlib import Path
import sys
src=Path(sys.argv[1]);dst=Path(sys.argv[2]);text=src.read_text()
hook='/usr/bin/timeout 60s "$HOME/factory-runtime/.venv/bin/python" -B "$HOME/factory-runtime/operations/forty-execution/factory_30_gap_preflight.py" --factory-private "$HOME/factory-runtime/private/autonomous-product-cycle" --ops "$HOME/factory-runtime/operations" --registry "$HOME/factory-runtime/operations/forty-family-master/forty_families.json" --module-dir "$HOME/factory-runtime/operations/forty-execution" || echo FACTORY_ENGINEERING_GATES_REQUIRES_REVIEW\n'
assert text.count("set -euo pipefail")==1
assert "factory_30_gap_preflight.py" not in text or hook in text
if hook not in text:text=text.replace("set -euo pipefail\n","set -euo pipefail\n"+hook,1)
assert text.count("factory_30_gap_preflight.py")==1
dst.write_text(text);dst.chmod(src.stat().st_mode&0o777)
PY
bash -n "$scheduler.new"
mv -f "$scheduler.new" "$scheduler"
"$py" -B - "$root" "$registry" "$target" <<'PY'
import json,sys
from pathlib import Path
root=Path(sys.argv[1]);target=Path(sys.argv[3]);sys.path.insert(0,str(target))
import factory_build50_family_bridge as bridge
import factory_build_50 as proto
import factory_40_family_master as master
e=bridge.inventory(root,sys.argv[2],proto,master)
verified={row['family_id'] for row in e['families'] if row['technical_50_stage_completed']>0}
for fid in ('F29','F30','F33'):
 assert fid in verified, 'CREATIVE_BUILD50_NOT_PROVEN:'+fid
for fid in ('F29','F30','F33'):
 product=__import__('factory_build50_creative_kits').PRODUCTS[fid]
 d=json.loads((root/'digital-products'/product/'manufacturing_manifest.json').read_text())
 assert d['qa_status']=='passed' and d['public_listing_enabled'] is False
d=json.loads((root/'engineering-gaps/dashboard.json').read_text())
assert d['registered_families']==40 and d['family_contracts_compiled']==40
assert len(d['families_without_50stage_proof'])==40-len(verified)
assert not d['commercial_products_approved']
print('FACTORY_NEW_CREATIVE_BUILD50_REAL_FAMILIES=F29,F30,F33')
print('FACTORY_TOTAL_INDEPENDENT_50_STAGE_FAMILIES='+str(len(verified)))
print('FACTORY_GAP_FAMILIES='+str(len(d['families_without_50stage_proof'])))
print('FACTORY_GAP_ENGINEERING_CODE_INSTALLED=PASS')
PY
test "$(crontab -l|sha256sum|cut -d' ' -f1)" = "$(sha256sum "$back/crontab"|cut -d' ' -f1)"
trap - EXIT
echo FACTORY_3_NEW_TECHNICAL_PRODUCERS_AND_40_GAP_GATES=PASS
echo FACTORY_SITES_AND_PAYMENTS_UNCHANGED=PASS
