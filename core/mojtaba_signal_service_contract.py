"""Single-identity, non-financial signal-service contract.

The contract supports paid research, market summaries, risk education and
operational alerts under mojtaba.bot.ai. It deliberately rejects investment
calls and guaranteed-profit language. It does not publish, charge, trade or
send messages by itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
import re
from typing import Iterable, Tuple


class SignalContractError(ValueError):
    """Raised when a signal offer or route is unsafe or incomplete."""


BOT_IDENTITY = "mojtaba.bot.ai"
ALLOWED_LANGUAGES = frozenset({"fa", "en", "ar"})
ALLOWED_CURRENCIES = frozenset({"TRX", "USD"})


class SignalServiceKind(str, Enum):
    RESEARCH_SUMMARY = "research_summary"
    MARKET_BRIEF = "market_brief"
    RISK_EDUCATION = "risk_education"
    ECONOMIC_REPORT = "economic_report"
    OPERATIONAL_ALERT = "operational_alert"


_SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")
_HOST = re.compile(r"^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")
_PATH = re.compile(r"^/[a-z0-9][a-z0-9/_-]*$|^/$")
_ENGLISH_BLOCKED = frozenset({
    "buy", "sell", "hold", "long", "short", "entry", "exit", "trade", "order",
    "guaranteed", "guarantee", "profit", "return", "invest", "signal-to-buy",
})
_NON_ENGLISH_BLOCKED = frozenset({
    "خرید", "فروش", "بخر", "بفروش", "نگهداری", "لانگ", "شورت", "ورود", "خروج",
    "معامله", "سرمایه گذاری", "سرمایه‌گذاری", "سود تضمینی", "بازده تضمینی",
})


def _slug(value: object, field: str) -> str:
    if not isinstance(value, str) or not _SLUG.fullmatch(value):
        raise SignalContractError(f"{field}_invalid")
    return value


def _host(value: object, field: str = "canonical_host") -> str:
    if not isinstance(value, str) or value != value.lower() or "://" in value or "/" in value or not _HOST.fullmatch(value):
        raise SignalContractError(f"{field}_invalid")
    return value


def _path(value: object) -> str:
    if not isinstance(value, str) or ".." in value or not _PATH.fullmatch(value):
        raise SignalContractError("path_prefix_invalid")
    return value


def _price(value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise SignalContractError("price_must_be_decimal_like")
    try:
        price = Decimal(str(value))
    except Exception as exc:
        raise SignalContractError("price_invalid") from exc
    if not price.is_finite() or price <= Decimal("0"):
        raise SignalContractError("price_must_be_finite_positive")
    return price


@dataclass(frozen=True)
class SignalTenantRoute:
    tenant_id: str
    canonical_host: str
    path_prefix: str
    language: str
    bot_identity: str = BOT_IDENTITY
    owner_approved: bool = False
    legal_reviewed: bool = False
    active: bool = False


def validate_route(route: SignalTenantRoute) -> None:
    _slug(route.tenant_id, "tenant_id")
    _host(route.canonical_host)
    _path(route.path_prefix)
    if route.language not in ALLOWED_LANGUAGES:
        raise SignalContractError("language_not_supported")
    if route.bot_identity != BOT_IDENTITY:
        raise SignalContractError("independent_bot_identity_prohibited")
    if type(route.owner_approved) is not bool or type(route.legal_reviewed) is not bool or type(route.active) is not bool:
        raise SignalContractError("route_gate_must_be_boolean")
    if route.active and not (route.owner_approved and route.legal_reviewed):
        raise SignalContractError("active_route_gates_incomplete")


def validate_route_registry(routes: Iterable[SignalTenantRoute]) -> Tuple[SignalTenantRoute, ...]:
    normalized = tuple(routes)
    seen_tenants = set()
    seen_endpoints = set()
    for route in normalized:
        validate_route(route)
        endpoint = (route.canonical_host, route.path_prefix, route.language)
        if route.tenant_id in seen_tenants:
            raise SignalContractError("duplicate_tenant_route")
        if endpoint in seen_endpoints:
            raise SignalContractError("duplicate_signal_endpoint")
        seen_tenants.add(route.tenant_id)
        seen_endpoints.add(endpoint)
    return tuple(sorted(normalized, key=lambda item: (item.canonical_host, item.path_prefix, item.language)))


@dataclass(frozen=True)
class SignalOffer:
    offer_id: str
    tenant_id: str
    bot_identity: str
    language: str
    service_kind: SignalServiceKind
    price: Decimal
    currency: str
    owner_approved: bool = False
    legal_reviewed: bool = False
    rights_cleared: bool = False
    financial_calls_enabled: bool = False
    guaranteed_profit_promised: bool = False
    active: bool = False


def validate_offer(offer: SignalOffer) -> None:
    _slug(offer.offer_id, "offer_id")
    _slug(offer.tenant_id, "tenant_id")
    if offer.bot_identity != BOT_IDENTITY:
        raise SignalContractError("independent_bot_identity_prohibited")
    if offer.language not in ALLOWED_LANGUAGES:
        raise SignalContractError("language_not_supported")
    if not isinstance(offer.service_kind, SignalServiceKind):
        raise SignalContractError("service_kind_invalid")
    _price(offer.price)
    if offer.currency not in ALLOWED_CURRENCIES:
        raise SignalContractError("currency_not_supported")
    for field in (
        "owner_approved", "legal_reviewed", "rights_cleared",
        "financial_calls_enabled", "guaranteed_profit_promised", "active",
    ):
        if type(getattr(offer, field)) is not bool:
            raise SignalContractError(f"{field}_must_be_boolean")
    if offer.financial_calls_enabled:
        raise SignalContractError("financial_signal_disabled")
    if offer.guaranteed_profit_promised:
        raise SignalContractError("guaranteed_profit_prohibited")
    if offer.active and not all((offer.owner_approved, offer.legal_reviewed, offer.rights_cleared)):
        raise SignalContractError("active_offer_gates_incomplete")


def _blocked_tokens(text: str) -> tuple[str, ...]:
    normalized = " ".join(text.lower().split())
    found = set()
    for token in _ENGLISH_BLOCKED:
        if re.search(r"(?<![a-z])" + re.escape(token) + r"(?![a-z])", normalized):
            found.add(token)
    for token in _NON_ENGLISH_BLOCKED:
        if token in normalized:
            found.add(token)
    return tuple(sorted(found))


def validate_request(*, request_text: str, financial_authorized: bool = False) -> None:
    if not isinstance(request_text, str) or not request_text.strip():
        raise SignalContractError("request_text_required")
    if type(financial_authorized) is not bool:
        raise SignalContractError("financial_authorized_must_be_boolean")
    blocked = _blocked_tokens(request_text)
    if blocked or financial_authorized:
        raise SignalContractError("financial_signal_disabled")


def validate_route_offer_alignment(route: SignalTenantRoute, offer: SignalOffer) -> None:
    validate_route(route)
    validate_offer(offer)
    if route.tenant_id != offer.tenant_id:
        raise SignalContractError("route_offer_tenant_mismatch")
    if route.language != offer.language:
        raise SignalContractError("route_offer_language_mismatch")

