#!/usr/bin/env python3
"""F41 private intake: bounded, idempotent invoice reconciliation; never delivers goods."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import time

import f41_merchant_audit_cli as audit
try:
    import f41_tron_mainnet_check as verifier
except ModuleNotFoundError as exc:
    if exc.name != "f41_tron_mainnet_check":
        raise
    import verifier

JOB = re.compile(r"job-[A-Za-z0-9][A-Za-z0-9_.-]{0,47}\Z")
MAX_PER_TICK = 3


def secure_dir(path):
    if path.is_symlink() or not path.is_dir():
        raise ValueError("F41_RUNTIME_DIR_INVALID")
    info = path.stat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise ValueError("F41_RUNTIME_DIR_PERMISSIONS")


def secure_file(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("F41_JOB_FILE_INVALID")
    info = path.stat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise ValueError("F41_JOB_FILE_PERMISSIONS")


def atomic_json(path, obj):
    data = (json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n").encode("utf8")
    tmp = path.parent / (".status-tmp-" + str(os.getpid()) + "-" + str(time.time_ns()))
    with tmp.open("xb") as stream:
        os.chmod(tmp, 0o600)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)


def process_one(source, outbox):
    dest = outbox / source.name
    if dest.is_symlink() or dest.exists():
        return "ALREADY_PROCESSED_OR_REVIEW"
    for name in ("READY", "invoices.csv", "payments.csv"):
        secure_file(source / name)
    if (source / "READY").stat().st_size:
        raise ValueError("F41_JOB_READY_MARKER_NOT_EMPTY")
    dest.mkdir(mode=0o700)
    status = {
        "job": source.name, "schema": "saeit.f41.private-intake.v1",
        "delivery_authorized": False, "payment_actions": 0,
        "public_site_writes": 0, "commercial_approval": False
    }
    try:
        inv = source / "invoices.csv"
        pay = source / "payments.csv"
        before = [audit.digest(audit.input_bytes(p)) for p in (inv, pay)]
        audit.build(inv, pay, dest / "reconciliation")
        onchain_enabled = os.environ.get("F41_WORKER_ONCHAIN_ENABLED") == "1"
        if onchain_enabled:
            evidence = verifier.write_private(inv, pay, dest / "onchain")
        else:
            evidence = {"live_matched_count": 0, "network_lookups_attempted": 0,
                        "simulation": False}
        after = [audit.digest(audit.input_bytes(p)) for p in (inv, pay)]
        if before != after:
            raise ValueError("F41_INPUT_CHANGED_DURING_PROCESSING")
        status.update(result="COMPLETE_READONLY",
                      live_solidified_matches=evidence["live_matched_count"],
                      attempted_network_lookups=evidence["network_lookups_attempted"],
                      request_simulated=evidence["simulation"],
                      onchain_check_enabled=onchain_enabled)
    except Exception as exc:
        code = str(exc)
        if not re.fullmatch(r"F41_[A-Z0-9_]+", code):
            code = "F41_JOB_EXECUTION_FAILED"
        status.update(result="REQUIRES_REPAIR", error_code=code)
    atomic_json(dest / "status.json", status)
    return status["result"]


def tick(runtime):
    secure_dir(runtime)
    inbox = runtime / "inbox"
    outbox = runtime / "outbox"
    for directory in (inbox, outbox):
        directory.mkdir(mode=0o700, exist_ok=True)
        secure_dir(directory)
    lock = runtime / ".worker.lock"
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(lock, flags, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError("F41_LOCK_INVALID")
        if stat.S_IMODE(os.fstat(fd).st_mode) & 0o077:
            raise ValueError("F41_LOCK_PERMISSIONS")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"state": "BUSY", "completed": 0, "review": 0}
        completed = reviewed = 0
        ready = 0
        for source in sorted(inbox.iterdir()):
            if not JOB.fullmatch(source.name):
                continue
            if source.is_symlink() or not source.is_dir():
                continue
            if (outbox / source.name).exists() or (outbox / source.name).is_symlink():
                continue
            if not (source / "READY").is_file():
                continue
            ready += 1
            if completed + reviewed >= MAX_PER_TICK:
                continue
            try:
                secure_dir(source)
                outcome = process_one(source, outbox)
            except Exception:
                # Unsafe/unsealed job remains untouched for correction.
                reviewed += 1
                continue
            if outcome == "COMPLETE_READONLY":
                completed += 1
            else:
                reviewed += 1
        summary = {
            "schema": "saeit.f41.private-intake-heartbeat.v1",
            "epoch": int(time.time()), "state": "RUNNING" if ready else "WAITING_FOR_INPUT",
            "ready_seen": ready, "completed_this_tick": completed,
            "repair_this_tick": reviewed, "max_per_tick": MAX_PER_TICK,
            "payment_actions": 0, "delivery_authorized": False
        }
        atomic_json(runtime / "heartbeat.json", summary)
        return summary
    finally:
        os.close(fd)


def main():
    parser = argparse.ArgumentParser(description="F41 private read-only intake worker: three jobs per tick")
    parser.add_argument("--runtime", required=True)
    args = parser.parse_args()
    print(json.dumps(tick(Path(args.runtime)), sort_keys=True))


if __name__ == "__main__":
    main()
