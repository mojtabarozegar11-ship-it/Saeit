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


def _restore_scope_defects(sql: bytes) -> tuple[str, ...]:
    """Reject SQL dump commands able to redirect an isolated restore.

    A digest-valid no-DROP dump may still CREATE DATABASE and USE an old
    production DB. Conservative read-only scanner: unfamiliar SQL should
    be separately reviewed, never executed or silently sanitized here.
    No SQL contents, user data or database names are printed.
    """
    if type(sql) is not bytes:
        return ("sql_archive_is_not_bytes",)
    patterns = (
        ("database_definition", rb"(?im)^[ \t]*(?:CREATE|DROP|ALTER)[ \t]+(?:DATABASE|SCHEMA)\b"),
        ("database_switch", rb"(?im)^[ \t]*USE[ \t]+"),
        ("destructive_table", rb"(?im)^[ \t]*(?:DROP|TRUNCATE)[ \t]+TABLE\b"),
        ("table_rename", rb"(?im)^[ \t]*RENAME[ \t]+TABLE\b"),
        ("user_definition", rb"(?im)^[ \t]*(?:CREATE|DROP)[ \t]+USER\b"),
        ("privilege_change", rb"(?im)^[ \t]*(?:GRANT|REVOKE)[ \t]+"),
        ("importer_directive", rb"(?im)^[ \t]*(?:SOURCE[ \t]+|\\\.[ \t]+|DELIMITER\b)"),
        ("global_setting", rb"(?im)^[ \t]*SET[ \t]+(?:@@GLOBAL\.|GLOBAL\b)"),
        ("file_export", rb"(?im)\bINTO[ \t]+(?:OUTFILE|DUMPFILE)\b"),
        ("cross_database_table", rb"(?im)^[ \t]*(?:(?:CREATE|ALTER|DROP|TRUNCATE)[ \t]+TABLE|(?:INSERT|REPLACE)[ \t]+INTO|UPDATE[ \t]+|DELETE[ \t]+FROM)[ \t]+(?:\x60[^\x60]+\x60|[A-Za-z_][\w$]*)[ \t]*\.[ \t]*"),
        ("mysql_executable_database_comment", rb"(?is)/\*!\d{5,6}[ \t]*(?:(?:CREATE|DROP|ALTER)[ \t]+(?:DATABASE|SCHEMA)\b|USE[ \t]+|(?:DROP|TRUNCATE)[ \t]+TABLE\b)"),
    )
    return tuple(reason for reason, pattern in patterns if re.search(pattern, sql))


