#!/usr/bin/env python3
"""Unified OFFLINE MojTrade research chain: invention → risk → execution twin.

No API, live/demo order, broker credentials, public signals or network. Inputs
are externally asserted data, not verified market truth. Reports are research
artifacts only; results never authorize an order or demonstrate profits.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import mojtrade_execution_twin as twin
import mojtrade_portfolio_risk_gate as risk
import mojtrade_replay_reconciliation as reconciliation
import mojtrade_research_handoff as handoff
import mojtrade_strategy_foundry as foundry


SCHEMA = "mojtrade.unified-shadow.v1"
SHADOW_KEYS = {"market_bars", "execution_book", "risk_context", "hypothetical_size",
               "candidate_id", "seed", "trials", "research_fee_bps"}
SIZE_KEYS = {"quantity", "unit_value_cash_per_price_point", "execution_buffer_cash",
             "client_latency_ms", "network_latency_ms", "venue_latency_ms",
             "ttl_ms", "time_in_force", "max_adverse_slippage_bps",
             "commission_bps_per_side"}


class ShadowReject(ValueError):
    """A mandatory boundary of the unified research workflow did not hold."""


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _record_report(dataset, journal, seed, trials, cost_bps):
    normalized = foundry.validate_dataset(dataset)
    input_hash = foundry.digest(normalized)
    if journal.exists() or journal.is_symlink():
        rows = foundry.read_private_registry(journal)
    else:
        rows = []
    for row in rows:
        prior = row["report"]
        if (prior["dataset_digest"] == input_hash and prior["seed"] == seed and
                prior["max_trials"] == trials and prior["cost_bps_per_side"] == cost_bps):
            # Reuse historical exactly matching invention, not new duplicates.
            return prior, foundry.append_private_registry(prior, journal)
    already_seen = {
        birth["structure_signature"]
        for row in rows
        if row["report"]["symbol"] == normalized["symbol"] and
        row["report"]["interval_seconds"] == normalized["interval_seconds"]
        for birth in row["report"]["birth_certificates"]
    }
    report = foundry.invent(normalized, seed=seed, max_trials=trials,
                            cost_bps=cost_bps, existing_signatures=already_seen)
    receipt = foundry.append_private_registry(report, journal)
    return report, receipt


def run_shadow(request, private_dir, *, now=None):
    if not isinstance(request, dict) or set(request) != SHADOW_KEYS:
        raise ShadowReject("shadow_schema_invalid")
    if (not isinstance(request["execution_book"], dict) or
            set(request["execution_book"]) != {"schema", "source_id", "symbol", "events"}):
        raise ShadowReject("execution_book_schema_invalid")
    if (not isinstance(request["hypothetical_size"], dict) or
            set(request["hypothetical_size"]) != SIZE_KEYS):
        raise ShadowReject("hypothetical_size_schema_invalid")
    if not isinstance(request["risk_context"], dict) or set(request["risk_context"]) != handoff.RISK_CONTEXT_KEYS:
        raise ShadowReject("risk_context_schema_invalid")
    if request["risk_context"].get("account_mode") != "DEMO":
        raise ShadowReject("non_demo_account_blocked")
    normalized = foundry.validate_dataset(request["market_bars"])
    candles = normalized["bars"]
    book = request["execution_book"]
    if book["schema"] != twin.SCHEMA:
        raise ShadowReject("execution_book_schema_version")
    mapped = handoff.RESEARCH_SYMBOL_MAP.get(normalized["symbol"])
    if mapped is None or book["symbol"] != mapped:
        raise ShadowReject("cross_source_symbol_mismatch")
    events = twin._events(book["events"])
    latest_observed = datetime.fromisoformat(candles[-1]["available_at"])
    decision = events[0]["t"]
    if events[0]["available_at"] > decision:
        raise ShadowReject("reference_quote_not_yet_observable_at_decision")
    if not 0 <= (decision - latest_observed).total_seconds() <= 5:
        raise ShadowReject("closed_bar_stale_or_unavailable")
    snapshot_time = risk._utc(request["risk_context"]["snapshot_at"])
    quote_time = risk._utc(request["risk_context"]["quote_at"])
    if snapshot_time != decision or quote_time != decision:
        raise ShadowReject("account_quote_not_bound_to_first_book_event")
    now = now or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ShadowReject("now_not_utc")
    now = now.astimezone(timezone.utc)
    if abs((now - decision).total_seconds()) > 1:
        raise ShadowReject("non_current_replay_context")
    best_bid, best_ask = events[0]["bids"][0]["price"], events[0]["asks"][0]["price"]
    last_close = Decimal(str(candles[-1]["close"]))
    if not best_bid <= last_close <= best_ask:
        raise ShadowReject("last_candle_close_outside_quote_spread")
    selected_id = request["candidate_id"]
    if selected_id is not None and (not isinstance(selected_id, str) or not selected_id.startswith("MTF-")):
        raise ShadowReject("candidate_id_invalid")
    parent = Path(private_dir)
    if not parent.exists() or not parent.is_dir() or parent.is_symlink():
        raise ShadowReject("private_research_dir_required")
    # Persistent report and risk state are owned by their respective modules,
    # each enforcing 0700 directory / 0600 file and locking.
    journal = parent / "unified-foundry-registry.jsonl"
    report, birth_receipt = _record_report(request["market_bars"], journal,
                                           request["seed"], request["trials"],
                                           request["research_fee_bps"])
    live_signals = [b for b in report["birth_certificates"] if
                    foundry.signal(b["program"], candles, len(candles) - 1)]
    if selected_id:
        live_signals = [b for b in live_signals if b["strategy_id"] == selected_id]
    if not live_signals:
        return _no_signal(report, birth_receipt)
    # Candidate order in the training-only birth ledger is deterministic and
    # does not choose the highest (reused) holdout profit score.
    cert = live_signals[0]
    side = cert["program"]["side"]
    entry = best_ask if side == "BUY" else best_bid
    distance = max(Decimal(str(foundry._atr(candles, len(candles) - 1))) *
                   Decimal(str(cert["program"]["stop_atr"])), entry * Decimal("0.0001"))
    stop = (entry - distance if side == "BUY" else entry + distance).quantize(
        Decimal("0.00000001"))
    if stop <= 0 or (side == "BUY" and stop >= entry) or (side == "SELL" and stop <= entry):
        raise ShadowReject("computed_stop_nonpositive")
    size = request["hypothetical_size"]
    trade = {"quantity": size["quantity"], "entry": str(entry), "stop": str(stop),
             "unit_value_cash_per_price_point": size["unit_value_cash_per_price_point"],
             "execution_buffer_cash": size["execution_buffer_cash"]}
    intent_fields = {
        "strategy_id": cert["strategy_id"], "side": side,
        "quantity": size["quantity"], "decision_at": decision.isoformat(),
        "client_latency_ms": size["client_latency_ms"],
        "network_latency_ms": size["network_latency_ms"],
        "venue_latency_ms": size["venue_latency_ms"],
        "ttl_ms": size["ttl_ms"], "time_in_force": size["time_in_force"],
        "max_adverse_slippage_bps": size["max_adverse_slippage_bps"],
        "commission_bps_per_side": size["commission_bps_per_side"],
    }
    # Preflight the entire synthetic execution contract BEFORE committing a
    # durable research risk reservation. Otherwise an invalid IOC/FOK request
    # could strand budget despite never being replayable.
    try:
        twin.replay({**book, "hypothetical_intents": [
            {"intent_id": "SHADOW-PREFLIGHT", **intent_fields}]})
    except twin.TwinReject as exc:
        raise ShadowReject("execution_twin_preflight:" + str(exc)) from exc
    try:
        risk_result = handoff.handoff(report, cert["strategy_id"],
                                     request["risk_context"], trade,
                                     parent / "unified-portfolio-risk.sqlite3", now=now)
    except handoff.HandoffReject as exc:
        raise ShadowReject("risk_handoff:" + str(exc)) from exc
    risk_decision = risk_result["risk_response"]["decisions"][0]
    if risk_decision["status"] != "RESEARCH_SLOT_RESERVED":
        return _result(report, birth_receipt, cert, risk_result, None, None,
                       "RESEARCH_RISK_REFUSED")
    # No order can originate from this code. It hands a pre-specified
    # HYPOTHETICAL intent to a no-network event replay.
    scenario = {**book, "hypothetical_intents": [
        {"intent_id": risk_decision["request_id"], **intent_fields}]}
    twin_result = twin.replay(scenario)
    try:
        reconciled = reconciliation.record_receipt(
            risk_result, twin_result, parent / "unified-replay-reconciliation.jsonl")
    except reconciliation.ReconciliationReject as exc:
        raise ShadowReject("research_reconciliation_failed_reserved_slot_not_released:" + str(exc)) from exc
    return _result(report, birth_receipt, cert, risk_result, twin_result, reconciled,
                   "RESEARCH_EXECUTION_REPLAYED")


def _result(report, birth_receipt, cert, risk_result, twin_result, reconciled, status):
    result = {"schema": SCHEMA, "mode": "RESEARCH_ONLY", "status": status,
              "execution": "disabled", "real_orders": 0, "public_signals": 0,
              "broker_eligible": False, "foundry_report_sha256": report["report_sha256"],
              "foundry_registry_sequence": birth_receipt["sequence"],
              "strategy_id": cert["strategy_id"], "strategy_state": cert["state"],
              "risk_handoff": risk_result, "execution_twin": twin_result,
              "reconciliation": reconciled,
              "limitations": ["input market and account data not independently authenticated",
                              "no independent financial edge proven",
                              "historical research slot never an order permission"]}
    result["report_sha256"] = _hash(result)
    return result


def _no_signal(report, receipt):
    result = {"schema": SCHEMA, "mode": "RESEARCH_ONLY",
              "status": "NO_CURRENT_RESEARCH_SIGNAL", "execution": "disabled",
              "real_orders": 0, "public_signals": 0, "broker_eligible": False,
              "foundry_report_sha256": report["report_sha256"],
              "foundry_registry_sequence": receipt["sequence"],
              "strategy_id": None, "strategy_state": None,
              "risk_handoff": None, "execution_twin": None, "reconciliation": None,
              "limitations": ["no eligible closed-bar signal",
                              "strategy not independently statistically validated"]}
    result["report_sha256"] = _hash(result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Unified offline MojTrade research shadow")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--private-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    path = args.input
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 3_000_000:
        raise ShadowReject("input_invalid_or_too_large")
    data = json.loads(path.read_text(encoding="utf-8"))
    print(json.dumps(run_shadow(data, args.private_dir), sort_keys=True,
                     ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
