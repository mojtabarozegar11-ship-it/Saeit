#!/usr/bin/env python3
"""Private-lead-safe sales-queue evidence from the existing live Moj Prop CRM.

Only published category names and presence booleans leave the host. No names,
emails, IDs, amounts, lead counts, notes, tokens or customer status rows are
logged. No message, payment, offer, database write or new customer is created.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path("/home/zomorod2/Saeit-staging")
COMMAND = ROOT / "core/management/commands/mojprop_sales_action_queue.py"
REVIEWED_SOURCE_GIT_SHA = "39594fd4fdb6e80803232fe5f642f0ad3948c57c"
CATEGORIES = frozenset((
    "urgent_unreviewed", "new_over_24h", "reviewing_without_draft",
    "draft_over_24h", "approved_not_issued", "issued_expires_soon",
    "issued_already_expired", "accepted_no_artifact",
    "prepared_not_dispatched", "sent_unacknowledged",
    "digital_without_issued_quote", "free_signals_awaiting_review",
    "signals_without_issued_quote", "terminal_offer_internal_review",
    "starter30_unquoted_manual_review",
    "prop01_challenge_interest_review",
))


def git_blob_sha256_legacy_sha1(source: bytes) -> str:
    """Compute Git's *blob SHA-1* for exact authenticated source matching."""
    header = b"blob " + str(len(source)).encode("ascii") + b"\x00"
    return hashlib.sha1(header + source).hexdigest()


def sanitize_action_queue(raw: object) -> dict:
    """Export presence only; refuse any unexpected schema/category or count."""
    if type(raw) is not dict or raw.get("schema") != "mojprop.sales_action_queue.v1":
        raise ValueError("unexpected queue schema")
    entries = raw.get("categories")
    if type(entries) is not list or len(entries) != len(CATEGORIES):
        raise ValueError("incomplete or duplicated queue categories")
    flags: dict[str, bool] = {}
    for entry in entries:
        if type(entry) is not dict:
            raise ValueError("untrusted queue entry")
        name, count = entry.get("category"), entry.get("count")
        if (type(name) is not str or name not in CATEGORIES or name in flags
                or type(count) is not int or not 0 <= count <= 1_000_000):
            raise ValueError("invalid category/count")
        flags[name] = count > 0
    if set(flags) != CATEGORIES:
        raise ValueError("missing queue category")
    # Do not serialize the original report: it may evolve to include private IDs.
    return {
        "schema": "mojprop.sales_queue.boolean_public_diagnostic.v1",
        "read_only": True,
        "exact_reviewed_queue_source": True,
        "any_actionable_consent_scoped_lead": any(flags.values()),
        "categories_with_work_pending": sorted(k for k, v in flags.items() if v),
        "exact_lead_counts_or_personal_data_emitted": False,
        "offer_or_payment_created": False,
        "customer_contact_sent": False,
        "revenue_recognized": False,
    }


def inspect_minimal_intake_presence(connection) -> dict:
    """An older deployed app may lack the reviewed queue command.

    Only inspect public schema names and EXISTS of consented active leads.
    A missing table or column is UNKNOWN, not "zero customers".
    """
    available = False
    active = None
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema=DATABASE() AND table_name='core_mojproprequest'"
        )
        table_exists = int(cursor.fetchone()[0]) == 1
        if table_exists:
            cursor.execute(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_schema=DATABASE() AND table_name='core_mojproprequest' "
                "AND column_name IN ('consent','status')"
            )
            available = int(cursor.fetchone()[0]) == 2
            if available:
                cursor.execute(
                    "SELECT EXISTS(SELECT 1 FROM core_mojproprequest "
                    "WHERE consent=1 AND status IN "
                    "('new','reviewing','offer_sent','approved'))"
                )
                active = int(cursor.fetchone()[0]) == 1
    return {
        "schema": "mojprop.sales_queue.boolean_public_diagnostic.v1",
        "read_only": True,
        "exact_reviewed_queue_source": False,
        "limited_intake_presence_checked": available,
        "other_queue_categories_not_checked": True,
        "any_actionable_consent_scoped_lead": active,
        "categories_with_work_pending":
            ["consented_active_intake"] if active is True else [],
        "exact_lead_counts_or_personal_data_emitted": False,
        "offer_or_payment_created": False,
        "customer_contact_sent": False,
        "revenue_recognized": False,
    }


def main() -> None:
    if ROOT.is_symlink() or not ROOT.is_dir():
        raise SystemExit("MOJPROP_LIVE_ROOT_NOT_VERIFIED")
    if ROOT.resolve() != ROOT or any(
        ancestor.is_symlink() for ancestor in
        (COMMAND, COMMAND.parent, COMMAND.parent.parent, COMMAND.parent.parent.parent)
    ):
        raise SystemExit("MOJPROP_UNSAFE_QUEUE_SOURCE")
    try:
        command_deployed = COMMAND.is_file()
        if command_deployed:
            source = COMMAND.read_bytes()
            if git_blob_sha256_legacy_sha1(source) != REVIEWED_SOURCE_GIT_SHA:
                raise SystemExit("MOJPROP_QUEUE_LIVE_SOURCE_DIFFERS_FROM_REVIEWED")
        os.chdir(ROOT)
        sys.path.insert(0, str(ROOT))
        os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
        import django
        django.setup()
        from django.db import connection
        if connection.vendor != "mysql":
            raise ValueError("unexpected database vendor")
        # Django first initializes the MySQL session using SET statements.
        # Open the connection before applying the *business-query* SELECT-only
        # wrapper; this does not run ORM business commands or mutate rows.
        connection.ensure_connection()
        # Enforce SELECT-only on the connection during ORM execution, even if
        # the current main source or a helper were to regress unexpectedly.
        def select_only(execute, sql, params, many, context):
            # Output never includes the SQL itself; its first word is an
            # allowlisted, fixed label for P0 troubleshooting only.
            words = sql.lstrip().upper().split(None, 1) if type(sql) is str else []
            verb = words[0] if words else ""
            if verb != "SELECT":
                safe = verb if verb in {"SET", "BEGIN", "SHOW", "PRAGMA",
                                       "START", "SAVEPOINT", "COMMIT", "ROLLBACK",
                                       "INSERT", "UPDATE", "DELETE"} else "OTHER"
                raise PermissionError("SQL_VERB_" + safe)
            return execute(sql, params, many, context)
        with connection.execute_wrapper(select_only):
            if command_deployed:
                from core.management.commands.mojprop_sales_action_queue import (
                    action_queue_snapshot,
                )
                # detail_limit=0: no IDs are collected for the JSON report.
                summary = sanitize_action_queue(action_queue_snapshot(detail_limit=0))
            else:
                summary = inspect_minimal_intake_presence(connection)
    except PermissionError as exc:
        # The exception is created only by our fixed enum above; never print
        # raw SQL, DB parameters or arbitrary exception messages.
        raise SystemExit("MOJPROP_QUEUE_NONSELECT_BLOCKED_" + str(exc))
    except Exception as exc:
        # Only the class is logged, never exception messages or customer data.
        raise SystemExit("MOJPROP_QUEUE_INSPECTION_BLOCKED_" + type(exc).__name__)
    print("MOJPROP_PRIVATE_SALES_QUEUE_GATE=" + json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
