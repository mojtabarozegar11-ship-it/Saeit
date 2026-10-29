#!/usr/bin/env python3
"""Read-only, fail-closed factory release triage from a pinned VPS snapshot.

Never authorizes restart, cleanup, cron edits, worker launch, or deployment.
No customer data, command lines, paths, or credentials are emitted.
"""
import argparse
import datetime as dt
import json
import math
import sys

RESERVE_BYTES = 5 * 1024**3 + 128 * 1024**2
UTC = dt.timezone.utc

def mapping(value):
    return value if isinstance(value, dict) else {}

def natural_int(value):
    return type(value) is int and value >= 0

def evaluate(snapshot, now=None):
    now = now or dt.datetime.now(UTC)
    reasons = []
    if not isinstance(snapshot, dict) or snapshot.get("schema") != "f01-vps-console-readonly.v1" or snapshot.get("read_only") is not True:
        reasons.append("SNAPSHOT_SCHEMA_OR_READONLY_INVALID")
        snapshot = {}
    stamp = snapshot.get("observed_utc")
    try:
        observed = dt.datetime.fromisoformat(stamp)
        if observed.tzinfo is None or not 0 <= (now - observed).total_seconds() <= 1800:
            reasons.append("SNAPSHOT_STALE_OR_FUTURE")
    except (ValueError, TypeError):
        reasons.append("SNAPSHOT_TIME_UNAVAILABLE")
    root = mapping(mapping(snapshot.get("filesystem")).get("target_1"))
    available = root.get("available_bytes")
    free = root.get("free_bytes")
    if root.get("state") != "OBSERVED" or not natural_int(available):
        reasons.append("FILESYSTEM_UNOBSERVED")
        available = None
    elif available < RESERVE_BYTES:
        reasons.append("ORDINARY_USER_CAPACITY_BELOW_5GIB_RESERVE")
    if not natural_int(free):
        free = None
    reserved_gap = free - available if free is not None and available is not None and free >= available else None
    guest = mapping(snapshot.get("guest"))
    cores, load = guest.get("cpu_count"), guest.get("loadavg")
    if not natural_int(cores) or cores == 0 or not isinstance(load, list) or not load or type(load[0]) not in (int, float) or not math.isfinite(load[0]) or load[0] < 0:
        reasons.append("CPU_PRESSURE_UNOBSERVED")
    elif load[0] > cores * 2:
        reasons.append("LOAD_ABOVE_TWICE_CPU_COUNT")
    memory = mapping(guest.get("memory")).get("MemTotal_kib")
    if not natural_int(memory) or memory < 7 * 1024**2:
        reasons.append("PAID_8GIB_RAM_NOT_OBSERVED")
    pressure = mapping(snapshot.get("process_pressure"))
    d = mapping(pressure.get("all_process_states")).get("D")
    if not natural_int(d):
        reasons.append("D_STATE_UNOBSERVED")
    elif d > 8:
        reasons.append("HIGH_UNINTERRUPTIBLE_SLEEP_COUNT")
    # A process-name match, cron entry or file header is never execution proof.
    cron = mapping(snapshot.get("cron"))
    if cron.get("state") != "OBSERVED":
        reasons.append("CRON_UNOBSERVED")
    else:
        ticks = cron.get("factory_per_minute_entries")
        if not natural_int(ticks) or ticks == 0:
            reasons.append("FACTORY_MINUTE_CRON_UNCONFIRMED")
        duplicates = cron.get("exact_duplicate_entries")
        if not natural_int(duplicates):
            reasons.append("CRON_DUPLICATE_COUNT_UNOBSERVED")
        elif duplicates:
            reasons.append("CRON_DUPLICATE_ENTRIES")
    queue = mapping(mapping(snapshot.get("queue")).get("target_1"))
    pending = queue.get("entries_at_least")
    if queue.get("state") != "OBSERVED" or not natural_int(pending):
        reasons.append("QUEUE_UNOBSERVED")
    elif pending:
        reasons.append("NONEMPTY_QUEUE_NEEDS_WORKER_RECEIPT")
    if queue.get("truncated") is True:
        reasons.append("QUEUE_SCAN_TRUNCATED")
    worker = mapping(snapshot.get("worker"))
    if worker.get("state") != "OBSERVED" or worker.get("truncated") is True:
        reasons.append("WORKER_SCAN_INCOMPLETE")
    init_shell = mapping(pressure.get("init_parent_executable_categories")).get("shell")
    if natural_int(init_shell) and init_shell > 32:
        reasons.append("ORPHAN_SHELL_STORM")
    # No guessed private paths: absent targets mean unconfigured probes, not missing files.
    for key, reason in (("locks", "LOCK_PROBE_NOT_CONFIGURED"),
                        ("sqlite", "DB_HEADER_PROBE_NOT_CONFIGURED"),
                        ("backup", "LOCAL_BACKUP_PROBE_NOT_CONFIGURED")):
        targets = mapping(snapshot.get(key))
        if not targets:
            reasons.append(reason)
        elif not any(mapping(v).get("state") in ("PRESENT", "OBSERVED") for v in targets.values()):
            reasons.append(reason.replace("NOT_CONFIGURED", "NOT_OBSERVED"))
    available_ram = mapping(guest.get("memory")).get("MemAvailable_kib")
    if natural_int(available_ram) and available_ram < 512 * 1024:
        reasons.append("AVAILABLE_RAM_BELOW_512MIB")
    if snapshot.get("offhost_backup_restored") != "VERIFIED":
        reasons.append("OFFHOST_RESTORE_NOT_PROVEN")
    if snapshot.get("worker_running_verified") is not True:
        reasons.append("WORKER_NOT_LIVE_VERIFIED")
    return {"schema": "f01-capacity-release-no-go.v1", "status": "NO_GO",
            "deployment_authorized": False, "restart_authorized": False,
            "cleanup_authorized": False, "cron_change_authorized": False,
            "observed_utc": stamp if isinstance(stamp, str) else None,
            "available_bytes_for_unprivileged": available,
            "free_bytes_including_privileged_reserve": free,
            "estimated_privileged_reserved_gap_bytes": reserved_gap,
            "reasons": sorted(set(reasons)),
            "interpretation": "Nonzero total free bytes can coexist with zero ordinary-user available bytes. Manual backup and owner release gates remain mandatory."}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("snapshot", help="local redacted JSON snapshot file; '-' for stdin")
    args = p.parse_args()
    try:
        if args.snapshot == "-":
            data = json.load(sys.stdin)
        else:
            with open(args.snapshot, encoding="utf-8") as handle:
                data = json.load(handle)
    except (OSError, ValueError):
        data = {}
    print(json.dumps(evaluate(data), sort_keys=True))
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
