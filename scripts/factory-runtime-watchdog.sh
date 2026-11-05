#!/usr/bin/env bash
set -euo pipefail
umask 077

root=/home/githubops/factory-runtime/private/autonomous-product-cycle
health="$root/production-health.json"
slots="$root/quality-excellence/product-flow/active-slots/current.json"
state="$root/production-state.json"
lane="$root/.f01-global-production-lane.json"

test -d "$root" && test ! -L "$root"
test -f "$health" && test ! -L "$health"
test -f "$slots" && test ! -L "$slots"
test -f "$state" && test ! -L "$state"
test -f "$lane" && test ! -L "$lane"

python3 - "$health" "$slots" "$state" "$lane" <<'PY'
import json, sys
from datetime import datetime, timezone
from pathlib import Path

def read_private_json(raw):
    path = Path(raw)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 200000:
        raise SystemExit("F01_WATCHDOG_PRIVATE_STATE_UNSAFE")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        raise SystemExit("F01_WATCHDOG_PRIVATE_STATE_INVALID")
    if not isinstance(data, dict):
        raise SystemExit("F01_WATCHDOG_PRIVATE_STATE_INVALID")
    return data

health, slots, state, lane = [read_private_json(p) for p in sys.argv[1:]]
if health.get("schema") != "saeit.factory.production-health.v1":
    raise SystemExit("F01_WATCHDOG_HEALTH_SCHEMA_INVALID")
try:
    finished = datetime.fromisoformat(health["last_cycle_finished_at_utc"].replace("Z", "+00:00"))
    age = (datetime.now(timezone.utc) - finished).total_seconds()
except (KeyError, TypeError, ValueError):
    raise SystemExit("F01_WATCHDOG_HEALTH_TIMESTAMP_INVALID")
if not (0 <= age <= 900):
    raise SystemExit("F01_WATCHDOG_HEALTH_STALE")

active = slots.get("active")
if (slots.get("schema") != "saeit.factory.product-slots.v1"
        or slots.get("capacity") != 1
        or not isinstance(active, list) or len(active) != 1
        or not isinstance(active[0], dict)
        or active[0].get("recipe") != "farm_enterprise_economics"
        or state.get("active_product_slot_capacity") != 1
        or state.get("active_product_slot_recipes") != ["farm_enterprise_economics"]):
    raise SystemExit("F01_WATCHDOG_FIRST_PRODUCT_NOT_EXCLUSIVE")

if (lane.get("schema") != "saeit.factory.global-single-production-lane.v1"
        or lane.get("owner") != "line41"
        or type(lane.get("generation")) is not int
        or lane["generation"] < 1):
    raise SystemExit("F01_WATCHDOG_GLOBAL_LANE_UNPROVEN")

if (state.get("publication_locked_until_owner_approval") is not True
        or type(state.get("commercial_quality_review_completed")) is not bool
        or state.get("publishable_product_count") != 0):
    raise SystemExit("F01_WATCHDOG_COMMERCIAL_HOLD_INVALID")

print("F01_WATCHDOG_RUNTIME_HEALTH=PASS")
print("F01_WATCHDOG_QC_RECEIPT=NOT_ASSESSED")
print("F01_WATCHDOG_COMMERCIAL_RELEASE=LOCKED")
PY

