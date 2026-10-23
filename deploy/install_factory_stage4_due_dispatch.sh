#!/usr/bin/env bash
# Install a private, idempotent Stage4 due-to-task bridge on the VPS.
set -euo pipefail
umask 077

test "$(id -un)" = githubops
test "$#" -eq 2
staged="$1"
expected_sha="$2"
base="$HOME/factory-runtime"
ops="$base/operations"
app="$base/django-app"
target="$ops/stage4-due-dispatch.py"
backup_dir="$ops/backups/stage4-due-dispatch"
receipt_dir="$ops/evidence/stage4-due-dispatch"
python="$base/.venv/bin/python"
master="$app/core/autonomous_brain.py"

for path in "$ops" "$app" "$master" "$staged" "$python"; do
  test ! -L "$path"
done
test -d "$ops" && test -d "$app" && test -f "$master"
test -f "$staged" && test -x "$python"
test "$(sha256sum "$staged" | cut -d' ' -f1)" = "$expected_sha"
test "$(sha256sum "$master" | cut -d' ' -f1)" = 8b1e268ece7e9d5aacb496679cdfc2003bc2f3f9a58828cc398f651afd7d1ab1
test ! -L "$target"
test ! -L "$backup_dir" && test ! -L "$receipt_dir"
command -v crontab >/dev/null
ps -eo comm= | grep -Eq '^(cron|crond)$'
"$python" -B -m py_compile "$staged"

mkdir -p -m 700 "$backup_dir" "$receipt_dir"
if test -f "$target"; then
  prior="$(sha256sum "$target" | cut -d' ' -f1)"
  backup="$backup_dir/dispatch-$prior.py"
  if test -f "$backup"; then
    cmp -s "$target" "$backup"
  else
    cp -p -- "$target" "$backup"
    chmod 600 "$backup"
  fi
fi
install -m 700 -- "$staged" "$target"
test "$(sha256sum "$target" | cut -d' ' -f1)" = "$expected_sha"

cd "$app"
export SAEIT_ENV=production MOJ_FACTORY_LOCAL_MODE=1
"$python" -B "$target" --root "$ops" --batch 12 | tee "$receipt_dir/preflight-$expected_sha.txt"
# A small first batch confirms that the real native master can create the
# pre-existing capability-authorized task. The worker remains in charge of QA.
"$python" -B "$target" --root "$ops" --apply --batch 6 | tee "$receipt_dir/pilot-$expected_sha.txt"
"$python" -B - "$receipt_dir/pilot-$expected_sha.txt" <<'PY'
import json,sys
from pathlib import Path
line=Path(sys.argv[1]).read_text(encoding="utf8").strip().splitlines()[-1]
if not line.startswith("STAGE4_DUE_DISPATCH="):
    raise SystemExit("STAGE4_PILOT_RECEIPT_MISSING")
obj=json.loads(line.partition("=")[2])
c=obj["counts"]
if c.get("due_seen",0)>0 and c.get("queued",0)+c.get("approval_gated",0)==0:
    raise SystemExit("STAGE4_PILOT_NO_TASKS_QUEUED")
print("STAGE4_PILOT_TASKS="+str(c.get("queued",0)))
print("STAGE4_PILOT_GATED="+str(c.get("approval_gated",0)))
PY

cron_before="$(mktemp "$ops/.stage4-cron-before.XXXXXX")"
cron_after="$(mktemp "$ops/.stage4-cron-after.XXXXXX")"
cron_error="$(mktemp "$ops/.stage4-cron-error.XXXXXX")"
trap 'rm -f -- "$cron_before" "$cron_after" "$cron_error"' EXIT
if ! crontab -l > "$cron_before" 2> "$cron_error"; then
  grep -Eiq 'no crontab' "$cron_error" || { echo STAGE4_CRON_READ_FAILED; exit 1; }
fi
marker='saeit-stage4-due-dispatch-v1'
if grep -Fq -- "$marker" "$cron_before"; then
  test "$(grep -Fc -- "$marker" "$cron_before")" = 1
  grep -F -- "$marker" "$cron_before" | grep -Fq -- "$target"
  echo STAGE4_CRON=ALREADY_PRESENT
else
  cp -- "$cron_before" "$backup_dir/crontab-prestage4-$expected_sha.txt"
  chmod 600 "$backup_dir/crontab-prestage4-$expected_sha.txt"
  cp -- "$cron_before" "$cron_after"
  printf '\n* * * * * cd %s && SAEIT_ENV=production MOJ_FACTORY_LOCAL_MODE=1 %s -B %s --root %s --apply --batch 12 >> %s/stage4-due-dispatch.log 2>&1 # %s\n' \
    "$app" "$python" "$target" "$ops" "$ops" "$marker" >> "$cron_after"
  crontab "$cron_after"
  echo STAGE4_CRON=INSTALLED_EVERY_MINUTE
fi
echo "STAGE4_DISPATCH_SOURCE_SHA256=$expected_sha"
echo STAGE4_SITE_FILES_MODIFIED=0
echo STAGE4_QUALITY_APPROVAL_AUTOGRANTED=NO
echo STAGE4_FACTORY_TASK_DISPATCH=ACTIVATED
