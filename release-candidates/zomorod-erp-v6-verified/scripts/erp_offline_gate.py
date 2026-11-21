#!/usr/bin/env python3
"""Offline-only, non-mutating ERP database integrity and restore verification.

Does not require privileged DB credentials, and never claims statutory compliance.
Defaults to a synthetic or local snapshot, not to the production path.
"""
from __future__ import annotations
import argparse
import json
import os
import sqlite3
import tempfile
from pathlib import Path

FINANCE_TABLES = (
    "journal_entries", "journal_lines", "ledger_accounts", "invoices",
    "invoice_payments", "inventory", "inventory_movements", "users",
)
CONTROL_TABLES = ("tasks", "task_events", "task_quality")
WORKFLOW_TABLES = ("requests", "request_events")
INDUSTRY_TABLES = ("industry_items", "industry_events")


def sqlscalar(db: sqlite3.Connection, sql: str) -> int:
    return int(db.execute(sql).fetchone()[0])


def snapshot_report(db: sqlite3.Connection, required: tuple[str, ...]) -> dict:
    db.execute("PRAGMA query_only=ON")
    present = {name for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    missing = sorted(set(required) - present)
    result = {
        "integrity": db.execute("PRAGMA integrity_check").fetchone()[0],
        "foreign_key_violations": len(db.execute("PRAGMA foreign_key_check").fetchall()),
        "missing_tables": missing,
        "counts": {},
        "anomalies": {},
    }
    for table in required:
        if table in present:
            result["counts"][table] = sqlscalar(db, f'SELECT COUNT(*) FROM "{table}"')
    if set(FINANCE_TABLES).issubset(present):
        result["anomalies"]["currency_unbalanced_entries"] = sqlscalar(db, """
            SELECT COUNT(*) FROM (
                SELECT entry_id,currency FROM journal_lines
                GROUP BY entry_id,currency
                HAVING SUM(debit)<>SUM(credit) OR SUM(debit)=0)
        """)
        result["anomalies"]["journal_entries_without_two_lines"] = sqlscalar(db, """
            SELECT COUNT(*) FROM (SELECT j.id FROM journal_entries j
                LEFT JOIN journal_lines l ON l.entry_id=j.id
                GROUP BY j.id HAVING COUNT(l.id)<2)
        """)
        result["anomalies"]["overpaid_invoices"] = sqlscalar(db, """
            SELECT COUNT(*) FROM invoices i WHERE
            COALESCE((SELECT SUM(amount) FROM invoice_payments p WHERE p.invoice_id=i.id),0)>i.amount
        """)
        result["anomalies"]["negative_stock"] = sqlscalar(db, """
            SELECT COUNT(*) FROM (SELECT i.id FROM inventory i
                LEFT JOIN inventory_movements m ON m.inventory_id=i.id
                GROUP BY i.id HAVING COALESCE(SUM(m.qty),0)<0)
        """)
    result["result"] = (
        "PASS_CHECKED_INVARIANTS"
        if result["integrity"] == "ok" and not result["foreign_key_violations"]
        and not missing and not any(result["anomalies"].values())
        else "INCOMPLETE_OR_NEEDS_INVESTIGATION"
    )
    return result


def open_readonly(file: Path) -> sqlite3.Connection:
    if not file.is_file() or file.is_symlink():
        raise ValueError("Missing or unsafe SQLite snapshot path")
    db = sqlite3.connect(file.resolve().as_uri() + "?mode=ro", uri=True, timeout=15)
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA query_only=ON")
    return db


def verified_restore(file: Path, required: tuple[str, ...]) -> dict:
    """SQLite backup API reads source, writes only a private temporary copy."""
    with open_readonly(file) as origin, tempfile.TemporaryDirectory(prefix="zm-erp-restore-") as folder:
        target = Path(folder) / "restored.sqlite3"
        with sqlite3.connect(target) as restored:
            origin.backup(restored)
            restored.commit()
            result = snapshot_report(restored, required)
    return result


def inspect(file: Path, required: tuple[str, ...]) -> dict:
    with open_readonly(file) as db:
        return snapshot_report(db, required)


def main() -> int:
    p=argparse.ArgumentParser(description="Strictly offline company data integrity / backup-restore checks")
    p.add_argument("sqlite_file", type=Path)
    p.add_argument("--domain", choices=("finance","control","workflow","industry"), default="finance")
    p.add_argument("--restore-test", action="store_true")
    args=p.parse_args()
    tables={"finance":FINANCE_TABLES,"control":CONTROL_TABLES,
            "workflow":WORKFLOW_TABLES,"industry":INDUSTRY_TABLES}[args.domain]
    try:
        result=verified_restore(args.sqlite_file,tables) if args.restore_test else inspect(args.sqlite_file,tables)
        print(json.dumps({"domain":args.domain,"source_modified":False,
                          "restore_test":args.restore_test,**result}, ensure_ascii=False, sort_keys=True))
        return 0 if result["result"]=="PASS_CHECKED_INVARIANTS" else 2
    except (OSError,sqlite3.Error,ValueError):
        print(json.dumps({"domain":args.domain,"result":"ERROR","source_modified":False}))
        return 2
if __name__=="__main__":
    raise SystemExit(main())
