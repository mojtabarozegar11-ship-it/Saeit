"""Atomic owner-funded capital reservations for MOJ PROP Plan 1.

This module is an execution-adjacent ledger, not a broker adapter.  It binds
one reservation to exactly one internal trader and, when supplied by a
trusted adapter, exactly one broker order.  It never submits, cancels, or
modifies a broker order.

SQLite is used deliberately here as a durable single-writer ledger primitive:
every state transition is inside BEGIN IMMEDIATE, all money is stored as
decimal text, idempotency keys are unique, and the append-only event stream
makes the reservation history auditable.  A production deployment must place
the database on durable storage, back it up, and keep the broker adapter
behind a separate verified permission gate.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import re
import sqlite3
from typing import Any

_REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
_ACTIVE = ("reserved", "submitted")


class LedgerError(Exception):
    """Base class for deterministic ledger failures."""


class LedgerConflict(LedgerError):
    """The requested operation conflicts with an existing immutable fact."""


class UnknownReservation(LedgerError):
    """The reservation identifier is not present in this ledger."""


class InvalidTransition(LedgerError):
    """The requested state transition is not permitted."""


@dataclass(frozen=True)
class Reservation:
    reservation_id: str
    idempotency_key: str
    account_ref: str
    trader_ref: str
    order_ref: str | None
    broker_order_ref: str | None
    status: str
    capital_usd: Decimal
    risk_usd: Decimal
    margin_usd: Decimal
    created_at: str
    updated_at: str
    release_reason: str | None


@dataclass(frozen=True)
class Exposure:
    account_ref: str
    trader_ref: str | None
    reserved_capital_usd: Decimal
    reserved_risk_usd: Decimal
    reserved_margin_usd: Decimal
    reservation_count: int


def _ref(value: str, label: str) -> str:
    if type(value) is not str or _REF.fullmatch(value) is None:
        raise ValueError(f"invalid {label}")
    return value


def _money(value: Decimal, label: str, positive: bool = False) -> Decimal:
    if (type(value) is not Decimal or not value.is_finite() or value < 0
            or (positive and value == 0)
            or value > Decimal("1000000000000")
            or value.as_tuple().exponent < -8):
        raise ValueError(f"invalid exact USD amount: {label}")
    return value


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _dec(value: str) -> Decimal:
    return Decimal(value)


class ReservationLedger:
    """Durable, atomic reservation and attribution ledger.

    The caller must provide already-authenticated internal references.  The
    ledger deliberately does not accept customer-supplied broker identifiers
    as authority and does not make a network call.
    """

    def __init__(self, database: str):
        self.database = database
        self._db = sqlite3.connect(database, timeout=10, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.execute("PRAGMA busy_timeout = 10000")
        self._db.execute("PRAGMA journal_mode = WAL")
        self._db.execute("PRAGMA synchronous = FULL")
        self._create_schema()

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> "ReservationLedger":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _create_schema(self) -> None:
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS owner_reservations (
                reservation_id TEXT PRIMARY KEY,
                idempotency_key TEXT NOT NULL UNIQUE,
                account_ref TEXT NOT NULL,
                trader_ref TEXT NOT NULL,
                order_ref TEXT UNIQUE,
                broker_order_ref TEXT UNIQUE,
                status TEXT NOT NULL CHECK (
                    status IN ('reserved','submitted','released','settled','cancelled')
                ),
                capital_usd TEXT NOT NULL,
                risk_usd TEXT NOT NULL,
                margin_usd TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                release_reason TEXT
            );
            CREATE TABLE IF NOT EXISTS order_attributions (
                broker_order_ref TEXT PRIMARY KEY,
                reservation_id TEXT NOT NULL UNIQUE
                    REFERENCES owner_reservations(reservation_id),
                account_ref TEXT NOT NULL,
                trader_ref TEXT NOT NULL,
                attributed_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS reservation_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                reservation_id TEXT NOT NULL
                    REFERENCES owner_reservations(reservation_id),
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                previous_hash TEXT NOT NULL,
                event_hash TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_reservation_active_account
                ON owner_reservations(account_ref, status);
            CREATE INDEX IF NOT EXISTS idx_reservation_active_trader
                ON owner_reservations(account_ref, trader_ref, status);
            """
        )

    def _begin(self) -> None:
        self._db.execute("BEGIN IMMEDIATE")

    def _finish(self) -> None:
        self._db.execute("COMMIT")

    def _abort(self) -> None:
        if self._db.in_transaction:
            self._db.execute("ROLLBACK")

    def _row(self, reservation_id: str) -> sqlite3.Row:
        row = self._db.execute(
            "SELECT * FROM owner_reservations WHERE reservation_id = ?",
            (reservation_id,),
        ).fetchone()
        if row is None:
            raise UnknownReservation(reservation_id)
        return row

    def _event(self, reservation_id: str, event_type: str,
               payload: dict[str, Any], when: str) -> None:
        previous = self._db.execute(
            "SELECT event_hash FROM reservation_events "
            "ORDER BY event_id DESC LIMIT 1"
        ).fetchone()
        previous_hash = previous["event_hash"] if previous else "GENESIS"
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        material = "|".join((previous_hash, reservation_id, event_type, encoded, when))
        event_hash = hashlib.sha256(material.encode("utf-8")).hexdigest()
        self._db.execute(
            "INSERT INTO reservation_events "
            "(reservation_id,event_type,payload_json,previous_hash,event_hash,created_at) "
            "VALUES (?,?,?,?,?,?)",
            (reservation_id, event_type, encoded, previous_hash, event_hash, when),
        )

    def _as_reservation(self, row: sqlite3.Row) -> Reservation:
        return Reservation(
            reservation_id=row["reservation_id"],
            idempotency_key=row["idempotency_key"],
            account_ref=row["account_ref"],
            trader_ref=row["trader_ref"],
            order_ref=row["order_ref"],
            broker_order_ref=row["broker_order_ref"],
            status=row["status"],
            capital_usd=_dec(row["capital_usd"]),
            risk_usd=_dec(row["risk_usd"]),
            margin_usd=_dec(row["margin_usd"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            release_reason=row["release_reason"],
        )

    def get(self, reservation_id: str) -> Reservation:
        return self._as_reservation(self._row(_ref(reservation_id, "reservation id")))

    def exposure(self, account_ref: str, trader_ref: str | None = None) -> Exposure:
        account = _ref(account_ref, "account reference")
        trader = _ref(trader_ref, "trader reference") if trader_ref is not None else None
        where = ["account_ref = ?", "status IN ('reserved','submitted')"]
        args: list[str] = [account]
        if trader is not None:
            where.append("trader_ref = ?")
            args.append(trader)
        rows = self._db.execute(
            "SELECT capital_usd, risk_usd, margin_usd "
            f"FROM owner_reservations WHERE {' AND '.join(where)}",
            args,
        ).fetchall()
        # Never let SQLite coerce decimal text through binary floating point.
        capital = sum((_dec(row["capital_usd"]) for row in rows), Decimal("0"))
        risk = sum((_dec(row["risk_usd"]) for row in rows), Decimal("0"))
        margin = sum((_dec(row["margin_usd"]) for row in rows), Decimal("0"))
        return Exposure(account, trader, capital, risk, margin, len(rows))

    def reserve(
        self, *, reservation_id: str, idempotency_key: str, account_ref: str,
        trader_ref: str, capital_usd: Decimal, risk_usd: Decimal,
        margin_usd: Decimal, max_account_risk_usd: Decimal,
        max_trader_risk_usd: Decimal, max_account_capital_usd: Decimal,
        order_ref: str | None = None,
    ) -> Reservation:
        rid = _ref(reservation_id, "reservation id")
        idem = _ref(idempotency_key, "idempotency key")
        account = _ref(account_ref, "account reference")
        trader = _ref(trader_ref, "trader reference")
        order = _ref(order_ref, "order reference") if order_ref is not None else None
        values = (
            _money(capital_usd, "capital", True),
            _money(risk_usd, "risk", True),
            _money(margin_usd, "margin", True),
            _money(max_account_risk_usd, "account risk limit"),
            _money(max_trader_risk_usd, "trader risk limit"),
            _money(max_account_capital_usd, "account capital limit"),
        )
        capital, risk, margin, account_limit, trader_limit, capital_limit = values
        self._begin()
        try:
            existing = self._db.execute(
                "SELECT * FROM owner_reservations WHERE idempotency_key = ?",
                (idem,),
            ).fetchone()
            if existing is not None:
                same = (
                    existing["reservation_id"] == rid
                    and existing["account_ref"] == account
                    and existing["trader_ref"] == trader
                    and existing["order_ref"] == order
                    and _dec(existing["capital_usd"]) == capital
                    and _dec(existing["risk_usd"]) == risk
                    and _dec(existing["margin_usd"]) == margin
                )
                if not same:
                    raise LedgerConflict("idempotency key reused with different facts")
                self._finish()
                return self._as_reservation(existing)
            if self._db.execute(
                "SELECT 1 FROM owner_reservations WHERE reservation_id = ?", (rid,)
            ).fetchone():
                raise LedgerConflict("reservation id already exists")
            account_exposure = self.exposure(account)
            trader_exposure = self.exposure(account, trader)
            if account_exposure.reserved_risk_usd + risk > account_limit:
                raise LedgerConflict("account risk reservation limit exceeded")
            if trader_exposure.reserved_risk_usd + risk > trader_limit:
                raise LedgerConflict("trader risk reservation limit exceeded")
            if account_exposure.reserved_capital_usd + capital > capital_limit:
                raise LedgerConflict("account capital reservation limit exceeded")
            when = _now()
            self._db.execute(
                "INSERT INTO owner_reservations "
                "(reservation_id,idempotency_key,account_ref,trader_ref,order_ref,"
                "broker_order_ref,status,capital_usd,risk_usd,margin_usd,created_at,"
                "updated_at,release_reason) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (rid, idem, account, trader, order, None, "reserved",
                 str(capital), str(risk), str(margin), when, when, None),
            )
            self._event(rid, "reserved", {
                "account_ref": account, "trader_ref": trader,
                "capital_usd": str(capital), "risk_usd": str(risk),
                "margin_usd": str(margin), "idempotency_key": idem,
            }, when)
            row = self._row(rid)
            self._finish()
            return self._as_reservation(row)
        except Exception:
            self._abort()
            raise

    def bind_broker_order(self, *, reservation_id: str,
                          broker_order_ref: str) -> Reservation:
        rid = _ref(reservation_id, "reservation id")
        broker = _ref(broker_order_ref, "broker order reference")
        self._begin()
        try:
            row = self._row(rid)
            if row["broker_order_ref"] is not None:
                if row["broker_order_ref"] == broker:
                    self._finish()
                    return self._as_reservation(row)
                raise LedgerConflict("reservation already bound to another broker order")
            taken = self._db.execute(
                "SELECT reservation_id FROM order_attributions "
                "WHERE broker_order_ref = ?", (broker,)
            ).fetchone()
            if taken is not None:
                raise LedgerConflict("broker order already attributed")
            if row["status"] != "reserved":
                raise InvalidTransition("only a reserved entry can be submitted")
            when = _now()
            self._db.execute(
                "INSERT INTO order_attributions "
                "(broker_order_ref,reservation_id,account_ref,trader_ref,attributed_at) "
                "VALUES (?,?,?,?,?)",
                (broker, rid, row["account_ref"], row["trader_ref"], when),
            )
            self._db.execute(
                "UPDATE owner_reservations SET broker_order_ref=?, status='submitted', "
                "updated_at=? WHERE reservation_id=?",
                (broker, when, rid),
            )
            self._event(rid, "submitted", {
                "broker_order_ref": broker,
                "account_ref": row["account_ref"],
                "trader_ref": row["trader_ref"],
            }, when)
            result = self._as_reservation(self._row(rid))
            self._finish()
            return result
        except Exception:
            self._abort()
            raise

    def release(self, *, reservation_id: str, reason: str) -> Reservation:
        rid = _ref(reservation_id, "reservation id")
        if type(reason) is not str or not reason.strip() or len(reason) > 512:
            raise ValueError("release reason required")
        self._begin()
        try:
            row = self._row(rid)
            if row["status"] in ("released", "cancelled"):
                self._finish()
                return self._as_reservation(row)
            if row["status"] != "reserved":
                raise InvalidTransition("submitted reservations need broker reconciliation")
            when = _now()
            self._db.execute(
                "UPDATE owner_reservations SET status='released', release_reason=?, "
                "updated_at=? WHERE reservation_id=?",
                (reason.strip(), when, rid),
            )
            self._event(rid, "released", {"reason": reason.strip()}, when)
            result = self._as_reservation(self._row(rid))
            self._finish()
            return result
        except Exception:
            self._abort()
            raise

    def settle(self, *, reservation_id: str, outcome: str) -> Reservation:
        rid = _ref(reservation_id, "reservation id")
        if type(outcome) is not str or not outcome.strip() or len(outcome) > 512:
            raise ValueError("settlement outcome required")
        self._begin()
        try:
            row = self._row(rid)
            if row["status"] == "settled":
                self._finish()
                return self._as_reservation(row)
            if row["status"] != "submitted":
                raise InvalidTransition("only a submitted reservation can settle")
            when = _now()
            self._db.execute(
                "UPDATE owner_reservations SET status='settled', updated_at=? "
                "WHERE reservation_id=?", (when, rid),
            )
            self._event(rid, "settled", {"outcome": outcome.strip()}, when)
            result = self._as_reservation(self._row(rid))
            self._finish()
            return result
        except Exception:
            self._abort()
            raise

    def verify_event_chain(self) -> bool:
        previous = "GENESIS"
        rows = self._db.execute(
            "SELECT * FROM reservation_events ORDER BY event_id"
        ).fetchall()
        for row in rows:
            material = "|".join((previous, row["reservation_id"],
                                 row["event_type"], row["payload_json"],
                                 row["created_at"]))
            digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
            if row["previous_hash"] != previous or row["event_hash"] != digest:
                return False
            previous = digest
        return True
