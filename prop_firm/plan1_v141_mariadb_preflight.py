"""Strict READ-ONLY MariaDB readiness evidence for MOJ-PROP-01 v1.4.1.

No migrations, DDL, inserts, updates, schema editors, secrets, payments, or
orders. This only reports current facts from a chosen Django DB connection.
Passing SQL checks is NOT proof of full DB rehearsal or permission to migrate.
A separately verified off-host backup/restore, free space, isolated rehearsal,
concurrency test, legal gates and explicit rollout approval are mandatory.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

PARENT = "0008_prospect_contact_intake"
TARGET = "0009_v141_sim_replay_journal"
STATES = frozenset(("prop_firm_propv141simstate", "prop_firm_propv141simreceipt"))
MIN_MARIA = (10, 6)


@dataclass(frozen=True)
class V141MariaDBPreflight:
    connected: bool
    mariadb_version: str | None
    schema_status: str
    supports_row_locks: bool
    supports_transactions: bool
    read_only_sql_completed: bool
    reasons: tuple[str, ...]
    # Explicitly not inferred from a DB version or from source-only tests.
    off_host_backup_restored_and_verified: bool = False
    db_disk_capacity_verified: bool = False
    real_mariadb_concurrency_test_verified: bool = False
    migration_rehearsal_verified: bool = False
    contract_and_broker_legality_verified: bool = False
    migration_authorized: bool = False
    release_authorized: bool = False


def _fail(*reasons, connected=False, version=None, status="UNKNOWN",
          locks=False, transactions=False):
    return V141MariaDBPreflight(
        connected=connected, mariadb_version=version,
        schema_status=status,
        supports_row_locks=locks,
        supports_transactions=transactions,
        read_only_sql_completed=False,
        reasons=tuple(dict.fromkeys(reasons)),
    )


def inspect_v141_mariadb_read_only(connection) -> V141MariaDBPreflight:
    """Inspect MariaDB through Django's EXISTING connection; SELECT only.

    Does not open or close a transaction, use cursor.execute with untrusted
    query fragments, log credentials, or attempt to reach any other host.
    Invocation on production should use a DB account with SELECT privileges.
    """
    if getattr(connection, "vendor", None) != "mysql":
        return _fail("mysql_django_backend_required")
    features = getattr(connection, "features", None)
    locks = getattr(features, "has_select_for_update", False) is True
    tx = getattr(features, "supports_transactions", False) is True
    reasons = []
    if not locks:
        reasons.append("row_lock_support_not_proven")
    if not tx:
        reasons.append("database_transaction_support_not_proven")
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT VERSION(), DATABASE(), @@default_storage_engine, "
                "@@autocommit, @@sql_mode"
            )
            row = cursor.fetchone()
            if not isinstance(row, (tuple, list)) or len(row) != 5:
                return _fail("unexpected_server_metadata_response",
                             connected=True,locks=locks,transactions=tx)
            version, db, engine, autocommit, sql_mode = row
            if type(version) is not str:
                reasons.append("server_version_not_text")
                version = ""
            if "MariaDB" not in version:
                reasons.append("actual_server_is_not_mariadb")
            m = re.match(r"^(\d+)\.(\d+)\.(\d+)", version)
            if m is None or tuple(map(int, m.groups()[:2])) < MIN_MARIA:
                reasons.append("mariadb_10_6_or_newer_required")
            if not db:
                reasons.append("no_schema_selected")
            if str(engine).lower() != "innodb":
                reasons.append("innodb_default_engine_required")
            modes = {x.strip().upper() for x in str(sql_mode).split(",")}
            if not ({"STRICT_TRANS_TABLES", "STRICT_ALL_TABLES"} & modes):
                reasons.append("strict_sql_mode_required")
            if type(autocommit) not in (int, bool) or autocommit not in (0, 1):
                reasons.append("autocommit_metadata_unexpected")

            cursor.execute(
                "SELECT name FROM django_migrations "
                "WHERE app = %s AND name IN (%s, %s)",
                ("prop_firm", PARENT, TARGET),
            )
            applied = {str(row[0]) for row in cursor.fetchall()}
            if PARENT not in applied:
                reasons.append("historical_parent_migration_0008_not_applied")
            cursor.execute(
                "SELECT table_name, engine FROM information_schema.tables "
                "WHERE table_schema = DATABASE() "
                "AND table_name IN (%s, %s)",
                tuple(sorted(STATES)),
            )
            observed = {str(name).lower(): str(backend).lower()
                        for name, backend in cursor.fetchall()}
            if TARGET in applied:
                status = "APPLIED"
                if set(observed) != STATES:
                    reasons.append("recorded_migration_missing_v141_tables")
            else:
                status = "PENDING"
                if observed:
                    reasons.append("unregistered_v141_table_collision")
            if any(engine != "innodb" for engine in observed.values()):
                reasons.append("v141_receipt_tables_not_innodb")
    except Exception:
        # A real DB driver exception often embeds credentials, hostnames or
        # SQL. Never output exception text in a user-visible audit.
        return _fail(*reasons,"database_read_only_inspection_failed",
                     connected=False,locks=locks,transactions=tx)
    return V141MariaDBPreflight(
        connected=True, mariadb_version=version,
        schema_status=status, supports_row_locks=locks,
        supports_transactions=tx, read_only_sql_completed=True,
        reasons=tuple(dict.fromkeys(reasons)),
    )
