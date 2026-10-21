#!/usr/bin/env bash
# Transactionally install measured private 40-family commercial offer preparation.
set -euo pipefail
umask 077
test "$(id -un)" = githubops && test "$#" -eq 1
stage="$1"
test -d "$stage" && test ! -L "$stage"
base="$HOME/factory-runtime"
ops="$base/operations"
root="$base/private/autonomous-product-cycle"
target="$ops/forty-execution"
module="$target/factory_commerce40_admission.py"
scheduler="$target/periodic-dispatch.sh"
registry="$ops/forty-family-master/forty_families.json"
py="$base/.venv/bin/python"
test -x "$py" && test -s "$registry" && test -s "$stage/factory_commerce40_admission.py"
test -s "$target/factory_build50_family_bridge.py" && test -s "$target/factory_40_family_master.py"
test -s "$target/factory_build_50.py" && test ! -L "$module"
test -f "$scheduler" && test ! -L "$scheduler"
test "$(crontab -l | grep -c SAEIT_FACTORY_FORTY_FAMILY_OPERATIONAL_DISPATCH_V1)" -eq 1
exec 9>"$ops/.commercial40-deployment.lock"
flock -w 30 9
# All agents that rewrite the same private dispatcher share this lock.
exec 8>"$ops/.forty-execution-shared-installer.lock"
flock -w 240 8
install -d -m 700 "$ops/backups"
backup="$ops/backups/commerce40-$(date -u +%Y%m%dT%H%M%SZ)-$$"
install -d -m 700 "$backup"
if test -f "$module";then cp -p "$module" "$backup/factory_commerce40_admission.py";fi
cp -p "$scheduler" "$backup/periodic-dispatch.sh"
crontab -l > "$backup/crontab"
rollback() {
 rc=$?
 if test "$rc" -ne 0;then
  if test -f "$backup/factory_commerce40_admission.py";then cp -p "$backup/factory_commerce40_admission.py" "$module";else rm -f "$module";fi
  cp -p "$backup/periodic-dispatch.sh" "$scheduler"
  rm -f "$module.new" "$scheduler.new"
  echo FACTORY_COMMERCE40_ROLLBACK=APPLIED
 fi
 return "$rc"
}
trap rollback EXIT
"$py" -B -m py_compile "$stage/factory_commerce40_admission.py"
install -m 600 "$stage/factory_commerce40_admission.py" "$module.new"
test "$(sha256sum "$stage/factory_commerce40_admission.py" | cut -d' ' -f1)" = "$(sha256sum "$module.new" | cut -d' ' -f1)"
mv -f "$module.new" "$module"
"$py" -B "$module" --factory-private "$root" --registry "$registry" --module-dir "$target"
# A single existing cron dispatcher drives recurring private readiness checks.
"$py" -B - "$scheduler" "$scheduler.new" <<'PY'
from pathlib import Path
import sys
source=Path(sys.argv[1]);dest=Path(sys.argv[2]);contents=source.read_text()
hook='/usr/bin/timeout 80s "$HOME/factory-runtime/.venv/bin/python" -B "$HOME/factory-runtime/operations/forty-execution/factory_commerce40_admission.py" --factory-private "$HOME/factory-runtime/private/autonomous-product-cycle" --registry "$HOME/factory-runtime/operations/forty-family-master/forty_families.json" --module-dir "$HOME/factory-runtime/operations/forty-execution" || echo FACTORY_COMMERCE40_READINESS_REQUIRES_REVIEW\n'
assert contents.count('set -euo pipefail')==1
assert 'factory_commerce40_admission.py' not in contents or hook in contents
if hook not in contents:
    contents=contents.replace('set -euo pipefail\n','set -euo pipefail\n'+hook,1)
assert contents.count('factory_commerce40_admission.py')==1
dest.write_text(contents);dest.chmod(source.stat().st_mode&0o777)
PY
bash -n "$scheduler.new";mv -f "$scheduler.new" "$scheduler"
"$py" -B - "$root" "$scheduler" <<'PY'
import json,sys
from pathlib import Path
root=Path(sys.argv[1])
data=json.loads((root/'commercial40/dashboard.json').read_text())
assert data['schema']=='saeit.factory.commerce40-readiness.v1'
assert data['private_commercial_sku_proposals']==40
assert len(data['rows'])==40
assert len({x['sku'] for x in data['rows']})==40
assert data['commercially_approved_families']==0 and data['sales_or_payments_processed']==0
assert data['sites_contacted']==0 and data['live_products_published_by_this_engine']==0
assert Path(sys.argv[2]).read_text().count('factory_commerce40_admission.py')==1
print('VPS_FACTORY_COMMERCE40_SKUS_PRIVATE=40')
print('VPS_FACTORY_COMMERCE40_VERIFIED_PRODUCT_FAMILIES='+str(data['genuine_verified_product_families']))
print('VPS_FACTORY_COMMERCE40_WITHOUT_TECHNICAL_PACKAGE='+str(data['families_without_trusted_package']))
print('VPS_FACTORY_COMMERCE40_VERIFIED_ZIPS='+str(data['strict_archives_verified']))
print('VPS_FACTORY_COMMERCE40_LIVE_SALES=0')
PY
test "$(crontab -l | sha256sum | cut -d' ' -f1)" = "$(sha256sum "$backup/crontab" | cut -d' ' -f1)"
trap - EXIT
echo VPS_FACTORY_COMMERCE40_DEPLOYMENT=PASS
echo VPS_FACTORY_COMMERCE40_SITES_AND_CHECKOUT=UNCHANGED
echo VPS_FACTORY_COMMERCE40_RECURRING_PRIVATE_REVALIDATION=PASS
echo VPS_FACTORY_COMMERCE40_BACKUP="$backup"
