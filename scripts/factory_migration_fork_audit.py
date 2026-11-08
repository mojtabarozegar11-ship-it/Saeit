#!/usr/bin/env python3
"""Compare factory migration histories without importing Django or touching a DB.

This identifies source-history forks only. It cannot establish which migrations
were applied on a live VPS and must never authorize a migration or deployment.
"""

import argparse
import ast
import hashlib
import json
import re
import sqlite3
import stat
from pathlib import Path


SCHEMA = "saeit.factory.migration-fork-audit.v1"
MAX_MIGRATIONS = 400
MAX_MIGRATION_BYTES = 1_000_000
MIGRATION_NAME = re.compile(r"^[0-9]{4}_[a-zA-Z0-9_]+\.py$")
MIGRATION_STEM = re.compile(r"^[0-9]{4}_[a-zA-Z0-9_]+$")
MAX_LEDGER_ROWS = 400
MAX_SNAPSHOT_BYTES = 5 * 1024**3
REQUIRED_TASK_FIELDS = ("factory_run_id", "product_id", "environment",
                        "next_retry_at")


def _inspect_sqlite_snapshot(path, current_only, reference_only, shared):
    """Inspect an explicitly supplied *offline copy*, never a running DB.

    immutable=1 and query_only are both intentional: no WAL/SHM creation or
    database writes. Refuse SQLite sidecars because ignoring WAL would produce
    potentially stale evidence. This cannot attest a live VPS or safe cutover.
    """
    snapshot = Path(path)
    def blocked(code):
        return {"state": "unavailable", "code": code,
                "live_vps_verified": False, "production_ready": False}

    if not snapshot.is_absolute():
        return blocked("SNAPSHOT_ABSOLUTE_PATH_REQUIRED")
    try:
        details = snapshot.lstat()
        if (not stat.S_ISREG(details.st_mode) or details.st_size < 100
                or details.st_size > MAX_SNAPSHOT_BYTES):
            return blocked("SNAPSHOT_FILE_UNSAFE")
        if any(Path(str(snapshot) + suffix).exists()
               for suffix in ("-wal", "-shm", "-journal")):
            return blocked("SNAPSHOT_JOURNAL_SIDECAR_PRESENT")
        with snapshot.open("rb") as stream:
            if stream.read(16) != b"SQLite format 3\x00":
                return blocked("SNAPSHOT_NOT_SQLITE")
        connection = sqlite3.connect(
            snapshot.as_uri() + "?mode=ro&immutable=1", uri=True, timeout=3)
        try:
            connection.execute("PRAGMA query_only=ON")
            connection.execute("PRAGMA trusted_schema=OFF")
            columns = {row[1] for row in connection.execute(
                "PRAGMA table_info(django_migrations)")}
            if not {"app", "name"}.issubset(columns):
                return blocked("SNAPSHOT_MIGRATION_TABLE_UNAVAILABLE")
            names = [row[0] for row in connection.execute(
                "SELECT name FROM django_migrations WHERE app='core' "
                "ORDER BY name LIMIT ?", (MAX_LEDGER_ROWS + 1,))]
            if (len(names) > MAX_LEDGER_ROWS or any(
                    not isinstance(name, str) or not MIGRATION_STEM.fullmatch(name)
                    for name in names)):
                return blocked("SNAPSHOT_MIGRATION_LEDGER_INVALID")
            task_columns = {row[1] for row in connection.execute(
                "PRAGMA table_info(core_agenttask)")}
            product_columns = {row[1] for row in connection.execute(
                "PRAGMA table_info(core_product)")}
            run_columns = {row[1] for row in connection.execute(
                "PRAGMA table_info(core_factoryrun)")}
        finally:
            connection.close()
    except (OSError, ValueError, sqlite3.Error):
        return blocked("SNAPSHOT_READ_FAILED")

    applied = set(names)
    current_hits = sorted(applied & set(current_only))
    reference_hits = sorted(applied & set(reference_only))
    if current_hits and reference_hits:
        branch = "mixed_fork"
    elif current_hits:
        branch = "current_branch_only"
    elif reference_hits:
        branch = "reference_branch_only"
    else:
        branch = "no_distinguishing_migrations"
    return {
        "state": "read_only_snapshot_observed",
        "mode": "explicit_consistent_copy_required",
        "live_vps_verified": False,
        "production_ready": False,
        "applied_core_count": len(names),
        "branch_evidence": branch,
        "applied_shared_count": len(applied & set(shared)),
        "applied_current_only": current_hits,
        "applied_reference_only": reference_hits,
        "unknown_applied": sorted(applied - set(current_only)
                                  - set(reference_only) - set(shared)),
        "agenttask_table_present": bool(task_columns),
        "agenttask_missing_worker_fields": sorted(
            set(REQUIRED_TASK_FIELDS) - task_columns),
        "product_table_present": bool(product_columns),
        "factoryrun_table_present": bool(run_columns),
    }


