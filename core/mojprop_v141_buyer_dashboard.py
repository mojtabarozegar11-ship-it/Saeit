"""Owner-scoped buyer navigation. No invoice issuance or financial writes."""
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache

from prop_firm.plan1_v141_native_checkout import CheckoutRejected, _check_signed_order, _release_enabled
from prop_firm.plan1_v141_native_payment_models import PropV141NativeOrder

_BASE = "/moj-prop-v141/"
_HOSTS = {"mojplaywin.com", "www.mojplaywin.com"}


@login_required
@never_cache
def buyer_dashboard(request):
    if request.method not in ("GET", "HEAD"):
        return HttpResponseNotAllowed(["GET", "HEAD"])
    if (not request.is_secure() or request.get_host().split(":")[0].lower() not in _HOSTS
            or not request.user.is_active):
        raise Http404("Private account unavailable")
    if set(request.GET) - {"page"} or len(request.GET.getlist("page")) > 1:
        raise Http404("Invalid account page")
    page_number = request.GET.get("page", "1")
    if not (page_number.isascii() and page_number.isdecimal()
            and 1 <= len(page_number) <= 6 and int(page_number) >= 1):
        raise Http404("Invalid account page")
    orders = (PropV141NativeOrder.objects.filter(buyer_id=request.user.pk)
              .select_related("native_receipt__book", "native_receipt__state",
                              "native_receipt__settlement")
              .order_by("-created_at", "-pk"))
    paginator = Paginator(orders, 20)
    number = int(page_number)
    if number > paginator.num_pages:
        raise Http404("Invalid account page")
    page = paginator.page(number)
    rows = []
    for order in page:
        try:
            _check_signed_order(order)
        except CheckoutRejected:
            continue
        receipt = getattr(order, "native_receipt", None)
        confirmed = (order.status == "settled" and receipt is not None
                     and receipt.book.owner_id == request.user.pk
                     and receipt.state.challenge_ref == order.reference
                     and receipt.book.state_id == receipt.state_id
                     and receipt.settlement.order_reference == order.reference)
        if confirmed:
            status = "Payment confirmed — simulated record"
        elif receipt is not None or order.status != "issued":
            status = "Requires merchant review"
        elif order.expires_at <= timezone.now():
            status = "Expired"
        else:
            status = "Invoice available" if _release_enabled() else "Payment paused"
        rows.append({
            "reference": order.reference,
            "status": status,
            "issued_at": order.issued_at,
            "invoice_url": _BASE + "payment/" + order.reference + "/" if
                order.status == "issued" and receipt is None or confirmed else "",
            "statement_url": _BASE + "statement/" + order.reference + "/" if
                confirmed and getattr(settings, "MOJ_PROP_V141_PORTFOLIO_ENABLED", False) is True else "",
        })
    response = render(request, "mojprop/v141-buyer-dashboard.html", {
        "rows": rows, "page": page, "base": _BASE,
    })
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["Pragma"] = "no-cache"
    response["Referrer-Policy"] = "no-referrer"
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    response["Content-Security-Policy"] = (
        "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; "
        "frame-ancestors 'none'; form-action 'self'; connect-src 'none'"
    )
    if request.method == "HEAD":
        response.content = b""
    return response