def _neutral_derivation_proven(directory: Path, data: dict, candidate: bytes) -> bool:
    """Compare every SQL byte with the immutable original except two selectors."""
    original_archive = directory / "mojprop-full-logical.sql.gz"
    if original_archive.is_symlink() or not original_archive.is_file():
        return False
    if original_archive.stat().st_size > 256 * 1024 * 1024:
        return False
    if not (
        data.get("schema") == "mojprop.target-neutral-backup-review.v1"
        and data.get("database_definition_lines_removed") == 1
        and data.get("database_selector_lines_removed") == 1
        and data.get("scope_command_scan_clear") is True
        and data.get("standalone_restore_verified") is False
        and data.get("legacy_source_unchanged") is True
    ):
        return False
    compressed = original_archive.read_bytes()
    if hashlib.sha256(compressed).hexdigest() != data.get("source_archive_sha256"):
        return False
    with gzip.open(original_archive, "rb") as stream:
        original = stream.read(512 * 1024 * 1024 + 1)
    if len(original) > 512 * 1024 * 1024:
        return False
    if hashlib.sha256(original).hexdigest() != data.get("source_sql_sha256"):
        return False
    removed_creates, removed_uses, pieces = [], [], []
    for line in original.splitlines(keepends=True):
        if re.match(rb"^[ \t]*CREATE[ \t]+DATABASE\b", line, flags=re.I):
            name = re.search(rb"\x60([^\x60]+)\x60", line)
            if name is None or not line.rstrip().endswith(b";"):
                return False
            removed_creates.append(name.group(1))
        elif re.match(rb"^[ \t]*USE[ \t]+", line, flags=re.I):
            name = re.fullmatch(
                rb"[ \t]*USE[ \t]+\x60([^\x60]+)\x60;[ \t]*(?:\r?\n)?",
                line, flags=re.I,
            )
            if name is None:
                return False
            removed_uses.append(name.group(1))
        else:
            pieces.append(line)
    return (
        len(removed_creates) == 1
        and len(removed_uses) == 1
        and removed_creates[0] == removed_uses[0]
        and b"".join(pieces) == candidate
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
        is_neutral = data.get("schema") == "mojprop.target-neutral-backup-review.v1"
        if data.get("schema") not in (None, "mojprop.target-neutral-backup-review.v1"):
            return {"verified": False, "restore_verified": False}
        archive = manifest_path.parent / (
            "mojprop-target-neutral.sql.gz" if is_neutral
            else "mojprop-full-logical.sql.gz"
        )
        if archive.is_symlink() or not archive.is_file():
            return {"verified": False, "restore_verified": False}
        if archive.stat().st_size > 256 * 1024 * 1024:
            return {"verified": False, "restore_verified": False}
        blob = archive.read_bytes()
        with gzip.open(archive, "rb") as stream:
            plain = stream.read(512 * 1024 * 1024 + 1)
        if len(plain) > 512 * 1024 * 1024:
            return {"verified": False, "restore_verified": False}
        if is_neutral:
            provenance = _neutral_derivation_proven(manifest_path.parent, data, plain)
            gzip_hash = data.get("derived_archive_sha256")
            sql_hash = data.get("derived_sql_sha256")
            compressed_bytes = data.get("derived_gzip_bytes")
            plain_bytes = data.get("derived_sql_bytes")
            schema_tables = data.get("tables_preserved")
            statement_count = data.get("tables_preserved")
        else:
            provenance = True
            gzip_hash = data.get("gzip_sha256")
            sql_hash = data.get("sql_sha256")
            compressed_bytes = data.get("compressed_bytes")
            plain_bytes = data.get("uncompressed_bytes")
            schema_tables = data.get("tables_in_live_schema")
            statement_count = data.get("create_table_statements")
    except (OSError, ValueError, TypeError, json.JSONDecodeError, EOFError):
        return {"verified": False, "restore_verified": False}
    exists = (
        provenance
        and hashlib.sha256(blob).hexdigest() == gzip_hash
        and hashlib.sha256(plain).hexdigest() == sql_hash
        and len(blob) == compressed_bytes
        and len(plain) == plain_bytes
        and len(re.findall(rb"(?m)^CREATE TABLE ", plain))
        == schema_tables == statement_count
        and isinstance(schema_tables, int)
        and schema_tables > 0
        and not _restore_scope_defects(plain)
    )
    # A readable archive is NOT a restored database. Never infer this from
    # a user-controlled flag or even an SQL checksum.
    return {"verified": exists, "restore_verified": False}


def audit(*, backup_manifest: str | None = None) -> dict:
    """Only Django migration introspection and parameter-free SELECT queries."""
    import os
    import pwd
    import sys

    # The cPanel workflow streams this file over SSH (stdin), so Python's
    # current directory is the account home, not the Django project root.
    # Pin the reviewed staging application explicitly before importing Django.
    app_root = Path("/home/zomorod2/Saeit-staging")
    if pwd.getpwuid(os.geteuid()).pw_name != "zomorod2":
        raise PermissionError("MOJPROP_OWNER_ACCOUNT_MISMATCH")
    if app_root.is_symlink() or not app_root.is_dir():
        raise RuntimeError("MOJPROP_STAGING_ROOT_UNAVAILABLE")
    os.chdir(app_root)
    sys.path.insert(0, str(app_root))
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
