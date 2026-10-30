#!/usr/bin/env python3
"""Offline, read-only consistency check for operator-supplied factory-stop evidence.

Never contacts a server or changes services. Passing means REVIEW_READY_ONLY,
not independent verification of host identity, operator authority or 100% stop.
"""
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

ZERO_FIELDS = (
    "active_factory_cron", "active_factory_systemd_units",
    "active_factory_supervisor_jobs", "active_factory_container_restarts",
    "active_factory_remote_triggers", "active_factory_workers",
    "active_factory_writers", "factory_d_state_processes",
    "active_factory_queue_consumers", "unclassified_factory_processes",
)
REQUIRED_TRUE = (
    "all_factory_owners_inventoried", "cron_inventory_complete",
    "systemd_inventory_complete", "supervisor_inventory_complete",
    "container_inventory_complete", "remote_trigger_inventory_complete",
    "db_and_wal_stable", "public_sites_healthy", "ssh_relay_healthy",
)
HASH = re.compile(r"[0-9a-f]{64}\Z")


def parse_utc(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("TIMESTAMP_NOT_UTC_Z")
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def validate(document, now=None):
    reasons = []
    now = now or dt.datetime.now(dt.timezone.utc)
    if document.get("schema") != "f01.factory_stop_operator_evidence.v1":
        reasons.append("INVALID_SCHEMA")
    op = document.get("operator")
    if not isinstance(op, dict) or op.get("authorized_console") is not True or op.get("independent_of_automation") is not True:
        reasons.append("OPERATOR_AUTHORITY_UNATTESTED")
    escrow = document.get("escrow")
    if not isinstance(escrow, dict) or escrow.get("offhost_readback") is not True or not isinstance(escrow.get("sha256"), str) or not HASH.fullmatch(escrow["sha256"]):
        reasons.append("ROLLBACK_ESCROW_UNVERIFIED")
    polls = document.get("polls")
    if not isinstance(polls, list) or len(polls) != 2:
        reasons.append("REQUIRE_EXACTLY_TWO_POLLS")
        polls = []
    times = []
    for i, poll in enumerate(polls):
        if not isinstance(poll, dict):
            reasons.append(f"POLL_{i}_NOT_OBJECT")
            continue
        try:
            when = parse_utc(poll.get("observed_utc"))
            times.append(when)
            if when > now + dt.timedelta(seconds=30) or now - when > dt.timedelta(minutes=15):
                reasons.append(f"POLL_{i}_STALE_OR_FUTURE")
        except (ValueError, TypeError):
            reasons.append(f"POLL_{i}_INVALID_TIMESTAMP")
        for field in ZERO_FIELDS:
            if type(poll.get(field)) is not int or poll[field] != 0:
                reasons.append(f"POLL_{i}_{field}_NOT_ZERO")
        for field in REQUIRED_TRUE:
            if poll.get(field) is not True:
                reasons.append(f"POLL_{i}_{field}_NOT_VERIFIED")
    if len(times) == 2 and not (dt.timedelta(seconds=60) <= times[1] - times[0] <= dt.timedelta(minutes=15)):
        reasons.append("POLL_INTERVAL_INVALID")
    # This is deliberately not an authorization or a factual host attestation.
    return {"schema": "f01.factory_hold_gate_result.v1",
            "decision": "REVIEW_READY_ONLY" if not reasons else "NO_GO",
            "full_factory_stop_verified": False,
            "production_backup_verified": False,
            "vps_mutation_performed": False,
            "reasons": sorted(set(reasons))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence_json", help="Operator-provided JSON path; read-only")
    args = parser.parse_args()
    try:
        payload = json.loads(Path(args.evidence_json).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("ROOT_NOT_OBJECT")
        result = validate(payload)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result = {"schema": "f01.factory_hold_gate_result.v1", "decision": "NO_GO",
                  "full_factory_stop_verified": False, "production_backup_verified": False,
                  "vps_mutation_performed": False, "reasons": [type(exc).__name__]}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["decision"] == "REVIEW_READY_ONLY" else 2

if __name__ == "__main__":
    sys.exit(main())
