#!/usr/bin/env bash
# One isolated, rollback-protected release of 1000 executable offline
# production-SUPPORT tools. No sale, product approval, native renderer claims.
set -euo pipefail
umask 077
test "$(id -un)" = githubops
test "$#" -eq 1
stage="$1"
test -d "$stage" && test ! -L "$stage"
test -s "$stage/factory_1000_workbench.py" && test ! -L "$stage/factory_1000_workbench.py"
base="$HOME/factory-runtime"
ops="$base/operations"
private="$base/private/autonomous-product-cycle"
registry="$ops/forty-family-master/forty_families.json"
target="$ops/production-workbench-1000"
catalog_dir="$private/production-toolkit"
python="$base/.venv/bin/python"
test -x "$python" && test -d "$private" && test ! -L "$private"
test -s "$registry" && test ! -L "$registry"
test ! -L "$target" && test ! -L "$catalog_dir"
install -d -m 700 "$target" "$catalog_dir" "$ops/backups"
exec 9>"$ops/.production-workbench-1000-deploy.lock"
/usr/bin/flock -w 30 9 || { echo WORKBENCH_INSTALL_LOCKED;exit 1; }
stamp="$(date -u +%Y%m%dT%H%M%SZ)-$$"
backup="$ops/backups/workbench1000-$stamp"
install -d -m 700 "$backup"
crontab -l > "$backup/crontab-before.txt"
chmod 600 "$backup/crontab-before.txt"
previous=0
if test -f "$target/runner.py";then
  test ! -L "$target/runner.py"
  cp -p "$target/runner.py" "$backup/runner.py"
  previous=1
fi
for name in catalog.json verification.json;do
  if test -f "$catalog_dir/$name";then
    test ! -L "$catalog_dir/$name"
    cp -p "$catalog_dir/$name" "$backup/$name"
  fi
done
rollback() {
  rc=$?
  if test "$rc" -ne 0;then
    if test "$previous" -eq 1;then
      cp -p "$backup/runner.py" "$target/runner.py"
    else
      rm -f -- "$target/runner.py"
    fi
    for name in catalog.json verification.json;do
      if test -s "$backup/$name";then
        cp -p "$backup/$name" "$catalog_dir/$name"
      else
        rm -f -- "$catalog_dir/$name"
      fi
    done
    echo WORKBENCH_SCOPED_ROLLBACK_APPLIED
  fi
  return "$rc"
}
trap rollback EXIT
"$python" -m py_compile "$stage/factory_1000_workbench.py"
"$python" -B "$stage/factory_1000_workbench.py" --registry "$registry" --selftest
cp -p "$stage/factory_1000_workbench.py" "$target/runner.py.new"
chmod 600 "$target/runner.py.new"
test "$(sha256sum "$stage/factory_1000_workbench.py" | awk '{print $1}')" = "$(sha256sum "$target/runner.py.new" | awk '{print $1}')"
mv -f "$target/runner.py.new" "$target/runner.py"
"$python" -B "$target/runner.py" --registry "$registry" --catalog-out "$catalog_dir/catalog.json.new" --selftest
"$python" -B - "$catalog_dir/catalog.json.new" <<'PY'
import json,sys
from collections import Counter
from pathlib import Path
data=json.loads(Path(sys.argv[1]).read_text(encoding='utf8'))
assert data['schema']=='saeit.factory.production-workbench.v1'
assert data['tools_count']==1000 and data['families']==40
assert len({x['id'] for x in data['tools']})==1000
assert all(x['commercial_publication_allowed'] is False for x in data['tools'])
assert all(x['scope']=='production_support_not_native_family_manufacturer' for x in data['tools'])
by_family=Counter(x['family_id'] for x in data['tools'])
assert set(by_family.values())=={25} and len(by_family)==40
assert data['native_manufacturing_executors_added']==0
print('WORKBENCH_1000_UNIQUE_EXECUTABLE_TOOL_BINDINGS=PASS')
print('WORKBENCH_FORTY_FAMILIES_TIMES_TWENTYFIVE=PASS')
PY
mv -f "$catalog_dir/catalog.json.new" "$catalog_dir/catalog.json"
"$python" -B - "$catalog_dir/verification.json.new" "$target/runner.py" "$catalog_dir/catalog.json" <<'PY'
import hashlib,json,sys,os
from pathlib import Path
from datetime import datetime,timezone
path=Path(sys.argv[1]);runner=Path(sys.argv[2]);catalog=Path(sys.argv[3])
doc={'schema':'saeit.factory.workbench-verification.v1',
     'verified_utc':datetime.now(timezone.utc).isoformat(),
     'tool_count':1000,'families':40,'synthetic_test_invocations_passed':1000,
     'runtime_sha256':hashlib.sha256(runner.read_bytes()).hexdigest(),
     'catalog_sha256':hashlib.sha256(catalog.read_bytes()).hexdigest(),
     'real_customer_product_manufactured_by_this_release':0,
     'independent_commercial_approval_recorded':False,
     'sites_affected':[],'payment_operations':0,
     'executable_operations_per_family':25,
     'unsupported_native_manufacturing_engines_unmodified':True}
path.write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n',encoding='utf8')
os.chmod(path,0o600)
PY
mv -f "$catalog_dir/verification.json.new" "$catalog_dir/verification.json"
test "$(crontab -l | sha256sum | awk '{print $1}')" = "$(sha256sum "$backup/crontab-before.txt" | awk '{print $1}')"
for marker in SAEIT_FACTORY_EVERY_MINUTE_V1 SAEIT_FACTORY_LIFECYCLE_12_V1 SAEIT_FACTORY_FORTY_FAMILY_OPERATIONAL_DISPATCH_V1;do
  test "$(crontab -l | grep -c "$marker")" -eq 1
done
trap - EXIT
echo WORKBENCH_1000_PRIVATE_INSTALL=PASS
echo WORKBENCH_1000_NO_SITE_CHANGES=PASS
echo WORKBENCH_BACKUP="$backup"
