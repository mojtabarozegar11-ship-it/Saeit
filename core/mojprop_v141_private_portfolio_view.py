"""Owner-only VIEW of one MOJ-PROP-01 virtual account statement.

NO customer-facing write/trade endpoint is installed. This route is disabled
by default until a legally approved, independently rehearsed 0010 migration,
source archive, auth review and explicit owner deployment approval exist.
The private website user's session can inspect ONLY their own virtual book.
No broker references, passwords, wallet identifiers or other users' balances
can be exposed by this view.
"""
import re

from django.conf import settings
from django.http import Http404, HttpResponseNotAllowed, JsonResponse
from django.views.decorators.cache import never_cache
from django.contrib.auth.decorators import login_required

from prop_firm.plan1_v141_virtual_tenant_models import PropV141VirtualBook

_ALLOWED_HOSTS = frozenset(("mojplaywin.com", "www.mojplaywin.com"))
_REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}\Z")


@login_required
@never_cache
def moj_prop_v141_private_portfolio(request, challenge_ref):
    """Read-only tenant-scoped display of realized demo P&L, not live equity."""
    if getattr(settings, "MOJ_PROP_V141_PORTFOLIO_ENABLED", False) is not True:
        raise Http404("Private preview not enabled")
    try:
        host = request.get_host().split(":", 1)[0].lower()
    except Exception as exc:
        raise Http404("Unrecognized host") from exc
    if host not in _ALLOWED_HOSTS or request.is_secure() is not True:
        raise Http404("Only authorized MojPlayWin HTTPS is allowed")
    if request.method not in ("GET", "HEAD"):
        return HttpResponseNotAllowed(["GET", "HEAD"])
    if request.META.get("QUERY_STRING", ""):
        raise Http404("Unexpected query")
    if not _REF.fullmatch(challenge_ref):
        raise Http404("Invalid opaque challenge reference")
    # Query MUST be scoped by authenticated owner AND exact challenge.
    book = (PropV141VirtualBook.objects
            .filter(owner_id=request.user.pk,
                    state__challenge_ref=challenge_ref)
            .select_related("state").first())
    if book is None or book.owner_id != request.user.pk:
        raise Http404("No matching private challenge")
    # No inferred equity, proof of trading, demo pass, capital allocation or
    # funding: these require independently reconciled equity snapshots.
    payload = dict(
        product="MOJ-PROP-01",
        contract_status="DRAFT_NO_PAID_ENROLLMENT",
        challenge_ref=book.state.challenge_ref,
        stage_max_unlocked=book.max_unlocked_stage,
        recorded_fill_events=book.last_sequence,
        completely_closed_virtual_positions=book.last_fully_closed_count,
        realized_virtual_net_usd=str(book.last_realized_net_usd),
        realized_only_no_floating_equity=True,
        user_has_independent_broker_account=False,
        company_broker_trade_receipt_verified=False,
        independently_reconciled_market_marks=False,
        paid_enrollment_active=False,
        live_orders_enabled=False,
        payouts_enabled=False,
    )
    response = JsonResponse(payload)
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["Pragma"] = "no-cache"
    response["Referrer-Policy"] = "no-referrer"
    response["X-Frame-Options"] = "DENY"
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    response["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    return response
