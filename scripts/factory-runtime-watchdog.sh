#!/usr/bin/env bash
set -euo pipefail
umask 077

root=/home/githubops/factory-runtime/private/autonomous-product-cycle
health="$root/production-health.json"
slots="$root/quality-excellence/product-flow/active-slots/current.json"
state="$root/production-state.json"

test -d "$root" && test ! -L "$root"
test -f "$health" && test ! -L "$health"
test -f "$slots" && test ! -L "$slots"
test -f "$state" && test ! -L "$state"

python3 - "$health" "$slots" "$state" <<'PY'
import json, sys, time
from datetime import datetime, timezone
health, slots, state = [json.loads(open(p, encoding="utf-8").read()) for p in sys.argv[1:]]
assert health.get("schema") == "saeit.factory.production-health.v1"
finished = datetime.fromisoformat(health["last_cycle_finished_at_utc"])
age = (datetime.now(timezone.utc) - finished).total_seconds()
assert 0 <= age <= 900, "FACTORY_HEALTH_STALE"
assert slots.get("capacity") == 1
assert len(slots.get("active", [])) <= 1
assert state.get("active_product_slot_capacity") == 1
assert state.get("commercial_quality_review_completed") is False or state.get("commercial_quality_review_completed") is True
assert state.get("publication_locked_until_owner_approval") is True
print("FACTORY_WATCHDOG=PASS")
PY
