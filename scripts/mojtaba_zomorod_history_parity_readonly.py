#!/usr/bin/env python3
"""Fail-closed, read-only lineage manifest for SITE-only legacy Zomorod SQLite.

Reads exact five historical agent tables, never their other business tables.
Never copies or prints private row bodies. A manifest proves only logical
equivalence of two already-consistent *offline* snapshots when independently
compared; it cannot itself perform backup/restore, replace the PHP dashboard,
or authorize deleting any legacy row/file/Cron. No VPS/factory interaction.
"""
from __future__ import annotations

from contextlib import closing
from hashlib import sha256
import json
import os
from pathlib import Path
import pwd
import sqlite3
import stat
from urllib.parse import quote

SITE_HOME = Path("/home/zomorod2")
RELATIVE = Path(".private/zomorod-business/site_agents.sqlite3")
MAX_BYTES = 512 * 1024 * 1024
MAX_ROWS_PER_TABLE = 5_000_000

# Explicit original PHP DDL column names. Unexpected/missing schema fails
# closed rather than silently signing incomplete history.
TABLES = {
    "agents": ("code", "title", "mission", "check_path", "enabled", "created_at"),
    "runs": ("id", "agent_code", "status", "http_code", "duration_ms", "detail", "occurred_at"),
    "site_work_state": ("agent_code", "last_check_at", "last_status", "last_artifact_id", "last_sha256"),
    "site_work_outputs": ("id", "agent_code", "check_path", "output_type", "status",
                          "http_code", "quality_score", "title", "findings_json",
                          "source_sha256", "elapsed_ms", "observed_at"),
    "site_work_generation_evidence": (
        "id", "agent_code", "candidate_sha256", "baseline_sha256",
        "benchmark_before", "benchmark_after", "tests_passed", "accepted", "created_at",
    ),
}
PRIMARY = {name: ("code" if name == "agents" else "agent_code" if name == "site_work_state"
                  else "id") for name in TABLES}
SCHEMA = "mojtaba.bot.ai.zomorod-legacy-history-lineage.v1"


def fail(reason: str) -> dict:
    return {"schema": SCHEMA, "state": reason, "manifest_complete": False,
            "retirement_authorized": False, "history_deleted": False,
            "database_modified": False, "rows_exported": False}


def _safe_path(path: Path, *, home: Path) -> bool:
    if home.is_symlink() or not home.is_dir() or path != home / RELATIVE:
        return False
    current = home
    for segment in RELATIVE.parts:
        current = current / segment
        if current.is_symlink():
            return False
    return path.is_file()


def _sidecar_exists(path: Path) -> bool:
    return any(Path(str(path) + suffix).exists() for suffix in ("-wal", "-shm", "-journal"))


def _file_identity(path: Path) -> tuple[int, int, int, int, int]:
    metadata = os.lstat(path)
    if not stat.S_ISREG(metadata.st_mode) or not 0 < metadata.st_size <= MAX_BYTES:
        raise ValueError("UNSAFE_SQLITE_FILE")
    return (metadata.st_dev, metadata.st_ino, metadata.st_size,
            metadata.st_mtime_ns, metadata.st_ctime_ns)


