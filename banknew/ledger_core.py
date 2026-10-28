"""MOJ Pay isolated double-entry ledger core.

No HTTP endpoint, wallet signing, settlement, deposit or customer access exists here.
A regulated service must add authenticated authorization, independently verified
funding events, reconciliation, external audit anchoring, backups and approvals.
Amounts are *integer minor units*, never floating point numbers.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from typing import Iterable

GENESIS_HASH = "0" * 64
MAX_UNITS = 10**38 - 1
_ACCOUNT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_REFERENCE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_ASSET = re.compile(r"[A-Z][A-Z0-9]{1,11}\Z")


class LedgerError(ValueError):
    """Invalid or unsafe financial journal operation."""


class IdempotencyConflict(LedgerError):
    """An existing request identifier was reused for a different operation."""


class InsufficientFunds(LedgerError):
    """The journal would make a natural-side account balance negative."""


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _reference(value: str, name: str) -> str:
    if not isinstance(value, str) or not _REFERENCE.fullmatch(value):
        raise LedgerError(f"Invalid {name}.")
    return value


def _units(value: int | str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise LedgerError("Amount must be an integer minor-unit quantity.")
    if isinstance(value, str) and not re.fullmatch(r"[1-9][0-9]*", value):
        raise LedgerError("Noncanonical amount.")
    units = int(value)
    if not 0 < units <= MAX_UNITS:
        raise LedgerError("Amount outside supported range.")
    return units


class Ledger:
    """Single-node transactional accounting kernel; intentionally NOT a payment API.

    Each registered account has a normal balance side: D for asset/expense,
    C for liability/equity/revenue. All journal legs balance *per asset*.
    Balances are stored as canonical text to preserve up to 38 decimal digits.
    A checksum chain is tamper-evident, not externally notarized.
    """

    def __init__(self, database: str = ":memory:") -> None:
        self.db = sqlite3.connect(database, timeout=10, isolation_level=None)
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA busy_timeout=10000")
        if database != ":memory:":
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS accounts(
          account_id TEXT PRIMARY KEY,
          asset TEXT NOT NULL,
          normal_side TEXT NOT NULL CHECK(normal_side IN ('D','C')),
          balance_units TEXT NOT NULL DEFAULT '0',
          created_utc TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS journals(
          seq INTEGER PRIMARY KEY AUTOINCREMENT,
          request_id TEXT NOT NULL UNIQUE,
          request_hash TEXT NOT NULL,
          external_ref TEXT NOT NULL,
          occurred_utc TEXT NOT NULL,
          previous_hash TEXT NOT NULL,
          journal_hash TEXT NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS postings(
          journal_seq INTEGER NOT NULL REFERENCES journals(seq),
          line_number INTEGER NOT NULL,
          account_id TEXT NOT NULL REFERENCES accounts(account_id),
          asset TEXT NOT NULL,
          side TEXT NOT NULL CHECK(side IN ('D','C')),
          units TEXT NOT NULL,
          PRIMARY KEY(journal_seq,line_number)
        );
        CREATE TRIGGER IF NOT EXISTS immutable_journal_update
          BEFORE UPDATE ON journals BEGIN
            SELECT RAISE(ABORT,'journal is append-only');
          END;
        CREATE TRIGGER IF NOT EXISTS immutable_journal_delete
          BEFORE DELETE ON journals BEGIN
            SELECT RAISE(ABORT,'journal is append-only');
          END;
        CREATE TRIGGER IF NOT EXISTS immutable_posting_update
          BEFORE UPDATE ON postings BEGIN
            SELECT RAISE(ABORT,'posting is append-only');
          END;
        CREATE TRIGGER IF NOT EXISTS immutable_posting_delete
          BEFORE DELETE ON postings BEGIN
            SELECT RAISE(ABORT,'posting is append-only');
          END;
        CREATE TRIGGER IF NOT EXISTS immutable_account_identity
          BEFORE UPDATE OF account_id,asset,normal_side,created_utc ON accounts BEGIN
            SELECT RAISE(ABORT,'account identity is immutable');
          END;
        CREATE TRIGGER IF NOT EXISTS immutable_account_delete
          BEFORE DELETE ON accounts BEGIN
            SELECT RAISE(ABORT,'account deletion forbidden');
          END;
        """)

    def close(self) -> None:
        self.db.close()

    def create_account(self, account_id: str, asset: str, normal_side: str) -> None:
        if not isinstance(account_id, str) or not _ACCOUNT.fullmatch(account_id):
            raise LedgerError("Invalid account identifier.")
        if not isinstance(asset, str) or not _ASSET.fullmatch(asset):
            raise LedgerError("Invalid asset identifier.")
        if normal_side not in ("D", "C"):
            raise LedgerError("Invalid natural balance side.")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.execute(
                "INSERT INTO accounts(account_id,asset,normal_side,created_utc)"
                " VALUES (?,?,?,?)",
                (account_id, asset, normal_side,
                 datetime.now(timezone.utc).isoformat(timespec="microseconds")),
            )
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def balance(self, account_id: str) -> int:
        row = self.db.execute(
            "SELECT balance_units FROM accounts WHERE account_id=?", (account_id,)
        ).fetchone()
        if row is None:
            raise LedgerError("Unknown account.")
        return int(row[0])

    def post(self, request_id: str, external_ref: str,
             lines: Iterable[tuple[str, str, int | str]]) -> tuple[int, str]:
        """Post one atomic balanced journal, or return the same prior result.

        Input legs: (account_id, 'D'|'C', integer minor units).
        Never use this direct core as proof of external funding or fiat settlement.
        """
        _reference(request_id, "request identifier")
        _reference(external_ref, "external reference")
        try:
            line_list = list(lines)
        except (ValueError, TypeError) as exc:
            raise LedgerError("Invalid journal lines.") from exc
        if len(line_list) < 2 or len(line_list) > 128:
            raise LedgerError("A journal requires between 2 and 128 legs.")
        normalized = []
        for item in line_list:
            if not isinstance(item, (tuple, list)) or len(item) != 3:
                raise LedgerError("Each journal leg needs account, side and amount.")
            account, side, amount = item
            if not isinstance(account, str) or not _ACCOUNT.fullmatch(account):
                raise LedgerError("Invalid account identifier.")
            if side not in ("D", "C"):
                raise LedgerError("Invalid posting side.")
            normalized.append({"account": account, "side": side,
                               "units": str(_units(amount))})
        operation_hash = _hash({"external_ref": external_ref, "legs": normalized})
        self.db.execute("BEGIN IMMEDIATE")
        try:
            prior = self.db.execute(
                "SELECT seq,request_hash,journal_hash FROM journals WHERE request_id=?",
                (request_id,),
            ).fetchone()
            if prior is not None:
                if prior[1] != operation_hash:
                    raise IdempotencyConflict("Request ID already used with different legs.")
                self.db.execute("COMMIT")
                return prior[0], prior[2]

            totals: dict[str, dict[str, int]] = {}
            changes: dict[str, int] = {}
            accounts: dict[str, tuple[str, str, int]] = {}
            assets: list[str] = []
            for leg in normalized:
                account = leg["account"]
                if account not in accounts:
                    row = self.db.execute(
                        "SELECT asset,normal_side,balance_units FROM accounts"
                        " WHERE account_id=?", (account,)
                    ).fetchone()
                    if row is None:
                        raise LedgerError("Posting references an unregistered account.")
                    accounts[account] = (row[0], row[1], int(row[2]))
                asset, normal_side, _ = accounts[account]
                units = int(leg["units"])
                totals.setdefault(asset, {"D": 0, "C": 0})[leg["side"]] += units
                changes[account] = changes.get(account, 0) + (
                    units if leg["side"] == normal_side else -units
                )
                assets.append(asset)
            if len(accounts) < 2:
                raise LedgerError("A journal must involve at least two accounts.")
            if any(v["D"] != v["C"] for v in totals.values()):
                raise LedgerError("Journal legs must balance separately for each asset.")
            resulting: dict[str, int] = {}
            for account, delta in changes.items():
                remaining = accounts[account][2] + delta
                if remaining < 0:
                    raise InsufficientFunds("Account has insufficient available balance.")
                if remaining > MAX_UNITS:
                    raise LedgerError("Account balance exceeds supported range.")
                resulting[account] = remaining

            prior_hash = self.db.execute(
                "SELECT journal_hash FROM journals ORDER BY seq DESC LIMIT 1"
            ).fetchone()
            previous = prior_hash[0] if prior_hash else GENESIS_HASH
            seq_row = self.db.execute(
                "SELECT seq FROM sqlite_sequence WHERE name='journals'"
            ).fetchone()
            next_seq = (seq_row[0] if seq_row else 0) + 1
            timestamp = datetime.now(timezone.utc).isoformat(
                timespec="microseconds"
            )
            header = {"seq": next_seq, "request_id": request_id,
                      "request_hash": operation_hash, "external_ref": external_ref,
                      "occurred_utc": timestamp, "previous_hash": previous}
            journal_hash = _hash(header)
            self.db.execute(
                "INSERT INTO journals(seq,request_id,request_hash,external_ref,"
                "occurred_utc,previous_hash,journal_hash) VALUES (?,?,?,?,?,?,?)",
                (next_seq, request_id, operation_hash, external_ref,
                 timestamp, previous, journal_hash),
            )
            for index, (leg, asset) in enumerate(zip(normalized, assets), 1):
                self.db.execute(
                    "INSERT INTO postings(journal_seq,line_number,account_id,"
                    "asset,side,units) VALUES (?,?,?,?,?,?)",
                    (next_seq, index, leg["account"], asset,
                     leg["side"], leg["units"]),
                )
            for account, remaining in resulting.items():
                self.db.execute(
                    "UPDATE accounts SET balance_units=? WHERE account_id=?",
                    (str(remaining), account),
                )
            self.db.execute("COMMIT")
            return next_seq, journal_hash
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def audit(self) -> dict[str, int | str]:
        """Recompute every posting, journal checksum and persisted balance."""
        accounts = {
            row[0]: {"asset": row[1], "normal": row[2], "balance": int(row[3]),
                     "reconstructed": 0}
            for row in self.db.execute(
                "SELECT account_id,asset,normal_side,balance_units FROM accounts"
            )
        }
        previous = GENESIS_HASH
        journals = list(self.db.execute(
            "SELECT seq,request_id,request_hash,external_ref,occurred_utc,"
            "previous_hash,journal_hash FROM journals ORDER BY seq"
        ))
        total_postings = 0
        for seq, request_id, req_hash, ref, timestamp, prev, digest in journals:
            header = {"seq": seq, "request_id": request_id,
                      "request_hash": req_hash, "external_ref": ref,
                      "occurred_utc": timestamp, "previous_hash": prev}
            if prev != previous or digest != _hash(header):
                raise LedgerError("Journal checksum chain failed.")
            legs = []
            totals: dict[str, dict[str, int]] = {}
            updates: dict[str, int] = {}
            for line_no, account, asset, side, value in self.db.execute(
                "SELECT line_number,account_id,asset,side,units FROM postings"
                " WHERE journal_seq=? ORDER BY line_number", (seq,)
            ):
                if line_no != len(legs) + 1 or account not in accounts:
                    raise LedgerError("Missing or invalid posting.")
                if accounts[account]["asset"] != asset or side not in ("D", "C"):
                    raise LedgerError("Asset or posting side mismatch.")
                units = _units(value)
                legs.append({"account": account, "side": side, "units": str(units)})
                totals.setdefault(asset, {"D": 0, "C": 0})[side] += units
                updates[account] = updates.get(account, 0) + (
                    units if side == accounts[account]["normal"] else -units
                )
            if len(legs) < 2 or any(v["D"] != v["C"] for v in totals.values()):
                raise LedgerError("Corrupt double-entry journal.")
            if _hash({"external_ref": ref, "legs": legs}) != req_hash:
                raise LedgerError("Journal payload checksum failed.")
            for account, delta in updates.items():
                accounts[account]["reconstructed"] += delta
                if not 0 <= accounts[account]["reconstructed"] <= MAX_UNITS:
                    raise LedgerError("Historical negative or excessive balance.")
            total_postings += len(legs)
            previous = digest
        for row in accounts.values():
            if row["reconstructed"] != row["balance"]:
                raise LedgerError("Account balance differs from immutable postings.")
        return {"accounts": len(accounts), "journals": len(journals),
                "postings": total_postings, "head_hash": previous}
