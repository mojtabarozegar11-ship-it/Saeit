#!/usr/bin/env bash
set -euo pipefail
umask 077
repo="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
runtime="/home/githubops/factory-runtime/operations/autonomous-product-runtime"

if [ "${SAEIT_FACTORY_SYSTEMD_INSTALL_APPROVED:-}" != "1" ]; then
  echo FACTORY_SYSTEMD_INSTALL_APPROVAL_REQUIRED >&2
  exit 1
fi
test "$(id -u)" -eq 0
test -d /home/githubops/factory-runtime
test -x "$runtime/run-local-cycle.sh"
test -f "$repo/scripts/factory-runtime-watchdog.sh"
test -f "$repo/deploy/systemd/saeit-factory-cycle.service"
test -f "$repo/deploy/systemd/saeit-factory-cycle.timer"
test -f "$repo/deploy/systemd/saeit-factory-watchdog.service"
test -f "$repo/deploy/systemd/saeit-factory-watchdog.timer"

# A legacy minute cron is currently present on the live VPS. Installing
# a second scheduler without first proving a controlled migration is forbidden.
if ! command -v crontab >/dev/null; then
  echo F01_PREFLIGHT_CRONTAB_INVENTORY_UNAVAILABLE >&2
  exit 3
fi
# Root installation is privileged; inspect EVERY account's cron as well as
# /etc crontab entries before installing a second producer. Checking only
# githubops would miss another production loop owned by root or another user.
if ! command -v getent >/dev/null; then
  echo F01_PREFLIGHT_USER_INVENTORY_UNAVAILABLE >&2
  exit 3
fi
if ! cron_accounts="$(getent passwd)" || [ -z "$cron_accounts" ]; then
  echo F01_PREFLIGHT_USER_INVENTORY_UNREADABLE >&2
  exit 3
fi
factory_cron_pattern='SAEIT_SINGLE_PRODUCT_FACTORY_V1|SAEIT_FACTORY_EVERY_MINUTE_V1|SAEIT_STRICT_SERIAL_PRODUCT_TO_QC1000|SAEIT_AGRI200|factory[-_/]|agri200|build50'
while IFS=: read -r cron_user _; do
  [ -n "$cron_user" ] || continue
  if cron_snapshot="$(LC_ALL=C crontab -u "$cron_user" -l 2>&1)"; then
    :
  elif [[ "$cron_snapshot" == *"no crontab for $cron_user"* ]]; then
    cron_snapshot=""
  else
    echo F01_PREFLIGHT_CRONTAB_INVENTORY_UNREADABLE >&2
    exit 3
  fi
  if printf '%s\n' "$cron_snapshot" | grep -Eiq "$factory_cron_pattern"; then
    echo F01_PREFLIGHT_COMPETING_FACTORY_CRON_PRESENT >&2
    exit 3
  fi
