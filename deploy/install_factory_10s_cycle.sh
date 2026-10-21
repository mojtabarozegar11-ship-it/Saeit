#!/usr/bin/env bash
# Install a private, reversible six-pulses-per-minute factory controller.
set -euo pipefail
umask 077
test "$(id -un)" = "githubops"
test "$#" -eq 1
stage="$1"
base="$HOME/factory-runtime"
ops="$base/operations"
private="$base/private/autonomous-product-cycle"
py="$base/.venv/bin/python"
target="$ops/factory-ten-second-v1"
marker="SAEIT_FACTORY_TEN_SECOND_V1"
test -d "$stage" && test ! -L "$stage"
test -d "$ops" && test -d "$private/quality-excellence" && test -x "$py"
test -s "$ops/autonomous-product-runtime/run-local-cycle.sh"
test -s "$ops/factory-code-self-upgrade/run-scan-and-edit.sh"
command -v crontab >/dev/null
command -v flock >/dev/null
for file in factory_10s_cycle.py factory_autonomous_jump_repair_v1.py factory_qa_native_rebuild_bridge_20261021.py factory_product_maker.py factory_personal_owner_passport_policy_20261020.py factory_ten_generation_builder_v1.py factory_f19_ten_generations_v1.py factory_build_50.py; do
  test -s "$stage/scripts/$file" && test ! -L "$stage/scripts/$file"
done
test -s "$stage/factory_config/forty_families.json"
"$py" -B -c 'import ast,pathlib,sys; [ast.parse(pathlib.Path(x).read_text()) for x in sys.argv[1:]]' "$stage/scripts/factory_10s_cycle.py"
"$py" -B -c 'import json,sys; v=json.load(open(sys.argv[1])); assert isinstance(v,(dict,list))' "$stage/factory_config/forty_families.json"
exec 8>"$ops/.factory-ten-second-install.lock"
flock -w 60 8
stamp="$(date -u +%Y%m%dT%H%M%SZ)-$$"
backup="$ops/backups/factory-ten-second-$stamp"
install -d -m 700 "$backup"
crontab -l > "$backup/old-crontab" 2>/dev/null || :
chmod 600 "$backup/old-crontab"
incoming="$ops/.factory-ten-second-$stamp"
install -d -m 700 "$incoming/modules"
cp -- "$stage/scripts/factory_10s_cycle.py" "$incoming/factory_10s_cycle.py"
for file in factory_autonomous_jump_repair_v1.py factory_qa_native_rebuild_bridge_20261021.py factory_product_maker.py factory_personal_owner_passport_policy_20261020.py factory_ten_generation_builder_v1.py factory_f19_ten_generations_v1.py factory_build_50.py; do
  cp -- "$stage/scripts/$file" "$incoming/modules/$file"
  test "$(sha256sum "$stage/scripts/$file" | cut -d' ' -f1)" = "$(sha256sum "$incoming/modules/$file" | cut -d' ' -f1)"
done
cp -- "$stage/factory_config/forty_families.json" "$incoming/modules/forty_families.json"
cat > "$incoming/run-six-ticks.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
umask 077
ops="$HOME/factory-runtime/operations"
target="$ops/factory-ten-second-v1"
exec 9>"$ops/.factory-ten-second-cron.lock"
flock -n 9 || exit 0
for tick in 0 1 2 3 4 5; do
  "$HOME/factory-runtime/.venv/bin/python" -B "$target/factory_10s_cycle.py" --mode tick || echo "FACTORY_10S_TICK_ERROR" >&2
  if test "$tick" -lt 5; then sleep 10; fi
done
SH
chmod -R go-rwx "$incoming"
chmod 700 "$incoming/run-six-ticks.sh"
bash -n "$incoming/run-six-ticks.sh"
if test -e "$target"; then
  test -d "$target" && test ! -L "$target"
  mv -- "$target" "$backup/previous-install"
fi
mv -- "$incoming" "$target"
restore() {
  rc=$?
  if test "$rc" -ne 0; then
    crontab - < "$backup/old-crontab" || :
    if test -d "$target" && test ! -L "$target"; then
      mv -- "$target" "$backup/failed-install"
    fi
    if test -d "$backup/previous-install"; then
      mv -- "$backup/previous-install" "$target"
    fi
    echo "FACTORY_10S_INSTALL_ROLLBACK=ATTEMPTED"
  fi
  exit "$rc"
}
trap restore EXIT
"$py" -B "$target/factory_10s_cycle.py" --mode check
grep -v "$marker" "$backup/old-crontab" > "$backup/proposed-crontab" || true
printf '* * * * * /bin/bash %s # %s\n' "$target/run-six-ticks.sh" "$marker" >> "$backup/proposed-crontab"
chmod 600 "$backup/proposed-crontab"
crontab - < "$backup/proposed-crontab"
test "$(crontab -l | grep -c "$marker")" -eq 1
"$py" -B "$target/factory_10s_cycle.py" --mode tick
"$py" -B - "$private/quality-excellence/ten-second-control/state.json" <<'PY'
import json,sys
from pathlib import Path
state=json.loads(Path(sys.argv[1]).read_text())
assert state["schema"]=="saeit.factory.private-10-second-cycle.v1"
assert state["ticks"]>=1
assert state["last_tick_utc_epoch"]>0
print("FACTORY_10S_INITIAL_TICKS="+str(state["ticks"]))
print("FACTORY_10S_INITIAL_DECISION="+state["last_decision"])
PY
trap - EXIT
echo "FACTORY_10S_SCHEDULER_CRON=INSTALLED"
echo "FACTORY_10S_PER_MINUTE=6"
echo "FACTORY_10S_SITE_CHANGES=0"
echo "FACTORY_10S_PUBLIC_RELEASES=0"
echo "FACTORY_10S_ROLLBACK_BACKUP=$backup"
