"""Host boundary for the independent MojProp.top business.

The legacy TRX commerce views are not a MojProp tenant. Until an independent
MojProp database, invoice ledger, delivery store, restore/rollback evidence and
tenant-separation proof are available, shared commerce routes must fail closed
on the MojProp host instead of silently serving another business.
"""
from __future__ import annotations

from functools import wraps
from html import escape

from django.http import HttpResponse

MOJPROP_HOSTS = frozenset({"mojprop.top", "www.mojprop.top"})
MOJPROP_SUPPORT_EMAIL = "mojtaba.rozegar11@gmail.com"


def request_host(request) -> str:
    return request.get_host().split(":", 1)[0].lower()


def is_mojprop_host(request) -> bool:
    return request.is_secure() and request_host(request) in MOJPROP_HOSTS


def standalone_commerce_unavailable(request, *args, **kwargs):
    """Return a truthful, non-payment response for an unproven route."""
    del args, kwargs
    html = f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MojProp.top checkout status</title>
<style>body{{margin:0;background:#101520;color:#f7f7f7;font:17px/1.65 system-ui}}main{{max-width:760px;margin:auto;padding:42px 20px}}article{{border:1px solid #475368;border-radius:16px;padding:24px;background:#182234}}a{{color:#83e5d4}}</style>
<main><article>
<h1>MojProp.top</h1>
<p>The independent MojProp checkout is not released yet.</p>
<p>No payment, wallet transfer or invoice is accepted on this route. The product information and manual request routes remain available while the independent invoice, delivery and recovery controls are completed.</p>
<p><a href="/">Return to MojProp.top</a> · <a href="/moj-prop/contact/">Request a manual review</a></p>
<p>Contact: <a href="mailto:{escape(MOJPROP_SUPPORT_EMAIL)}">{escape(MOJPROP_SUPPORT_EMAIL)}</a></p>
</article></main></html>"""
    response = HttpResponse(html, status=503, content_type="text/html; charset=utf-8")
    response["Cache-Control"] = "no-store"
    response["X-MojProp-Commerce"] = "standalone-not-released"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def guard_legacy_commerce(view):
    """Keep legacy commerce routes off the MojProp host."""
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if is_mojprop_host(request):
            return standalone_commerce_unavailable(request)
        return view(request, *args, **kwargs)

    return wrapped
