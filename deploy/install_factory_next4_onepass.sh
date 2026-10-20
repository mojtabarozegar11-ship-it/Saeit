#!/usr/bin/env bash
# One-step F08 F09 F32 F38 fixed-scope BUILD50 install and technical evidence.
set -euo pipefail
umask 077
test "$(id -un)" = githubops && test "$#" -eq 1
stage="$1";test -d "$stage" && test ! -L "$stage"
base="$HOME/factory-runtime";ops="$base/operations";root="$base/private/autonomous-product-cycle"
target="$ops/forty-execution";scheduler="$target/periodic-dispatch.sh"
registry="$ops/forty-family-master/forty_families.json"
manifest="$ops/build-toolchain/toolchain-manifest.json";py="$base/.venv/bin/python"
test -x "$py" && test -s "$registry" && test -s "$manifest"
test -f "$scheduler" && test ! -L "$scheduler" && test -s "$target/factory_build_50.py"
test "$(crontab -l|grep -c SAEIT_FACTORY_FORTY_FAMILY_OPERATIONAL_DISPATCH_V1)" -eq 1
exec 9>"$ops/.next4-install.lock";flock -w 30 9
install -d -m 700 "$ops/backups"
backup="$ops/backups/next4-$(date -u +%Y%m%dT%H%M%SZ)-$$"
install -d -m 700 "$backup"
for f in factory_build50_next4_media.py factory_next4_review.py factory_next4_cycle.py;do
 test -s "$stage/$f" && test ! -L "$stage/$f"
 if test -f "$target/$f";then test ! -L "$target/$f";cp -p "$target/$f" "$backup/$f";fi
done
cp -p "$scheduler" "$backup/periodic-dispatch.sh"
crontab -l > "$backup/crontab"
rollback(){
 rc=$?
 if test "$rc" -ne 0;then
  for f in factory_build50_next4_media.py factory_next4_review.py factory_next4_cycle.py;do
   if test -f "$backup/$f";then cp -p "$backup/$f" "$target/$f";else rm -f "$target/$f";fi
  done
  cp -p "$backup/periodic-dispatch.sh" "$scheduler"
  echo NEXT4_CODE_ROLLBACK=PASS
 fi
 return "$rc"
}
trap rollback EXIT
for f in factory_build50_next4_media.py factory_next4_review.py factory_next4_cycle.py;do
 "$py" -B -m py_compile "$stage/$f"
 install -m 600 "$stage/$f" "$target/$f.new"
 test "$(sha256sum "$stage/$f"|cut -d' ' -f1)" = "$(sha256sum "$target/$f.new"|cut -d' ' -f1)"
 mv -f "$target/$f.new" "$target/$f"
done
read -r bin toolpython < <("$py" -B - "$target/factory_specialist_pilots.py" "$manifest" <<'PY'
import importlib.util,sys
spec=importlib.util.spec_from_file_location('verified_pilot',sys.argv[1])
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
root,python=m.toolchain(sys.argv[2]);print(root/'bin',python)
PY
)
test -x "$toolpython" && test -x "$bin/ffmpeg"
"$toolpython" -c 'import PIL,reportlab'
for fid in F09 F32 F38 F08;do
 echo "NEXT4_REAL_BUILD_START=$fid"
 timeout 240s env FACTORY_TOOLCHAIN_BIN="$bin" "$toolpython" -B "$target/factory_build50_next4_media.py" --factory-private "$root" --family "$fid"
done
"$py" -B - "$root" "$registry" "$target" <<'PY'
import sys,json
from pathlib import Path
root=Path(sys.argv[1]);sys.path.insert(0,sys.argv[3])
import factory_build_50 as proto
import factory_build50_family_bridge as bridge
import factory_40_family_master as master
import factory_build50_next4_media as maker
state=bridge.inventory(root,sys.argv[2],proto,master)
verified={f['family_id'] for f in state['families'] if f['technical_50_stage_completed']>0}
assert set(maker.PRODUCTS).issubset(verified)
for fid,product in maker.PRODUCTS.items():
 d=json.loads((root/'digital-products'/product/'manufacturing_manifest.json').read_text())
 assert d['family_id']==fid and d['qa_status']=='passed'
 assert d['independent_human_review'] is False and d['public_listing_enabled'] is False
print('NEXT4_FOUR_REAL_BUILD50_PROOFS=PASS')
print('NEXT4_TOTAL_50_STAGE_FAMILIES='+str(len(verified)))
print('NEXT4_FAMILIES_STILL_LACKING_PROOF='+str(40-len(verified)))
PY
"$py" -B - "$scheduler" "$scheduler.new" "$bin" "$toolpython" <<'PY'
from pathlib import Path
import sys
src=Path(sys.argv[1]);dest=Path(sys.argv[2])
text=src.read_text()
hook='/usr/bin/timeout 70s /usr/bin/env FACTORY_TOOLCHAIN_BIN="'+sys.argv[3]+'" "'+sys.argv[4]+'" -B "$HOME/factory-runtime/operations/forty-execution/factory_next4_cycle.py" --factory-private "$HOME/factory-runtime/private/autonomous-product-cycle" --module-dir "$HOME/factory-runtime/operations/forty-execution" || echo NEXT4_RECONCILE_REWORK\n'
assert text.count('set -euo pipefail')==1
assert 'factory_next4_cycle.py' not in text or hook in text
if hook not in text:text=text.replace('set -euo pipefail\n','set -euo pipefail\n'+hook,1)
assert text.count('factory_next4_cycle.py')==1
dest.write_text(text);dest.chmod(src.stat().st_mode&0o777)
PY
bash -n "$scheduler.new";mv -f "$scheduler.new" "$scheduler"
test "$(crontab -l|sha256sum|cut -d' ' -f1)" = "$(sha256sum "$backup/crontab"|cut -d' ' -f1)"
trap - EXIT
echo NEXT4_REAL_TECHNICAL_MAKERS_AND_CRON_RECONCILE=PASS
echo NEXT4_PUBLIC_STORES_PAYMENTS=UNTOUCHED
