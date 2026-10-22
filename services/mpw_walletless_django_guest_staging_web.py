"""No-registration TRX customer journey on isolated staging MariaDB only.

An anonymous browser submits one CSRF-protected POST. A unique password-disabled
Django buyer is created in a test_ DB with a signed, HTTP-only buyer cookie.
The paid-only status and private download reuse the genuine Django financial
evidence gates. No form asks for email, password, sender address or tx hash.
NEVER register these URL patterns on the public MojPlayWin Passenger site.
"""
from __future__ import annotations
from types import SimpleNamespace
from django.db import transaction
from django.http import Http404
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET,require_POST
from django.views.decorators.cache import never_cache

from services.mpw_trx_walletless_core import PaymentHold
from services.mpw_walletless_django_test_bridge import _test_only_guard
from services.mpw_walletless_django_guest_claim import (
    COOKIE_NAME,create_guest_buyer,read_guest_buyer,install_guest_cookie,
)
from services.mpw_walletless_django_staging_web import (
    _start_order,_show_invoice,_invoice_status,_download_paid
)
from services.mpw_walletless_django_guest_handoff import (
    create_wallet_handoff,redeem_wallet_handoff
)

def _authenticate_guest(request,*,create=False):
    from django.conf import settings
    from django.db import connection
    try:_test_only_guard(settings,connection)
    except PaymentHold as exc:
        raise Http404("Guest checkout is unavailable") from exc
    host=request.get_host().lower().split(":")[0]
    if not request.is_secure() or not host.endswith((".test",".invalid")):
        raise Http404("Only secure isolated checkout staging is permitted")
    previous=getattr(request,"user",None)
    if previous is not None and getattr(previous,"is_authenticated",False):
        raise Http404("Use the regular signed-in checkout")
    cookie=request.COOKIES.get(COOKIE_NAME)
    buyer_id=read_guest_buyer(cookie)
    issued=None
    if buyer_id is None and create:
        remote=request.META.get("REMOTE_ADDR")
        try:
            buyer_id,issued=create_guest_buyer(remote_ip=remote)
        except PaymentHold as exc:
            raise Http404("Anonymous checkout capacity reached") from exc
    if buyer_id is None:
        raise Http404("Unrecognized or expired secure guest receipt")
    # This is NOT login(). The short request-scoped principal is reconstructed
    # only AFTER signing-key, DB token-digest and disabled-password checks.
    request.user=SimpleNamespace(
        pk=buyer_id,is_authenticated=True,is_active=True,is_guest_claim=True,
    )
    return issued

@never_cache
@csrf_protect
@require_POST
def guest_start_order(request,product_id):
    with transaction.atomic():
        issued=_authenticate_guest(request,create=True)
        response=_start_order(request,product_id)
        if issued is not None:
            install_guest_cookie(response,issued)
        response["Vary"]="Cookie"
        return response

@never_cache
@require_GET
def guest_show_invoice(request,invoice_id):
    _authenticate_guest(request)
    try:
        path=create_wallet_handoff(invoice_id=invoice_id,buyer_id=request.user.pk)
    except PaymentHold:
        # Too many mobile launches: do NOT offer a dead link. QR still works.
        path=None
    return _show_invoice(
        request,invoice_id,guest_checkout=True,wallet_handoff_path=path,
    )

@never_cache
@require_GET
def guest_invoice_status(request,invoice_id):
    _authenticate_guest(request)
    return _invoice_status(request,invoice_id)

@never_cache
@require_GET
def guest_redeem_wallet_link(request,token):
    """One-time wallet-browser bearer link, no existing cookie required."""
    from django.conf import settings
    from django.db import connection
    from django.http import HttpResponseRedirect
    try:_test_only_guard(settings,connection)
    except PaymentHold as exc:
        raise Http404("Wallet handoff is not available") from exc
    host=request.get_host().lower().split(":")[0]
    if not request.is_secure() or not host.endswith((".test",".invalid")):
        raise Http404
    try:
        invoice_id,new_cookie=redeem_wallet_handoff(token)
    except PaymentHold as exc:
        raise Http404("Expired or already-used wallet link") from exc
    result=HttpResponseRedirect(f"/commerce/trx-easy/invoice/{invoice_id}/")
    install_guest_cookie(result,new_cookie)
    result["Cache-Control"]="no-store, private, max-age=0"
    result["Referrer-Policy"]="no-referrer"
    result["X-Robots-Tag"]="noindex, nofollow"
    return result

@never_cache
@require_GET
def guest_download_paid(request,invoice_id):
    _authenticate_guest(request)
    return _download_paid(request,invoice_id)

# Exclusive staging routing. The guest and registered routes cannot be
# mounted concurrently under identical paths. A combined routing dispatcher
# must be audited before any future public release.
STAGING_GUEST_URLPATTERNS=(
    ("commerce/trx-easy/start/<int:product_id>/",guest_start_order),
    ("commerce/trx-easy/invoice/<int:invoice_id>/",guest_show_invoice),
    ("commerce/trx-easy/claim/<str:token>/",guest_redeem_wallet_link),
    ("commerce/trx-easy/status/<int:invoice_id>/",guest_invoice_status),
    ("commerce/trx-easy/download/<int:invoice_id>/",guest_download_paid),
)
