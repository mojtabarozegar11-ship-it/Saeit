"""Read factory operational evidence privately on the VPS, never through CI.

The factory SQLite database is independent of the cPanel Django database.
Read using SQLite's mode=ro and query_only. Store a permission-restricted
report next to this staged source. No customer data, figures or exceptions
cross SSH; a fixed status marker is the only allowed output.
"""

from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile


def _load_business_review(source_root):
    source = source_root / "core" / "business_management.py"
    spec = importlib.util.spec_from_file_location("business_os_vps_analysis", source)
    if spec is None or spec.loader is None:
        raise RuntimeError("Invalid staged analysis module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _count_or_unknown(connection, module, timestamp, table, condition="", requirements=()):
    columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
    if not set(requirements).issubset(columns):
        return module.unknown(f"{table}: source table or required columns absent")
    try:
        count = connection.execute(f"SELECT COUNT(*) FROM {table} {condition}").fetchone()[0]
        return module.observed(count, f"vps_private_factory_sqlite:{table}", timestamp)
    except sqlite3.DatabaseError:
        return module.unknown(f"{table}: read-only query failed")


def build_factory_snapshot(source_root, database):
    """Pure read-only collection; source root must already be private staged."""
    module = _load_business_review(source_root)
    timestamp = datetime.now(timezone.utc).isoformat()
    if not database.is_file() or database.is_symlink():
        raise RuntimeError("Factory source unavailable; no fallback empty DB")
    db_uri = database.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(db_uri, uri=True, timeout=12)
    try:
        connection.execute("PRAGMA query_only=ON")
        queued = _count_or_unknown(connection, module, timestamp, "core_agenttask",
                                   "WHERE status='queued'", ("status",))
        blocked = _count_or_unknown(connection, module, timestamp, "core_agenttask",
                                    "WHERE status='blocked'", ("status",))
        active = _count_or_unknown(connection, module, timestamp, "core_product",
                                   "WHERE active=1", ("active",))
        draft = _count_or_unknown(connection, module, timestamp, "core_product",
                                  "WHERE factory_managed=1 AND active=0",
                                  ("factory_managed", "active"))
        run_receipts = _count_or_unknown(connection, module, timestamp,
                                         "core_factoryrun", requirements=("id",))
    finally:
        connection.close()
    metrics = {
        "queued_tasks": queued,
        "blocked_tasks": blocked,
        "active_products": active,
        "orders": module.unknown("Only cPanel/store order systems can verify orders"),
        "pending_approvals": module.unknown("Not independently connected from factory VPS"),
        "independently_validated_market": module.unknown("No attributable customer tests"),
        "verified_collected_cash": module.unknown("No payment and ledger reconciliation"),
        "accepted_factory_products": module.unknown("Run receipts are not specialist acceptance"),
        "site_health": module.unknown("Website health evidence not connected"),
    }
    review = module.review_business(metrics)
    review.update({
        "generated_at": timestamp,
        "scope": "VPS local isolated factory SQLite only; cPanel and payment data excluded",
        "metrics": metrics,
        "additional_operational_indicators": {
            "factory_managed_drafts": draft,
            "factory_run_rows_not_acceptance": run_receipts,
        },
    })
    return review


def _write_private(source_root, report):
    private_dir = source_root / "private"
    private_dir.mkdir(mode=0o700, exist_ok=True)
    os.chmod(private_dir, 0o700)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=private_dir,
            prefix=".factory-review-", suffix=".json", delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            os.fchmod(handle.fileno(), 0o600)
            json.dump(report, handle, ensure_ascii=False, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, private_dir / "factory-review.json")
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def main():
    source_root = Path(__file__).resolve().parent.parent
    expected_releases = Path.home().resolve() / "saeit-business-os-staging" / "releases"
    if expected_releases not in source_root.parents:
        raise RuntimeError("Not a VPS private staging release")
    db = Path.home().resolve() / "factory-runtime" / "private" / "factory-fresh-isolated.sqlite3"
    report = build_factory_snapshot(source_root, db)
    _write_private(source_root, report)
    # A successful run must prove the task sensor works, not merely that a
    # JSON file could be written. No counts or source contents are emitted.
    if not all(report["metrics"][key]["state"] == "observed"
               for key in ("queued_tasks", "blocked_tasks")):
        raise RuntimeError("Factory task schema unavailable")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Never log the exception; it might contain private path or DB details.
        print("BUSINESS_OS_VPS_SOURCE_UNAVAILABLE", file=sys.stderr)
        raise SystemExit(1)
    print("BUSINESS_OS_VPS_PRIVATE_REPORT_CREATED")
