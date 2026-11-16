"""Moj Prop two-phase *simulation* evaluation kernel (C120).

Deterministic, strictly bounded financial mathematics over submitted snapshots.
It does NOT verify a broker account, execute trades, authorize a funded
challenge, confer a license, invoice TRX, allocate capital or issue a payout.
The rules here are illustrative unless a separately reviewed, legally binding
customer contract specifies these exact limits. Missing ticks cannot establish
that a daily drawdown was never breached between snapshots.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import json
import re
from typing import Sequence

MAX_SNAPSHOTS = 20000
MAX_EQUITY = Decimal("1000000000000.00")
MAX_TRADES_PER_SNAPSHOT = 100000
BPS = Decimal(10000)
_EVENT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{7,79}\Z")
_MODES = frozenset(("static_initial", "trailing_peak"))


class ChallengeInputError(ValueError):
    """A malformed journal or policy cannot produce a passing verdict."""


def _decimal_money(value: object, field: str) -> Decimal:
    if type(value) is not Decimal or not value.is_finite():
        raise ChallengeInputError("invalid_" + field)
    try:
        with localcontext() as ctx:
            ctx.prec = 40
            if (value <= 0 or value > MAX_EQUITY
                    or value != value.quantize(Decimal("0.01"))):
                raise ChallengeInputError("invalid_" + field)
    except (InvalidOperation, OverflowError) as exc:
        raise ChallengeInputError("invalid_" + field) from exc
    return value


def _bps(value: object, field: str, *, maximum: int = 10000) -> int:
    if type(value) is not int or not 1 <= value <= maximum:
        raise ChallengeInputError("invalid_" + field)
    return value


@dataclass(frozen=True)
class ChallengePolicy:
    """Operator-reviewed *example* rules; no default funded-program contract."""
    starting_equity: Decimal
    phase1_profit_target_bps: int
    phase2_profit_target_bps: int
    max_daily_loss_bps: int
    max_overall_loss_bps: int
    minimum_trading_days: int
    overall_drawdown_mode: str = "static_initial"

    def validate(self) -> None:
        _decimal_money(self.starting_equity, "starting_equity")
        _bps(self.phase1_profit_target_bps, "phase1_target")
        _bps(self.phase2_profit_target_bps, "phase2_target")
        _bps(self.max_daily_loss_bps, "daily_loss")
        _bps(self.max_overall_loss_bps, "overall_loss")
        if (type(self.minimum_trading_days) is not int
                or not 1 <= self.minimum_trading_days <= 365):
            raise ChallengeInputError("invalid_minimum_trading_days")
        if type(self.overall_drawdown_mode) is not str or self.overall_drawdown_mode not in _MODES:
            raise ChallengeInputError("invalid_drawdown_mode")


@dataclass(frozen=True)
class EquitySnapshot:
    """One unverified simulation observation; NOT a broker attestation."""
    event_id: str
    phase: int
    observed_at: datetime
    balance: Decimal
    equity: Decimal
    trades_executed: int

    def validate(self, expected_phase: int) -> datetime:
        if type(self.event_id) is not str or _EVENT_ID.fullmatch(self.event_id) is None:
            raise ChallengeInputError("invalid_event_id")
        if type(self.phase) is not int or self.phase != expected_phase:
            raise ChallengeInputError("invalid_snapshot_phase")
        if (type(self.observed_at) is not datetime
                or self.observed_at.tzinfo is None
                or self.observed_at.utcoffset() is None):
            raise ChallengeInputError("naive_or_invalid_snapshot_time")
        if (type(self.trades_executed) is not int
                or not 0 <= self.trades_executed <= MAX_TRADES_PER_SNAPSHOT):
            raise ChallengeInputError("invalid_trades_executed")
        _decimal_money(self.balance, "balance")
        _decimal_money(self.equity, "equity")
        return self.observed_at.astimezone(timezone.utc)


def _percent_bps(numerator: Decimal, denominator: Decimal) -> str:
    with localcontext() as ctx:
        ctx.prec = 40
        return format((numerator / denominator * BPS).quantize(Decimal("0.01")), "f")


def evaluate_simulated_phase(
    policy: ChallengePolicy,
    snapshots: Sequence[EquitySnapshot],
    *,
    phase: int,
) -> dict:
    """Evaluate provided observations without EVER claiming a funded pass.

    Day opening reference is previous day's last observed equity, and the
    overall rule is either fixed starting equity or previous observed peak.
    These are explicit educational definitions, not universal prop rules.
    A sampled path can miss intraday breaches and market or broker fees.
    """
    if type(policy) is not ChallengePolicy:
        raise ChallengeInputError("unreviewed_policy")
    policy.validate()
    if type(phase) is not int or phase not in (1, 2):
        raise ChallengeInputError("invalid_phase")
    if type(snapshots) not in (list, tuple) or len(snapshots) > MAX_SNAPSHOTS:
        raise ChallengeInputError("invalid_snapshot_collection")
    if any(type(item) is not EquitySnapshot for item in snapshots):
        raise ChallengeInputError("invalid_snapshot_type")

    previous_at = None
    previous_day = None
    previous_equity = policy.starting_equity
    day_open = policy.starting_equity
    peak = policy.starting_equity
    active_days = set()
    event_ids = set()
    first_breach = None
    last_equity = policy.starting_equity
    digest = bytes(32)
    worst_daily_loss_bps = Decimal(0)
    worst_overall_loss_bps = Decimal(0)
    target = (policy.phase1_profit_target_bps if phase == 1
              else policy.phase2_profit_target_bps)

    with localcontext() as ctx:
        ctx.prec = 40
        for index, observation in enumerate(snapshots):
            at = observation.validate(phase)
            if observation.event_id in event_ids:
                raise ChallengeInputError("duplicate_event_id")
            if previous_at is not None and at <= previous_at:
                raise ChallengeInputError("nonmonotonic_snapshot_time")
            event_ids.add(observation.event_id)
            day = at.date()
            if previous_day is not None and day != previous_day:
                day_open = previous_equity
            effective = min(observation.balance, observation.equity)
            peak = max(peak, observation.balance, observation.equity)
            overall_reference = (
                policy.starting_equity if policy.overall_drawdown_mode == "static_initial"
                else peak
            )
            daily_loss = max(Decimal(0), day_open - effective)
            overall_loss = max(Decimal(0), overall_reference - effective)
            # Different days have different opening bases; compare risk in
            # basis points of that day and the selected overall reference.
            worst_daily_loss_bps = max(worst_daily_loss_bps, daily_loss / day_open * BPS)
            worst_overall_loss_bps = max(
                worst_overall_loss_bps, overall_loss / overall_reference * BPS,
            )
            daily_floor = day_open * (BPS - policy.max_daily_loss_bps) / BPS
            total_floor = overall_reference * (BPS - policy.max_overall_loss_bps) / BPS
            if first_breach is None and effective < total_floor:
                first_breach = "observed_overall_drawdown_breach"
            if first_breach is None and effective < daily_floor:
                first_breach = "observed_daily_drawdown_breach"
            if observation.trades_executed > 0:
                active_days.add(day.isoformat())

            # Ordered hash chain for *record reconciliation*, not independent
            # evidence of real execution or a cryptographically signed feed.
            canonical = json.dumps({
                "index": index, "event_id": observation.event_id,
                "phase": phase, "at_utc": at.isoformat(),
                "balance": format(observation.balance, "f"),
                "equity": format(observation.equity, "f"),
                "trades_executed": observation.trades_executed,
            }, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
            digest = hashlib.sha256(digest + canonical).digest()
            previous_day, previous_at = day, at
            previous_equity = observation.equity
            last_equity = effective

        target_equity = policy.starting_equity * (BPS + target) / BPS
        target_met = last_equity >= target_equity
        days_met = len(active_days) >= policy.minimum_trading_days
        if first_breach is not None:
            status = "observed_simulation_rule_breach"
        elif snapshots and target_met and days_met:
            status = "simulation_target_met_review_required"
        else:
            status = "simulation_in_progress"

        return {
            "schema": "mojprop.simulated.phase_evaluation.v1",
            "phase": phase,
            "status": status,
            "first_observed_breach": first_breach,
            "snapshot_count": len(snapshots),
            "observed_trading_days": len(active_days),
            "minimum_trading_days": policy.minimum_trading_days,
            "trading_days_met": days_met,
            "target_equity": format(target_equity, "f"),
            "latest_observed_equity": format(last_equity, "f"),
            "profit_target_observed": target_met,
            "worst_observed_daily_loss_bps": format(worst_daily_loss_bps.quantize(Decimal("0.01")), "f"),
            "worst_observed_overall_loss_bps": format(worst_overall_loss_bps.quantize(Decimal("0.01")), "f"),
            "observations_sha256": digest.hex(),
            "daily_reference_definition": "previous_day_last_observed_equity_utc",
            "overall_reference_definition": policy.overall_drawdown_mode,
            "data_provenance": "self_reported_not_broker_verified",
            "between_snapshot_breaches_verified": False,
            "requires_independent_broker_evidence": True,
            "official_challenge_passed": False,
            "funded_account_provisioning_allowed": False,
            "payout_allowed": False,
            "payment_collected": False,
        }


def evaluate_two_phase_simulation(
    policy: ChallengePolicy,
    phase1_snapshots: Sequence[EquitySnapshot],
    phase2_snapshots: Sequence[EquitySnapshot] = (),
) -> dict:
    """Review both *simulated* phases without automatically unlocking capital.

    Phase 2 is only interpreted as an educational independent journal after
    phase 1 meets the observed target. It is never an authorized live phase-2
    account. Neither two green self-reported journals nor any report here
    confers a funded account, actual broker challenge pass or payout rights.
    """
    first = evaluate_simulated_phase(policy, phase1_snapshots, phase=1)
    if type(phase2_snapshots) not in (list, tuple):
        raise ChallengeInputError("invalid_phase2_collection")
    if first["status"] != "simulation_target_met_review_required":
        if phase2_snapshots:
            raise ChallengeInputError("phase2_requires_phase1_simulation_target")
        second = None
        phase2_note = "not_started_phase1_rules_unmet"
    else:
        second = evaluate_simulated_phase(policy, phase2_snapshots, phase=2)
        phase2_note = (
            "simulation_target_met_but_no_authoritative_evidence"
            if second["status"] == "simulation_target_met_review_required"
            else "simulation_incomplete_or_breached"
        )
    return {
        "schema": "mojprop.simulated.two_phase_program.v1",
        "phase1": first,
        "phase2": second,
        "phase2_note": phase2_note,
        "phase2_uses_fresh_initial_equity": True,
        "independent_human_and_broker_review_required": True,
        "verified_contract_and_provider_required": True,
        "official_program_passed": False,
        "funded_account_provisioning_allowed": False,
        "payment_collected": False,
        "payout_allowed": False,
    }
