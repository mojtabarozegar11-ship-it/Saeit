"""Read-only overview of the authoritative PHP V7 finance ledger.

Never write to the PHP SQLite file or copy private rows into Django. Financial
quantities are integer minor units and currencies are never aggregated together.
"""
from __future__ import annotations

import sqlite3
import stat
from decimal import Decimal
from pathlib import Path
from urllib.parse import quote

ALLOWED_CURRENCIES = frozenset(("IRR", "USD", "EUR", "AED"))
REQUIRED_COLUMNS = {
    "journal_entries": frozenset(("id", "doc_no", "doc_date")),
    "journal_lines": frozenset(("entry_id", "account_id", "debit", "credit", "currency")),
    "ledger_accounts": frozenset(("id", "code", "type")),
    "invoices": frozenset(("id", "kind", "currency", "amount")),
    "invoice_payments": frozenset(("invoice_id", "amount")),
}


class LedgerUnavailable(RuntimeError):
    """No usable, explicitly configured and schema-compatible PHP ledger."""


def _major(minor: int) -> str:
    return format(Decimal(int(minor)) / Decimal(100), ",.2f")


def _validate_path(name: str | Path) -> Path:
    if not name:
        raise LedgerUnavailable("PHP_LEDGER_NOT_CONFIGURED")
    path = Path(name)
    if not path.is_absolute() or path.is_symlink():
        raise LedgerUnavailable("PHP_LEDGER_PATH_REJECTED")
    try:
        metadata = path.stat()
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size < 4096:
            raise LedgerUnavailable("PHP_LEDGER_MISSING_OR_EMPTY")
        with path.open("rb") as stream:
            if stream.read(16) != b"SQLite format 3\x00":
                raise LedgerUnavailable("PHP_LEDGER_INVALID_HEADER")
    except OSError as exc:
        raise LedgerUnavailable("PHP_LEDGER_INACCESSIBLE") from exc
    return path


def read_php_finance_snapshot(name: str | Path) -> dict:
    """Read aggregate-only metrics; never return customer or employee rows."""
    path = _validate_path(name)
    uri = "file:" + quote(str(path.resolve(strict=True)), safe="/") + "?mode=ro"
    try:
        # SQLite opens the actual PHP ledger strictly read-only; query_only
        # additionally prevents accidental DML or schema writes in this module.
        with sqlite3.connect(uri, uri=True, timeout=3) as db:
            db.execute("PRAGMA query_only=ON")
            db.execute("PRAGMA busy_timeout=3000")
            # One read transaction gives all monetary aggregates the same
            # SQLite snapshot even while the PHP application posts entries.
            db.execute("BEGIN")
            for table, required in REQUIRED_COLUMNS.items():
                columns = {row[1] for row in db.execute("PRAGMA table_info(" + table + ")")}
                if not required.issubset(columns):
                    raise LedgerUnavailable("PHP_LEDGER_SCHEMA_MISMATCH")
            document_count = int(db.execute("SELECT COUNT(*) FROM journal_entries").fetchone()[0])
            invoice_count = int(db.execute("SELECT COUNT(*) FROM invoices").fetchone()[0])
            turnovers = []
            for currency, debit, credit in db.execute(
                "SELECT currency, COALESCE(SUM(debit),0), COALESCE(SUM(credit),0)"
                " FROM journal_lines GROUP BY currency ORDER BY currency"
            ):
                if currency not in ALLOWED_CURRENCIES:
                    raise LedgerUnavailable("PHP_LEDGER_CURRENCY_UNSUPPORTED")
                debit, credit = int(debit), int(credit)
                turnovers.append({
                    "currency": currency, "debit": _major(debit),
                    "credit": _major(credit), "difference": _major(debit - credit),
                    "balanced": debit == credit,
                })
            imbalance_count = int(db.execute(
                "SELECT COUNT(*) FROM ("
                " SELECT entry_id,currency FROM journal_lines"
                " GROUP BY entry_id,currency HAVING SUM(debit)<>SUM(credit)"
                ")"
            ).fetchone()[0])
            invoices = []
            for currency, kind, count, amount, paid in db.execute(
                "SELECT i.currency,i.kind,COUNT(*),COALESCE(SUM(i.amount),0),"
                " COALESCE(SUM((SELECT COALESCE(SUM(p.amount),0)"
                " FROM invoice_payments p WHERE p.invoice_id=i.id)),0)"
                " FROM invoices i GROUP BY i.currency,i.kind ORDER BY i.currency,i.kind"
            ):
                if currency not in ALLOWED_CURRENCIES or kind not in ("sale", "purchase"):
                    raise LedgerUnavailable("PHP_LEDGER_INVOICE_CLASS_UNSUPPORTED")
                amount, paid = int(amount), int(paid)
                invoices.append({
                    "currency": currency, "kind": kind, "count": int(count),
                    "amount": _major(amount), "paid": _major(paid),
                    "outstanding": _major(amount - paid),
                    "overpaid": paid > amount,
                })
    except (sqlite3.Error, OSError, ValueError, OverflowError) as exc:
        raise LedgerUnavailable("PHP_LEDGER_READONLY_QUERY_FAILED") from exc

    return {
        "authority": "PHP V7 (read-only)",
        "document_count": document_count, "invoice_count": invoice_count,
        "imbalance_count": imbalance_count,
        "turnovers": tuple(turnovers), "invoices": tuple(invoices),
    }