done <<< "$cron_accounts"
for cron_file in /etc/crontab /etc/cron.d/*; do
  if [ ! -e "$cron_file" ] && [ ! -L "$cron_file" ]; then
    continue
  fi
  if [ -L "$cron_file" ] || [ ! -f "$cron_file" ] || [ ! -r "$cron_file" ]; then
    echo F01_PREFLIGHT_SYSTEM_CRON_INVENTORY_UNREADABLE >&2
    exit 3
  fi
  if grep -Eiq "$factory_cron_pattern" "$cron_file"; then
    echo F01_PREFLIGHT_COMPETING_SYSTEM_FACTORY_CRON_PRESENT >&2
    exit 3
  fi
done
timer_snapshot="$(systemctl list-timers --all --no-legend --no-pager)" || {
  echo F01_PREFLIGHT_TIMER_INVENTORY_UNREADABLE >&2
  exit 3
}
if printf '%s\n' "$timer_snapshot" | grep -Eiq '(factory|agri200|strict[-_]?serial|build50).*\.timer'; then
  echo F01_PREFLIGHT_COMPETING_SYSTEMD_TIMER_PRESENT >&2
  exit 3
fi

# The live vps-only-loop.sh executes factory_staging_tick and invokes master,
# discovery and intake commands. It is an independently running factory writer,
# not a verified participant in the F01 global lane. Enabling an additional
# systemd scheduler while it runs could create concurrent production paths.
if ! command -v pgrep >/dev/null; then
  echo F01_PREFLIGHT_PROCESS_INVENTORY_UNAVAILABLE >&2
  exit 3
fi
if pgrep -f '/vps-only-loop[.]sh|manage[.]py[[:space:]]+factory_staging_tick' >/dev/null; then
  echo F01_PREFLIGHT_COMPETING_STAGING_LOOP_PRESENT >&2
  exit 3
else
  scan_status=$?
  if [ "$scan_status" -ne 1 ]; then
    echo F01_PREFLIGHT_PROCESS_INVENTORY_UNREADABLE >&2
    exit 3
  fi
fi

# Read-only admission: a timer is not evidence of a safe single-product runtime.
# Refuse installation unless the existing VPS source and private state identify
# exactly the one permitted product. This runs before touching systemd files.
python3 - "$runtime" <<'PY'
import json
import os
from pathlib import Path
import sys

runtime = Path(sys.argv[1])
private = Path("/home/githubops/factory-runtime/private/autonomous-product-cycle")
expected = "farm_enterprise_economics"

def verified_json(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 100000:
        raise SystemExit("F01_PREFLIGHT_MISSING_OR_UNSAFE_STATE:" + path.name)
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        raise SystemExit("F01_PREFLIGHT_INVALID_STATE:" + path.name)
    if not isinstance(obj, dict):
        raise SystemExit("F01_PREFLIGHT_INVALID_STATE:" + path.name)
    return obj

slot = verified_json(private / "quality-excellence/product-flow/active-slots/current.json")
active = slot.get("active")
if (slot.get("schema") != "saeit.factory.product-slots.v1"
        or slot.get("capacity") != 1
        or not isinstance(active, list)
        or len(active) != 1
        or not isinstance(active[0], dict)
        or active[0].get("recipe") != expected):
    raise SystemExit("F01_PREFLIGHT_SLOT_NOT_EXACT_FIRST_PRODUCT")

state = verified_json(private / "production-state.json")
if (state.get("active_product_slot_capacity") != 1
        or state.get("active_product_slot_recipes") != [expected]
        or state.get("publication_locked_until_owner_approval") is not True
        or state.get("commercial_quality_review_completed") is not False):
    raise SystemExit("F01_PREFLIGHT_STATE_NOT_EXACT_FIRST_PRODUCT")

reservation = verified_json(private / ".f01-global-production-lane.json")
if (reservation.get("schema") != "saeit.factory.global-single-production-lane.v1"
        or reservation.get("owner") != "line41"
        or type(reservation.get("generation")) is not int
        or reservation["generation"] < 1):
    raise SystemExit("F01_PREFLIGHT_GLOBAL_SINGLETON_NOT_PROVEN")

runner = runtime / "run-local-cycle.sh"
core = runtime / "scripts/factory_vps_product_cycle.py"
singleton = runtime / "scripts/factory_global_singleton_v1.py"
for path in (runner, core, singleton):
    if (path.is_symlink() or not path.is_file()
            or path.stat().st_size > 1000000):
        raise SystemExit("F01_PREFLIGHT_RUNTIME_SOURCE_MISSING:" + path.name)
runner_text = runner.read_text(encoding="utf-8")
core_text = core.read_text(encoding="utf-8")
if (expected not in runner_text
        or "factory_vps_product_cycle.py" not in runner_text
        or "factory_global_singleton_v1.py" not in core_text):
    raise SystemExit("F01_PREFLIGHT_UNVERIFIED_RUNNER_CONTENT")
if not os.access(runner, os.X_OK):
    raise SystemExit("F01_PREFLIGHT_RUNNER_NOT_EXECUTABLE")
print("F01_PREFLIGHT_LOCAL_SINGLE_PRODUCT=PASS")
PY

install -d -m 700 "$runtime"
install -m 700 "$repo/scripts/factory-runtime-watchdog.sh" "$runtime/factory-runtime-watchdog.sh"
install -m 644 deploy/systemd/saeit-factory-cycle.service /etc/systemd/system/saeit-factory-cycle.service
install -m 644 deploy/systemd/saeit-factory-cycle.timer /etc/systemd/system/saeit-factory-cycle.timer
install -m 644 deploy/systemd/saeit-factory-watchdog.service /etc/systemd/system/saeit-factory-watchdog.service
install -m 644 deploy/systemd/saeit-factory-watchdog.timer /etc/systemd/system/saeit-factory-watchdog.timer
systemctl daemon-reload
systemctl enable --now saeit-factory-cycle.timer
systemctl enable --now saeit-factory-watchdog.timer
systemctl --no-pager --full status saeit-factory-cycle.timer saeit-factory-watchdog.timer