def _dependencies(tree):
    """Read static same-app dependency tuples, never evaluate migration code."""
    deps = set()
    for cls in tree.body:
        if not isinstance(cls, ast.ClassDef) or cls.name != "Migration":
            continue
        for stmt in cls.body:
            if not isinstance(stmt, ast.Assign) or not any(
                isinstance(target, ast.Name) and target.id == "dependencies"
                for target in stmt.targets
            ):
                continue
            if not isinstance(stmt.value, (ast.List, ast.Tuple)):
                return None
            for item in stmt.value.elts:
                if not isinstance(item, ast.Tuple) or len(item.elts) != 2:
                    # An external swappable_dependency is expected; no code is run.
                    continue
                app, name = item.elts
                if (isinstance(app, ast.Constant) and app.value == "core"
                        and isinstance(name, ast.Constant)
                        and isinstance(name.value, str)):
                    deps.add(name.value)
            return sorted(deps)
    return None


def _data_operations(tree):
    """Identify data-bearing operations in Migration.operations, without running them."""
    operations = set()
    for cls in tree.body:
        if not isinstance(cls, ast.ClassDef) or cls.name != "Migration":
            continue
        for stmt in cls.body:
            if not isinstance(stmt, ast.Assign) or not any(
                isinstance(target, ast.Name) and target.id == "operations"
                for target in stmt.targets
            ):
                continue
            for node in ast.walk(stmt.value):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr in {"RunPython", "RunSQL"}
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "migrations"):
                    operations.add(node.func.attr)
    return sorted(operations)


def _inventory(root, side):
    folder = Path(root) / "core" / "migrations"
    blockers = []
    files = {}
    if folder.is_symlink() or not folder.is_dir():
        blockers.append({"code": "MIGRATION_DIR_UNAVAILABLE", "side": side})
        return files, blockers
    candidates = sorted(p for p in folder.iterdir()
                        if MIGRATION_NAME.fullmatch(p.name))
    if len(candidates) > MAX_MIGRATIONS:
        blockers.append({"code": "MIGRATION_LIMIT_EXCEEDED", "side": side})
        return files, blockers
    for path in candidates:
        name = path.stem
        try:
            safe_file = (not path.is_symlink() and path.is_file()
                         and path.stat().st_size <= MAX_MIGRATION_BYTES)
        except OSError:
            safe_file = False
        if not safe_file:
            blockers.append({"code": "MIGRATION_FILE_UNSAFE", "side": side,
                             "component": name})
            continue
        try:
            raw = path.read_bytes()
            tree = ast.parse(raw.decode("utf-8"), filename=path.name)
        except (OSError, UnicodeError, SyntaxError):
            blockers.append({"code": "MIGRATION_UNREADABLE", "side": side,
                             "component": name})
            continue
        deps = _dependencies(tree)
        if deps is None:
            blockers.append({"code": "MIGRATION_DEPS_UNVERIFIED", "side": side,
                             "component": name})
            continue
        files[name] = {"sha256": hashlib.sha256(raw).hexdigest(), "deps": deps,
                       "data_operations": _data_operations(tree)}
    for name, data in files.items():
        for dependency in data["deps"]:
            if dependency not in files and dependency not in {"__first__", "__latest__"}:
                blockers.append({"code": "MIGRATION_PARENT_MISSING", "side": side,
                                 "component": name, "dependency": dependency})
    return files, blockers


