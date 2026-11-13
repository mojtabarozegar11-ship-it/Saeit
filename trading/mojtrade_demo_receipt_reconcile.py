"""Offline cTrader demo history receipt reconciliation — never real-income proof.

Consumes log records emitted by MojTradeDemoHistoryAuditBot on a demo account.
The input log is *not* authenticated to cTrader or the broker merely because
its syntax is valid. Broker statement corroboration remains mandatory.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
import stat

PREFIX = "MOJTRADE_AUDIT_V1|"
MAX_BYTES = 8_000_000
MAX_DEALS = 20_000
START_FIELDS = frozenset({"session", "alias", "currency", "symbol", "mode", "count"})
DEAL_FIELDS = frozenset({
    "session", "deal_id", "position_id", "closed_utc", "side", "lots",
    "gross", "commission", "swap", "net", "balance_after",
})
END_FIELDS = frozenset({
    "session", "count", "wins", "gross", "commission", "swap", "net",
    "demo_only", "external_broker_reconciliation",
})
CURRENCY = re.compile(r"^[A-Za-z]{3,10}$")
SYMBOL = re.compile(r"^[A-Za-z0-9._-]{3,40}$")
ALIAS = re.compile(r"^[A-Za-z0-9_-]{3,40}$")
SESSION = re.compile(r"^[0-9a-f]{32}$")


class DemoAuditError(ValueError):
    """Invalid, inconsistent or unauthenticated account-history snapshot."""


def _fields(record: str, expected: frozenset[str]) -> dict[str, str]:
    tokens = record.split("|")
    values = {}
    for token in tokens:
        if "=" not in token:
            raise DemoAuditError("audit_record_field_missing")
        key, value = token.split("=", 1)
        if key in values or key not in expected or not value or "|" in value:
            raise DemoAuditError("audit_record_field_invalid_or_duplicate")
        values[key] = value
    if set(values) != set(expected):
        raise DemoAuditError("audit_record_schema_mismatch")
    return values


def _count(value: str, field: str, *, lower: int = 0, upper: int = MAX_DEALS) -> int:
    if not re.fullmatch(r"[0-9]{1,20}", value):
        raise DemoAuditError(field + "_invalid")
    result = int(value)
    if not lower <= result <= upper:
        raise DemoAuditError(field + "_out_of_range")
    return result


def _money(value: str, field: str) -> Decimal:
    if not re.fullmatch(r"-?(?:[0-9]+(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?[eE][-+]?[0-9]+)", value):
        raise DemoAuditError(field + "_invalid")
    try:
        number = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise DemoAuditError(field + "_invalid") from exc
    if not number.is_finite() or number.adjusted() > 14:
        raise DemoAuditError(field + "_nonfinite_or_unbounded")
    return number


def _timestamp(value: str, now: datetime):
    if not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{7}Z", value):
        raise DemoAuditError("audit_closing_time_invalid")
    try:
        when = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DemoAuditError("audit_closing_time_invalid") from exc
    if when.tzinfo is None or when > now:
        raise DemoAuditError("audit_closing_time_future_or_unaware")
    return when


def reconcile_text(text: str, *, now: datetime | None = None) -> dict:
    """Strictly check one START/DEAL*/END session, full totals and identity."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise DemoAuditError("audit_now_must_be_aware")
    now = now.astimezone(timezone.utc)
    lines = []
    for line in text.splitlines():
        if "MOJTRADE_AUDIT_V1" not in line:
            continue
        offset = line.find(PREFIX)
        if offset < 0:
            raise DemoAuditError("audit_protocol_line_invalid")
        lines.append(line[offset:].strip())
    if len(lines) < 2 or len(lines) > MAX_DEALS + 2:
        raise DemoAuditError("audit_incomplete_or_oversized")
    parts = [line[len(PREFIX):].split("|", 1) for line in lines]
    if any(len(p) != 2 for p in parts):
        raise DemoAuditError("audit_record_invalid")
    if parts[0][0] != "START" or parts[-1][0] != "END":
        raise DemoAuditError("audit_missing_single_start_or_end")
    if any(p[0] != "DEAL" for p in parts[1:-1]):
        raise DemoAuditError("audit_unexpected_or_duplicate_session_record")
    start = _fields(parts[0][1], START_FIELDS)
    end = _fields(parts[-1][1], END_FIELDS)
    if not SESSION.fullmatch(start["session"]) or end["session"] != start["session"]:
        raise DemoAuditError("audit_session_mismatch")
    if not ALIAS.fullmatch(start["alias"]) or not CURRENCY.fullmatch(start["currency"]) or not SYMBOL.fullmatch(start["symbol"]):
        raise DemoAuditError("audit_identity_invalid")
    if start["mode"] != "demo" or end["demo_only"] != "true" or end["external_broker_reconciliation"] != "false":
        raise DemoAuditError("audit_live_or_independently_attested_claim_rejected")
    announced = _count(start["count"], "start_count")
    completed = _count(end["count"], "end_count")
    if announced != completed or announced != len(parts) - 2:
        raise DemoAuditError("audit_count_mismatch")
    seen = set()
    entries = []
    for _, payload in parts[1:-1]:
        row = _fields(payload, DEAL_FIELDS)
        if row["session"] != start["session"]:
            raise DemoAuditError("audit_mixed_sessions")
        deal_id = _count(row["deal_id"], "deal_id", lower=1, upper=2_147_483_647)
        position_id = _count(row["position_id"], "position_id", lower=1, upper=2_147_483_647)
        if deal_id in seen or row["side"] not in {"buy", "sell"}:
            raise DemoAuditError("audit_duplicate_deal_or_side_invalid")
        seen.add(deal_id)
        closed = _timestamp(row["closed_utc"], now)
        lots = _money(row["lots"], "lots")
        if lots <= 0:
            raise DemoAuditError("audit_quantity_invalid")
        amounts = {name: _money(row[name], name) for name in (
            "gross", "commission", "swap", "net", "balance_after"
        )}
        entries.append({
            "deal_id": deal_id, "position_id": position_id,
            "closing_time": closed, "side": row["side"],
            "lots": lots, **amounts,
        })
    if any(
        (next_entry["closing_time"], next_entry["deal_id"]) <
        (prev_entry["closing_time"], prev_entry["deal_id"])
        for prev_entry, next_entry in zip(entries, entries[1:])
    ):
        raise DemoAuditError("audit_deal_order_invalid")

    totals = {
        name: sum((row[name] for row in entries), Decimal(0))
        for name in ("gross", "commission", "swap", "net")
    }
    winners = sum(row["net"] > 0 for row in entries)
    if _count(end["wins"], "wins") != winners:
        raise DemoAuditError("audit_win_count_mismatch")
    # Floating-point source cBot accumulates using double and prints
    # round-trip numbers. A tolerance smaller than one cent accommodates
    # double-sum drift without allowing meaningful reconciliation errors.
    for name, total in totals.items():
        reported = _money(end[name], "summary_" + name)
        if abs(reported - total) > Decimal("0.0001"):
            raise DemoAuditError("audit_broker_net_totals_mismatch_" + name)

    wins = [row["net"] for row in entries if row["net"] > 0]
    losses = [-row["net"] for row in entries if row["net"] < 0]
    loss_total = sum(losses, Decimal(0))
    profit_factor = sum(wins, Decimal(0)) / loss_total if loss_total else None
    negative = sum(row["net"] < 0 for row in entries)
    flat = len(entries) - winners - negative
    cumulative, high, worst = Decimal(0), Decimal(0), Decimal(0)
    for row in entries:
        cumulative += row["net"]
        high = max(high, cumulative)
        worst = max(worst, high - cumulative)

    return {
        "schema": "mojtrade-demo-history-audit-v1",
        "alias": start["alias"],
        "symbol": start["symbol"],
        "account_currency": start["currency"],
        "mode": "demo",
        "closing_deal_count": len(entries),
        "distinct_closing_deals": len(seen),
        "first_closing_utc": entries[0]["closing_time"].isoformat() if entries else None,
        "last_closing_utc": entries[-1]["closing_time"].isoformat() if entries else None,
        "wins": winners, "losses": negative, "breakeven": flat,
        "win_rate": str(Decimal(winners) / len(entries)) if entries else None,
        "gross_account_currency": str(totals["gross"]),
        "commissions_account_currency": str(totals["commission"]),
        "swaps_account_currency": str(totals["swap"]),
        "broker_reported_net_account_currency": str(totals["net"]),
        "realized_demo_trade_profit_factor": str(profit_factor) if profit_factor is not None else None,
        "max_closed_deal_cumulative_drawdown_amount": str(worst),
        "unique_deal_ids_sha256": hashlib.sha256(",".join(str(n) for n in sorted(seen)).encode()).hexdigest(),
        "source_log_is_independently_authenticated": False,
        "broker_statement_reconciled": False,
        "complete_account_transaction_ledger_reconciled": False,
        "real_account_revenue_verified": False,
        "real_account_trades": 0,
        "broker_order_placement_enabled": False,
        "profits_are_demo_only_not_withdrawable": True,
    }


def reconcile_file(path: Path) -> dict:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise DemoAuditError("private_log_path_invalid")
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise DemoAuditError("private_log_permissions_too_open")
    with path.open("rb") as handle:
        raw = handle.read(MAX_BYTES + 1)
    if not raw or len(raw) > MAX_BYTES:
        raise DemoAuditError("private_log_size_invalid")
    try:
        text = raw.decode("utf-8")
    except UnicodeError as exc:
        raise DemoAuditError("private_log_not_utf8") from exc
    result = reconcile_text(text)
    result["source_log_sha256"] = hashlib.sha256(raw).hexdigest()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only, unauthenticated until broker corroboration, cTrader demo receipt verification"
    )
    parser.add_argument("--private-log", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = reconcile_file(args.private_log)
    except (DemoAuditError, OSError) as exc:
        parser.exit(2, f"MOJTRADE_DEMO_AUDIT_REJECTED: {exc}\n")
    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
