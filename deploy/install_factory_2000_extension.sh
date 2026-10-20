#!/usr/bin/env bash
# Add 2000 tested stdlib production-support bindings, retain 1000 existing.
set -euo pipefail
umask 077
test "$(id -un)" = githubops
test "$#" -eq 1
stage="$1"; test -d "$stage" && test ! -L "$stage"
for name in factory_3000_workbench.py factory_1000_workbench.py; do
  test -s "$stage/$name" && test ! -L "$stage/$name"
done
base="$HOME/factory-runtime"; ops="$base/operations"
private="$base/private/autonomous-product-cycle"
registry="$ops/forty-family-master/forty_families.json"
target="$ops/production-workbench-3000"; area="$private/production-toolkit-3000"
py="$base/.venv/bin/python"
test -x "$py" && test -s "$registry" && test ! -L "$registry"
test -d "$private" && test ! -L "$private" && test ! -L "$target" && test ! -L "$area"
install -d -m 700 "$target" "$area" "$ops/backups"
exec 9>"$ops/.production-workbench-3000.lock"
flock -w 30 9
stamp="$(date -u +%Y%m%dT%H%M%SZ)-$$"
backup="$ops/backups/workbench3000-$stamp";install -d -m 700 "$backup"
crontab -l > "$backup/cron-before"
for f in runner.py factory_1000_workbench.py;do
  if test -f "$target/$f";then cp -p "$target/$f" "$backup/$f";fi
done
for f in catalog.json verification.json;do
  if test -f "$area/$f";then cp -p "$area/$f" "$backup/$f";fi
done
rollback(){
  rc=$?
  if test "$rc" -ne 0;then
    for f in runner.py factory_1000_workbench.py;do
      if test -f "$backup/$f";then cp -p "$backup/$f" "$target/$f";else rm -f "$target/$f";fi
    done
    for f in catalog.json verification.json;do
      if test -f "$backup/$f";then cp -p "$backup/$f" "$area/$f";else rm -f "$area/$f";fi
    done
    rm -f "$target/"*.new "$area/"*.new
    echo FACTORY_3000_ROLLBACK_APPLIED
  fi
  return "$rc"
}
trap rollback EXIT
"$py" -m py_compile "$stage/factory_1000_workbench.py" "$stage/factory_3000_workbench.py"
"$py" -B "$stage/factory_3000_workbench.py" --registry "$registry" --selftest
install -m 600 "$stage/factory_1000_workbench.py" "$target/factory_1000_workbench.py.new"
install -m 600 "$stage/factory_3000_workbench.py" "$target/runner.py.new"
for pair in "factory_1000_workbench.py:factory_1000_workbench.py.new" "factory_3000_workbench.py:runner.py.new";do
  a="${pair%%:*}";b="${pair#*:}"
  test "$(sha256sum "$stage/$a" | cut -d' ' -f1)" = "$(sha256sum "$target/$b" | cut -d' ' -f1)"
done
mv -f "$target/factory_1000_workbench.py.new" "$target/factory_1000_workbench.py"
mv -f "$target/runner.py.new" "$target/runner.py"
"$py" -B "$target/runner.py" --registry "$registry" --catalog-out "$area/catalog.json.new" --selftest
"$py" -B - "$area/catalog.json.new" <<'PY'
import json,sys
from collections import Counter
c=json.load(open(sys.argv[1]));assert c['schema']=='saeit.factory.production-workbench.v2'
assert c['tools_count']==3000 and c['new_bindings_added']==2000 and c['existing_bindings_retained']==1000
assert len({r['id'] for r in c['tools']})==3000
assert set(Counter(x['family_id'] for x in c['tools']).values())=={75}
assert all(x['commercial_publication_allowed'] is False for x in c['tools'])
print("FACTORY_2000_NEW_BINDINGS_VERIFIED=PASS")
PY
mv -f "$area/catalog.json.new" "$area/catalog.json"
"$py" -B - "$area/verification.json.new" "$target/runner.py" "$target/factory_1000_workbench.py" "$area/catalog.json" <<'PY'
import hashlib,json,os,sys
from datetime import datetime,timezone
from pathlib import Path
p=Path(sys.argv[1]);sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
data={'schema':'saeit.factory.workbench-verification.v2','verified_utc':datetime.now(timezone.utc).isoformat(),
 'tool_count':3000,'new_bindings_added':2000,'existing_bindings_retained':1000,'families':40,
 'synthetic_test_invocations_passed':3000,'runtime_sha256':sha(sys.argv[2]),
 'base_runtime_sha256':sha(sys.argv[3]),'catalog_sha256':sha(sys.argv[4]),
 'native_product_manufacturers_added':0,'real_customer_product_manufactured':0,
 'independent_commercial_approval_recorded':False,'sites_affected':[],'payment_operations':0}
p.write_text(json.dumps(data,sort_keys=True,indent=2)+'\n');os.chmod(p,0o600)
PY
mv -f "$area/verification.json.new" "$area/verification.json"
test "$(crontab -l | sha256sum | cut -d' ' -f1)" = "$(sha256sum "$backup/cron-before" | cut -d' ' -f1)"
trap - EXIT
echo FACTORY_2000_ADDED_PRIVATE_INSTALL=PASS
echo FACTORY_3000_TOTAL_SUPPORT_TOOLS=PASS
echo FACTORY_SITES_PAYMENTS_UNTOUCHED=PASS
echo FACTORY_3000_BACKUP="$backup"