def audit(current_root, reference_root, sqlite_snapshot=None):
    current, current_errors = _inventory(current_root, "current")
    reference, reference_errors = _inventory(reference_root, "reference")
    shared = sorted(set(current) & set(reference))
    changed = [name for name in shared
               if current[name]["sha256"] != reference[name]["sha256"]]
    current_only = sorted(set(current) - set(reference))
    reference_only = sorted(set(reference) - set(current))
    reference_by_number = {}
    for name in reference:
        reference_by_number.setdefault(name[:4], set()).add(name)
    number_collisions = [
        {"number": name[:4], "current": name,
         "reference": sorted(reference_by_number[name[:4]])}
        for name in current_only if reference_by_number.get(name[:4])
    ]
    unshared_data_operations = [
        {"migration": name, "operations": reference[name]["data_operations"]}
        for name in reference_only if reference[name]["data_operations"]
    ]
    blockers = current_errors + reference_errors
    if not current:
        blockers.append({"code": "MIGRATION_HISTORY_EMPTY", "side": "current"})
    if not reference:
        blockers.append({"code": "MIGRATION_HISTORY_EMPTY", "side": "reference"})
    if current and reference and not shared:
        blockers.append({"code": "MIGRATION_SHARED_ANCESTOR_MISSING",
                         "component": "core"})
    blockers.extend({"code": "MIGRATION_CONTENT_DIVERGED", "component": name}
                    for name in changed)
    if current_only and reference_only:
        blockers.append({"code": "UNRECONCILED_MIGRATION_BRANCHES",
                         "component": "core"})
    blockers.sort(key=lambda x: (x["code"], x.get("side", ""),
                                 x.get("component", "")))
    report = {
        "schema": SCHEMA,
        "mode": "offline_source_read_only",
        "live_vps_verified": False,
        "database_schema_verified": False,
        "production_ready": False,
        "status": "blocked" if blockers else "no_source_fork_detected",
        "current_count": len(current),
        "reference_count": len(reference),
        "identical_shared_count": len(shared) - len(changed),
        "changed_shared_files": changed,
        "current_only": current_only,
        "reference_only": reference_only,
        "reference_unshared_data_operations": unshared_data_operations,
        "same_number_different_files": number_collisions,
        "blockers": blockers,
    }
    if sqlite_snapshot is not None:
        snapshot = _inspect_sqlite_snapshot(
            sqlite_snapshot, current_only, reference_only, shared)
        report["sqlite_snapshot"] = snapshot
        # A path supplied by the caller is not an attested VPS snapshot, and
        # even a valid copy cannot prove that the running factory uses it.
        report["blockers"].append({"code": "SNAPSHOT_NOT_LIVE_VERIFICATION"})
        if snapshot["state"] == "unavailable":
            report["blockers"].append({"code": snapshot["code"]})
        report["blockers"].sort(key=lambda x: (
            x["code"], x.get("side", ""), x.get("component", "")))
        report["status"] = "blocked"
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current-root", type=Path, required=True)
    parser.add_argument("--reference-root", type=Path, required=True)
    parser.add_argument("--sqlite-snapshot", type=Path,
                        help="Explicit offline consistent SQLite copy, never the live DB")
    args = parser.parse_args(argv)
    result = audit(args.current_root, args.reference_root, args.sqlite_snapshot)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 2 if result["blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
