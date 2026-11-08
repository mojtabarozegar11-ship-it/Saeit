"""Offline, read-only comparison of C15 receipts with a broker export.

The user-provided CSV is evidence to check, NOT an authenticated broker feed.
This tool cannot enable trading or establish commercial readiness.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re


ACCOUNT_RE = re.compile(r"^[0-9]{1,20}$")
POSITION_RE = re.compile(r"^[1-9][0-9]{0,19}$")
REQUEST_RE = re.compile(r"^[0-9a-f]{32}$")
LABELS = ("MojTrade-OMEGA-X-DEMO", "MojTrade-Demo-QuantumScalp-v2-")
FIELDS = frozenset({"account", "position_id", "label", "state",
                    "opened_utc", "stop_loss", "take_profit"})


class EvidenceError(ValueError):
    """Invalid or ambiguous evidence; never silently skip affected records."""


def _positive_number(raw: str) -> bool:
    try:
        value = Decimal(raw)
    except (InvalidOperation, TypeError):
        return False
    return value.is_finite() and value > 0


def _valid_day(day: str) -> bool:
    try:
        return len(day) == 10 and datetime.strptime(day, "%Y-%m-%d").date().isoformat() == day
    except (ValueError, TypeError):
        return False


def _is_mojtrade(label: str) -> bool:
    return label == LABELS[0] or label.startswith(LABELS[1])


def parse_broker_csv(stream, *, account: str, day: str) -> dict[str, dict[str, str]]:
    """Read an explicitly normalized CSV, requiring all rows to identify the account."""
    if not ACCOUNT_RE.fullmatch(account) or not _valid_day(day):
        raise EvidenceError("invalid_scope")
    reader = csv.DictReader(stream, strict=True)
    if not reader.fieldnames or set(reader.fieldnames) != FIELDS:
        raise EvidenceError("invalid_broker_columns")
    positions: dict[str, dict[str, str]] = {}
    for line, record in enumerate(reader, start=2):
        if None in record or any(value is None for value in record.values()):
            raise EvidenceError(f"malformed_broker_row:{line}")
        if record["account"] != account:
            raise EvidenceError(f"broker_account_mismatch:{line}")
        position = record["position_id"]
        if not POSITION_RE.fullmatch(position):
            raise EvidenceError(f"invalid_broker_position:{line}")
        if position in positions:
            raise EvidenceError(f"duplicate_broker_position:{line}")
        if record["state"] not in ("open", "closed"):
            raise EvidenceError(f"invalid_broker_state:{line}")
        try:
            opened = datetime.fromisoformat(record["opened_utc"].replace("Z", "+00:00"))
        except ValueError as exc:
            raise EvidenceError(f"invalid_broker_timestamp:{line}") from exc
        if opened.tzinfo is None or opened.astimezone(timezone.utc).date().isoformat() != day:
            raise EvidenceError(f"broker_day_mismatch:{line}")
        if not record["label"]:
            raise EvidenceError(f"missing_broker_label:{line}")
        positions[position] = record
    return positions


def reconcile(receipt_report: dict, broker_positions: dict[str, dict[str, str]],
              *, account: str, day: str) -> dict:
    """Compare receipt IDs and broker-reported position IDs without mutating either source."""
    if not ACCOUNT_RE.fullmatch(account) or not _valid_day(day):
        raise EvidenceError("invalid_scope")
    if not isinstance(receipt_report, dict) or (receipt_report.get("account") != account or
            receipt_report.get("day") != day or
            receipt_report.get("broker_verified") is not False or
            not isinstance(receipt_report.get("truncated"), bool) or
            not isinstance(receipt_report.get("receipts"), list)):
        raise EvidenceError("invalid_receipt_report")
    issues: list[str] = []
    if receipt_report["truncated"]:
        issues.append("truncated_receipts")
    if not receipt_report["receipts"]:
        issues.append("no_receipts")
    seen_requests: set[str] = set()
    claimed_positions: set[str] = set()
    matched = 0
    for row in receipt_report["receipts"]:
        if not isinstance(row, dict):
            raise EvidenceError("invalid_receipt_row")
        request_id = row.get("request_id", "")
        state = row.get("state")
        position_id = row.get("reported_broker_position_id")
        if (not isinstance(request_id, str) or not REQUEST_RE.fullmatch(request_id) or
                request_id in seen_requests or state not in ("reserved", "committed", "cancelled")):
            raise EvidenceError("invalid_or_duplicate_receipt")
        seen_requests.add(request_id)
        if state != "committed":
            if position_id is not None:
                issues.append(f"unexpected_position_for_{state}:{request_id}")
            if state == "reserved":
                issues.append(f"unsettled_reservation:{request_id}")
            continue
        if not isinstance(position_id, str) or not POSITION_RE.fullmatch(position_id):
            issues.append(f"missing_broker_id:{request_id}")
            continue
        if position_id in claimed_positions:
            issues.append(f"duplicate_claimed_position:{position_id}")
            continue
        claimed_positions.add(position_id)
        broker = broker_positions.get(position_id)
        if broker is None:
            issues.append(f"position_missing_from_broker_evidence:{position_id}")
            continue
        if not _is_mojtrade(broker["label"]):
            issues.append(f"unexpected_strategy_label:{position_id}")
            continue
        if not _positive_number(broker["stop_loss"]) or not _positive_number(broker["take_profit"]):
            issues.append(f"protection_not_evidenced:{position_id}")
            continue
        matched += 1
    for position_id, broker in broker_positions.items():
        if _is_mojtrade(broker["label"]) and position_id not in claimed_positions:
            issues.append(f"orphan_mojtrade_position:{position_id}")
    if not claimed_positions:
        issues.append("no_committed_trade_evidence")
    return {
        "account": account,
        "day": day,
        "receipt_count": len(seen_requests),
        "matched_fills": matched,
        "issues": sorted(issues),
        "evidence_consistent": not issues,
        "broker_source_authenticated": False,
        "commercial_readiness": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only MojTrade receipt cross-check")
    parser.add_argument("--receipts", type=Path, required=True)
    parser.add_argument("--broker-csv", type=Path, required=True)
    parser.add_argument("--account", required=True)
    parser.add_argument("--day", required=True)
    args = parser.parse_args()
    try:
        with args.receipts.open("r", encoding="utf-8") as source:
            report = json.load(source)
        with args.broker_csv.open("r", encoding="utf-8-sig", newline="") as source:
            broker = parse_broker_csv(source, account=args.account, day=args.day)
        result = reconcile(report, broker, account=args.account, day=args.day)
    except (OSError, ValueError, csv.Error) as exc:
        # Never print sensitive contents of a malformed broker export.
        print(json.dumps({"evidence_consistent": False,
                          "broker_source_authenticated": False,
                          "commercial_readiness": False,
                          "error": type(exc).__name__}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result["evidence_consistent"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
