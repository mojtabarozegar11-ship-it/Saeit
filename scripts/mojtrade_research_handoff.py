#!/usr/bin/env python3
"""Research-only handoff from an invented strategy to portfolio risk slots.

This bridge has no brokerage client, order sender, public signal publisher,
network access, paid service, or capability to authorize demo/live trades.
Hash receipts detect ordinary corruption, not an adversary who rewrites data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

try:
    from mojtrade_portfolio_risk_gate import RiskReject, reserve_research_slots
except ImportError:
    # Permit tests to import a local copy without installing a package.
    import importlib.util
    source = Path(__file__).with_name("mojtrade_portfolio_risk_gate.py")
    if not source.is_file():
        raise
    spec = importlib.util.spec_from_file_location("mojtrade_portfolio_risk_gate", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    RiskReject = module.RiskReject
    reserve_research_slots = module.reserve_research_slots


SCHEMA = "mojtrade.foundry-to-risk-handoff.v1"
FOUNDRY_SCHEMA = "mojtrade.strategy-foundry.v1"
RISK_CONTEXT_KEYS = {
    "account_id", "account_mode", "risk_day", "snapshot_at", "quote_at",
    "equity_cash", "day_start_equity_cash", "peak_equity_cash",
    "consecutive_losses", "open_positions",
}
TRADE_KEYS = {
    "quantity", "entry", "stop", "unit_value_cash_per_price_point",
    "execution_buffer_cash",
}
RESEARCH_SYMBOL_MAP = {
    "BTC/USD": "BTCUSD", "ETH/USD": "ETHUSD",
    "EUR/USD": "EURUSD", "GBP/USD": "GBPUSD", "USD/JPY": "USDJPY",
    "XAU/USD": "XAUUSD", "XAG/USD": "XAGUSD",
    "BTCUSD": "BTCUSD", "ETHUSD": "ETHUSD", "EURUSD": "EURUSD",
    "GBPUSD": "GBPUSD", "USDJPY": "USDJPY", "XAUUSD": "XAUUSD",
    "XAGUSD": "XAGUSD",
}


class HandoffReject(ValueError):
    """Invalid strategy provenance or unsupported research-only handoff."""


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def _hash(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _check_hash(item, field):
    if not isinstance(item, dict) or item.get(field) != _hash(
            {k: v for k, v in item.items() if k != field}):
        raise HandoffReject(field + "_invalid")


def _verify_birth_report(report, candidate_id):
    if not isinstance(report, dict):
        raise HandoffReject("foundry_report_invalid")
    if (report.get("schema") != FOUNDRY_SCHEMA or
            report.get("mode") != "RESEARCH_ONLY" or
            report.get("execution") != "disabled" or
            report.get("orders") != 0 or report.get("public_signals") != 0):
        raise HandoffReject("foundry_mode_not_research")
    _check_hash(report, "report_sha256")
    gate = report.get("multiple_testing_gate")
    if (not isinstance(gate, dict) or
            gate.get("status") != "NOT_STATISTICALLY_VALIDATED" or
            gate.get("eligible_for_broker_or_public_signals") is not False):
        raise HandoffReject("foundry_statistical_gate_missing_or_unsafe")
    certs = report.get("birth_certificates")
    if not isinstance(certs, list) or len(certs) > 96:
        raise HandoffReject("foundry_births_invalid")
    if not isinstance(candidate_id, str) or not candidate_id.startswith("MTF-"):
        raise HandoffReject("candidate_id_invalid")
    hits = [cert for cert in certs if isinstance(cert, dict) and
            cert.get("strategy_id") == candidate_id]
    if len(hits) != 1:
        raise HandoffReject("candidate_not_unique_in_report")
    cert = hits[0]
    _check_hash(cert, "receipt_sha256")
    program = cert.get("program")
    if (not isinstance(program, dict) or program.get("side") not in ("BUY", "SELL") or
            not isinstance(program.get("conditions"), list) or
            len(program["conditions"]) < 2):
        raise HandoffReject("candidate_program_invalid")
    if (cert.get("state") != "RESEARCH_ONLY_UNPROVEN" or
            cert.get("broker_eligible") is not False or
            cert.get("execution") != "disabled" or cert.get("orders") != 0 or
            cert.get("data_digest") != report.get("dataset_digest") or
            cert.get("source_id") != report.get("dataset_source_id") or
            cert.get("ast_hash") != _hash(program)):
        raise HandoffReject("candidate_provenance_invalid")
    trial = report.get("trial_ledger")
    if (not isinstance(trial, list) or
            len([t for t in trial if isinstance(t, dict) and
                 t.get("strategy_id") == candidate_id and
                 t.get("state") == "BORN_RESEARCH_ONLY" and
                 t.get("trial") == cert.get("trial_number")]) != 1):
        raise HandoffReject("candidate_trial_ledger_mismatch")
    symbol = RESEARCH_SYMBOL_MAP.get(report.get("symbol"))
    if not symbol:
        raise HandoffReject("unmapped_research_symbol")
    if cert.get("generator_version") != FOUNDRY_SCHEMA:
        raise HandoffReject("candidate_generator_version_mismatch")
    return cert, symbol


def handoff(report, candidate_id, risk_context, trade, db_path, *, now=None):
    """Propose only a research risk slot; never execute any market operation."""
    cert, symbol = _verify_birth_report(report, candidate_id)
    if not isinstance(risk_context, dict) or set(risk_context) != RISK_CONTEXT_KEYS:
        raise HandoffReject("risk_context_schema")
    if risk_context.get("account_mode") != "DEMO":
        raise HandoffReject("non_demo_account_prohibited")
    if not isinstance(trade, dict) or set(trade) != TRADE_KEYS:
        raise HandoffReject("trade_hypothesis_schema")
    if now is not None and (not isinstance(now, datetime) or now.tzinfo is None):
        raise HandoffReject("now_invalid")
    payload = {"report_sha256": report["report_sha256"],
               "birth_receipt_sha256": cert["receipt_sha256"],
               "account_id": risk_context["account_id"],
               "snapshot_at": risk_context["snapshot_at"],
               "quote_at": risk_context["quote_at"]}
    request_id = "MTB-" + _hash(payload)[:24]
    proposal = {"request_id": request_id, "symbol": symbol,
                "strategy_id": cert["strategy_id"],
                "side": cert["program"]["side"], **trade}
    risk_payload = {**risk_context, "proposals": [proposal]}
    # The shared portfolio gate owns *all* risk decisions; the bridge cannot
    # bypass it, raise its frozen limits, or place orders.
    try:
        risk = reserve_research_slots(risk_payload, db_path, now=now)
    except RiskReject as exc:
        raise HandoffReject("shared_risk_gate:" + str(exc)) from exc
    result = {
        "schema": SCHEMA, "mode": "RESEARCH_ONLY",
        "execution": "disabled", "orders": 0, "public_signals": 0,
        "broker_eligible": False, "strategy_id": candidate_id,
        "research_symbol": report["symbol"], "mapped_symbol": symbol,
        "birth_receipt_sha256": cert["receipt_sha256"],
        "foundry_report_sha256": report["report_sha256"],
        "risk_response": risk,
        "limitations": ["hash receipts are not authenticated signatures",
                        "report not independently statistically validated",
                        "hypothetical prices not verified against venue quotes",
                        "research slot not an order authorization"],
    }
    result["handoff_sha256"] = _hash(result)
    return result


def _read_small_json(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 3_000_000:
        raise HandoffReject("input_missing_nonregular_or_too_large")
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline research-only strategy handoff")
    parser.add_argument("--foundry-report", required=True, type=Path)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--db", required=True, type=Path)
    args = parser.parse_args(argv)
    request = _read_small_json(args.request)
    if not isinstance(request, dict) or set(request) != {"strategy_id", "risk_context", "trade"}:
        raise HandoffReject("handoff_request_schema")
    result = handoff(_read_small_json(args.foundry_report), request["strategy_id"],
                     request["risk_context"], request["trade"], args.db)
    print(_canonical(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
