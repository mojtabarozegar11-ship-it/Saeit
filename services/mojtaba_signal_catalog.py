"""Fixed prelaunch paid-signal subscription catalog for the single mojtaba.bot.ai agent.

The catalog makes each planned subscription product and price explicit, but it deliberately does not
activate billing, publication, trading, or customer delivery.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
import re

class SignalCatalogError(ValueError):
    pass

_PLAN_ID = re.compile(r"^[a-z][a-z0-9-]{2,39}$")
_AGENT = "mojtaba.bot.ai"

@dataclass(frozen=True)
class SignalPlan:
    plan_id: str
    title: str
    cadence: str
    price_usd: Decimal
    description: str

    def __post_init__(self):
        if type(self.plan_id) is not str or not _PLAN_ID.fullmatch(self.plan_id):
            raise SignalCatalogError("invalid plan identifier")
        if (type(self.title) is not str or not 4 <= len(self.title.strip()) <= 180
                or any(ord(ch) < 32 or 0xD800 <= ord(ch) <= 0xDFFF
                       for ch in self.title)):
            raise SignalCatalogError("plan title is required")
        if type(self.cadence) is not str or self.cadence not in (
                "weekly", "monthly", "quarterly"):
            raise SignalCatalogError("unsupported plan cadence")
        if (type(self.description) is not str
                or not 40 <= len(self.description.strip()) <= 800
                or "risk" not in self.description.casefold()
                or "guaranteed" in self.description.casefold()
                or any(ord(ch) < 32 or 0xD800 <= ord(ch) <= 0xDFFF
                       for ch in self.description)):
            raise SignalCatalogError("plan must disclose risk without a promise of return")
        if (type(self.price_usd) is not Decimal
                or not self.price_usd.is_finite()
                or not Decimal("0.01") <= self.price_usd <= Decimal("10000.00")):
            raise SignalCatalogError("finite bounded positive price required")
        try:
            exact_cents = self.price_usd.quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError) as exc:
            raise SignalCatalogError("invalid price precision") from exc
        if self.price_usd != exact_cents:
            raise SignalCatalogError("price must have two decimals")

PLANS = MappingProxyType({
    "education-weekly": SignalPlan(
        "education-weekly", "Weekly live-signal subscription (prelaunch)", "weekly",
        Decimal("9.90"),
        "Planned live signal feed with dated source records, invalidation levels and capital-loss risk disclosure; activation requires verified delivery.",
    ),
    "education-monthly": SignalPlan(
        "education-monthly", "Monthly live-signal subscription (prelaunch)", "monthly",
        Decimal("29.90"),
        "Planned recurring live signal feed with four weekly deliveries, dated provenance, explicit market risk and limitations; activation requires verified delivery and renewal. No guaranteed return.",
    ),
    "education-quarterly": SignalPlan(
        "education-quarterly", "Quarterly live-signal subscription (prelaunch)", "quarterly",
        Decimal("79.90"),
        "Planned twelve-week live signal feed with source fingerprints, review status and explicit capital-loss risk; activation requires verified delivery and renewal. No promise of profit.",
    ),
})

def get_signal_plan(plan_id):
    if type(plan_id) is not str or plan_id not in PLANS:
        raise SignalCatalogError("unknown signal subscription plan")
    return PLANS[plan_id]

def build_manual_signal_offer(plan_id, *, agent=_AGENT):
    """Create a quote-shaped product record without enabling a payment route."""
    if type(agent) is not str or agent != _AGENT:
        raise SignalCatalogError("only the single authorized agent may own this catalog")
    plan = get_signal_plan(plan_id)
    return {
        "schema": "mojtaba.signal.subscription.offer.v1",
        "product_type": "signal_subscription",
        "feed_mode": "live_signal_feed_required",
        "training_product": False,
        "agent": _AGENT,
        "plan_id": plan.plan_id,
        "title": plan.title,
        "cadence": plan.cadence,
        "description": plan.description,
        "amount": format(plan.price_usd, "f"),
        "currency": "USD",
        "commercial_stage": "manual_offer_only",
        "payment_enabled": False,
        "publication_allowed": False,
        "trading_enabled": False,
        "delivery_confirmed": False,
        "contract_required": True,
        "risk_disclosure_required": True,
    }
