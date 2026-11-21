#!/usr/bin/env python3
"""Game Economy Stress Lab v1.0.0: deterministic, offline, stdlib-only.

This models an illustrative game economy, not player behaviour or revenue.
No network, personal data, payments, random loot or external dependencies.
"""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN, localcontext
import io
import json
from pathlib import Path
import sys

VERSION = "1.0.0"
FIELDS = (
    "sessions", "session_minutes", "initial_wallet", "earn_per_minute",
    "spend_per_minute", "earn_growth_per_session", "spend_growth_per_session",
    "wallet_cap", "players", "retention_per_session",
)
DEFAULTS = {
    "sessions": 12, "session_minutes": 15, "initial_wallet": 150,
    "earn_per_minute": 8, "spend_per_minute": 6,
    "earn_growth_per_session": 0.02, "spend_growth_per_session": 0.03,
    "wallet_cap": 2000, "players": 1000, "retention_per_session": 0.88,
}
Q = Decimal("0.0001")


def _number(value, name, lower, upper):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError(f"{name}: numeric value required")
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"{name}: invalid number") from exc
    if not number.is_finite() or number < lower or number > upper:
        raise ValueError(f"{name}: outside permitted finite range [{lower}, {upper}]")
    return number


def validate(config):
    if not isinstance(config, dict):
        raise ValueError("configuration must be a JSON object")
    unknown = set(config) - set(FIELDS)
    if unknown:
        raise ValueError("unknown configuration fields: " + ", ".join(sorted(unknown)))
    data = {**DEFAULTS, **config}
    sessions = data["sessions"]
    players = data["players"]
    if type(sessions) is not int or not 1 <= sessions <= 360:
        raise ValueError("sessions must be an integer from 1 to 360")
    if type(players) is not int or not 1 <= players <= 10_000_000:
        raise ValueError("players must be an integer from 1 to 10000000")
    bounds = {
        "session_minutes": (Decimal("0.1"), Decimal("1440")),
        "initial_wallet": (Decimal(0), Decimal("1e9")),
        "earn_per_minute": (Decimal(0), Decimal("1e7")),
        "spend_per_minute": (Decimal(0), Decimal("1e7")),
        "earn_growth_per_session": (Decimal("-0.5"), Decimal("0.5")),
        "spend_growth_per_session": (Decimal("-0.5"), Decimal("0.5")),
        "wallet_cap": (Decimal(0), Decimal("1e12")),
        "retention_per_session": (Decimal(0), Decimal(1)),
    }
    for name, (lo, hi) in bounds.items():
        data[name] = _number(data[name], name, lo, hi)
    if data["initial_wallet"] > data["wallet_cap"]:
        raise ValueError("initial_wallet cannot exceed wallet_cap")
    return data


def _str(value):
    return format(value.quantize(Q, rounding=ROUND_HALF_EVEN), "f")


def simulate(config):
    """Return per-player ledger and retention-weighted cohort expectations.

    Spend demand is limited by funds available in that session; wallet overflow
    is discarded after spending. All calculations use exact Decimal arithmetic.
    """
    data = validate(config)
    with localcontext() as context:
        context.prec = 42
        wallet = data["initial_wallet"]
        minutes = data["session_minutes"]
        earn_rate = data["earn_per_minute"]
        spend_rate = data["spend_per_minute"]
        retention = data["retention_per_session"]
        active = Decimal(data["players"])
        rows = []
        totals = {key: Decimal(0) for key in (
            "expected_player_sessions", "cohort_earned", "cohort_spent",
            "cohort_unmet_spending", "cohort_wallet_overflow",
        )}
        for index in range(1, data["sessions"] + 1):
            if earn_rate > Decimal("1e12") or spend_rate > Decimal("1e12"):
                raise ValueError("projected rate exceeds bounded model capacity")
            before = wallet
            earned = earn_rate * minutes
            demand = spend_rate * minutes
            spent = min(before + earned, demand)
            unmet = demand - spent
            pre_cap = before + earned - spent
            overflow = max(Decimal(0), pre_cap - data["wallet_cap"])
            wallet = pre_cap - overflow
            if wallet < 0 or wallet > data["wallet_cap"]:
                raise ArithmeticError("wallet conservation invariant violated")
            if before + earned != spent + overflow + wallet:
                raise ArithmeticError("ledger conservation invariant violated")
            rows.append({
                "session": index,
                "expected_active_players": _str(active),
                "wallet_before": _str(before),
                "earned": _str(earned),
                "spend_requested": _str(demand),
                "spent": _str(spent),
                "unmet_spending": _str(unmet),
                "wallet_overflow": _str(overflow),
                "wallet_after": _str(wallet),
            })
            totals["expected_player_sessions"] += active
            totals["cohort_earned"] += active * earned
            totals["cohort_spent"] += active * spent
            totals["cohort_unmet_spending"] += active * unmet
            totals["cohort_wallet_overflow"] += active * overflow
            active *= retention
            earn_rate *= 1 + data["earn_growth_per_session"]
            spend_rate *= 1 + data["spend_growth_per_session"]
        return {
            "schema": "mpw.game-economy-stress-lab.v1",
            "version": VERSION,
            "model": "deterministic_per_player_ledger_and_expected_retained_cohort",
            "assumptions": [
                "Expected active players = starting players * retention^(session-1).",
                "A single representative player wallet path is modeled; no individual variation.",
                "Spending is limited to available funds; surplus above wallet cap is discarded.",
                "No inference about engagement, retention, monetization, or real demand.",
            ],
            "sessions": rows,
            "summary": {**{k: _str(v) for k, v in totals.items()},
                        "wallet_after_final_session": _str(wallet)},
        }


def render_csv(result):
    output = io.StringIO(newline="")
    fields = list(result["sessions"][0])
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(result["sessions"])
    return output.getvalue()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Local JSON configuration (max 64 KiB)")
    parser.add_argument("--format", choices=("json", "csv"), default="json")
    args = parser.parse_args(argv)
    path = Path(args.config)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
        parser.error("config must be a regular local file <= 64 KiB")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        result = simulate(data)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    sys.stdout.write(render_csv(result) if args.format == "csv" else
                     json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
