#!/usr/bin/env bash
# Install seven private technical producers without relaxing QA1000 or enabling sales.
set -euo pipefail
umask 077
test "$(id -un)" = githubops
test "$#" -eq 1
stage="$1"
test -d "$stage" && test ! -L "$stage"
base="$HOME/factory-runtime"
ops="$base/operations"
target="$ops/forty-execution"
root="$base/private/autonomous-product-cycle"
scheduler="$target/periodic-dispatch.sh"
py="$base/.venv/bin/python"
test -x "$py" && test -f "$scheduler" && test ! -L "$scheduler"
test -s "$target/factory_build_50.py"
exec 9>"$ops/.seven-gap-install.lock"
flock -w 80 9
exec 8>"$ops/.forty-execution-shared-installer.lock"
flock -w 180 8
install -d -m 700 "$ops/backups"
backup="$ops/backups/seven-gap-$(date -u +%Y%m%dT%H%M%SZ)-$$"
install -d -m 700 "$backup"
files="factory_seven_missing_builders.py factory_build50_f23_assistant.py factory_f23_assistant_independent_review.py factory_f23_offline_assistant_runtime.py"
for f in $files; do
  test -s "$stage/$f" && test ! -L "$stage/$f"
  if test -f "$target/$f"; then
    test ! -L "$target/$f"
    cp -p "$target/$f" "$backup/$f"
  fi
done
cp -p "$scheduler" "$backup/periodic-dispatch.sh"
crontab -l > "$backup/crontab"
rollback() {
  rc=$?
  if test "$rc" -ne 0; then
    for f in $files; do
      if test -f "$backup/$f"; then
        cp -p "$backup/$f" "$target/$f"
      else
        rm -f "$target/$f"
      fi
    done
    cp -p "$backup/periodic-dispatch.sh" "$scheduler"
    rm -f "$scheduler.new"
    echo SEVEN_GAP_INSTALL_ROLLED_BACK
  fi
  return "$rc"
}
trap rollback EXIT
for f in $files; do
  "$py" -B -m py_compile "$stage/$f"
  install -m 600 "$stage/$f" "$target/$f.new"
  test "$(sha256sum "$stage/$f" | cut -d' ' -f1)" = "$(sha256sum "$target/$f.new" | cut -d' ' -f1)"
  mv -f "$target/$f.new" "$target/$f"
done
# One bounded private attempt on all seven; if native dependencies are absent,
# retain honest source candidates and explicit missing-gate receipts.
set +e
/usr/bin/timeout 760s "$py" -B "$target/factory_seven_missing_builders.py" --factory-private "$root" > "$backup/first-cycle.jsonl"
first_rc=$?
set -e
test "$first_rc" -eq 0 || test "$first_rc" -eq 2
"$py" -B - "$backup/first-cycle.jsonl" <<'PY'
import json,sys
from pathlib import Path
line=Path(sys.argv[1]).read_text().strip().splitlines()[-1]
assert line.startswith("ZOMORODMELAL_SEVEN_GAP_BUILDERS=")
data=json.loads(line.split("=",1)[1])
assert len(data)==7 and {r["family_id"] for r in data}=={"F12","F13","F16","F17","F23","F26","F40"}
assert all(r["independent_quality_1000_passed"] is False for r in data)
print("SEVEN_GAP_ACTUAL_PRIVATE_PRODUCTION="+json.dumps(
    {x["family_id"]:x["status"] for x in data},sort_keys=True))
print("SEVEN_GAP_QUALITY_1000_INDEPENDENTLY_CERTIFIED=0")
PY
# Recompute the existing 40-family technical ledger from source-bound,
# independently rechecked receipts; prototypes lacking native proof remain red.
registry="$ops/forty-family-master/forty_families.json"
test -s "$registry" && test -s "$target/factory_commerce40_admission.py"
"$py" -B "$target/factory_commerce40_admission.py" --factory-private "$root" --registry "$registry" --module-dir "$target"
"$py" -B - "$scheduler" "$scheduler.new" <<'PY'
from pathlib import Path
import sys
src=Path(sys.argv[1]);dst=Path(sys.argv[2]);text=src.read_text()
hook='/usr/bin/flock -n "$HOME/factory-runtime/operations/.seven-gap-periodic.lock" /usr/bin/timeout 180s "$HOME/factory-runtime/.venv/bin/python" -B "$HOME/factory-runtime/operations/forty-execution/factory_seven_missing_builders.py" --factory-private "$HOME/factory-runtime/private/autonomous-product-cycle" --tick || echo SEVEN_GAP_PENDING_REWORK\n'
assert text.count("set -euo pipefail")==1
assert text.count("factory_seven_missing_builders.py") in (0,1)
if hook not in text:
    assert "factory_seven_missing_builders.py" not in text
    text=text.replace("set -euo pipefail\n","set -euo pipefail\n"+hook,1)
assert text.count("factory_seven_missing_builders.py")==1
dst.write_text(text)
dst.chmod(src.stat().st_mode&0o777)
PY
bash -n "$scheduler.new"
mv -f "$scheduler.new" "$scheduler"
test "$(crontab -l | sha256sum | cut -d' ' -f1)" = "$(sha256sum "$backup/crontab" | cut -d' ' -f1)"
trap - EXIT
echo SEVEN_GAP_BUILDERS_INSTALLED_AND_PERIODIC_REWORK_REGISTERED
echo SEVEN_GAP_COMMERCIAL_AND_PUBLICATION_GATES_UNCHANGED
