"""Minimal customer-facing TRX feature switch; no network or database access."""
from __future__ import annotations

def checkout_flags(request):
    from django.conf import settings
    try:
        host=request.get_host().split(":")[0].lower()
    except Exception:
        host=""
    released=bool(
        host in ("mojplaywin.com","www.mojplaywin.com")
        and request.is_secure()
        and getattr(settings,"MPW_WALLETLESS_TRX_PUBLIC_ENABLED",False) is True
        and getattr(settings,"MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED",False) is True
    )
    return {"mpw_trx_easy_enabled":released}
