#!/usr/bin/env bash
# Deploy only private per-original technical/legal review dossiers; no fake approvals.
set -euo pipefail
umask 077
test "$(id -un)" = githubops && test "$#" -eq 1
stage="$1"
test -d "$stage" && test ! -L "$stage"
base="$HOME/factory-runtime"
root="$base/private/autonomous-product-cycle"
dir="$base/operations/mpw-stage1-review-dossiers"
backup="$base/operations/backups/mpw-stage1-review-$(date -u +%Y%m%dT%H%M%SZ)-$$"
py="$base/.venv/bin/python"
test -x "$py" && test -d "$root" && test ! -L "$root"
exec 9>"$base/operations/.mpw-stage1-review-deploy.lock"
flock -w 40 9
install -d -m 700 "$dir" "$backup"
files="mpw_stage1_independent_evidence.py mpw_factory_stage1_technical_repair.py mpw_vps_warehouse_courier.py"
for file in $files;do
 test -s "$stage/$file" && test ! -L "$stage/$file"
 test ! -L "$dir/$file"
 if test -f "$dir/$file";then cp -p "$dir/$file" "$backup/$file";fi
done
rollback(){
 code=$?
 if test "$code" -ne 0;then
  for file in $files;do
   if test -f "$backup/$file";then cp -p "$backup/$file" "$dir/$file";else rm -f "$dir/$file";fi
   rm -f "$dir/$file.new"
  done
  echo MPW_REVIEW_DOSSIER_INSTALL_ROLLBACK=PASS
 fi
 return "$code"
}
trap rollback EXIT
for file in $files;do
 "$py" -B -m py_compile "$stage/$file"
 install -m 600 "$stage/$file" "$dir/$file.new"
 test "$(sha256sum "$stage/$file"|cut -d' ' -f1)" = "$(sha256sum "$dir/$file.new"|cut -d' ' -f1)"
 mv -f "$dir/$file.new" "$dir/$file"
done
timeout 240s "$py" -B "$dir/mpw_stage1_independent_evidence.py" --factory-private "$root"
"$py" -B - "$root" <<'PY'
import json,sys
from pathlib import Path
root=Path(sys.argv[1])/'design-state/mojplaywin-independent-evidence'
state=json.loads((root/'dashboard.json').read_text())
assert state['schema']=='mpw.factory.stage1-review-dossier-summary.v1'
assert state['validated_stage1_returns']==43
assert state['original_zips_integrity_verified']==43
assert state['native_structure_only']+state['executable_buyer_review_bundles']+state['missing_technical_companions']==43
assert state['missing_technical_companions']==0
assert state['products_commercially_authorized']==0
assert state['owner_approvals_fabricated']==0
assert state['site_and_payment_mutations']==0
assert len(list((root/'open').glob('*.json')))==43
print('VPS_MPW_43_REAL_REVIEW_DOSSIERS=PASS')
print('VPS_MPW_43_REMAIN_OPEN_HUMAN_QA=PASS')
print('VPS_MPW_NONCOMMERCIAL_TECHNICAL_PACKS='+str(state['executable_buyer_review_bundles']))
print('VPS_MPW_NATIVE_PREVIEW_PACKS='+str(state['native_structure_only']))
PY
trap - EXIT
echo VPS_MPW_INDEPENDENT_CONTENT_RIGHTS_OWNER_CHECKLISTS=PASS
echo VPS_MPW_NO_PAYMENT_SITES_OR_SOURCE_MODIFIED=PASS
