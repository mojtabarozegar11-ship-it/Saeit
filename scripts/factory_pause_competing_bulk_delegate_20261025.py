#!/usr/bin/env python3
"""Pause only the obsolete broad stage-1-to-6 bulk delegate, preserving storefront and order queue."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

HOME = Path("/home/githubops")
OPS = HOME / "factory-runtime/operations"
BACKUPS = OPS / "backups"
MARKER = "SAEIT_FACTORY_OWNER_DELEGATE_COORDINATION_V1"
ENGLISH = "SAEIT_ENGLISH_FIRST_SINGLE_ACTIVE_20261025"
COMMENT = "# PAUSED_BULK_DELEGATE_FOR_ONE_ENGLISH_PRODUCT_20261025 "
EXPECTED_PATH = "/home/githubops/factory-runtime/operations/production-instructions/delegated-internal-autonomy.py"

def crons():
    return subprocess.run(["crontab", "-l"], capture_output=True, text=True,
                          timeout=12, check=True).stdout

def act(run_id, apply):
    if os.geteuid() == 0 or os.getenv("USER") != "githubops":
        raise RuntimeError("REQUIRES_GITHUBOPS_NONROOT")
    for p in (OPS, BACKUPS, HOME / "factory-runtime/private/autonomous-product-cycle/production-instructions/orders"):
        if not p.is_dir() or p.is_symlink():
            raise RuntimeError("REQUIRED_PRIVATE_PATH_MISSING_OR_SYMLINK")
    if not re.fullmatch(r"[0-9]{5,15}-[0-9]{1,3}", run_id):
        raise RuntimeError("INVALID_RUN_ID")
    lock = OPS / ".exclusive-private-producer-cron-edit.lock"
    if lock.is_symlink():
        raise RuntimeError("UNSAFE_CRON_LOCK")
    with lock.open("a+b") as guard:
        fcntl.flock(guard.fileno(), fcntl.LOCK_EX)
        before = crons()
        rows = before.splitlines()
        active = [line for line in rows if line.strip() and not line.lstrip().startswith("#")]
        targets = [line for line in active if MARKER in line]
        english = [line for line in active if ENGLISH in line]
        if len(targets) != 1 or len(english) != 1:
            raise RuntimeError("EXACTLY_ONE_BULK_AND_ONE_ENGLISH_CRON_REQUIRED")
        target = targets[0]
        if not (target.startswith("*/5 * * * * ")
                and EXPECTED_PATH in target
                and "--batch 50" in target
                and target.rstrip().endswith("# " + MARKER)
                and target.count(EXPECTED_PATH) == 1):
            raise RuntimeError("UNKNOWN_BULK_DELEGATE_CRON_CONTENT")
        if any(MARKER in line for line in active if line != target):
            raise RuntimeError("COMPETING_BULK_DELEGATE_CRON")
        updated = "\n".join(COMMENT + row if row == target else row for row in rows) + "\n"
        report = {
            "mode": "APPLY" if apply else "DRY_RUN",
            "bulk_delegate_found": 1,
            "bulk_delegate_newly_paused": False,
            "english_first_cron_preserved": True,
            "remaining_active_cron_entries": len(active) - int(apply),
            "order_list_modified": False,
            "customer_warehouse_modified": False,
            "storefront_modified": False,
            "other_cron_lines_modified": False,
        }
        if not apply:
            return report
        backup = BACKUPS / ("bulk-delegate-paused-" + run_id + ".cron")
        if backup.exists() or backup.is_symlink():
            raise RuntimeError("BACKUP_ALREADY_EXISTS")
        fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w", encoding="utf8") as stream:
            stream.write(before)
            stream.flush()
            os.fsync(stream.fileno())
        if crons() != before:
            raise RuntimeError("CRON_CHANGED_CONCURRENTLY")
        fd, tmp = tempfile.mkstemp(prefix=".private-producer-pause-", dir=str(OPS))
        try:
            with os.fdopen(fd, "w", encoding="utf8") as stream:
                stream.write(updated)
            try:
                subprocess.run(["crontab", tmp], check=True, timeout=12)
                if crons() != updated:
                    raise RuntimeError("CRON_VERIFY_FAILED")
                if sum(ENGLISH in line and not line.startswith("#")
                       for line in crons().splitlines()) != 1:
                    raise RuntimeError("ENGLISH_FIRST_CRON_NOT_PRESERVED")
            except Exception:
                if crons() == updated:
                    subprocess.run(["crontab", str(backup)], check=True, timeout=12)
                raise
        finally:
            os.unlink(tmp)
        report["bulk_delegate_newly_paused"] = True
        report["cron_backup"] = backup.name
        return report

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        print("BULK_DELEGATE_PAUSE=" + json.dumps(act(args.run_id, args.apply), sort_keys=True), flush=True)
    except Exception as err:
        print("BULK_DELEGATE_PAUSE_FAILED=" + type(err).__name__ + ":" + str(err)[:200], flush=True)
        raise
