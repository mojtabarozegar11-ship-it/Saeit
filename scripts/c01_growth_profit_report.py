#!/usr/bin/env python3
"""C-01: private, read-only, evidence-bound two-market cash-funnel reconciliation.

This is a *report of supplied records*, never a bank/payment/GA4 verification.
No network, Django import, database write, or live-site action.
"""
import argparse
import csv
import hashlib
import json
import re
import sys
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

FIELDS = (
    "event_id", "occurred_at", "market", "unit_id", "channel", "campaign_id",
    "event_type", "order_id", "currency", "amount", "quantity", "evidence_ref",
)
MARKETS = {"ZM_IR", "MPW_GLOBAL"}
EVENTS = {"visit", "lead", "paid_order", "refund", "cogs", "ad_spend", "other_cost"}
MONEY_EVENTS = EVENTS - {"visit", "lead"}
D = Decimal
CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$")
MONEY = re.compile(r"^(?:0|[1-9]\d{0,17})(?:\.\d{1,8})?$")


class InvalidEvidence(ValueError):
    pass


def decimal_text(value):
    return format(value, "f")


def ratio(num, den):
    return decimal_text((num / den).quantize(D("0.0001"))) if den else None


def _identifier(value, field, *, required=True):
    if not value and not required:
        return value
    if not CODE.fullmatch(value):
        raise InvalidEvidence(f"invalid {field} (no personal identifiers, spaces or URLs)")
    return value


def _read(path):
    p = Path(path)
    if p.is_symlink() or not p.is_file():
        raise InvalidEvidence("input must be an existing regular file, not a symlink")
    if p.stat().st_size > 25 * 1024 * 1024:
        raise InvalidEvidence("input exceeds 25 MiB bound")
    raw = p.read_bytes()
    if b"\x00" in raw:
        raise InvalidEvidence("NUL bytes in input")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise InvalidEvidence("input must be UTF-8") from exc
    rows = csv.DictReader(text.splitlines())
    if rows.fieldnames is None or tuple(rows.fieldnames) != FIELDS:
        raise InvalidEvidence("CSV must have exactly the documented header; PII columns prohibited")
    return rows, hashlib.sha256(raw).hexdigest()