def scan(*, home: Path = SITE_HOME) -> dict:
    """Read an already checkpointed, quiescent database at the sole site path.

    Home injection exists for offline fixture tests; production CLI verifies
    exact non-root cPanel identity before invoking scan.
    """
    home = Path(home)
    path = home / RELATIVE
    if not _safe_path(path, home=home):
        return fail("missing_or_unsafe_site_database")
    if _sidecar_exists(path):
        return fail("sqlite_wal_or_journal_present_snapshot_unreliable")
    try:
        before = _file_identity(path)
        uri = "file:" + quote(str(path), safe="/") + "?mode=ro&immutable=1"
        with closing(sqlite3.connect(uri, uri=True, timeout=2)) as conn:
            conn.execute("PRAGMA query_only=ON")
            quick = conn.execute("PRAGMA quick_check(1)").fetchone()
            if quick != ("ok",):
                return fail("sqlite_integrity_not_verified")
            available = {
                name for (name,) in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            if not set(TABLES).issubset(available):
                return fail("incomplete_site_agent_history_tables")
            rows = {}
            for table, expected in TABLES.items():
                actual = tuple(row[1] for row in conn.execute(f"PRAGMA table_info({table})"))
                if actual != expected:
                    return fail("legacy_history_schema_drift")
                total = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                if type(total) is not int or not 0 <= total <= MAX_ROWS_PER_TABLE:
                    return fail("legacy_history_rows_outside_limit")
                digest = sha256((SCHEMA + "\0" + table + "\0").encode("utf-8"))
                count = 0
                # All original columns, including private text, stay local;
                # nothing except the cumulative digest/row count is emitted.
                for values in conn.execute(
                    f"SELECT * FROM {table} ORDER BY {PRIMARY[table]}"
                ):
                    if any(type(x) not in (type(None), str, int, float, bytes)
                           for x in values):
                        return fail("unexpected_sqlite_value_type")
                    if any(isinstance(x, (bytes, bytearray)) for x in values):
                        return fail("binary_private_history_not_supported")
                    raw = json.dumps(values, ensure_ascii=False, allow_nan=False,
                                     separators=(",", ":")).encode("utf-8")
                    digest.update(len(raw).to_bytes(8, "big"))
                    digest.update(raw)
                    count += 1
                if count != total:
                    return fail("history_count_drift_during_read")
                rows[table] = {"count": count, "row_content_sha256": digest.hexdigest()}
        if _sidecar_exists(path) or _file_identity(path) != before:
            return fail("sqlite_changed_during_read")
        aggregate = sha256(json.dumps(rows, sort_keys=True, separators=(",", ":"))
                           .encode("utf-8")).hexdigest()
        return {
            "schema": SCHEMA, "state": "offline_source_history_manifest_only",
            "table_count": len(TABLES), "tables": rows,
            "table_total_rows": sum(v["count"] for v in rows.values()),
            "lineage_sha256": aggregate,
            "manifest_complete": True,
            "proves_live_worker_execution": False,
            "proves_off_host_restore": False,
            "panel_replaced": False,
            "retirement_authorized": False,
            "history_deleted": False, "database_modified": False,
            "rows_exported": False,
        }
    except (OSError, ValueError, TypeError, OverflowError, sqlite3.Error):
        return fail("sqlite_history_manifest_unavailable")


def compare(source: dict, independently_restored: dict) -> dict:
    """Compare manifests, NOT a restoration drill or authority to delete."""
    valid = all(
        isinstance(x, dict) and x.get("schema") == SCHEMA
        and x.get("state") == "offline_source_history_manifest_only"
        and x.get("manifest_complete") is True
        and type(x.get("table_total_rows")) is int
        and len(x.get("tables", {})) == len(TABLES)
        and all(type(x["tables"].get(t, {}).get("count")) is int
                and isinstance(x["tables"].get(t, {}).get("row_content_sha256"), str)
                and len(x["tables"][t]["row_content_sha256"]) == 64 for t in TABLES)
        for x in (source, independently_restored)
    )
    same = bool(valid and source["tables"] == independently_restored["tables"]
                and source["lineage_sha256"] == independently_restored["lineage_sha256"])
    return {
        "schema": SCHEMA, "state": "matching_manifest" if same else "not_verified",
        "all_five_tables_equal": same,
        "records_equal": same,
        "restore_procedure_verified": False,
        "retirement_authorized": False,
        "live_host_changed": False,
    }


def main() -> None:
    # No custom path, command, host, network or shell input. Exactly the
    # existing cPanel owner is permitted to inspect its own historical DB.
    if (os.geteuid() == 0 or pwd.getpwuid(os.geteuid()).pw_name != "zomorod2"
            or Path.home() != SITE_HOME):
        raise SystemExit("CPANEL_SITE_OWNER_ONLY")
    print(json.dumps(scan(), sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
