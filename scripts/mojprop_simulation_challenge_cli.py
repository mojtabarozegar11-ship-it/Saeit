#!/usr/bin/env python3
"""Offline, no-network Moj Prop two-phase simulated evaluation entrypoint.

Usage: python -m scripts.mojprop_simulation_challenge_cli < journal.json
No account creation, files, webhooks, trading, keys, DB, merchant or payout.
The journal is *unverified* no matter which numbers the sender claims.
Output never echoes buyer names, raw trades, customer data or identifiers.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import json
import re
import sys

from services.mojprop_simulation_challenge import (
    ChallengeInputError, ChallengePolicy, EquitySnapshot,
    evaluate_two_phase_simulation,
)

MAX_STDIN_BYTES = 65536
_MONEY = re.compile(r"(?:0|[1-9][0-9]{0,11})\.[0-9]{2}\Z")
_ACCOUNT_MARK = re.compile(r"-?(?:0|[1-9][0-9]{0,11})\.[0-9]{2}\Z")
_POLICY_FIELDS = frozenset((
    "starting_equity", "phase1_profit_target_bps", "phase2_profit_target_bps",
    "max_daily_loss_bps", "max_overall_loss_bps", "minimum_trading_days",
    "overall_drawdown_mode",
))
_EVENT_FIELDS = frozenset((
    "event_id", "phase", "observed_at", "balance", "equity", "trades_executed",
))


def _unique_fields(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ChallengeInputError("duplicate_json_field")
        result[key] = value
    return result


def _money(raw: object) -> Decimal:
    if type(raw) is not str or _MONEY.fullmatch(raw) is None:
        raise ChallengeInputError("invalid_money_not_exact_decimal_string")
    return Decimal(raw)


def _account_mark(raw: object) -> Decimal:
    if type(raw) is not str or _ACCOUNT_MARK.fullmatch(raw) is None:
        raise ChallengeInputError("invalid_account_mark")
    return Decimal(raw)


def _event(value: object, phase: int) -> EquitySnapshot:
    if type(value) is not dict or set(value) != _EVENT_FIELDS:
        raise ChallengeInputError("invalid_event_contract")
    ts = value["observed_at"]
    if type(ts) is not str or not 20 <= len(ts) <= 35:
        raise ChallengeInputError("invalid_observation_clock")
    try:
        at = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, OverflowError) as exc:
        raise ChallengeInputError("invalid_observation_clock") from exc
    return EquitySnapshot(
        event_id=value["event_id"], phase=value["phase"],
        observed_at=at, balance=_account_mark(value["balance"]),
        equity=_account_mark(value["equity"]),
        trades_executed=value["trades_executed"],
    )


def assess_json_bytes(data: bytes) -> dict:
    """Pure, bounded parser and education-only evaluation, zero external IO."""
    if type(data) is not bytes or not 1 <= len(data) <= MAX_STDIN_BYTES:
        raise ChallengeInputError("invalid_input_size")
    try:
        text = data.decode("utf-8")
        doc = json.loads(text, object_pairs_hook=_unique_fields,
                         parse_constant=lambda _: (_ for _ in ()).throw(
                             ChallengeInputError("nonfinite_input")))
    except (UnicodeDecodeError, ValueError, RecursionError, MemoryError) as exc:
        raise ChallengeInputError("invalid_json_document") from exc
    if type(doc) is not dict or set(doc) != {"schema", "policy", "phase1", "phase2"}:
        raise ChallengeInputError("invalid_root_contract")
    if doc["schema"] != "mojprop.simulated.input.v1":
        raise ChallengeInputError("unreviewed_schema")
    policy_fields = doc["policy"]
    if type(policy_fields) is not dict or set(policy_fields) != _POLICY_FIELDS:
        raise ChallengeInputError("invalid_policy_contract")
    p = dict(policy_fields)
    p["starting_equity"] = _money(p["starting_equity"])
    policy = ChallengePolicy(**p)
    if (type(doc["phase1"]) is not list or type(doc["phase2"]) is not list
            or len(doc["phase1"]) > 20000 or len(doc["phase2"]) > 20000):
        raise ChallengeInputError("invalid_journal_collection")
    one = [_event(item, 1) for item in doc["phase1"]]
    two = [_event(item, 2) for item in doc["phase2"]]
    result = evaluate_two_phase_simulation(policy, one, two)
    result["input_schema"] = "mojprop.simulated.input.v1"
    return result


def main() -> int:
    try:
        result = assess_json_bytes(sys.stdin.buffer.read(MAX_STDIN_BYTES + 1))
    except (ChallengeInputError, OSError):
        # Do not print untrusted buyer JSON, credentials or error detail.
        print('{"ok":false,"error":"invalid_simulation_input","payment_collected":false}')
        return 2
    print(json.dumps({"ok": True, "result": result},
                     sort_keys=True, separators=(",", ":"), ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
