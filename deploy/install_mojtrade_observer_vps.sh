#!/usr/bin/env bash
# Install only MojTrade's read-only market observer in the isolated githubops VPS.
# No application/database/factory changes, broker credentials or real orders.
set -euo pipefail
umask 077

test "$(id -un)" = githubops || { echo MOJTRADE_WRONG_RUNTIME_USER; exit 2; }
test "$#" -eq 1 && [[ "$1" =~ ^[a-f0-9]{64}$ ]] || { echo MOJTRADE_INVALID_EXPECTED_SHA; exit 2; }
expected_sha="$1"
base="$HOME/factory-runtime"
operations="$base/operations/mojtrade"
private="$base/private/mojtrade"
python_bin="$base/.venv/bin/python"
staged="$operations/observer.py.staged"
target="$operations/observer.py"
tag=SAEIT_MOJTRADE_OBSERVER_V1

test -x "$python_bin" && test -d "$base/private" && test -d "$base/operations" || {
  echo MOJTRADE_RUNTIME_PRECHECK_FAILED; exit 2;
}
command -v crontab >/dev/null && command -v flock >/dev/null && command -v timeout >/dev/null || {
  echo MOJTRADE_SCHEDULER_COMMAND_MISSING; exit 2;
}
if ! systemctl is-active --quiet cron 2>/dev/null && ! systemctl is-active --quiet crond 2>/dev/null; then
  echo MOJTRADE_CRON_DAEMON_INACTIVE; exit 2
fi
# The repository also ships a systemd timer for this observer. Never install
# a second hourly cron runner when that timer is already active or enabled.
if systemctl is-active --quiet mojtrade-observer.timer 2>/dev/null || \
   systemctl is-enabled --quiet mojtrade-observer.timer 2>/dev/null; then
  echo MOJTRADE_COMPETING_SYSTEMD_TIMER_FOUND; exit 2
fi
test -f "$staged" && test ! -L "$staged" && test ! -L "$operations" || {
  echo MOJTRADE_STAGED_SOURCE_INVALID; exit 2;
}
actual_sha="$(sha256sum "$staged" | awk '{print $1}')"
test "$actual_sha" = "$expected_sha" || { echo MOJTRADE_SOURCE_SHA_MISMATCH; exit 2; }
test ! -L "$target" || { echo MOJTRADE_TARGET_SYMLINK_REJECTED; exit 2; }
free_mb="$(df -Pm "$base" | awk 'NR==2 {print $4}')"
[[ "$free_mb" =~ ^[0-9]+$ ]] && (( free_mb >= 500 )) || {
  echo MOJTRADE_INSUFFICIENT_FREE_SPACE; exit 2;
}

install -d -m 700 "$operations" "$private"
test "$(stat -c %a "$private")" = 700 || { echo MOJTRADE_PRIVATE_DIR_INSECURE; exit 2; }
"$python_bin" -m py_compile "$staged"

# Only external operation: public, unauthenticated market-data GET requests.
# An outage or provider restriction leaves all existing schedules untouched.
candidate="$private/validated-payload.candidate.json"
test ! -L "$candidate" || { echo MOJTRADE_CANDIDATE_SYMLINK; exit 2; }
timeout 80 "$python_bin" "$staged" --output "$candidate"
"$python_bin" - "$candidate" <<'PY'
import json,sys
from pathlib import Path
p=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
assert p['source']=='mojtrade-vps' and p['schema_version']==1
assert [s['symbol'] for s in p['signals']]==['BTC/USD','ETH/USD']
assert all(s['market']=='crypto' and s['timeframe']=='1h' for s in p['signals'])
print('MOJTRADE_PRIVATE_PROVIDER_PAYLOAD_VALIDATED')
PY

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
old_cron="$operations/cron-before-$stamp.txt"
crontab -l > "$old_cron" 2>/dev/null || : > "$old_cron"
chmod 600 "$old_cron"
count="$(grep -c "$tag" "$old_cron" || true)"
(( count <= 1 )) || { echo MOJTRADE_DUPLICATE_EXISTING_SCHEDULE; exit 2; }
if grep -E 'mojtrade/observer\.py|mojtrade_observe_market\.py' "$old_cron" | grep -v "$tag" >/dev/null; then
  echo MOJTRADE_COMPETING_SCHEDULE_FOUND; exit 2
fi

backup="$operations/observer-before-$stamp.py"
had_target=0
if test -f "$target"; then
  install -m 600 "$target" "$backup"
  had_target=1
fi
changed_code=0
changed_cron=0
rollback() {
  status=$?
  trap - EXIT
  if (( status != 0 )); then
    if (( changed_cron )); then crontab "$old_cron"; fi
    if (( changed_code )); then
      if (( had_target )); then install -m 600 "$backup" "$target"; else rm -f -- "$target"; fi
    fi
    echo MOJTRADE_INSTALL_ROLLBACK_APPLIED
  fi
  return "$status"
}
trap rollback EXIT

install -m 600 "$staged" "$operations/observer.py.new"
mv -f -- "$operations/observer.py.new" "$target"
changed_code=1
candidate_cron="$operations/cron-candidate-$stamp.txt"
grep -v "$tag" "$old_cron" > "$candidate_cron" || true
printf '%s\n' "13 * * * * /usr/bin/flock -n $operations/observer.lock $python_bin $target --output $private/validated-payload.json >> $operations/observer.log 2>&1 # $tag" >> "$candidate_cron"
chmod 600 "$candidate_cron"
changed_cron=1
crontab "$candidate_cron"
test "$(crontab -l | grep -c "$tag" || true)" -eq 1
mv -f -- "$candidate" "$private/validated-payload.json"
payload_sha="$(sha256sum "$private/validated-payload.json" | awk '{print $1}')"
receipt="$private/activation-receipt.json"
receipt_tmp="$private/.activation-receipt-$stamp.tmp"
"$python_bin" - "$receipt_tmp" "$stamp" "$expected_sha" "$payload_sha" "$operations" "$private" <<'PY'
import json
import os
import sys
from pathlib import Path

destination = Path(sys.argv[1])
stamp, source_sha, payload_sha, operations, private = sys.argv[2:]
receipt = {
    "schema": "mojtrade.vps-observer-activation-receipt.v1",
    "installed_at": stamp,
    "source_sha256": source_sha,
    "payload_sha256": payload_sha,
    "operations_dir": operations,
    "private_dir": private,
    "runtime": "githubops",
    "execution": "disabled",
    "orders": 0,
    "publication_enabled": False,
    "delivery_enabled": False,
}
destination.write_text(json.dumps(receipt, separators=(",", ":")) + "\n", encoding="utf-8")
os.chmod(destination, 0o600)
PY
mv -f -- "$receipt_tmp" "$receipt"
trap - EXIT
echo MOJTRADE_OBSERVER_PRIVATE_OUTPUT_VERIFIED
echo MOJTRADE_OBSERVER_HOURLY_SCHEDULE_VERIFIED
echo MOJTRADE_FACTORY_AND_MASTER_UNMODIFIED
echo MOJTRADE_REAL_ORDERS_ZERO
