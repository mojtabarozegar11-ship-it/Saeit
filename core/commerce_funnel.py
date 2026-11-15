"""Small, failure-tolerant, privacy-preserving commerce funnel recorder."""
from __future__ import annotations

import re

from django.db import DatabaseError

from .models import CommerceFunnelEvent, Product


_CAMPAIGN_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._~-]*$")


def _value(request, name: str, limit: int) -> str:
    value = request.GET.get(name, "")
    if not isinstance(value, str):
        return ""
    value = value.strip()
    # Campaign attribution must not copy visitor emails, links, contact data,
    # query strings or HTML into the analytics database.
    if not value or len(value) > limit or not _CAMPAIGN_TOKEN.fullmatch(value):
        return ""
    return value


def record_funnel_event(request, event_name: str, product: Product | None = None) -> None:
    """Record a bounded funnel fact without allowing analytics to break sales."""
    if event_name not in dict(CommerceFunnelEvent.EVENT_CHOICES):
        return
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
