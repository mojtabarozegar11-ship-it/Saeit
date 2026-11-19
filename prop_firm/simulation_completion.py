"""Necessary challenge-completion criteria; never awards a pass or payout.

The reviewed policy sets 50 closed positions and 32% best-day share.
No unapproved profit target, funded entitlement or reward is invented.
"""
from decimal import Decimal
from .simulation_policy import SIMULATION_POLICY

def completion_evidence(engine, *, expired):
    """Compute definite failure from replayed server-owned engine state.

    Unresolved positions or pending orders require review at expiry.
    Missing necessary criteria can establish failure, never establish success.
    """
    if engine.blocked is True:
        return ("drawdown_limit_reached",)
    if expired is not True or engine.positions or engine.pending:
        return ()
    reasons=[]
    if engine.closed_trade_count < SIMULATION_POLICY.minimum_closed_positions:
        reasons.append("minimum_closed_positions_not_met")
    if engine.realized_pnl <= 0:
        reasons.append("positive_net_profit_not_met")
    else:
        best=max([Decimal("0"), *engine.realized_by_day.values()])
        if best*Decimal("100") > engine.realized_pnl*SIMULATION_POLICY.canonical_best_day_share_pct:
            reasons.append("best_day_share_exceeds_limit")
    return tuple(reasons)


def review_completion(engine, *, expired, reviewed_profit_target_pct=None):
    """Return review evidence only, never an entitlement or financial commitment.

    A reviewed target is an internal input in percent, not browser data.
    None deliberately means the new contract's target is not established.
    """
    failures=completion_evidence(engine, expired=expired)
    if failures:
        return {"state":"failed","reasons":failures,"pass_attested":False}
    if expired is not True:
        return {"state":"in_progress","reasons":(),"pass_attested":False}
    if engine.positions or engine.pending:
        return {"state":"review_required","reasons":("unresolved_positions_or_orders",),"pass_attested":False}
    if not isinstance(reviewed_profit_target_pct, Decimal) or not reviewed_profit_target_pct.is_finite() or reviewed_profit_target_pct <= 0:
        return {"state":"review_required","reasons":("reviewed_profit_target_missing",),"pass_attested":False}
    required_profit=SIMULATION_POLICY.starting_balance_usd*reviewed_profit_target_pct/Decimal("100")
    if engine.realized_pnl < required_profit:
        return {"state":"failed","reasons":("reviewed_profit_target_not_met",),"pass_attested":False}
    return {"state":"pass_candidate","reasons":(),"pass_attested":False}
