#!/usr/bin/env python3
"""Read-only capacity gate for growing Mojtaba.bot on the existing VPS.

This script does not install software, modify cron, change the database,
order hardware, or authorize spending. Its output intentionally omits paths
and database contents so it can be attached to an operations report.
"""

import argparse
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import sys


GIB = 1024 ** 3
MIB = 1024 ** 2
SCHEMA = "mojtaba.vps.expansion-preflight.v1"


@dataclass(frozen=True)
class CapacitySnapshot:
    total_bytes: int
    available_bytes: int
    used_bytes: int
    database_bytes: int


def _check_path(path: Path, *, directory: bool) -> None:
    """Refuse symlinked targets/ancestors and unexpected filesystem nodes."""
    absolute = path.absolute()
    if any(item.is_symlink() for item in (absolute, *absolute.parents)):
        raise ValueError("UNSAFE_SYMLINKED_PATH")
    if directory and not absolute.is_dir():
        raise ValueError("OPERATIONS_DIRECTORY_MISSING")
    if not directory and not absolute.is_file():
        raise ValueError("DATABASE_FILE_MISSING")


def collect_capacity(operations_dir: Path, database_file: Path) -> CapacitySnapshot:
    """Inspect filesystem metadata only; never connect to or read the DB."""
    _check_path(operations_dir, directory=True)
    _check_path(database_file, directory=False)
    disk = os.statvfs(operations_dir)
    total = disk.f_blocks * disk.f_frsize
    available = disk.f_bavail * disk.f_frsize
    used = (disk.f_blocks - disk.f_bfree) * disk.f_frsize
    return CapacitySnapshot(total, available, used, database_file.stat().st_size)


def evaluate_capacity(snapshot: CapacitySnapshot, *, planned_growth_bytes: int = GIB) -> dict:
    """Require rollback copy, existing master reserve, and growth headroom."""
    values = (
        snapshot.total_bytes, snapshot.available_bytes,
        snapshot.used_bytes, snapshot.database_bytes, planned_growth_bytes,
    )
    if any(not isinstance(v, int) or isinstance(v, bool) or v < 0 for v in values):
        raise ValueError("INVALID_CAPACITY_VALUE")
    if not snapshot.total_bytes or snapshot.available_bytes > snapshot.total_bytes:
        raise ValueError("INVALID_FILESYSTEM_CAPACITY")
    if snapshot.used_bytes > snapshot.total_bytes:
        raise ValueError("INVALID_FILESYSTEM_USAGE")

    # Match the existing master activation's backup reserve, then add a
    # separately budgeted buffer for the proposed expansion itself.
    reserve = max(2 * GIB, math.ceil(snapshot.total_bytes * 0.05))
    required = snapshot.database_bytes + reserve + planned_growth_bytes
    shortfall = max(0, required - snapshot.available_bytes)
    ready = shortfall == 0
    return {
        "schema": SCHEMA,
        "safe_for_scoped_vps_expansion": ready,
        "disk_used_percent": round(snapshot.used_bytes / snapshot.total_bytes * 100, 2),
        "available_bytes": snapshot.available_bytes,
        "database_backup_bytes": snapshot.database_bytes,
        "protected_reserve_bytes": reserve,
        "planned_growth_bytes": planned_growth_bytes,
        "required_available_bytes": required,
        "shortfall_bytes": shortfall,
        "next_action": (
            "review_and_approve_scoped_software_expansion"
            if ready else "pause_expansion_review_storage_or_plan_server_migration"
        ),
        "database_or_service_modified": False,
        "files_deleted": False,
        "deployment_performed": False,
        "hardware_purchase_authorized": False,
        "financial_commitment_created": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operations-dir", type=Path, required=True)
    parser.add_argument("--database-file", type=Path, required=True)
    parser.add_argument("--planned-growth-mib", type=int, default=1024)
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.planned_growth_mib < 0:
            raise ValueError("INVALID_PLANNED_GROWTH")
        snapshot = collect_capacity(args.operations_dir, args.database_file)
        report = evaluate_capacity(snapshot, planned_growth_bytes=args.planned_growth_mib * MIB)
    except (OSError, ValueError) as exc:
        # Do not leak local paths or exception strings into shared logs.
        print(json.dumps({"schema": SCHEMA, "safe_for_scoped_vps_expansion": False,
                          "error_class": type(exc).__name__, "next_action": "manual_capacity_review"}))
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 2 if args.require_ready and not report["safe_for_scoped_vps_expansion"] else 0


if __name__ == "__main__":
    sys.exit(main())
