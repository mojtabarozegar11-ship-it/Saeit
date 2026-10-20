#!/usr/bin/env bash
# Private, transactional source install; execute source-bound technical package repairs.
set -euo pipefail
umask 077
test "$(id -un)" = githubops && test "$#" -eq 1
stage="$1";test -d "$stage" && test ! -L "$stage"
base="$HOME/factory-runtime";ops="$base/operations"
root="$base/private/autonomous-product-cycle"
target="$ops/mpw-stage1-technical-repair"
scheduler="$ops/forty-execution/periodic-dispatch.sh"
py="$base/.venv/bin/python"
test -x "$py" && test -d "$root" && test ! -L "$root"
test -f "$scheduler" && test ! -L "$scheduler"
test "$(crontab -l|grep -c SAEIT_FACTORY_FORTY_FAMILY_OPERATIONAL_DISPATCH_V1)" -eq 1
exec 9>"$ops/.mpw-repair-install.lock";flock -w 35 9
install -d -m 700 "$target" "$ops/backups"
backup="$ops/backups/mpw-stage1-real-repair-$(date -u +%Y%m%dT%H%M%SZ)-$$"
install -d -m 700 "$backup"
files="mpw_factory_stage1_technical_repair.py mpw_vps_warehouse_courier.py factory_customer_packager.py factory_native_customer_packager.py factory_product_maker.py"
for file in $files;do
 test -s "$stage/$file" && test ! -L "$stage/$file"
 if test -f "$target/$file";then test ! -L "$target/$file";cp -p "$target/$file" "$backup/$file";fi
done
cp -p "$scheduler" "$backup/periodic-dispatch.sh"
crontab -l > "$backup/crontab"
install_stage=source_install
rollback(){
 code=$?
 if test "$code" -ne 0;then
  printf 'MPW_STAGE1_INSTALL_FAILURE_STAGE=%s EXIT_CODE=%s\n' "$install_stage" "$code" >&2
  for file in $files;do
   if test -f "$backup/$file";then cp -p "$backup/$file" "$target/$file";else rm -f "$target/$file";fi
  done
  cp -p "$backup/periodic-dispatch.sh" "$scheduler"
  rm -f "$scheduler.new"
  echo MPW_TECHNICAL_REPAIR_CODE_ROLLBACK=PASS
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
install_stage=disk_reserve
# `df -Pk` reports KiB; 262144 KiB = 256 MiB (not 256 GiB).
free_kib="$(df -Pk "$root" | awk 'END {print $4}')"
case "$free_kib" in ''|*[!0-9]*) echo MPW_STAGE1_DISK_METRIC_INVALID >&2; exit 1;; esac
if test "$free_kib" -lt 262144;then
  printf 'MPW_STAGE1_DISK_INSUFFICIENT_KIB=%s REQUIRED_KIB=262144\n' "$free_kib" >&2
  exit 1
fi
echo MPW_STAGE1_DISK_RESERVE_256MIB=PASS
install_stage=technical_repair
timeout 490s "$py" -B "$target/mpw_factory_stage1_technical_repair.py" --factory-private "$root" --max-new 43
install_stage=verify_repair_receipts
"$py" -B - "$root" <<'PY'
import json,sys
from pathlib import Path
root=Path(sys.argv[1])
base=root/'design-state/mojplaywin-actual-technical-repair'
report=json.loads((base/'execution-status.json').read_text())
assert report['schema']=='mpw.factory.stage1-executed-technical-repair.v1'
assert report['tenant']=='mojplaywin-main'
assert len(report['results'])==report['returned_products_inspected']
assert report['returned_products_inspected']<=50
assert report['source_product_rebuilds_verified']==0
assert report['commercially_approved_returns']==0
assert report['stage1_returns_remaining_open']==report['returned_products_inspected']
assert report['public_store_products_modified']==0
for item in report['results']:
    assert item['human_release_pending'] is True
    assert item['consumer_bundle_status'] in (
        'new_independently_verified','preexisting_independently_verified',
        'held_for_rework','absent','new_native_structure_verified_private_review',
        'preexisting_native_private_preview_verified')
print('VPS_MPW_RETURNED_PRODUCTS_INDEPENDENTLY_AUDITED='+str(report['returned_products_inspected']))
print('VPS_MPW_SOURCE_ZIPS_VERIFIED='+str(report['original_stock_zips_verified']))
print('VPS_MPW_ACTUAL_NEW_BUYER_BUNDLES='+str(report['new_customer_bundles_technically_repaired']))
print('VPS_MPW_NEW_NATIVE_PRIVATE_PREVIEWS='+str(report['new_native_private_previews_statically_validated']))
print('VPS_MPW_EXISTING_NATIVE_PRIVATE_PREVIEWS='+str(report['existing_native_private_previews_revalidated']))
print('VPS_MPW_REPAIR_BLOCKED='+str(report['technical_package_attempts_blocked']))
print('VPS_MPW_HUMAN_QA_UNRESOLVED='+str(report['independent_content_rights_review_still_required']))
PY
install_stage=scheduler_hook
"$py" -B - "$scheduler" "$scheduler.new" "$py" <<'PY'
from pathlib import Path
import sys
src=Path(sys.argv[1]);dst=Path(sys.argv[2]);contents=src.read_text()
hook='/usr/bin/timeout 90s "'+sys.argv[3]+'" -B "$HOME/factory-runtime/operations/mpw-stage1-technical-repair/mpw_factory_stage1_technical_repair.py" --factory-private "$HOME/factory-runtime/private/autonomous-product-cycle" --max-new 3 || echo MPW_REPAIR_TECHNICAL_REWORK_PENDING\n'
assert contents.count('set -euo pipefail')==1
assert 'mpw_factory_stage1_technical_repair.py' not in contents or hook in contents
if hook not in contents:
 contents=contents.replace('set -euo pipefail\n','set -euo pipefail\n'+hook,1)
assert contents.count('mpw_factory_stage1_technical_repair.py')==1
dst.write_text(contents);dst.chmod(src.stat().st_mode&0o777)
PY
bash -n "$scheduler.new";mv -f "$scheduler.new" "$scheduler"
install_stage=cron_integrity
 test "$(crontab -l|sha256sum|cut -d' ' -f1)" = "$(sha256sum "$backup/crontab"|cut -d' ' -f1)"
trap - EXIT
echo MPW_REAL_PRIVATE_TECHNICAL_REWORK_EXECUTION=PASS
echo MPW_REPAIR_EXISTING_FIVE_MINUTE_SCHEDULER=PASS
echo MPW_SOURCE_VERSION_AND_SITES_AND_PAYMENTS_UNCHANGED=PASS
