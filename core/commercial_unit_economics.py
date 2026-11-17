"""Conservative unit economics for the *existing* MojPlayWin digital catalog.

All inputs are transparent assumptions, not observed sales, settlement or rates.
No transaction, invoice, wallet, order, campaign or legal approval occurs here.
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_UP


def exact_decimal(value, field, *, zero_allowed=True):
    if isinstance(value, (float, bool)):
        raise ValueError(f"{field}: exact decimal required")
    try:
        number = Decimal(str(value))
    except (ValueError, ArithmeticError) as exc:
        raise ValueError(f"{field}: invalid number") from exc
    if not number.is_finite() or number < 0 or (number == 0 and not zero_allowed):
        raise ValueError(f"{field}: expected nonnegative finite amount")
    return number


def percent(value, field):
    rate = exact_decimal(value, field)
    if rate > 100:
        raise ValueError(f"{field}: maximum 100 percent")
    return rate / Decimal("100")


@dataclass(frozen=True)
class SaleEconomics:
    price_usd: Decimal
    revenue_usd: Decimal
    per_sale_cost_usd: Decimal
    contribution_per_sale_usd: Decimal
    monthly_fixed_cost_usd: Decimal
    month_net_estimate_usd: Decimal
    breakeven_units: int | None
    units_for_target_net: int | None
    assumptions_only: bool = True


def estimate_digital_sale(*, price_usd, hypothetical_sales, processor_fee_percent,
                          network_fee_usd, fulfillment_usd, support_usd,
                          refund_reserve_percent, acquisition_usd,
                          monthly_fixed_cost_usd=0, target_net_usd=0):
    if (not isinstance(hypothetical_sales, int) or isinstance(hypothetical_sales, bool)
            or hypothetical_sales < 0):
        raise ValueError("hypothetical_sales must be nonnegative integer")
    price = exact_decimal(price_usd, "price_usd", zero_allowed=False)
    fee_pct = percent(processor_fee_percent, "processor_fee_percent")
    refund_pct = percent(refund_reserve_percent, "refund_reserve_percent")
    costs = sum((
        price * fee_pct, price * refund_pct,
        exact_decimal(network_fee_usd, "network_fee_usd"),
        exact_decimal(fulfillment_usd, "fulfillment_usd"),
        exact_decimal(support_usd, "support_usd"),
        exact_decimal(acquisition_usd, "acquisition_usd"),
    ), Decimal("0"))
    # Round expenses upward to cents, not downward to an optimistic margin.
    costs = costs.quantize(Decimal("0.01"), rounding=ROUND_UP)
    overhead = exact_decimal(monthly_fixed_cost_usd, "monthly_fixed_cost_usd")
    goal = exact_decimal(target_net_usd, "target_net_usd")
    contribution = price - costs
    if contribution <= 0:
        minimum = None
        needed = None
    else:
        minimum = int((overhead / contribution).to_integral_value(rounding=ROUND_CEILING))
        needed = int(((overhead + goal) / contribution).to_integral_value(rounding=ROUND_CEILING))
    return SaleEconomics(
        price_usd=price,
        revenue_usd=price * hypothetical_sales,
        per_sale_cost_usd=costs,
        contribution_per_sale_usd=contribution,
        monthly_fixed_cost_usd=overhead,
        month_net_estimate_usd=contribution * hypothetical_sales - overhead,
        breakeven_units=minimum,
        units_for_target_net=needed,
    )
