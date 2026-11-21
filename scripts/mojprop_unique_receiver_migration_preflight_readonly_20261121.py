#!/usr/bin/env python3
"""Read-only isolated MOJ PROP migration + UNIQUE recipient reconciliation.

Invoke on the effective cPanel Django application with its configured
`mojprop` alias. No migrate, schema_editor, ALTER, CREATE, DROP, INSERT,
UPDATE, DELETE, fake-applied migrations, customer email, wallet address or
treasury credentials are performed or printed. It is a planning safety check,
not permission to run DDL, accept TRX or declare an isolated restore passed.

A complete private restorable logical dump can be *checked* via optional
--backup-manifest. SQL import must be rehearsed in an independent database
by a separately authorized procedure, never in the live tenant.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
from pathlib import Path

_APP = "prop_firm"
_DB_ALIAS = "mojprop"
_FIFTH = "0005_optional_payer_wallet"
_TARGET = "0006_unique_invoice_receivers"


def _migration_issues(
    *,
    known_nodes: set[str],
    applied: set[str],
    target_dependencies: set[str],
    model_recipient_unique: bool,
    db_recipient_unique: bool,
    duplicate_recipient_groups: int,
    backup_archive_verified: bool,
    isolated_restore_verified: bool,
) -> tuple[str, ...]:
    """Pure fail-closed assessment, never a replacement for DB observation."""
    errors = []
    if _FIFTH not in known_nodes or _FIFTH not in applied:
        errors.append("fifth_migration_not_both_installed_and_applied")
    if _TARGET not in known_nodes:
        errors.append("exclusive_receiver_migration_not_present_in_effective_source")
    if _TARGET in known_nodes and _FIFTH not in target_dependencies:
        errors.append("exclusive_receiver_migration_dependency_mismatch")
    # Historical names from another branch may be valid old data, not rubbish
    # to delete or fake; their graph must be reconciled before production DDL.
    unknown = sorted(applied - known_nodes)
    if unknown:
        errors.append("historical_applied_migrations_without_installed_sources")
    if not model_recipient_unique:
        errors.append("effective_django_model_allows_reused_recipient")
    if not db_recipient_unique:
        errors.append("live_payment_table_has_no_unique_recipient_index")
    if duplicate_recipient_groups < 0:
        errors.append("recipient_duplicate_count_unavailable")
    elif duplicate_recipient_groups:
        errors.append("existing_recipient_collisions_need_private_remediation")
    if not backup_archive_verified:
        errors.append("complete_independent_logical_backup_not_verified")
    if not isolated_restore_verified:
        errors.append("private_isolated_database_restore_not_proven")
    return tuple(errors)


def _exact_recipient_unique(constraints: dict) -> bool:
    """Single recipient index only; a unique TXID or composite is inadequate."""
    return any(
        type(meta) is dict
        and meta.get("unique") is True
        and meta.get("columns") == ["recipient"]
        for meta in constraints.values()
    )


def _verify_local_backup_manifest(raw: str | None) -> dict:
    """Digest/checksize verification only; never claims an import worked."""
    if not raw:
        return {"verified": False, "restore_verified": False}
    original = Path(raw).expanduser()
    if original.is_symlink() or not original.is_file():
        return {"verified": False, "restore_verified": False}
    try:
        manifest_path = original.resolve(strict=True)
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        archive = manifest_path.parent / "mojprop-full-logical.sql.gz"
        if archive.is_symlink() or not archive.is_file():
            return {"verified": False, "restore_verified": False}
        if archive.stat().st_size > 256 * 1024 * 1024:
            return {"verified": False, "restore_verified": False}
        blob = archive.read_bytes()
        with gzip.open(archive, "rb") as stream:
            plain = stream.read(512 * 1024 * 1024 + 1)
        if len(plain) > 512 * 1024 * 1024:
            return {"verified": False, "restore_verified": False}
    except (OSError, ValueError, TypeError, json.JSONDecodeError, EOFError):
        return {"verified": False, "restore_verified": False}
    exists = (
        hashlib.sha256(blob).hexdigest() == data.get("gzip_sha256")
        and hashlib.sha256(plain).hexdigest() == data.get("sql_sha256")
        and len(blob) == data.get("compressed_bytes")
        and len(plain) == data.get("uncompressed_bytes")
        and len(re.findall(rb"(?m)^CREATE TABLE ", plain))
        == data.get("tables_in_live_schema")
        == data.get("create_table_statements")
        and data.get("tables_in_live_schema", 0) > 0
        and not re.search(rb"(?im)^\\s*(DROP|TRUNCATE)\\s+TABLE\\s", plain)
    )
    # A readable archive is NOT a restored database. Never infer this from
    # a user-controlled flag or even an SQL checksum.
    return {"verified": exists, "restore_verified": False}


def audit(*, backup_manifest: str | None = None) -> dict:
    """Only Django migration introspection and parameter-free SELECT queries."""
    import os

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()
    from django.db import connections
    from django.db.migrations.loader import MigrationLoader
    from prop_firm.models import PropSimulationPayment

    if _DB_ALIAS not in connections.databases:
        raise RuntimeError("DEDICATED_MOJPROP_DATABASE_ALIAS_MISSING")
    conn = connections[_DB_ALIAS]
    if not conn.settings_dict.get("ENGINE", "").endswith(".mysql"):
        raise RuntimeError("MOJPROP_EXPECTED_MARIADB_ALIAS_MISSING")

    loader = MigrationLoader(conn, ignore_no_migrations=True)
    known = {name for app, name in loader.graph.nodes if app == _APP}
    applied = {name for app, name in loader.applied_migrations if app == _APP}
    dependencies = set()
    target_node = loader.disk_migrations.get((_APP, _TARGET))
    if target_node is not None:
        dependencies = {name for app, name in target_node.dependencies if app == _APP}

    table = PropSimulationPayment._meta.db_table
    escaped = conn.ops.quote_name(table)
    with conn.cursor() as cursor:
        constraints = conn.introspection.get_constraints(cursor, table)
        cursor.execute(
            f"SELECT COUNT(*) FROM (SELECT recipient FROM {escaped} "
            "GROUP BY recipient HAVING COUNT(*)>1) AS collisions"
        )
        duplicate_groups = cursor.fetchone()[0]
        cursor.execute(f"SELECT COUNT(*) FROM {escaped}")
        payments = cursor.fetchone()[0]
    backup = _verify_local_backup_manifest(backup_manifest)
    issues = _migration_issues(
        known_nodes=known,
        applied=applied,
        target_dependencies=dependencies,
        model_recipient_unique=PropSimulationPayment._meta.get_field("recipient").unique,
        db_recipient_unique=_exact_recipient_unique(constraints),
        duplicate_recipient_groups=duplicate_groups,
        backup_archive_verified=backup["verified"],
        isolated_restore_verified=backup["restore_verified"],
    )
    return {
        "scope": "dedicated_mojprop_alias_only",
        "read_only": True,
        "status": "BLOCKED" if issues else "SCHEMA_PREFLIGHT_ONLY",
        "actual_payment_count": payments,
        "duplicate_recipient_groups": duplicate_groups,
        "installed_migrations_count": len(known),
        "applied_migrations_count": len(applied),
        "historical_migrations_without_source": sorted(applied - known),
        "exclusive_receiver_migration_installed": _TARGET in known,
        "exclusive_receiver_migration_applied": _TARGET in applied,
        "exclusive_receiver_dependency_valid": _FIFTH in dependencies,
        "effective_model_recipient_unique": PropSimulationPayment._meta.get_field("recipient").unique,
        "live_db_unique_recipient": _exact_recipient_unique(constraints),
        "private_backup_archive_digest_verified": backup["verified"],
        "isolated_database_restore_verified": False,
        "blockers": issues,
        "never_automatically_apply_migrations": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup-manifest", help="Local private manifest only; no SQL exposure")
    arguments = parser.parse_args()
    result = audit(backup_manifest=arguments.backup_manifest)
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0 if not result["blockers"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
