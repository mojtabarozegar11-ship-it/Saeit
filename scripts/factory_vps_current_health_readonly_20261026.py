#!/usr/bin/env python3
"""Read-only, aggregate-only health evidence for the owner VPS factory."""
import collections
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

BASE = Path("/home/githubops/factory-runtime")
PRIVATE = BASE / "private/autonomous-product-cycle"
ORDERS = PRIVATE / "production-instructions/orders"
INDEX = PRIVATE / "production-instructions/owner-agri200-p0-index.json"
OPS = BASE / "operations/production-instructions"
LIMIT = 250000
ORDER_PATTERN = re.compile(r"WO-[0-9]{8}\Z")
HEX = re.compile(r"[0-9a-f]{64}\Z")


def safe_json(path, maximum=LIMIT):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum:
        raise ValueError("unsafe_or_missing")
    return json.loads(path.read_text(encoding="utf8"))


def command(args):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=7,
                           check=False)
        return p.stdout if p.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def inventory():
    if os.geteuid() == 0 or any(p.is_symlink() or not p.is_dir()
                                for p in (BASE, PRIVATE, OPS, ORDERS)):
        raise RuntimeError("UNSAFE_OR_MISSING_FACTORY_ROOT")
    usage = shutil.disk_usage(PRIVATE)
    cron = command(["crontab", "-l"])
    active = ([line for line in cron.splitlines()
               if line.strip() and not line.lstrip().startswith("#")]
              if cron is not None else None)
    tags = (
        "SAEIT_STRICT_SERIAL_PRODUCT_TO_QC1000_20261025",
        "SAEIT_AGRI200_AUTONOMOUS_CLOSED_LOOP_V1",
    )
    timers = command(["systemctl", "list-timers", "--all", "--no-legend",
                      "--no-pager"])
    processes = command(["ps", "-eo", "args="])
    ids = []
    try:
        idx = safe_json(INDEX, 100000)
        listed = idx.get("order_ids_ranked")
        if isinstance(listed, list) and len(listed) <= 2000:
            ids = [v for v in listed if isinstance(v, str)
                   and ORDER_PATTERN.fullmatch(v)]
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        pass
    valid, missing, invalid = 0, 0, 0
    for ident in ids:
        path = ORDERS / (ident + ".json")
        if not path.exists() and not path.is_symlink():
            missing += 1
            continue
        try:
            doc = safe_json(path)
            if (doc.get("id") != ident or
                    doc.get("status") not in
                    ("issued", "in_engineering", "blocked_rework", "completed_verified") or
                    not HEX.fullmatch(str(doc.get("fingerprint", "")))):
                raise ValueError("invalid")
            valid += 1
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            invalid += 1
    order_status = collections.Counter()
    order_origins = collections.Counter()
    known_origins = {"site-topic-snapshot", "mojplaywin-site-qa-return",
                     "owner_requested_education700_p0"}
    unsafe = 0
    for path in ORDERS.iterdir():
        if path.suffix != ".json":
            continue
        try:
            doc = safe_json(path)
            status = doc.get("status")
            order_status[status if isinstance(status, str) else "UNSET"] += 1
            origin = doc.get("origin")
            order_origins[origin if isinstance(origin, str) and origin in known_origins else "other"] += 1
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            unsafe += 1
    serial = OPS / "strict-serial-fullcycle-v1.py"
    sha = None
    if serial.is_file() and not serial.is_symlink() and serial.stat().st_size < 200000:
        sha = hashlib.sha256(serial.read_bytes()).hexdigest()
    state = PRIVATE / "production-instructions/stage-06/strict-serial-active-v1.json"
    state_summary = {"present": state.is_file() and not state.is_symlink()}
    if state_summary["present"]:
        try:
            value = safe_json(state, 100000)
            state_summary.update({
                "last_cycle_utc": value.get("last_cycle_utc"),
                "all_complete": value.get("all_complete"),
                "last_order_certified": value.get("last_order_certified"),
            })
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            state_summary["read_error"] = True
    finished = PRIVATE / "product-lifecycle/approved-finished-goods"
    approved_archive_dirs = 0
    if finished.is_dir() and not finished.is_symlink():
        approved_archive_dirs = sum(1 for folder in finished.iterdir()
                                    if folder.is_dir() and not folder.is_symlink()
                                    and (folder / "product.zip").is_file()
                                    and (folder / "receipt.json").is_file())
    qa_root = PRIVATE / "design-intake/mpw-live-three-sku-qa"
    sku_copies = {}
    for ident in (72, 225, 879):
        location = qa_root / "copies" / str(ident)
        sku_copies[str(ident)] = (sum(1 for x in location.iterdir()
                                      if x.is_file() and not x.is_symlink())
                                  if location.is_dir() and not location.is_symlink() else 0)
    return {
        "schema": "saeit.factory.owner-vps-current-health.v1",
        "observed_utc": datetime.now(timezone.utc).isoformat(),
        "read_only": True, "server_written_bytes": 0,
        "disk_total_gib": round(usage.total / 2**30, 3),
        "disk_free_gib": round(usage.free / 2**30, 3),
        "cron_readable": active is not None,
        "cron_active_count": len(active) if active is not None else None,
        "cron_marker_counts": ({tag: sum(tag in row for row in active)
                                for tag in tags} if active is not None else None),
        "leech_cron_like_count": (sum(bool(re.search("leech|WO-26102501", row, re.I))
                                      for row in active) if active is not None else None),
        "systemd_timers_readable": timers is not None,
        "related_timer_count": (sum(bool(re.search("factory|agri200|qc1000|strict.serial",
                                                    row, re.I)) for row in timers.splitlines())
                                if timers is not None else None),
        "process_inventory_readable": processes is not None,
        "related_process_count": (sum(bool(re.search("factory|agri200|strict.serial",
                                                     row, re.I)) for row in processes.splitlines())
                                  if processes is not None else None),
        "agri_index_entries": len(ids),
        "agri_existing_valid": valid, "agri_missing": missing, "agri_invalid": invalid,
        "current_order_file_status_counts": dict(order_status),
        "current_order_origin_counts": dict(order_origins),
        "current_order_unsafe": unsafe,
        "serial_worker_deployed_sha256": sha,
        "serial_tick": state_summary,
        "finished_archive_directories_with_receipts": approved_archive_dirs,
        "existing_three_sku_private_copies": sku_copies,
    }


if __name__ == "__main__":
    print("FACTORY_OWNER_VPS_READONLY=" + json.dumps(inventory(), sort_keys=True))
