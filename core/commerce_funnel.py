"""Small, failure-tolerant, privacy-preserving commerce funnel recorder."""
from __future__ import annotations

import hashlib
import hmac
import time

from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError

from .models import CommerceFunnelEvent, Product


def _value(request, name: str, limit: int) -> str:
    value = request.GET.get(name, "") or request.POST.get(name, "")
    return value.strip()[:limit] if isinstance(value, str) else ""


# Only suppress known automated observations; do not suppress invoice, payment,
# or delivery facts merely because a client's user agent is unconventional.
_OBSERVATION_EVENTS = frozenset(("view_store", "view_item", "begin_checkout"))
_AUTOMATION_SIGNATURES = (
    "curl/", "python-urllib/", "python-requests/", "python-httpx/",
    "httpx/", "wget/", "go-http-client/", "node-fetch/", "axios/",
    "headlesschrome", "headless", "postmanruntime/", "uptimerobot",
    "ahrefs", "semrush", "facebookexternalhit", "google-inspectiontool",
    "mojprop-", "mpw-", "crawler", "spider", "bot/",
)


def _observation_dedupe_key(request, event_name: str, product: Product | None) -> str:
    """Return a short-lived HMAC key for repeated observation requests.

    Raw IP/user-agent values never enter the database or cache key. This is
    limited to GET/HEAD observation events; invoice, payment and delivery
    facts are never deduplicated here.
    """
    ip = request.META.get("REMOTE_ADDR", "")
    ua = request.META.get("HTTP_USER_AGENT", "")
    product_id = getattr(product, "pk", 0) or 0
    material = "|".join((
        str(event_name), str(product_id), str(ip)[:120], str(ua)[:300],
        str(int(time.time() // 900)),
    ))
    digest = hmac.new(
        str(settings.SECRET_KEY).encode("utf-8"),
        material.encode("utf-8", "replace"),
        hashlib.sha256,
    ).hexdigest()
    return "mpw:funnel:observation:" + digest


def _known_automated_observation(request, event_name: str) -> bool:
    if event_name not in _OBSERVATION_EVENTS:
        return False
    if getattr(request, "method", "") not in ("GET", "HEAD"):
        return False
    user_agent = getattr(request, "META", {}).get("HTTP_USER_AGENT", "")
    if not isinstance(user_agent, str):
        return False
    agent = user_agent.lower()[:300]
    # Unknown or browser-looking traffic is NEVER certified human.
    return any(marker in agent for marker in _AUTOMATION_SIGNATURES)


def record_funnel_event(request, event_name: str, product: Product | None = None) -> None:
    """Record a bounded funnel fact without allowing analytics to break sales."""
    if event_name not in dict(CommerceFunnelEvent.EVENT_CHOICES):
        return
    if _known_automated_observation(request, event_name):
        return
    if event_name in _OBSERVATION_EVENTS and getattr(request, "method", "") in ("GET", "HEAD"):
        try:
            if not cache.add(_observation_dedupe_key(request, event_name, product), 1, timeout=900):
                return
        except Exception:
            # Telemetry deduplication must never block a storefront or checkout.
            pass
    try:
        CommerceFunnelEvent.objects.create(
            event_name=event_name,
            product=product,
            source=_value(request, "utm_source", 40),
            medium=_value(request, "utm_medium", 40),
            campaign=_value(request, "utm_campaign", 80),
        )
    except DatabaseError:
        # Funnel telemetry is diagnostic only; commerce must remain available.
        return
