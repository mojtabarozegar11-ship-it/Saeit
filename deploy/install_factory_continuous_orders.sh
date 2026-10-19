#!/usr/bin/env bash
# Wire the continuous private work order generator into the VPS minutely
# factory cycle between manufacturing/research and warehouse, with no sites.
set -euo pipefail
umask 077
test "$(id -un)" = githubops
test "$(id -u)" -ne 0
test "$#" -eq 1
source_file="$1"
test -f "$source_file" && test ! -L "$source_file"
base="$HOME/factory-runtime"
ops="$base/operations"
private="$base/private/autonomous-product-cycle"
runner="$ops/production-warehouse/run-minute-cycle.sh"
destdir="$ops/production-instructions"
dest="$destdir/generate-orders.py"
python="$base/.venv/bin/python"
marker="FACTORY_AUTONOMOUS_WORK_ORDER_GENERATOR_V1"
test -d "$ops" && test ! -L "$ops"
test -d "$private" && test ! -L "$private"
test -x "$python"
test -f "$runner" && test ! -L "$runner"
test -s "$private/research-dossiers/autonomous-portfolio.json"
test "$(crontab -l | grep -c SAEIT_FACTORY_EVERY_MINUTE_V1)" -eq 1
command -v flock >/dev/null
exec 8>"$ops/.production-instructions-deploy.lock"
flock -w 30 8 || { echo FACTORY_ORDER_DEPLOY_LOCK_BUSY; exit 1; }
test ! -L "$destdir"
install -d -m 700 "$destdir" "$ops/backups"
stamp="$(date -u +%Y%m%dT%H%M%SZ)-$$"
back="$ops/backups/production-orders-$stamp"
install -d -m 700 "$back"
cp -p "$runner" "$back/original-minute-runner.sh"
chmod 600 "$back/original-minute-runner.sh"
if test -f "$dest"; then
  test ! -L "$dest"
  cp -p "$dest" "$back/original-generator.py"
  chmod 600 "$back/original-generator.py"
fi
"$python" -B -c 'import ast,sys;ast.parse(open(sys.argv[1],encoding="utf8").read())' "$source_file"
temporary="$(mktemp "$destdir/.generator.XXXXXX")"
install -m 600 "$source_file" "$temporary"
mv -f -- "$temporary" "$dest"
chmod 600 "$dest"

# Only patch a known and currently deployed minutely factory runner.
"$python" -B - "$runner" "$dest" "$private" "$marker" <<'PY'
from pathlib import Path
import os,sys,tempfile
path=Path(sys.argv[1]); dest=Path(sys.argv[2]); root=Path(sys.argv[3]);marker=sys.argv[4]
original=path.read_text(encoding="utf8")
needle="# Stock existing valid goods even if the current manufacturing cycle fails."
footer='test "$mfg_rc" -eq 0 && test "$wh_rc" -eq 0'
if original.count(needle)!=1:
    raise RuntimeError("FACTORY_ORDER_UNKNOWN_MINUTE_RUNNER")
if marker in original:
    if original.count(marker)!=1:raise RuntimeError("FACTORY_ORDER_DUPLICATE_MARKER")
    print("FACTORY_ORDER_GENERATOR_ALREADY_WIRED")
    sys.exit(0)
if original.count(footer)!=1:raise RuntimeError("FACTORY_ORDER_UNKNOWN_RUNNER_FOOTER")
insert=f'''# {marker}
order_rc=0
"$HOME/factory-runtime/.venv/bin/python" -B "{dest}" --factory-private "{root}" || order_rc=$?
if test "$order_rc" -eq 0; then
  echo FACTORY_WORK_ORDER_ENGINE=ok
else
  echo "FACTORY_WORK_ORDER_ENGINE_ERROR=$order_rc"
fi
'''
patched=original.replace(needle,insert+needle,1)
patched=patched.replace(footer,footer+' && test "$order_rc" -eq 0',1)
if patched.count(marker)!=1 or patched.count(needle)!=1:
    raise RuntimeError("FACTORY_ORDER_INSERTION_FAILED")
fd,temp=tempfile.mkstemp(prefix=".minute-atomic-",dir=str(path.parent))
try:
    os.fchmod(fd,0o700)
    with os.fdopen(fd,"w",encoding="utf8") as stream:
        stream.write(patched);stream.flush();os.fsync(stream.fileno())
    os.replace(temp,str(path))
finally:
    if os.path.exists(temp):os.unlink(temp)
PY
bash -n "$runner"
test "$(grep -c "$marker" "$runner")" -eq 1

# Validate with the actual 25 factory dossiers. No stock file is touched.
"$python" -B "$dest" --factory-private "$private"
"$python" -B - "$private/production-instructions/order-status.json" <<'PY'
import json,sys
from pathlib import Path
state=json.loads(Path(sys.argv[1]).read_text(encoding="utf8"))
assert state["schema"]=="saeit.factory.production-instructions.v1"
assert state["last_action"] in ("issued","capacity_hold","no_new_meaningful_input")
assert state["distribution_enabled"] is False
assert state["site_connection_required"] is False
assert state["candidate_instructions"]>0
print("FACTORY_WORK_ORDER_ENGINE_INSTALLED=PASS")
print("FACTORY_WORK_ORDER_LAST_ACTION="+state["last_action"])
print("FACTORY_WORK_ORDERS_ISSUED_TOTAL="+str(state["instructions_issued_total"]))
print("FACTORY_WORK_ORDERS_PENDING="+str(state["pending_instructions"]))
PY
test "$(crontab -l | grep -c SAEIT_FACTORY_EVERY_MINUTE_V1)" -eq 1
echo FACTORY_WORK_ORDERS_EVERY_MINUTE=ENABLED
echo FACTORY_WORK_ORDERS_WEBSITE_INDEPENDENCE=true
echo FACTORY_WORK_ORDERS_WAREHOUSE_UNCHANGED=true
echo FACTORY_WORK_ORDERS_BACKUP="$back"
