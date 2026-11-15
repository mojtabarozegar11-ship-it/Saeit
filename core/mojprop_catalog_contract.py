"""Single source of truth for four non-executable Moj Prop service offers.

These prices are *indicative starting amounts*, not approved customer invoices.
Public route samples are static commercial evidence; no payment is enabled.
"""
from __future__ import annotations

from dataclasses import dataclass
from .models import MojPropRequest


@dataclass(frozen=True)
class PublicMojPropService:
    route: str
    label: str
    sample_slug: str
    from_usd: int


SERVICES = (
    PublicMojPropService("blueprint", "Prop-program design", "prop-blueprint", 149),
    PublicMojPropService("brief", "Private market brief", "gold-market-brief", 39),
    PublicMojPropService("signals", "Educational signals and market brief", "educational-signal", 29),
    PublicMojPropService("audit", "mojtaba.bot.ai commercial-gate audit", "commercial-gate-audit", 249),
)


def public_service_catalog() -> list[dict]:
    expected = dict(MojPropRequest.ROUTE_CHOICES)
    paid_service_routes = {item.route for item in SERVICES}
    # The digital SKU *inquiry* in the companion checkout PR is not a fifth
    # priced Moj Prop service. Reject unknown routes, but do not crash the
    # four-offer public GET endpoint after that separate migration is applied.
    non_service_inquiries = {"digital": "Digital product purchase inquiry"}
    if (not paid_service_routes.issubset(expected)
            or any(expected[item.route] != item.label for item in SERVICES)
            or {route: label for route, label in expected.items()
                if route not in paid_service_routes}
            not in ({}, non_service_inquiries})):
        raise RuntimeError("Moj Prop catalog and Django intake route contract differ")
    if len({item.sample_slug for item in SERVICES}) != len(SERVICES):
        raise RuntimeError("Moj Prop sample slugs are not unique")
    return [
        {
            "route": item.route,
            "title": item.label,
            "sample_url": f"/moj-prop/samples/{item.sample_slug}/",
            "indicative_from_usd": item.from_usd,
            "offer_status": "written_quote_required",
            "checkout_enabled": False,
            "automated_trading_enabled": False,
            "central_service_agent": "mojtaba.bot.ai",
        }
        for item in SERVICES
    ]
