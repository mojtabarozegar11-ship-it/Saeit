#!/usr/bin/env bash
# Build genuine playable HTML5 games, motion GIF+MP4, synthesized WAV+MP3.
set -euo pipefail
umask 077
test "$(id -un)" = githubops && test "$#" -eq 1
stage="$1";test -d "$stage" && test ! -L "$stage"
base="$HOME/factory-runtime";ops="$base/operations";root="$base/private/autonomous-product-cycle"
target="$ops/forty-execution";scheduler="$target/periodic-dispatch.sh"
manifest="$ops/build-toolchain/toolchain-manifest.json"
registry="$ops/forty-family-master/forty_families.json";py="$base/.venv/bin/python"
test -x "$py" && test -s "$manifest" && test -s "$registry"
test -f "$scheduler" && test ! -L "$scheduler" && test -s "$target/factory_build_50.py"
test "$(crontab -l|grep -c SAEIT_FACTORY_FORTY_FAMILY_OPERATIONAL_DISPATCH_V1)" -eq 1
exec 9>"$ops/.three-real-builders-install.lock";flock -w 30 9
install -d -m 700 "$ops/backups"
backup="$ops/backups/three-real-builders-$(date -u +%Y%m%dT%H%M%SZ)-$$"
install -d -m 700 "$backup"
for file in factory_build50_three_media.py factory_three_independent_review.py factory_three_builder_cycle.py;do
 test -s "$stage/$file" && test ! -L "$stage/$file"
 if test -f "$target/$file";then test ! -L "$target/$file";cp -p "$target/$file" "$backup/$file";fi
done
cp -p "$scheduler" "$backup/periodic-dispatch.sh"
crontab -l > "$backup/crontab"
rollback(){
 rc=$?
 if test "$rc" -ne 0;then
  for file in factory_build50_three_media.py factory_three_independent_review.py factory_three_builder_cycle.py;do
   if test -f "$backup/$file";then cp -p "$backup/$file" "$target/$file";else rm -f "$target/$file";fi
  done
  cp -p "$backup/periodic-dispatch.sh" "$scheduler"
  echo FACTORY_THREE_BUILDERS_SOURCE_ROLLBACK=PASS
 fi
 return "$rc"
}
trap rollback EXIT
for file in factory_build50_three_media.py factory_three_independent_review.py factory_three_builder_cycle.py;do
 "$py" -B -m py_compile "$stage/$file"
 install -m 600 "$stage/$file" "$target/$file.new"
 test "$(sha256sum "$stage/$file"|cut -d' ' -f1)" = "$(sha256sum "$target/$file.new"|cut -d' ' -f1)"
 mv -f "$target/$file.new" "$target/$file"
done
read -r bin toolpython < <("$py" -B - "$target/factory_specialist_pilots.py" "$manifest" <<'PY'
import importlib.util,sys
spec=importlib.util.spec_from_file_location('factory_pinned_pilot',sys.argv[1])
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
root,python=m.toolchain(sys.argv[2]);print(root/'bin',python)
PY
)
test -x "$bin/ffmpeg" && test -x "$toolpython"
"$toolpython" -c 'from PIL import Image'
for family in F14 F39 F37;do
 echo "FACTORY_THREE_START=$family"
 timeout 240s env FACTORY_TOOLCHAIN_BIN="$bin" "$toolpython" -B "$target/factory_build50_three_media.py" --factory-private "$root" --family "$family"
done
"$py" -B - "$root" "$registry" "$target" <<'PY'
import sys,json
from pathlib import Path
root=Path(sys.argv[1]);sys.path.insert(0,sys.argv[3])
import factory_build_50 as proto
import factory_40_family_master as master
import factory_build50_family_bridge as bridge
import factory_build50_three_media as maker
ledger=bridge.inventory(root,sys.argv[2],proto,master)
valid={x['family_id'] for x in ledger['families'] if x['technical_50_stage_completed']>0}
assert set(maker.PRODUCTS).issubset(valid)
for family,product in maker.PRODUCTS.items():
 d=json.loads((root/'digital-products'/product/'manufacturing_manifest.json').read_text())
 assert d['family_id']==family and d['qa_status']=='passed'
 assert not d['public_listing_enabled'] and not d['owner_publication_approval']
print('FACTORY_THREE_REAL_50_STAGE_BUILDERS=PASS')
print('FACTORY_VERIFIED_TECHNICAL_FAMILIES='+str(len(valid)))
print('FACTORY_MISSING_REAL_TECHNICAL_PROOF='+str(40-len(valid)))
PY
"$py" -B - "$scheduler" "$scheduler.new" "$bin" "$toolpython" <<'PY'
from pathlib import Path
import sys
src=Path(sys.argv[1]);dst=Path(sys.argv[2]);text=src.read_text()
hook='/usr/bin/timeout 70s /usr/bin/env FACTORY_TOOLCHAIN_BIN="'+sys.argv[3]+'" "'+sys.argv[4]+'" -B "$HOME/factory-runtime/operations/forty-execution/factory_three_builder_cycle.py" --factory-private "$HOME/factory-runtime/private/autonomous-product-cycle" --module-dir "$HOME/factory-runtime/operations/forty-execution" || echo FACTORY_THREE_RECONCILE_REWORK\n'
assert text.count('set -euo pipefail')==1
assert 'factory_three_builder_cycle.py' not in text or hook in text
if hook not in text:text=text.replace('set -euo pipefail\n','set -euo pipefail\n'+hook,1)
assert text.count('factory_three_builder_cycle.py')==1
dst.write_text(text);dst.chmod(src.stat().st_mode & 0o777)
PY
bash -n "$scheduler.new";mv -f "$scheduler.new" "$scheduler"
test "$(crontab -l|sha256sum|cut -d' ' -f1)" = "$(sha256sum "$backup/crontab"|cut -d' ' -f1)"
trap - EXIT
echo FACTORY_THREE_REAL_PRODUCERS_FIVE_MINUTE_RECONCILE=PASS
echo FACTORY_PAYMENT_CPANEl_PUBLIC_STORES=UNCHANGED
echo FACTORY_BACKUP="$backup"
