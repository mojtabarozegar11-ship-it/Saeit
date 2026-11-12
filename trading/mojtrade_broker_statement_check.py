"""Exact cTrader demo-history vs separately exported statement cross-check.

Accepted CSV is a deliberately *normalized* cTrader statement, NOT an
assumption about the platform's native CSV headers. No account connection,
broker API, execution, promotion or real-money profit claim occurs here.
The operator must obtain both independent exports from the authorized demo
account, verify broker provenance separately, and normalize columns without
altering any economic or identifying trade values.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat

from trading.mojtrade_demo_receipt_reconcile import (
    DemoAuditError, MAX_BYTES, _count, _fields, _money, _timestamp,
    reconcile_text, START_FIELDS, DEAL_FIELDS, END_FIELDS, PREFIX,
)

SCHEMA = "mojtrade-demo-statement-crosscheck-v1"
MAX_STATEMENT_BYTES = 8_000_000
MAX_MANIFEST_BYTES = 32_000
FIELDS = (
    "deal_id", "position_id", "closed_utc", "symbol", "label",
    "side", "lots", "gross", "commission", "swap", "net",
    "balance_after", "currency",
)
LABEL = "MojTrade-OMEGA-X-DEMO"
MONEY_TOLERANCE = Decimal("0.01")
LOTS_TOLERANCE = Decimal("0.00000001")
TIME_TOLERANCE = timedelta(seconds=1)
ALLOWED_BROKER = "LiteFinance"
ALLOWED_SOURCE = "ctrader_history_statement_export"
_SHA256 = re.compile(r"[0-9a-f]{64}")


class StatementCrosscheckError(ValueError):
    """Refuse to certify an inconsistent, missing or wrong-account statement."""


def _private_bytes(path: Path, maximum: int) -> bytes:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise StatementCrosscheckError("private_source_path_invalid")
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise StatementCrosscheckError("private_source_permissions_insecure")
    try:
        with path.open("rb") as stream:
            data = stream.read(maximum + 1)
    except OSError as exc:
        raise StatementCrosscheckError("private_source_unavailable") from exc
    if not 0 < len(data) <= maximum:
        raise StatementCrosscheckError("private_source_size_invalid")
    return data


def _manifest(raw: bytes, statement_sha: str, report: dict) -> dict:
    try:
        obj = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise StatementCrosscheckError("statement_manifest_invalid_json") from exc
    expected = {
        "schema_version", "broker", "account_mode", "account_alias",
        "account_currency", "symbol", "source", "full_label_history",
        "statement_sha256", "exported_at_utc",
    }
    if (
        not isinstance(obj, dict) or set(obj) != expected
        or type(obj["schema_version"]) is not int or obj["schema_version"] != 1
        or obj["broker"] != ALLOWED_BROKER or obj["account_mode"] != "demo"
        or obj["account_alias"] != report["alias"]
        or obj["account_currency"] != report["account_currency"]
        or obj["symbol"] != report["symbol"]
        or obj["source"] != ALLOWED_SOURCE
        or obj["full_label_history"] is not True
        or obj["statement_sha256"] != statement_sha
    ):
        raise StatementCrosscheckError("statement_manifest_identity_or_scope_mismatch")
    timestamp = obj["exported_at_utc"]
    if not isinstance(timestamp, str) or not timestamp.endswith("Z"):
        raise StatementCrosscheckError("statement_manifest_export_time_invalid")
    try:
        exported = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise StatementCrosscheckError("statement_manifest_export_time_invalid") from exc
    if exported.tzinfo is None or exported > datetime.now(timezone.utc) + timedelta(minutes=1):
        raise StatementCrosscheckError("statement_manifest_future_or_unaware")
    return obj


def _parse_log_deals(text: str, expected: dict) -> dict[int, dict]:
    """Re-open a rigorously reconciled log; re-use its strict field validators."""
    reconcile_text(text)
    records = [line[line.find(PREFIX) + len(PREFIX):].strip()
               for line in text.splitlines() if PREFIX in line]
    start = _fields(records[0].split("|", 1)[1], START_FIELDS)
    if (start["alias"], start["symbol"], start["currency"]) != (
        expected["alias"], expected["symbol"], expected["account_currency"]
    ):
        raise StatementCrosscheckError("demo_log_identity_mismatch")
    result = {}
    for record in records[1:-1]:
        line = _fields(record.split("|", 1)[1], DEAL_FIELDS)
        deal_id = _count(line["deal_id"], "deal_id", lower=1, upper=2_147_483_647)
        result[deal_id] = {
            "position_id": _count(line["position_id"], "position_id",
                                   lower=1, upper=2_147_483_647),
            "closed_utc": _timestamp(line["closed_utc"], datetime.now(timezone.utc)),
            "side": line["side"], "symbol": expected["symbol"],
            "label": LABEL, "currency": expected["account_currency"],
            "lots": _money(line["lots"], "lots"),
            **{key: _money(line[key], key) for key in
               ("gross", "commission", "swap", "net", "balance_after")},
        }
    return result


def compare_bytes(log_bytes: bytes, statement_bytes: bytes, manifest_bytes: bytes) -> dict:
    """Compare exact deal IDs and all economics; never claim external attestation."""
    if not log_bytes or len(log_bytes) > MAX_BYTES:
        raise StatementCrosscheckError("demo_log_missing_or_oversized")
    if not statement_bytes or len(statement_bytes) > MAX_STATEMENT_BYTES:
        raise StatementCrosscheckError("statement_missing_or_oversized")
    if not manifest_bytes or len(manifest_bytes) > MAX_MANIFEST_BYTES:
        raise StatementCrosscheckError("statement_manifest_missing_or_oversized")
    try:
        source_text = log_bytes.decode("utf-8")
        statement_text = statement_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise StatementCrosscheckError("source_encoding_invalid") from exc
    try:
        parsed = reconcile_text(source_text)
    except DemoAuditError as exc:
        raise StatementCrosscheckError("demo_log_invalid") from exc
    digest = hashlib.sha256(statement_bytes).hexdigest()
    manifest = _manifest(manifest_bytes, digest, parsed)
    try:
        reader = csv.DictReader(io.StringIO(statement_text, newline=""))
        if reader.fieldnames != list(FIELDS):
            raise StatementCrosscheckError("statement_columns_not_normalized")
        exported = {}
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise StatementCrosscheckError("statement_row_malformed")
            if len(exported) >= 20_000:
                raise StatementCrosscheckError("statement_too_many_deals")
            if (
                row["symbol"] != parsed["symbol"]
                or row["label"] != LABEL
                or row["currency"] != parsed["account_currency"]
                or row["side"] not in {"buy", "sell"}
            ):
                raise StatementCrosscheckError("statement_identity_or_side_mismatch")
            deal_id = _count(row["deal_id"], "deal_id", lower=1, upper=2_147_483_647)
            if deal_id in exported:
                raise StatementCrosscheckError("statement_deal_repeated")
            exported[deal_id] = {
                "position_id": _count(row["position_id"], "position_id",
                                      lower=1, upper=2_147_483_647),
                "closed_utc": _timestamp(row["closed_utc"], datetime.now(timezone.utc)),
                "side": row["side"], "symbol": row["symbol"],
                "label": row["label"], "currency": row["currency"],
                "lots": _money(row["lots"], "lots"),
                **{key: _money(row[key], key) for key in
                   ("gross", "commission", "swap", "net", "balance_after")},
            }
    except (DemoAuditError, csv.Error, ValueError) as exc:
        if isinstance(exc, StatementCrosscheckError):
            raise
        raise StatementCrosscheckError("statement_data_invalid") from exc
    try:
        source = _parse_log_deals(source_text, parsed)
    except DemoAuditError as exc:
        raise StatementCrosscheckError("demo_log_deal_data_invalid") from exc
    if source.keys() != exported.keys():
        raise StatementCrosscheckError("statement_missing_or_extra_deal_ids")

    for deal_id, expected in source.items():
        actual = exported[deal_id]
        for key in ("position_id", "side", "symbol", "label", "currency"):
            if actual[key] != expected[key]:
                raise StatementCrosscheckError("statement_trade_identity_mismatch")
        if abs(actual["closed_utc"] - expected["closed_utc"]) > TIME_TOLERANCE:
            raise StatementCrosscheckError("statement_trade_timestamp_mismatch")
        if abs(actual["lots"] - expected["lots"]) > LOTS_TOLERANCE:
            raise StatementCrosscheckError("statement_trade_quantity_mismatch")
        for key in ("gross", "commission", "swap", "net", "balance_after"):
            if abs(actual[key] - expected[key]) > MONEY_TOLERANCE:
                raise StatementCrosscheckError("statement_trade_financial_mismatch_" + key)

    log_net = Decimal(parsed["broker_reported_net_account_currency"])
    statement_net = sum((row["net"] for row in exported.values()), Decimal(0))
    if abs(log_net - statement_net) > MONEY_TOLERANCE:
        raise StatementCrosscheckError("statement_net_total_mismatch")
    return {
        "schema": SCHEMA,
        "account_alias": parsed["alias"],
        "account_currency": parsed["account_currency"],
        "symbol": parsed["symbol"],
        "mode": "demo",
        "matched_closing_deals": len(source),
        "missing_or_extra_deals": 0,
        "statement_net_demo_only": str(statement_net),
        "bot_log_net_demo_only": str(log_net),
        "log_sha256": hashlib.sha256(log_bytes).hexdigest(),
        "statement_sha256": digest,
        "statement_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "statement_source_claim": manifest["source"],
        "two_exports_matched_within_money_tolerance": True,
        "exports_independent_of_broker_platform": False,
        "source_cryptographically_authenticated_to_broker": False,
        "separate_authenticated_account_statement_verified": False,
        "deposit_withdrawal_conversion_reconciled": False,
        "account_is_live": False,
        "real_income_verified": False,
        "live_order_execution_enabled": False,
    }


def compare_private_files(log: Path, statement: Path, manifest: Path) -> dict:
    return compare_bytes(
        _private_bytes(log, MAX_BYTES),
        _private_bytes(statement, MAX_STATEMENT_BYTES),
        _private_bytes(manifest, MAX_MANIFEST_BYTES),
    )


def main():
    parser = argparse.ArgumentParser(
        description="Reconcile two private cTrader DEMO extracts by closing-deal ID; no orders"
    )
    parser.add_argument("--demo-log", type=Path, required=True)
    parser.add_argument("--normalized-statement", type=Path, required=True)
    parser.add_argument("--statement-manifest", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = compare_private_files(
            args.demo_log, args.normalized_statement, args.statement_manifest,
        )
    except (StatementCrosscheckError, OSError) as exc:
        parser.exit(2, f"MOJTRADE_STATEMENT_MATCH_BLOCKED: {exc}\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
