"""Fixed educational signal-plan catalog for the single mojtaba.bot.ai agent.

The catalog makes a product and price explicit, but it deliberately does not
activate billing, publication, trading, or customer delivery.
"""
from dataclasses import dataclass
from decimal import Decimal
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
        if type(self.title) is not str or not 4 <= len(self.title.strip()) <= 180:
            raise SignalCatalogError("plan title is required")
        if type(self.cadence) is not str or self.cadence not in (
                "weekly", "monthly", "quarterly"):
            raise SignalCatalogError("unsupported plan cadence")
        if (type(self.description) is not str
                or not 40 <= len(self.description.strip()) <= 800
                or "risk" not in self.description.casefold()
                or "guaranteed" in self.description.casefold()
                or any(ord(ch) < 32 for ch in self.description)):
            raise SignalCatalogError("plan must disclose risk without a promise of return")
        if type(self.price_usd) is not Decimal or not self.price_usd.is_finite() or self.price_usd <= 0:
            raise SignalCatalogError("finite positive price required")
        if self.price_usd != self.price_usd.quantize(Decimal("0.01")):
            raise SignalCatalogError("price must have two decimals")

PLANS = MappingProxyType({
    "education-weekly": SignalPlan(
        "education-weekly", "Weekly educational market brief", "weekly",
        Decimal("9.90"),
        "Source-backed scenarios, invalidation levels and risk disclosure; no personalized advice.",
    ),
    "education-monthly": SignalPlan(
        "education-monthly", "Monthly educational market brief", "monthly",
        Decimal("29.90"),
        "Four weekly educational briefs with dated provenance, explicit market risk and limitations; no personalized advice.",
    ),
    "education-quarterly": SignalPlan(
        "education-quarterly", "Quarterly educational market brief", "quarterly",
        Decimal("79.90"),
        "A twelve-week educational archive with source fingerprints, review status and explicit capital-loss risk; without promises of profit.",
    ),
})

def get_signal_plan(plan_id):
    if type(plan_id) is not str or plan_id not in PLANS:
        raise SignalCatalogError("unknown educational signal plan")
    return PLANS[plan_id]

def build_manual_signal_offer(plan_id, *, agent=_AGENT):
    """Create a quote-shaped product record without enabling a payment route."""
    if agent != _AGENT:
        raise SignalCatalogError("only the single authorized agent may own this catalog")
    plan = get_signal_plan(plan_id)
    return {
        "schema": "mojtaba.signal.offer.v1",
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
