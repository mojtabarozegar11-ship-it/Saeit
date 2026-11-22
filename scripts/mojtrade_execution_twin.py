#!/usr/bin/env python3
"""Offline quote-depth execution twin for hypothetical short-horizon intents.

No broker client, market data network, financial account, order endpoint, or
public signal. All prices and available sizes are caller-provided and untrusted.
It simulates an IOC/FOK execution against limited visible depth at the first
eligible event after modeled latency; it does not predict exchange execution.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path


SCHEMA = "mojtrade.execution-twin.research.v1"
MAX_BYTES = 1_500_000
MAX_EVENTS = 4000
MAX_INTENTS = 128
MAX_LEVELS = 5
D = Decimal


class TwinReject(ValueError):
    """Untrustworthy scenario or unbounded research replay."""


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False)


def _digest(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _decimal(value, key, *, positive=False, nonnegative=False, maximum="1e12"):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise TwinReject(key + "_type")
    if isinstance(value, str) and len(value) > 32:
        raise TwinReject(key + "_too_long")
    try:
        result = D(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise TwinReject(key + "_invalid") from exc
    if (not result.is_finite() or result > D(maximum) or
            result.as_tuple().exponent < -12):
        raise TwinReject(key + "_unbounded")
    if positive and result <= 0:
        raise TwinReject(key + "_must_be_positive")
    if nonnegative and result < 0:
        raise TwinReject(key + "_must_be_nonnegative")
    return result


def _name(value, key, max_length=64):
    if (not isinstance(value, str) or not 1 <= len(value) <= max_length or
            not value.isascii() or not all(ch.isalnum() or ch in "._-/" for ch in value)):
        raise TwinReject(key + "_invalid")
    return value


def _time(value):
    if not isinstance(value, str) or len(value) > 40:
        raise TwinReject("timestamp_invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TwinReject("timestamp_parse") from exc
    if parsed.tzinfo is None:
        raise TwinReject("timestamp_not_utc")
    return parsed.astimezone(timezone.utc)


def _levels(value, side):
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_LEVELS:
        raise TwinReject("book_levels_invalid")
    result = []
    previous = None
    for raw in value:
        if not isinstance(raw, dict) or set(raw) != {"price", "size"}:
            raise TwinReject("level_schema")
        price = _decimal(raw["price"], "level_price", positive=True)
        size = _decimal(raw["size"], "level_size", positive=True)
        if previous is not None:
            if (side == "BID" and price >= previous) or (side == "ASK" and price <= previous):
                raise TwinReject("book_depth_not_price_sorted")
        previous = price
        result.append({"price": price, "size": size})
    return result


def _events(raw):
    if not isinstance(raw, list) or not 2 <= len(raw) <= MAX_EVENTS:
        raise TwinReject("event_count")
    events = []
    prev = None
    for index, item in enumerate(raw):
        if not isinstance(item, dict) or set(item) != {
                "t", "available_at", "venue_status", "bids", "asks"}:
            raise TwinReject("event_schema")
        at, available = _time(item["t"]), _time(item["available_at"])
        if prev is not None and at <= prev:
            raise TwinReject("event_duplicate_or_time_reversal")
        if available < at or available > at + timedelta(seconds=5):
            raise TwinReject("observation_availability_invalid")
        prev = at
        if item["venue_status"] not in ("OPEN", "HALT"):
            raise TwinReject("venue_status_invalid")
        bids = _levels(item["bids"], "BID")
        asks = _levels(item["asks"], "ASK")
        if bids[0]["price"] >= asks[0]["price"]:
            raise TwinReject("crossed_or_locked_spread")
        events.append({"index": index, "t": at, "available_at": available,
                       "status": item["venue_status"], "bids": bids, "asks": asks})
    if (events[-1]["t"] - events[0]["t"]).total_seconds() > 3600:
        raise TwinReject("event_horizon_exceeds_one_hour")
    return events


def _intents(raw, events):
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_INTENTS:
        raise TwinReject("intent_count")
    intents = []
    seen = set()
    for item in raw:
        expected = {"intent_id", "strategy_id", "side", "quantity", "decision_at",
                    "client_latency_ms", "network_latency_ms", "venue_latency_ms",
                    "ttl_ms", "time_in_force", "max_adverse_slippage_bps",
                    "commission_bps_per_side"}
        if not isinstance(item, dict) or set(item) != expected:
            raise TwinReject("intent_schema")
        intent_id, strategy = _name(item["intent_id"], "intent_id"), _name(
            item["strategy_id"], "strategy_id")
        if intent_id in seen:
            raise TwinReject("duplicate_intent_id")
        seen.add(intent_id)
        side, tif = item["side"], item["time_in_force"]
        if side not in ("BUY", "SELL") or tif not in ("IOC", "FOK"):
            raise TwinReject("side_or_tif_unsupported")
        quantity = _decimal(item["quantity"], "quantity", positive=True)
        commission = _decimal(item["commission_bps_per_side"], "commission", nonnegative=True,
                              maximum="500")
        slip = _decimal(item["max_adverse_slippage_bps"], "slippage", nonnegative=True,
                        maximum="500")
        latencies = []
        for k in ("client_latency_ms", "network_latency_ms", "venue_latency_ms", "ttl_ms"):
            value = item[k]
            if type(value) is not int or value < 0 or value > 60_000 or (k == "ttl_ms" and value == 0):
                raise TwinReject(k + "_invalid")
            latencies.append(value)
        decision = _time(item["decision_at"])
        if decision < events[0]["t"] or decision > events[-1]["t"]:
            raise TwinReject("decision_outside_recorded_market")
        # Ref quote must have actually become observable by decision time.
        observed = [e for e in events if e["available_at"] <= decision]
        if not observed:
            raise TwinReject("no_observable_reference_quote")
        reference = observed[-1]["asks"][0]["price"] if side == "BUY" else observed[-1]["bids"][0]["price"]
        arrival = decision + timedelta(milliseconds=sum(latencies[:3]))
        deadline = arrival + timedelta(milliseconds=latencies[3])
        intents.append({"id": intent_id, "strategy": strategy, "side": side,
                        "tif": tif, "quantity": quantity, "decision_at": decision,
                        "arrival": arrival, "deadline": deadline, "reference": reference,
                        "max_slip": slip, "commission": commission,
                        "input_sha256": _digest(item)})
    return intents


def _eligible_levels(intent, event):
    ladder = event["asks"] if intent["side"] == "BUY" else event["bids"]
    side = intent["side"]
    bound = intent["reference"] * (
        (1 + intent["max_slip"] / D(10_000)) if side == "BUY"
        else (1 - intent["max_slip"] / D(10_000)))
    return [level for level in ladder if
            (level["price"] <= bound if side == "BUY" else level["price"] >= bound)]


def _fill(intent, event):
    levels = _eligible_levels(intent, event)
    wanted = intent["quantity"]
    available = sum((level["size"] for level in levels), D(0))
    if intent["tif"] == "FOK" and available < wanted:
        return [], "FOK_DEPTH_INSUFFICIENT"
    fills = []
    left = wanted
    for level in levels:
        amount = min(left, level["size"])
        if amount <= 0:
            continue
        level["size"] -= amount
        left -= amount
        fills.append({"size": amount, "price": level["price"]})
        if left == 0:
            break
    if not fills:
        return [], "SLIPPAGE_CAP_OR_NO_LIQUIDITY"
    return fills, ("FILLED" if left == 0 else "PARTIAL_CANCELLED")


def replay(scenario):
    if not isinstance(scenario, dict) or set(scenario) != {
            "schema", "source_id", "symbol", "events", "hypothetical_intents"}:
        raise TwinReject("scenario_schema")
    if scenario["schema"] != SCHEMA:
        raise TwinReject("scenario_version")
    source_id = _name(scenario["source_id"], "source_id", 80)
    symbol = _name(scenario["symbol"], "symbol", 32)
    events = _events(scenario["events"])
    intents = _intents(scenario["hypothetical_intents"], events)
    # Ordered by first possible observed venue event, then modeled arrival,
    # then stable ID. Each level's available size is shared across intents.
    remaining = {intent["id"]: intent for intent in intents}
    decisions = {}
    for event in events:
        due = sorted((i for i in remaining.values() if i["arrival"] <= event["t"]),
                     key=lambda i: (i["arrival"], i["id"]))
        for intent in due:
            if event["t"] > intent["deadline"]:
                fills, state = [], "EXPIRED_BEFORE_EXECUTION"
            elif event["status"] == "HALT":
                fills, state = [], "VENUE_HALTED"
            else:
                fills, state = _fill(intent, event)
            decisions[intent["id"]] = (intent, event["index"], fills, state)
            del remaining[intent["id"]]
    for intent in remaining.values():
        decisions[intent["id"]] = (intent, None, [], "NO_EXECUTABLE_EVENT")
    receipts = []
    for intent in intents:
        _, event_idx, fills, state = decisions[intent["id"]]
        filled = sum((f["size"] for f in fills), D(0))
        notional = sum((f["size"] * f["price"] for f in fills), D(0))
        avg = notional / filled if filled else None
        direction = D(1) if intent["side"] == "BUY" else D(-1)
        slip_cash = sum((direction * (f["price"] - intent["reference"]) * f["size"]
                         for f in fills), D(0))
        commission_cash = notional * intent["commission"] / D(10_000)
        partial_fills = [{"size": str(f["size"]), "price": str(f["price"])} for f in fills]
        receipt = {
            "intent_id": intent["id"], "strategy_id": intent["strategy"],
            "input_sha256": intent["input_sha256"], "status": state,
            "decision_at": intent["decision_at"].isoformat(),
            "modeled_arrival_at": intent["arrival"].isoformat(),
            "first_execution_event_index": event_idx,
            "reference_price": str(intent["reference"]),
            "requested_quantity": str(intent["quantity"]),
            "filled_quantity": str(filled),
            "cancelled_quantity": str(intent["quantity"] - filled),
            "average_fill_price": str(avg) if avg is not None else None,
            "partial_fills": partial_fills,
            "signed_slippage_cost_cash": str(slip_cash),
            "commission_cash": str(commission_cash),
            "broker_order_submitted": False,
        }
        receipt["receipt_sha256"] = _digest(receipt)
        receipts.append(receipt)
    result = {
        "schema": SCHEMA, "mode": "RESEARCH_SIMULATION_ONLY",
        "source_id": source_id, "symbol": symbol,
        "scenario_sha256": _digest(scenario),
        "real_orders": 0, "public_signals": 0, "broker_connected": False,
        "hypothetical_intents_evaluated": len(intents), "receipts": receipts,
        "limitations": ["event depth is caller-supplied, not venue-certified",
                        "modeled latency, no observed actual round-trip telemetry",
                        "no hidden liquidity, market impact or queue priority",
                        "no quote-to-trade exchange reconciliation",
                        "not evidence of executable or profitable strategy"],
    }
    result["report_sha256"] = _digest(result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Research-only quote-depth execution replay")
    parser.add_argument("--input", required=True, type=Path)
    args = parser.parse_args(argv)
    path = args.input
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise TwinReject("unsafe_or_oversize_input")
    scenario = json.loads(path.read_text(encoding="utf-8"))
    print(_canonical(replay(scenario)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
