#!/usr/bin/env bash
# Activate English-first serial WO admission; do not modify stores or customer stock.
set -euo pipefail
umask 077
test "$#" -eq 1
src="$1"
base="/home/githubops/factory-runtime"
ops="$base/operations/production-instructions"
private="$base/private/autonomous-product-cycle"
backups="$base/operations/backups"
py="$base/.venv/bin/python"
marker="SAEIT_ENGLISH_FIRST_SINGLE_ACTIVE_20261025"
test "$(id -un)" = githubops
test -d "$src" && test ! -L "$src"
test -d "$ops" && test ! -L "$ops" && test -d "$private" && test ! -L "$private"
test -d "$backups" && test ! -L "$backups"
test -x "$py"
test -f "$ops/strict-serial-fullcycle-v1.py"
run="${GITHUB_RUN_ID:-manual}-${GITHUB_RUN_ATTEMPT:-1}"
[[ "$run" =~ ^[A-Za-z0-9-]{1,55}$ ]]
backup="$backups/english-first-serial-$run"
test ! -e "$backup"
install -d -m 700 "$backup"
crontab -l > "$backup/crontab.before"
chmod 600 "$backup/crontab.before"

install_code() {
  local source="$1" target="$2" short="$3" tmp
  test -f "$source" && test ! -L "$source" && test ! -L "$target"
  "$py" -B -c 'import ast,sys;ast.parse(open(sys.argv[1],encoding="utf8").read())' "$source"
  if test -f "$target"; then cp -p "$target" "$backup/$short.previous"; fi
  tmp="$(mktemp "$ops/.english-first-stage.XXXXXX")"
  install -m 600 "$source" "$tmp"
  test "$(sha256sum "$source" | awk '{print $1}')" = "$(sha256sum "$tmp" | awk '{print $1}')"
  mv -- "$tmp" "$target"
}
install_code "$src/scripts/factory_english_first_serial_intake_v1.py" "$ops/english-first-serial-intake-v1.py" "serial"
install_code "$src/scripts/factory_stage1_handoff.py" "$ops/stage1-english-first-worker.py" "stage1"

"$py" -B "$ops/english-first-serial-intake-v1.py" --factory-private "$private" --operations "$ops" --dry-run

temp="$(mktemp "$ops/.english-first-cron.XXXXXX")"
python3 -B - "$backup/crontab.before" "$temp" "$marker" <<'PY'
import sys
from pathlib import Path
old,new,marker=sys.argv[1:]
lines=Path(old).read_text().splitlines()
pause=(
    "SAEIT_FACTORY_STAGE1_INDEPENDENT_V1",
    "SAEIT_FACTORY_TEN_SECOND_V1",
    "SAEIT_FACTORY_FORTY_FAMILY_OPERATIONAL_DISPATCH_V1",
    "SAEIT_FACTORY_BUILD50_FORTY_FAMILY_BRIDGE_V1",
    "SAEIT_OWNER500_AUTONOMOUS_F28_V1",
    "SAEIT_AGRI200_NAVIGATOR_PRIVATE_V1",
    "SAEIT_STRICT_SERIAL_PRODUCT_TO_QC1000_20261025",
)
if any(marker in row and not row.lstrip().startswith('#') for row in lines):
    raise SystemExit("ENGLISH_FIRST_ALREADY_ACTIVE")
result=[]
paused={}
for line in lines:
    if line.lstrip().startswith('#'):
        result.append(line)
        continue
    matches=[m for m in pause if m in line]
    if matches:
        if len(matches)!=1 or "factory-runtime" not in line:
            raise SystemExit("UNSAFE_PRODUCER_CRON_SCOPE")
        paused[matches[0]]=paused.get(matches[0],0)+1
        result.append("# PAUSED_FOR_ENGLISH_FIRST_SERIAL_20261025 "+line)
    else: result.append(line)
if paused.get("SAEIT_FACTORY_STAGE1_INDEPENDENT_V1")!=1:
    raise SystemExit("BULK_STAGE1_CRON_NOT_FOUND_FOR_PAUSE")
result.append(
    "* * * * * /usr/bin/flock -n /home/githubops/factory-runtime/operations/production-instructions/.english-first-cron.lock "
    "/usr/bin/timeout 58s /home/githubops/factory-runtime/.venv/bin/python -B "
    "/home/githubops/factory-runtime/operations/production-instructions/english-first-serial-intake-v1.py "
    "--factory-private /home/githubops/factory-runtime/private/autonomous-product-cycle "
    "--operations /home/githubops/factory-runtime/operations/production-instructions "
    "--require-cron >> /home/githubops/factory-runtime/operations/production-instructions/english-first-serial.log 2>&1 "
    "# "+marker)
Path(new).write_text("\n".join(result)+"\n")
print("ENGLISH_FIRST_PAUSED_MARKERS="+str(sorted(paused)))
PY
if ! test "$(crontab -l | sha256sum | awk '{print $1}')" = "$(sha256sum "$backup/crontab.before" | awk '{print $1}')"; then
  echo ORIGINAL_CRON_CHANGED_ABORT >&2
  exit 1
fi
crontab "$temp"
rm -f -- "$temp"
test "$(crontab -l | grep -F "$marker" | grep -vc '^#')" -eq 1
test "$(crontab -l | grep -F 'SAEIT_FACTORY_STAGE1_INDEPENDENT_V1' | grep -vc '^#' || true)" -eq 0
echo ENGLISH_FIRST_CRON=INSTALLED
echo "CRON_BACKUP=$backup/crontab.before"
# A safe first live tick genuinely admits exactly the first English product.
# If Stage 1 is blocked, leave the one-product scheduler intact and report failure.
timeout 53s "$py" -B "$ops/english-first-serial-intake-v1.py" \
  --factory-private "$private" --operations "$ops" --require-cron
echo ENGLISH_FIRST_SINGLE_ACTIVE_ORDER=RUNNING
echo NO_STORE_OR_CUSTOMER_FULFILLMENT_WRITES=true
