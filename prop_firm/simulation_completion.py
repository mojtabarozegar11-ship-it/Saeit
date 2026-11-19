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
