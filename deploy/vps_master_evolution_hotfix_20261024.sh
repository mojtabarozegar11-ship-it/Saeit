#!/usr/bin/env bash
# One-shot, hash-anchored repair of the existing PRIVATE VPS master evolution module.
# Does not seed agents, touch websites, edit cron, spawn workers, or change the DB.
set -euo pipefail
umask 077
test "$(id -un)" = githubops
test "$#" -eq 3
expected_old="$1"
expected_new="$2"
candidate="$3"
base="$HOME/factory-runtime"
root="$base/operations/master-agent"
private="$base/private/master-agent"
backups="$base/operations/backups"
state="$private/evolution.json"
py="$base/.venv/bin/python"
test -x "$py" && test -d "$root" && test -d "$private"
test -f "$root/evolution.py" && test ! -L "$root/evolution.py"
test -f "$candidate" && test ! -L "$candidate"
test -f "$state" && test ! -L "$state"
test "$(sha256sum "$candidate" | awk '{print $1}')" = "$expected_new"
command -v flock >/dev/null
command -v crontab >/dev/null
exec 8>"$root/activation.lock"
flock -w 25 8
exec 9>"$root/master-evolution.lock"
flock -w 25 9
current="$(sha256sum "$root/evolution.py" | awk '{print $1}')"
if test "$current" = "$expected_new"; then
  echo MASTER_HOTFIX_ALREADY_INSTALLED
  exit 0
fi
test "$current" = "$expected_old" || { echo MASTER_HOTFIX_SOURCE_DRIFT_STOP; exit 77; }
cron_before="$(crontab -l | sha256sum | awk '{print $1}')"
"$py" - "$state" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
if not p.is_file() or p.is_symlink() or p.stat().st_size > 2000000:
    raise SystemExit("MASTER_HOTFIX_STATE_INVALID")
obj = json.loads(p.read_text(encoding="utf-8"))
if not isinstance(obj, dict) or obj.get("schema") != "saeit.master.evolution.v1":
    raise SystemExit("MASTER_HOTFIX_STATE_SCHEMA_MISMATCH")
if obj.get("max_steps") not in (1, 2, 3):
    raise SystemExit("MASTER_HOTFIX_STEPS_INVALID")
print("MASTER_HOTFIX_PRIVATE_STATE_PREFLIGHT_OK")
PY
install -d -m 700 "$backups"
backup_source="$backups/master-evolution-before-${expected_new:0:12}.py"
backup_state="$backups/master-evolution-state-before-${expected_new:0:12}.json"
test ! -e "$backup_source" && test ! -L "$backup_source" && test ! -e "$backup_state" && test ! -L "$backup_state" || { echo MASTER_HOTFIX_BACKUP_COLLISION_STOP; exit 78; }
cp -p "$root/evolution.py" "$backup_source"
cp -p "$state" "$backup_state"
chmod 600 "$backup_source" "$backup_state"
test "$(sha256sum "$backup_source" | awk '{print $1}')" = "$expected_old"
changed=0
rollback_on_failure() {
  rc=$?
  trap - EXIT
  if test "$rc" -ne 0 && test "$changed" -eq 1; then
    set +e
    cp -p "$backup_source" "$root/evolution.py.rollback.tmp"
    mv -f "$root/evolution.py.rollback.tmp" "$root/evolution.py"
    cp -p "$backup_state" "$state"
    echo MASTER_HOTFIX_ROLLBACK_ATTEMPTED
  fi
  exit "$rc"
}
trap rollback_on_failure EXIT
trap 'exit 143' TERM
cp -p "$candidate" "$root/evolution.py.hotfix.tmp"
chmod 600 "$root/evolution.py.hotfix.tmp"
test "$(sha256sum "$root/evolution.py.hotfix.tmp" | awk '{print $1}')" = "$expected_new"
changed=1
mv -f "$root/evolution.py.hotfix.tmp" "$root/evolution.py"
"$py" - "$root/evolution.py" <<'PY'
import ast, sys
from pathlib import Path
ast.parse(Path(sys.argv[1]).read_text(encoding="utf-8"))
print("MASTER_HOTFIX_LIVE_SOURCE_SYNTAX_OK")
PY
export SAEIT_ENV=production MOJ_FACTORY_LOCAL_MODE=1 DJANGO_SETTINGS_MODULE=config.settings
cd "$base/django-app"
db="$("$py" - <<'PY'
from django.conf import settings
print(settings.DATABASES["default"]["NAME"])
PY
)"
test -n "$db"
"$py" -B "$root/evolution.py" --db "$db" --state "$state"
"$py" - "$state" <<'PY'
import json, sys
from pathlib import Path
obj = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
mark = obj.get("completion_watermark")
if not isinstance(mark, dict) or type(mark.get("complete")) is not bool:
    raise SystemExit("MASTER_HOTFIX_WATERMARK_MISSING")
if obj.get("max_steps") not in (1, 2, 3):
    raise SystemExit("MASTER_HOTFIX_RESULT_INVALID")
print("MASTER_HOTFIX_LIVE_WATERMARK_VERIFIED")
PY
test "$(sha256sum "$root/evolution.py" | awk '{print $1}')" = "$expected_new"
test "$(crontab -l | sha256sum | awk '{print $1}')" = "$cron_before"
echo MASTER_HOTFIX_CRON_UNCHANGED
echo MASTER_HOTFIX_PRIVATE_DEPLOY_VERIFIED
