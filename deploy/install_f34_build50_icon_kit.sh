#!/usr/bin/env bash
# Release an actual 50-stage F34 art product to the PRIVATE factory warehouse.
# Production and ZIP hash proofs are mandatory; no store/product public listing.
set -euo pipefail
umask 077
test "$(id -un)" = githubops && test "$(id -u)" -ne 0
test "$#" -eq 1
source_dir="$1"
test -d "$source_dir" && test ! -L "$source_dir"
base="$HOME/factory-runtime"
ops="$base/operations"
private="$base/private/autonomous-product-cycle"
target="$ops/f34-build50-icons"
registry="$ops/forty-family-master/forty_families.json"
bridge="$ops/fifty-family-bridge"
stock="$ops/production-warehouse/factory_production_warehouse.py"
primary="$base/.venv/bin/python"
manifest="$ops/build-toolchain/toolchain-manifest.json"
test -x "$primary" && test -s "$registry" && test -s "$stock"
test -s "$manifest" && test ! -L "$manifest"
test -s "$bridge/factory_build50_family_bridge.py"
test -s "$private/production-warehouse/stock-register.json"
test "$(crontab -l | grep -c SAEIT_FACTORY_LIFECYCLE_12_V1)" -eq 1
test "$(crontab -l | grep -c SAEIT_FACTORY_BUILD50_FORTY_FAMILY_BRIDGE_V1)" -eq 1
test ! -L "$target" && test ! -L "$private"
install -d -m 700 "$target" "$ops/backups"
exec 8>"$ops/.f34-original-icons-install.lock"
/usr/bin/flock -w 25 8 || exit 1
toolpython="$("$primary" - "$manifest" <<'PY'
import json,sys,re
from pathlib import Path
p=Path(sys.argv[1]); m=json.loads(p.read_text('utf8'))
assert m.get('schema')=='saeit.factory.toolchain.v1'
assert len(m['checks'])>=6 and all(isinstance(x,dict) and x.get('passed') is True for x in m['checks'].values())
root=Path(m['root'])
assert root.is_dir() and not root.is_symlink() and re.fullmatch('[0-9a-f]{40}',root.name)
assert root.parent==p.parent/'versions'
py=root/'venv/bin/python'
assert str(py)==str(m.get('python')) and py.is_file()
assert (root/'proof.json').is_file()
print(py)
PY
)"
"$toolpython" -c 'from PIL import Image,ImageDraw; print("F34_APPROVED_PRIVATE_PIL_RUNTIME=PASS")'
stamp="$(date -u +%Y%m%dT%H%M%S)-$$"
backup="$ops/backups/f34-build50-$stamp"
install -d -m 700 "$backup"
cp "$private/production-warehouse/stock-register.json" "$backup/stock-register-before.json"
cp "$private/production-family-management/build50-family-dashboard.json" "$backup/family-ledger-before.json"
chmod 600 "$backup"/*
for name in factory_build50_f34_icon_kit.py factory_f34_independent_icon_review.py factory_build_50.py; do
 test -s "$source_dir/$name" && test ! -L "$source_dir/$name"
 if test -f "$target/$name"; then
  test ! -L "$target/$name"
  cp -p "$target/$name" "$backup/$name.old"
 fi
 install -m 600 "$source_dir/$name" "$target/$name"
done
"$toolpython" -B -m py_compile "$target/factory_build50_f34_icon_kit.py" "$target/factory_f34_independent_icon_review.py" "$target/factory_build_50.py"
"$toolpython" -B "$target/factory_build50_f34_icon_kit.py" --factory-private "$private"
"$primary" -B "$stock" --factory-private "$private" --strict-build50
"$primary" -B "$bridge/factory_build50_family_bridge.py" --factory-private "$private" --registry "$registry" --output "$private/production-family-management/build50-family-dashboard.json"
"$primary" -B - "$private" <<'PY'
import json,sys,hashlib,zipfile
from pathlib import Path
p=Path(sys.argv[1]);product='fieldwork_ui_48_icons'
state=json.loads((p/'build-50'/product/'state.json').read_text('utf8'))
manifest=json.loads((p/'digital-products'/product/'manufacturing_manifest.json').read_text('utf8'))
ledger=json.loads((p/'production-family-management/build50-family-dashboard.json').read_text('utf8'))
stock=json.loads((p/'production-warehouse/stock-register.json').read_text('utf8'))
assert state['status']=='awaiting_owner_acceptance' and state['completed_stages']==50
assert manifest['family_id']=='F34' and manifest['qa_status']=='passed'
assert not manifest['owner_publication_approval'] and not manifest['public_listing_enabled']
assert not manifest['independent_human_review']
arc=p/'digital-products'/product/(product+'-internal-qa.zip')
assert hashlib.sha256(arc.read_bytes()).hexdigest()==manifest['artifact_sha256']
with zipfile.ZipFile(arc) as z:
 assert len(z.namelist())==100 and z.testzip() is None
 assert 'fieldwork_ui_48_icons/preview.html' in z.namelist()
assert len(ledger['families'])==40 and ledger['families'][33]['family_id']=='F34'
assert ledger['families'][33]['technical_50_stage_completed']>=1
assert ledger['counts']['technical_products_with_verified_50_stages']>=3
assert ledger['counts']['families_without_verified_50_stage_executor']<=37
assert ledger['commercial_release_allowed'] is False
assert any(x.get('product_id')==product for x in stock['records'])
print('F34_REAL_ICONS_48=VERIFIED')
print('F34_NEW_ORIGINAL_PRIVATE_STOCK=1')
print('F34_FIFTY_STAGES=PASS')
print('F34_PRIVATE_FACTORY_VALIDATED_PRODUCT_FAMILIES='+str(40-ledger['counts']['families_without_verified_50_stage_executor']))
print('F34_PUBLIC_STORE_RELEASE=NOT_AUTHORIZED')
PY
echo F34_REAL_PRODUCT_VPS_INSTALL=PASS
echo F34_INSTALL_BACKUP="$backup"
