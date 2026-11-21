"""Pure preflight for the new simulation contract only; no execution."""
from .rules import RiskDecision, dec, percent
from .simulation_policy import SIMULATION_POLICY as P

def authorize_simulation_order(*, account_capital, equity, day_open_equity,
                               risk_at_stop, open_risk_before, broker_minimum_risk,
                               verified_stop=False, authoritative_snapshot=False,
                               mode="challenge", execution_authorized=False):
    if mode not in ("challenge", "real"):
        raise ValueError("invalid mode")
    capital, equity, opening, single, aggregate, minimum = map(dec, (
        account_capital, equity, day_open_equity, risk_at_stop,
        open_risk_before, broker_minimum_risk))
    if capital <= 0 or min(equity, opening, single, aggregate, minimum) < 0:
        raise ValueError("Invalid risk amounts")
    daily_floor = opening - percent(capital, P.daily_loss_limit_pct)
    total_floor = capital - percent(capital, P.total_loss_limit_pct)
    reasons = []
    if capital != P.starting_balance_usd:
        reasons.append("unsupported_capital_tier")
    if equity <= daily_floor:
        reasons.append("daily_loss_floor_reached")
    if equity <= total_floor:
        reasons.append("total_loss_floor_reached")
    if authoritative_snapshot is not True:
        reasons.append("authoritative_simulator_snapshot_required")
    if verified_stop is not True:
        reasons.append("stop_loss_required")
    if single <= 0 or single > percent(capital, P.max_risk_per_trade_pct):
        reasons.append("per_order_risk_limit")
    if aggregate + single > percent(capital, P.max_open_risk_pct):
        reasons.append("aggregate_risk_limit")
    if equity - aggregate - single <= max(daily_floor, total_floor):
        reasons.append("stop_risk_exceeds_drawdown_headroom")
    if minimum > single:
        reasons.append("minimum_order_not_feasible")
    if mode == "real":
        reasons.append("real_execution_disabled")
    # This API is a pure simulator preflight. An execution request must fail closed.
    if execution_authorized is not False:
        reasons.append("execution_request_not_supported")
    return RiskDecision(not reasons, tuple(reasons), daily_floor, total_floor)
