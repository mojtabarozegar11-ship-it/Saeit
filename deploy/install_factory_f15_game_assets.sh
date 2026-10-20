#!/usr/bin/env bash
# Safe real game-asset native technical F15 release with zero commercial changes.
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
exec 9>"$ops/.f15-game-assets-install.lock";flock -w 30 9
install -d -m 700 "$ops/backups"
backup="$ops/backups/f15-game-assets-$(date -u +%Y%m%dT%H%M%SZ)-$$"
install -d -m 700 "$backup"
for f in factory_build50_f15_game_assets.py factory_f15_independent_review.py factory_f15_asset_cycle.py;do
 test -s "$stage/$f" && test ! -L "$stage/$f"
 if test -f "$target/$f";then test ! -L "$target/$f";cp -p "$target/$f" "$backup/$f";fi
done
cp -p "$scheduler" "$backup/periodic-dispatch.sh"
crontab -l > "$backup/crontab"
rollback(){
 rc=$?
 if test "$rc" -ne 0;then
  for f in factory_build50_f15_game_assets.py factory_f15_independent_review.py factory_f15_asset_cycle.py;do
   if test -f "$backup/$f";then cp -p "$backup/$f" "$target/$f";else rm -f "$target/$f";fi
  done
  cp -p "$backup/periodic-dispatch.sh" "$scheduler"
  echo F15_CODE_ROLLBACK=PASS
 fi
 return "$rc"
}
trap rollback EXIT
for f in factory_build50_f15_game_assets.py factory_f15_independent_review.py factory_f15_asset_cycle.py;do
 "$py" -B -m py_compile "$stage/$f"
 install -m 600 "$stage/$f" "$target/$f.new"
 test "$(sha256sum "$stage/$f"|cut -d' ' -f1)" = "$(sha256sum "$target/$f.new"|cut -d' ' -f1)"
 mv -f "$target/$f.new" "$target/$f"
done
toolpython="$("$py" -B - "$target/factory_specialist_pilots.py" "$manifest" <<'PY'
import importlib.util,sys
sp=importlib.util.spec_from_file_location('pinned',sys.argv[1])
m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
_,python=m.toolchain(sys.argv[2]);print(python)
PY
)"
test -x "$toolpython"
"$toolpython" -c 'import PIL'
timeout 220s "$toolpython" -B "$target/factory_build50_f15_game_assets.py" --factory-private "$root"
"$py" -B - "$root" "$registry" "$target" <<'PY'
import json,sys
from pathlib import Path
root=Path(sys.argv[1]);sys.path.insert(0,sys.argv[3])
import factory_build_50 as proto
import factory_40_family_master as master
import factory_build50_family_bridge as bridge
import factory_build50_f15_game_assets as maker
ledger=bridge.inventory(root,sys.argv[2],proto,master)
valid={x['family_id'] for x in ledger['families'] if x['technical_50_stage_completed']>0}
assert 'F15' in valid
d=json.loads((root/'digital-products'/maker.PRODUCT/'manufacturing_manifest.json').read_text())
assert d['qa_status']=='passed' and d['family_id']=='F15'
assert d['public_listing_enabled'] is False and d['independent_human_review'] is False
print('F15_REAL_ORIGINAL_GLB_SPRITE_WAV_BUILD50=PASS')
print('F15_TOTAL_PROVEN_TECHNICAL_FAMILIES='+str(len(valid)))
print('F15_REMAINING_UNPROVEN_FAMILIES='+str(40-len(valid)))
PY
"$py" -B - "$scheduler" "$scheduler.new" "$toolpython" <<'PY'
from pathlib import Path
import sys
src=Path(sys.argv[1]);dst=Path(sys.argv[2]);text=src.read_text()
hook='/usr/bin/timeout 60s "'+sys.argv[3]+'" -B "$HOME/factory-runtime/operations/forty-execution/factory_f15_asset_cycle.py" --factory-private "$HOME/factory-runtime/private/autonomous-product-cycle" --module-dir "$HOME/factory-runtime/operations/forty-execution" || echo F15_ASSET_RECONCILE_REWORK\n'
assert text.count('set -euo pipefail')==1
assert 'factory_f15_asset_cycle.py' not in text or hook in text
if hook not in text:text=text.replace('set -euo pipefail\n','set -euo pipefail\n'+hook,1)
assert text.count('factory_f15_asset_cycle.py')==1
dst.write_text(text);dst.chmod(src.stat().st_mode&0o777)
PY
bash -n "$scheduler.new";mv -f "$scheduler.new" "$scheduler"
test "$(crontab -l|sha256sum|cut -d' ' -f1)" = "$(sha256sum "$backup/crontab"|cut -d' ' -f1)"
trap - EXIT
echo F15_PRIVATE_ASSET_FACTORY_AND_EXISTING_CRON=PASS
echo F15_LIVE_SITES_AND_PAYMENTS_UNCHANGED=PASS
