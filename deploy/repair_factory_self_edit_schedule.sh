#!/usr/bin/env bash
# Restore only the previously installed private self-edit scanner's hourly cron.
# Do not reinstall source, mutate production code, touch the factory loop, or
# treat a zero-candidate scan as a commercial result.
set -euo pipefail
umask 077
test "$(id -un)" = githubops
test "$(id -u)" -ne 0

root="$HOME/factory-runtime"
ops="$root/operations"
target="$ops/factory-code-self-upgrade"
source="$target/source/scripts/factory_code_self_upgrade.py"
runner="$target/run-scan-and-edit.sh"
proof="$root/private/autonomous-product-cycle/code-self-upgrade/evolution-proof.json"
marker="SAEIT_FACTORY_CODE_SELF_EDIT_HOURLY_V1"

test -d "$ops" && test ! -L "$ops"
test -d "$target" && test ! -L "$target"
test -d "$target/source" && test ! -L "$target/source"
test -d "$target/source/scripts" && test ! -L "$target/source/scripts"
test -s "$source" && test ! -L "$source"
test -x "$runner" && test ! -L "$runner"
test -x "$root/.venv/bin/python"
command -v crontab >/dev/null
command -v flock >/dev/null
bash -n "$runner"
grep -Fq '"$ops/factory-code-self-upgrade/source/scripts/factory_code_self_upgrade.py"' "$runner"
grep -Fq -- '--out "$HOME/factory-runtime/private/autonomous-product-cycle/code-self-upgrade"' "$runner"

# Coordinate with the existing isolated scanner installer and preserve all
# unrelated cron jobs exactly as found.
exec 8>"$ops/.code-self-upgrade-install.lock"
flock -w 70 8
previous="$(mktemp "$ops/.factory-self-edit-cron-before.XXXXXX")"
proposed="$(mktemp "$ops/.factory-self-edit-cron-proposed.XXXXXX")"
trap 'rm -f -- "$previous" "$proposed"' EXIT
crontab -l > "$previous" || test "$?" -eq 1
count="$(grep -c "$marker" "$previous" || true)"
case "$count" in
  0) ;;
  1)
    grep -Fq "17 * * * * /bin/bash $runner # $marker" "$previous"
    echo FACTORY_SELF_EDIT_SCHEDULE_ALREADY_PRESENT
    ;;
  *)
    echo FACTORY_SELF_EDIT_DUPLICATE_SCHEDULE_REFUSED
    exit 3
    ;;
esac

# Perform the existing private scan once, then validate its evidence before
# scheduling future runs; the scan is source-read-only and never promotes code.
"$runner"
"$root/.venv/bin/python" -B - "$proof" <<'PY'
import json, sys, time
from pathlib import Path
path = Path(sys.argv[1])
if path.is_symlink() or not path.is_file():
    raise SystemExit("FACTORY_SELF_EDIT_PROOF_MISSING")
state = json.loads(path.read_text(encoding="utf-8"))
if state.get("schema") != "saeit.factory.code-self-upgrade.v1":
    raise SystemExit("FACTORY_SELF_EDIT_PROOF_SCHEMA_INVALID")
if not 0 <= time.time() - path.stat().st_mtime < 300:
    raise SystemExit("FACTORY_SELF_EDIT_PROOF_NOT_FRESH")
if state.get("candidate_count", -1) + state.get("preexisting_verified_repairs", -1) != 4:
    raise SystemExit("FACTORY_SELF_EDIT_PROOF_COVERAGE_INVALID")
if state.get("validated_repair_rule_coverage") != 4:
    raise SystemExit("FACTORY_SELF_EDIT_PROOF_COVERAGE_INVALID")
if state.get("candidates_with_measured_improvement") != state.get("candidate_count"):
    raise SystemExit("FACTORY_SELF_EDIT_PROOF_INVALID_CANDIDATES")
if state.get("unresolved_known_security_regressions") != 0:
    raise SystemExit("FACTORY_SELF_EDIT_KNOWN_REGRESSION")
if state.get("production_code_promotions") != 0:
    raise SystemExit("FACTORY_SELF_EDIT_UNEXPECTED_PRODUCTION_EDIT")
print("FACTORY_SELF_EDIT_PRIVATE_SCAN_VERIFIED")
print("FACTORY_SELF_EDIT_CANDIDATES=" + str(state["candidate_count"]))
print("FACTORY_SELF_EDIT_VERIFIED_PREEXISTING_REPAIRS=" + str(state["preexisting_verified_repairs"]))
print("FACTORY_SELF_EDIT_PRODUCTION_PROMOTIONS=0")
PY

if [ "$count" = 0 ]; then
  cp -- "$previous" "$proposed"
  printf '17 * * * * /bin/bash %s # %s\n' "$runner" "$marker" >> "$proposed"
  if ! crontab "$proposed"; then
    crontab "$previous" || :
    echo FACTORY_SELF_EDIT_SCHEDULE_REPAIR_FAILED
    exit 4
  fi
  current="$(mktemp "$ops/.factory-self-edit-cron-current.XXXXXX")"
  trap 'rm -f -- "$previous" "$proposed" "$current"' EXIT
  crontab -l > "$current"
  if [ "$(grep -c "$marker" "$current" || true)" != 1 ] || ! grep -Fq "17 * * * * /bin/bash $runner # $marker" "$current"; then
    crontab "$previous" || :
    echo FACTORY_SELF_EDIT_SCHEDULE_POSTCHECK_FAILED
    exit 5
  fi
  echo FACTORY_SELF_EDIT_SCHEDULE_RESTORED
else
  echo FACTORY_SELF_EDIT_SCHEDULE_VERIFIED
fi
echo FACTORY_SELF_EDIT_SITE_CHANGES=0
echo FACTORY_SELF_EDIT_FACTORY_LOOP_CHANGES=0
