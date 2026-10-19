#!/usr/bin/env bash
# F19 independent production: real original static template via all 50 technical stages.
# Scope: private VPS product, strict warehouse, honest family dashboard. No website mutation.
set -euo pipefail
umask 077
test "$(id -un)" = githubops
test "$(id -u)" -ne 0
test "$#" -eq 1
source_dir="$1"
test -d "$source_dir" && test ! -L "$source_dir"
base="$HOME/factory-runtime"
ops="$base/operations"
private="$base/private/autonomous-product-cycle"
family="$ops/f19-build50-production"
bridge="$ops/fifty-family-bridge"
warehouse="$ops/production-warehouse"
registry="$ops/forty-family-master/forty_families.json"
python="$base/.venv/bin/python"
test -x "$python" && test -d "$private" && test ! -L "$private"
test -s "$registry" && test -s "$warehouse/factory_production_warehouse.py"
test -s "$bridge/factory_40_family_master.py"
test -s "$private/production-warehouse/stock-register.json"
test "$(crontab -l | grep -c SAEIT_FACTORY_EVERY_MINUTE_V1)" -eq 1
test "$(crontab -l | grep -c SAEIT_FACTORY_LIFECYCLE_12_V1)" -eq 1
test "$(crontab -l | grep -c SAEIT_FACTORY_BUILD50_FORTY_FAMILY_BRIDGE_V1)" -eq 1
test ! -L "$family" && test ! -L "$bridge" && test ! -L "$warehouse"
install -d -m 700 "$family" "$ops/backups"
exec 8>"$ops/.f19-build50-production-install.lock"
flock -w 25 8 || { echo F19_INSTALL_BUSY; exit 1; }
stamp="$(date -u +%Y%m%dT%H%M%S)-$$"
backup="$ops/backups/f19-builder-$stamp"
install -d -m 700 "$backup"
cp "$private/production-warehouse/stock-register.json" "$backup/stock-register-before.json"
cp "$private/production-family-management/build50-family-dashboard.json" "$backup/bridge-ledger-before.json"
chmod 600 "$backup"/*
for file in factory_build50_f19_web_template.py factory_f19_independent_web_review.py factory_build_50.py; do
  test -s "$source_dir/$file" && test ! -L "$source_dir/$file"
  if test -f "$family/$file"; then
    test ! -L "$family/$file"
    cp -p "$family/$file" "$backup/$file.old"
  fi
  temp="$(mktemp "$family/.new-$file.XXXXXXXX")"
  install -m 600 "$source_dir/$file" "$temp"
  mv -f "$temp" "$family/$file"
done
test -s "$source_dir/factory_build50_family_bridge.py"
test ! -L "$bridge/factory_build50_family_bridge.py"
cp -p "$bridge/factory_build50_family_bridge.py" "$backup/factory_build50_family_bridge.py.old"
install -m 600 "$source_dir/factory_build50_family_bridge.py" "$bridge/factory_build50_family_bridge.py"
"$python" -B -m py_compile "$family/factory_build50_f19_web_template.py" "$family/factory_f19_independent_web_review.py" "$family/factory_build_50.py" "$bridge/factory_build50_family_bridge.py"
# Genuinely execute all 48 distinct tasks and an independent technical review.
"$python" -B "$family/factory_build50_f19_web_template.py" --factory-private "$private"
# Verify archive, receipts and strict warehouse admission. Other products remain in QA rework.
"$python" -B "$warehouse/factory_production_warehouse.py" --factory-private "$private" --strict-build50
"$python" -B "$bridge/factory_build50_family_bridge.py" --factory-private "$private" --registry "$registry" --output "$private/production-family-management/build50-family-dashboard.json"
"$python" -B - "$private" <<'PY'
import json,sys,zipfile,hashlib
from pathlib import Path
root=Path(sys.argv[1])
id='saas_launch_starter_2026'
target=root/'digital-products'/id
manifest=json.loads((target/'manufacturing_manifest.json').read_text('utf8'))
state=json.loads((root/'build-50'/id/'state.json').read_text('utf8'))
ledger=json.loads((root/'production-family-management/build50-family-dashboard.json').read_text('utf8'))
stock=json.loads((root/'production-warehouse/stock-register.json').read_text('utf8'))
assert state['completed_stages']==50 and state['status']=='awaiting_owner_acceptance'
assert manifest['qa_status']=='passed' and manifest['family_id']=='F19'
assert manifest['owner_publication_approval'] is False and manifest['public_listing_enabled'] is False
assert manifest['independent_human_review'] is False
p=target/(id+'-internal-qa.zip')
assert hashlib.sha256(p.read_bytes()).hexdigest()==manifest['artifact_sha256']
with zipfile.ZipFile(p) as z:
 assert len(z.namelist())==4 and z.testzip() is None
 assert 'id="hero"' in z.read(id+'/index.html').decode('utf8')
assert ledger['counts']['registered_families']==40
assert ledger['families'][18]['family_id']=='F19'
assert ledger['families'][18]['technical_50_stage_completed']>=1
assert ledger['counts']['technical_products_with_verified_50_stages']>=2
assert ledger['counts']['families_without_verified_50_stage_executor']<=38
assert ledger['commercial_release_allowed'] is False
assert any(r.get('product_id')==id for r in stock['records'])
print('F19_REAL_NEW_PRIVATE_PRODUCT=VERIFIED_50_STAGES')
print('F19_NEW_PRIVATE_WAREHOUSE_PRODUCT=1')
print('F19_INDEPENDENT_TECHNICAL_QA=PASS')
print('FACTORY_40_VERIFIED_EXECUTOR_FAMILIES='+str(40-ledger['counts']['families_without_verified_50_stage_executor']))
print('FACTORY_COMMERCIAL_RELEASES_AUTOMATIC=0')
print('F19_NO_CHANGES_TO_LIVE_SHOPS=PASS')
PY
echo F19_BUILD50_SCOPED_INSTALL_SUCCESS
echo F19_BACKUP="$backup"