def reconcile(path, *, as_of):
    """Fail closed on ambiguous financial evidence; output only aggregated groups."""
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", as_of):
            raise ValueError("not YYYY-MM-DD")
        cutoff = date.fromisoformat(as_of)
    except ValueError as exc:
        raise InvalidEvidence("as_of must be YYYY-MM-DD") from exc
    rows, digest = _read(path)
    seen = set()
    groups = defaultdict(lambda: {"visits": 0, "leads": 0, "orders": {},
                                  "refunds": defaultdict(D), "cogs": {},
                                  "ad_spend": D(0), "other_cost": D(0),
                                  "ad_spend_evidence": False,
                                  "other_cost_evidence": False, "events": 0})
    earliest = latest = None
    count = 0
    for line, row in enumerate(rows, start=2):
        count += 1
        if count > 200000:
            raise InvalidEvidence("event row cap exceeded")
        if None in row or any(v is None for v in row.values()):
            raise InvalidEvidence(f"line {line}: malformed CSV")
        try:
            eid = _identifier(row["event_id"], "event_id")
            if eid in seen:
                raise InvalidEvidence("duplicate event_id")
            seen.add(eid)
            timestamp = datetime.fromisoformat(row["occurred_at"].replace("Z", "+00:00"))
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise InvalidEvidence("timestamp must include timezone offset")
            event_day = timestamp.date()
            if event_day > cutoff:
                raise InvalidEvidence("future event relative to as_of")
            market = row["market"]
            if market not in MARKETS:
                raise InvalidEvidence("unknown market")
            unit = _identifier(row["unit_id"], "unit_id")
            channel = _identifier(row["channel"], "channel")
            campaign = _identifier(row["campaign_id"], "campaign_id")
            currency = _identifier(row["currency"], "currency")
            if currency not in {"IRR", "USD", "CAD", "TRX", "USDT", "ETH"}:
                raise InvalidEvidence("currency not supported; no FX conversions are inferred")
            kind = row["event_type"]
            if kind not in EVENTS:
                raise InvalidEvidence("unsupported event_type")
            order_id = _identifier(row["order_id"], "order_id", required=False)
            ref = _identifier(row["evidence_ref"], "evidence_ref", required=False)
            if not row["quantity"].isdigit() or not 0 < int(row["quantity"]) <= 1000000:
                raise InvalidEvidence("quantity must be a positive bounded integer")
            qty = int(row["quantity"])
            if kind in MONEY_EVENTS:
                if not MONEY.fullmatch(row["amount"]):
                    raise InvalidEvidence("money must be a nonnegative decimal, no scientific notation")
                amount = D(row["amount"])
                if not ref:
                    raise InvalidEvidence("financial event missing evidence_ref")
                if qty != 1:
                    raise InvalidEvidence("financial event quantity must be 1")
                if kind in {"paid_order", "refund"} and amount <= 0:
                    raise InvalidEvidence("paid_order/refund must be positive")
            else:
                if row["amount"] != "0" or order_id:
                    raise InvalidEvidence("visit/lead must have amount 0 and no order_id")
                amount = D(0)
            if kind in {"paid_order", "refund", "cogs"}:
                if not order_id:
                    raise InvalidEvidence("order-linked event requires order_id")
            elif order_id:
                raise InvalidEvidence("only order-linked events may have order_id")
            g = groups[(market, unit, channel, campaign, currency)]
            g["events"] += 1
            if kind == "visit":
                g["visits"] += qty
            elif kind == "lead":
                g["leads"] += qty
            elif kind == "paid_order":
                if order_id in g["orders"]:
                    raise InvalidEvidence("duplicate paid_order for order_id")
                g["orders"][order_id] = amount
            elif kind == "refund":
                g["refunds"][order_id] += amount
            elif kind == "cogs":
                if order_id in g["cogs"]:
                    raise InvalidEvidence("duplicate COGS for order_id")
                g["cogs"][order_id] = amount
            elif kind == "ad_spend":
                g["ad_spend"] += amount
                g["ad_spend_evidence"] = True
            else:
                g["other_cost"] += amount
                g["other_cost_evidence"] = True
            earliest = min(earliest, event_day) if earliest else event_day
            latest = max(latest, event_day) if latest else event_day
        except (ValueError, InvalidOperation) as exc:
            raise InvalidEvidence(f"line {line}: {exc}") from exc
    if not count:
        raise InvalidEvidence("no events: cannot infer zero revenue or spend")
    output = []
    for key in sorted(groups):
        g = groups[key]
        orders = g["orders"]
        if any(k not in orders for k in g["refunds"]):
            raise InvalidEvidence("refund without matching paid order in same market/unit/channel/campaign/currency")
        if any(g["refunds"][k] > v for k, v in orders.items()):
            raise InvalidEvidence("refund exceeds recorded order amount")
        if any(k not in orders for k in g["cogs"]):
            raise InvalidEvidence("COGS without matching paid order")
        paid = sum(orders.values(), D(0))
        refunds = sum(g["refunds"].values(), D(0))
        net = paid - refunds
        cogs_complete = set(g["cogs"]) == set(orders)
        costs_complete = cogs_complete and g["ad_spend_evidence"] and g["other_cost_evidence"]
        gross = net - sum(g["cogs"].values(), D(0)) if cogs_complete else None
        contribution = gross - g["ad_spend"] - g["other_cost"] if costs_complete else None
        output.append({
            "market": key[0], "unit_id": key[1], "channel": key[2],
            "campaign_id": key[3], "currency": key[4], "event_count": g["events"],
            "visits_recorded": g["visits"], "leads_recorded": g["leads"],
            "paid_orders_recorded": len(orders),
            "gross_receipts_recorded": decimal_text(paid),
            "refunds_recorded": decimal_text(refunds),
            "net_receipts_recorded": decimal_text(net),
            "ad_spend_recorded": decimal_text(g["ad_spend"]) if g["ad_spend_evidence"] else None,
            "other_cost_recorded": decimal_text(g["other_cost"]) if g["other_cost_evidence"] else None,
            "cogs_coverage_complete": cogs_complete,
            "cost_evidence_complete": costs_complete,
            "gross_margin_recorded": decimal_text(gross) if gross is not None else None,
            "cash_contribution_recorded": decimal_text(contribution) if contribution is not None else None,
            "order_conversion_per_visit": ratio(D(len(orders)), D(g["visits"])),
            "lead_conversion_per_visit": ratio(D(g["leads"]), D(g["visits"])),
            "roas_recorded": ratio(net, g["ad_spend"]) if g["ad_spend_evidence"] else None,
            "cost_per_paid_order": ratio(g["ad_spend"], D(len(orders))) if g["ad_spend_evidence"] else None,
            "cac": None, "ltv": None,
        })
    return {
        "schema": "c01-growth-profit-report/v1", "as_of": as_of,
        "first_event_date": earliest.isoformat(), "last_event_date": latest.isoformat(),
        "source_sha256": digest, "source_event_count": count,
        "verification_level": "SUPPLIED_RECORDS_ONLY_NOT_BANK_VERIFIED",
        "attribution_note": "Recorded channel tags are descriptive, not causal attribution; no FX mixing.",
        "cost_note": "Missing explicit COGS/ad spend/other cost evidence yields null profitability, not zero.",
        "groups": output,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="private local evidence CSV")
    parser.add_argument("--as-of", required=True, help="YYYY-MM-DD reporting cutoff")
    args = parser.parse_args(argv)
    try:
        result = reconcile(args.input, as_of=args.as_of)
    except (InvalidEvidence, OSError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
