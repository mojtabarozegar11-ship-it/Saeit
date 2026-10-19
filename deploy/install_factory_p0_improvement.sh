#!/usr/bin/env bash
# Safe private installation of evidence-bound P0 improvement loop, no live-site changes.
set -euo pipefail
umask 077
test "$(id -un)" = githubops
test "$#" -eq 1
stage="$1"
test -d "$stage" && test ! -L "$stage"
test -f "$stage/factory_p0_improvement.py" && test ! -L "$stage/factory_p0_improvement.py"
ops="$HOME/factory-runtime/operations"
private="$HOME/factory-runtime/private/autonomous-product-cycle"
py="$HOME/factory-runtime/.venv/bin/python"
test -x "$py" && test -d "$private"
command -v flock >/dev/null
command -v crontab >/dev/null
test "$(crontab -l | grep -c SAEIT_FACTORY_EVERY_MINUTE_V1)" -eq 1
test "$(crontab -l | grep -c SAEIT_FACTORY_LIFECYCLE_12_V1)" -eq 1
test "$(crontab -l | grep -c SAEIT_FACTORY_FORTY_FAMILY_MASTER_V1)" -eq 1
"$py" -B -c 'import ast,sys;ast.parse(open(sys.argv[1],encoding="utf-8").read())' "$stage/factory_p0_improvement.py"
exec 8>"$ops/.p0-measured-improvement-install.lock"
flock -w 60 8
test ! -L "$ops/p0-measured-improvement" && test ! -L "$ops/backups"
install -d -m 700 "$ops/p0-measured-improvement" "$ops/backups"
dest="$ops/p0-measured-improvement/factory_p0_improvement.py"
runner="$ops/p0-measured-improvement/run-p0.sh"
backup="$ops/backups/p0-improvement-$(date -u +%Y%m%dT%H%M%SZ)-$$"
install -d -m 700 "$backup"
crontab -l > "$backup/crontab-original"
chmod 600 "$backup/crontab-original"
test ! -L "$dest" && test ! -L "$runner"
if test -f "$dest"; then cp -p "$dest" "$backup/previous-source.py"; fi
if test -f "$runner"; then cp -p "$runner" "$backup/previous-runner.sh"; fi
restored=0
rollback() {
  rc=$?
  if test "$rc" -ne 0 && test "$restored" -eq 0; then
    if test -f "$backup/crontab-proposed" &&
       test "$(crontab -l 2>/dev/null | sha256sum | awk '{print $1}')" = "$(sha256sum "$backup/crontab-proposed" | awk '{print $1}')"; then
      crontab - < "$backup/crontab-original" || true
    fi
    if test -f "$backup/previous-source.py"; then cp -p "$backup/previous-source.py" "$dest"; else rm -f "$dest"; fi
    if test -f "$backup/previous-runner.sh"; then cp -p "$backup/previous-runner.sh" "$runner"; else rm -f "$runner"; fi
    echo P0_PRIVATE_INSTALL_ROLLED_BACK
  fi
  exit "$rc"
}
trap rollback EXIT
incoming="$(mktemp "$ops/p0-measured-improvement/.source.XXXXXX")"
install -m 600 "$stage/factory_p0_improvement.py" "$incoming"
mv -f -- "$incoming" "$dest"
cat > "$runner" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
umask 077
ops="$HOME/factory-runtime/operations"
exec 7>"$ops/.p0-measured-improvement-cycle.lock"
flock -n 7 || exit 0
exec >> "$ops/p0-measured-improvement.log" 2>&1
exec "$HOME/factory-runtime/.venv/bin/python" -B \
  "$ops/p0-measured-improvement/factory_p0_improvement.py" \
  --factory-private "$HOME/factory-runtime/private/autonomous-product-cycle"
SH
chmod 700 "$runner"
bash -n "$runner"
"$runner"
"$py" -B - "$private/p0-improvement/last-report.json" <<'PY'
import json,sys
from pathlib import Path
a=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert a["schema"]=="saeit.factory.p0.measured-improvement.v1"
assert a["auto_site_publish"] is False
assert a["automatic_quality_approval"] is False
assert a["generation_auto_promotion"] is False
assert isinstance(a["new_rework_tickets"],list)
assert a["verified_approved_stock"]>=0
print("P0_PRIVATE_LIVE_SMOKE=PASS")
print("P0_PRIVATE_FINISHED_VERIFIED="+str(a["verified_approved_stock"]))
print("P0_NEW_REWORK_TICKETS="+str(len(a["new_rework_tickets"])))
PY
marker=SAEIT_FACTORY_P0_MEASURED_IMPROVEMENT_V1
grep -v "$marker" "$backup/crontab-original" > "$backup/crontab-proposed" || true
printf '23 * * * * /bin/bash %s # %s\n' "$runner" "$marker" >> "$backup/crontab-proposed"
chmod 600 "$backup/crontab-proposed"
test "$(crontab -l | sha256sum | awk '{print $1}')" = "$(sha256sum "$backup/crontab-original" | awk '{print $1}')"
crontab - < "$backup/crontab-proposed"
test "$(crontab -l | grep -c "$marker")" -eq 1
test "$(crontab -l | grep -c SAEIT_FACTORY_EVERY_MINUTE_V1)" -eq 1
test "$(crontab -l | grep -c SAEIT_FACTORY_LIFECYCLE_12_V1)" -eq 1
test "$(crontab -l | grep -c SAEIT_FACTORY_FORTY_FAMILY_MASTER_V1)" -eq 1
restored=1
trap - EXIT
echo P0_MEASURED_IMPROVEMENT_PRIVATE_INSTALL=PASS
echo P0_IMPROVEMENT_SCAN_SCHEDULE=HOURLY
echo P0_WEBSITE_CHANGE=false
echo P0_PRODUCT_APPROVAL_BYPASS=false
echo P0_BACKUP="$backup"
