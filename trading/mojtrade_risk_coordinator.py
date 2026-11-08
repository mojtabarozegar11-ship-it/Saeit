"""Fail-closed, DEMO-only central admission controller for cTrader adapters.

Uses SQLite BEGIN IMMEDIATE for serialized cross-client reservations. This is a
source artifact, NOT a running service and NOT authorization to place orders.
Bind to loopback; deploy behind authenticated HTTPS reverse proxy if approved.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
import os
import re
import sqlite3
import time
from urllib.parse import parse_qs, urlsplit


ACCOUNT_RE = re.compile(r"^[0-9]{1,20}$")
REQUEST_RE = re.compile(r"^[a-f0-9]{32}$")
DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
LIMIT = Decimal("0.02")
CAP = 3
TTL_SECONDS = 90


class Denied(Exception):
    pass


def finite_decimal(raw: str) -> Decimal:
    try:
        value = Decimal(raw)
    except (InvalidOperation, TypeError) as exc:
        raise Denied("invalid_number") from exc
    if not value.is_finite():
        raise Denied("invalid_number")
    return value


def valid_day(day: str) -> str:
    if not DAY_RE.fullmatch(day):
        raise Denied("invalid_day")
    try:
        datetime.strptime(day, "%Y-%m-%d")
    except ValueError as exc:
        raise Denied("invalid_day") from exc
    return day


@dataclass(frozen=True)
class Admission:
    account: str
    day: str
    request_id: str
    equity: Decimal
    realized_today: Decimal
    open_positions: int

    @classmethod
    def parse(cls, fields: dict[str, str], today: str) -> "Admission":
        if fields.get("mode") != "demo":
            raise Denied("demo_only")
        account = fields.get("account", "")
        day = valid_day(fields.get("day", ""))
        request_id = fields.get("request_id", "")
        if not ACCOUNT_RE.fullmatch(account) or not REQUEST_RE.fullmatch(request_id):
            raise Denied("invalid_identity")
        if day != today:
            raise Denied("stale_day")
        equity = finite_decimal(fields.get("equity", ""))
        realized = finite_decimal(fields.get("realized_today", ""))
        if equity <= 0:
            raise Denied("invalid_equity")
        try:
            positions = int(fields.get("open_positions", ""))
        except (TypeError, ValueError) as exc:
            raise Denied("invalid_position_count") from exc
        if positions < 0 or positions > 10000:
            raise Denied("invalid_position_count")
        return cls(account, day, request_id, equity, realized, positions)


class Ledger:
    def __init__(self, db_path: str, *, enabled: bool = False, clock=time.time):
        if not db_path:
            raise ValueError("explicit database path required")
        self.db_path = db_path
        self.enabled = enabled
        self.clock = clock
        db = self._connection()
        try:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS day_state (
                    account TEXT NOT NULL, day TEXT NOT NULL,
                    baseline TEXT NOT NULL, halted INTEGER NOT NULL DEFAULT 0,
                    last_equity TEXT NOT NULL, updated REAL NOT NULL,
                    PRIMARY KEY (account, day)
                );
                CREATE TABLE IF NOT EXISTS reservations (
                    request_id TEXT PRIMARY KEY, account TEXT NOT NULL,
                    day TEXT NOT NULL, state TEXT NOT NULL,
                    expires REAL NOT NULL, created REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS active_reservations
                    ON reservations(account, day, state, expires);
                """
            )
        finally:
            db.close()

    def _connection(self):
        db = sqlite3.connect(self.db_path, timeout=10, isolation_level=None)
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        return db

    def seed_day(self, account: str, day: str, equity: str) -> None:
        """Operator-only enrollment; cannot overwrite an existing baseline."""
        if not ACCOUNT_RE.fullmatch(account):
            raise Denied("invalid_identity")
        valid_day(day)
        value = finite_decimal(equity)
        if value <= 0:
            raise Denied("invalid_equity")
        now = self.clock()
        db = self._connection()
        try:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "INSERT INTO day_state(account,day,baseline,last_equity,updated) "
                "VALUES (?,?,?,?,?)",
                (account, day, str(value), str(value), now),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _refresh_daily(self, db: sqlite3.Connection, admission: Admission, now: float) -> None:
        """Persist observations and latch daily loss, without consuming a slot.

        Caller must hold an immediate SQLite transaction.
        """
        if admission.day != datetime.fromtimestamp(now, timezone.utc).date().isoformat():
            raise Denied("stale_day")
        if not admission.equity.is_finite() or admission.equity <= 0:
            raise Denied("invalid_equity")
        if not admission.realized_today.is_finite():
            raise Denied("invalid_number")
        state = db.execute(
            "SELECT baseline,halted FROM day_state WHERE account=? AND day=?",
            (admission.account, admission.day),
        ).fetchone()
        if state is None:
            # Unattended UTC rollover requires a fresh pre-midnight equity snapshot.
            midnight = datetime.strptime(admission.day, "%Y-%m-%d").replace(
                tzinfo=timezone.utc).timestamp()
            yesterday = (datetime.fromtimestamp(midnight, timezone.utc).date()
                         - timedelta(days=1)).isoformat()
            old = db.execute(
                "SELECT last_equity,updated FROM day_state "
                "WHERE account=? AND day=?",
                (admission.account, yesterday),
            ).fetchone()
            if (old is None or not midnight <= now <= midnight + 120 or
                    not midnight - 120 <= old[1] < midnight):
                raise Denied("baseline_not_enrolled")
            carried = Decimal(old[0])
            if not carried.is_finite() or carried <= 0:
                raise Denied("invalid_prior_baseline")
            db.execute(
                "INSERT INTO day_state(account,day,baseline,last_equity,updated) "
                "VALUES (?,?,?,?,?)",
                (admission.account, admission.day, str(carried),
                 str(carried), now),
            )
            state = (str(carried), 0)
        baseline, halted = Decimal(state[0]), state[1]
        if baseline <= 0 or not baseline.is_finite() or halted:
            raise Denied("risk_halted")
        if (admission.equity <= baseline * (1 - LIMIT) or
                admission.realized_today <= -(baseline * LIMIT)):
            db.execute(
                "UPDATE day_state SET halted=1,last_equity=?,updated=? "
                "WHERE account=? AND day=?",
                (str(admission.equity), now, admission.account, admission.day),
            )
            db.commit()  # Latch persists even if a future retry is denied.
            raise Denied("daily_loss_reached")
        db.execute(
            "UPDATE day_state SET last_equity=?,updated=? "
            "WHERE account=? AND day=?",
            (str(admission.equity), now, admission.account, admission.day),
        )

    def observe(self, admission: Admission) -> None:
        """Observe equity even with no trade signal or a full position book."""
        now = self.clock()
        db = self._connection()
        try:
            db.execute("BEGIN IMMEDIATE")
            self._refresh_daily(db, admission, now)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def reserve(self, admission: Admission) -> str:
        if not self.enabled:
            raise Denied("disabled")
        now = self.clock()
        db = self._connection()
        try:
            db.execute("BEGIN IMMEDIATE")
            if db.execute(
                "SELECT 1 FROM reservations WHERE request_id=?",
                (admission.request_id,),
            ).fetchone():
                raise Denied("duplicate_request")
            self._refresh_daily(db, admission, now)
            active = db.execute(
                "SELECT COUNT(*) FROM reservations WHERE account=? AND day=? "
                "AND state IN ('reserved','committed') AND expires>?",
                (admission.account, admission.day, now),
            ).fetchone()[0]
            if admission.open_positions + active >= CAP:
                raise Denied("position_cap")
            db.execute(
                "INSERT INTO reservations(request_id,account,day,state,expires,created) "
                "VALUES (?,?,?,'reserved',?,?)",
                (admission.request_id, admission.account, admission.day,
                 now + TTL_SECONDS, now),
            )
            db.commit()
            return admission.request_id
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def settle(self, request_id: str, account: str, *, filled: bool) -> None:
        if not REQUEST_RE.fullmatch(request_id) or not ACCOUNT_RE.fullmatch(account):
            raise Denied("invalid_identity")
        db = self._connection()
        try:
            db.execute("BEGIN IMMEDIATE")
            state = db.execute(
                "SELECT state,expires FROM reservations WHERE request_id=? AND account=?",
                (request_id, account),
            ).fetchone()
            if state is None or state[0] != "reserved" or state[1] <= self.clock():
                raise Denied("unknown_or_expired_reservation")
            db.execute(
                "UPDATE reservations SET state=? WHERE request_id=?",
                ("committed" if filled else "cancelled", request_id),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def status(self, account: str, day: str) -> dict[str, object]:
        """Authenticated, non-mutating operator snapshot; not broker readiness.

        No trade permission is derived from this response. A healthy coordinator
        cannot establish that a cBot, TLS endpoint or broker is operational.
        """
        if not ACCOUNT_RE.fullmatch(account):
            raise Denied("invalid_identity")
        valid_day(day)
        now = self.clock()
        db = self._connection()
        try:
            row = db.execute(
                "SELECT baseline,last_equity,halted,updated FROM day_state "
                "WHERE account=? AND day=?", (account, day),
            ).fetchone()
            if row is None:
                raise Denied("baseline_not_enrolled")
            active = db.execute(
                "SELECT COUNT(*) FROM reservations WHERE account=? AND day=? "
                "AND state IN ('reserved','committed') AND expires>?",
                (account, day, now),
            ).fetchone()[0]
        finally:
            db.close()
        age = max(0, int(now - row[3]))
        today = datetime.fromtimestamp(now, timezone.utc).date().isoformat()
        return {
            "account": account,
            "day": day,
            "baseline": row[0],
            "last_equity": row[1],
            "halted": bool(row[2]),
            "last_risk_update_age_seconds": age,
            "telemetry_fresh": day == today and age <= 120,
            "active_reservations": active,
            "demo_reservations_enabled": self.enabled,
        }


class Handler(BaseHTTPRequestHandler):
    ledger: Ledger
    token: str

    def _reply(self, code: int, body: str, content_type: str = "text/plain; charset=us-ascii") -> None:
        payload = body.encode("ascii")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path == "/health":
            # Liveness only. This does not establish DB or broker readiness.
            self._reply(200, "SERVICE_UP")
            return
        address = urlsplit(self.path)
        if address.path != "/v1/status":
            self._reply(404, "NOT_FOUND")
            return
        if not hmac.compare_digest(
                self.headers.get("Authorization", ""), "Bearer " + self.token):
            self._reply(401, "DENIED|unauthorized")
            return
        try:
            fields = parse_qs(address.query, strict_parsing=True, max_num_fields=2)
            if set(fields) != {"account", "day"} or any(
                    len(values) != 1 for values in fields.values()):
                raise Denied("invalid_query")
            snapshot = self.ledger.status(fields["account"][0], fields["day"][0])
            self._reply(200, json.dumps(snapshot, sort_keys=True),
                        "application/json; charset=us-ascii")
        except (Denied, ValueError, UnicodeError) as exc:
            self._reply(409, "DENIED|" + str(exc))
        except (sqlite3.Error, OSError):
            self._reply(503, "DENIED|storage_unavailable")

    def do_POST(self):
        authorization = self.headers.get("Authorization", "")
        if not hmac.compare_digest(authorization, "Bearer " + self.token):
            self._reply(401, "DENIED|unauthorized")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 4096:
                raise Denied("invalid_body")
            parsed = parse_qs(self.rfile.read(length).decode("ascii"),
                              strict_parsing=True, max_num_fields=10)
            if any(len(values) != 1 for values in parsed.values()):
                raise Denied("duplicate_field")
            fields = {k: v[0] for k, v in parsed.items()}
            if self.path in ("/v1/reserve", "/v1/observe"):
                today = datetime.fromtimestamp(self.ledger.clock(), timezone.utc).date().isoformat()
                request = Admission.parse(fields, today)
                if self.path == "/v1/observe":
                    self.ledger.observe(request)
                    self._reply(200, "OBSERVED")
                else:
                    ticket = self.ledger.reserve(request)
                    self._reply(200, "GRANTED|" + ticket)
            elif self.path in ("/v1/commit", "/v1/cancel"):
                self.ledger.settle(
                    fields.get("request_id", ""),
                    fields.get("account", ""),
                    filled=self.path == "/v1/commit",
                )
                self._reply(200, "SETTLED")
            else:
                self._reply(404, "NOT_FOUND")
        except (Denied, ValueError, UnicodeError) as exc:
            self._reply(409, "DENIED|" + str(exc))
        except (sqlite3.Error, OSError):
            self._reply(503, "DENIED|storage_unavailable")

    def log_message(self, format, *args):
        # Never log Authorization or user-supplied financial values.
        return


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=os.environ.get("MOJTRADE_RISK_DB", ""))
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--enable-demo-reservations", action="store_true")
    parser.add_argument("--seed-account")
    parser.add_argument("--seed-day")
    parser.add_argument("--seed-equity")
    args = parser.parse_args()
    ledger = Ledger(args.db, enabled=args.enable_demo_reservations)
    if args.seed_account:
        if not args.seed_day or not args.seed_equity:
            parser.error("seed requires --seed-day and --seed-equity")
        ledger.seed_day(args.seed_account, args.seed_day, args.seed_equity)
        print("Baseline enrolled (no orders submitted).")
        return
    token = os.environ.get("MOJTRADE_RISK_TOKEN", "")
    if len(token) < 32:
        parser.error("MOJTRADE_RISK_TOKEN must be at least 32 characters")
    Handler.ledger = ledger
    Handler.token = token
    httpd = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print("Loopback-only risk coordinator; TLS reverse proxy required for clients.")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
