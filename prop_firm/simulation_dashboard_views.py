"""Private simulation dashboard; no representation of live brokerage balances."""
from django.http import Http404
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe
from .simulation_identity import is_verified_simulation_user
from .models import PropSimulationAccount, PropPlan1Invoice
from .simulation_invoice_contract import PRODUCT_CODE, SUPPORTED_CONTRACT_VERSIONS
from .simulation_checkout_views import checkout_context, retry_checkout_page_context

@never_cache
@require_safe
def simulation_dashboard(request):
    if (request.get_host().lower() != "mojplaywin.com" or not request.is_secure()
            or not is_verified_simulation_user(request.user)):
        raise Http404
    invoices = PropPlan1Invoice.objects.filter(
        simulation_owner__owner=request.user, buyer_email=request.user.email,
        product_code=PRODUCT_CODE, contract_version__in=SUPPORTED_CONTRACT_VERSIONS,
    ).order_by("-created_at")[:50]
    accounts = PropSimulationAccount.objects.filter(
        owner=request.user, invoice__simulation_owner__owner=request.user,
        invoice__buyer_email=request.user.email, invoice__product_code=PRODUCT_CODE,
        invoice__contract_version__in=SUPPORTED_CONTRACT_VERSIONS, invoice__status="paid",
    ).order_by("-created_at")[:50]
    # Only the explicitly selected, owned account is replayed. Never scan every
    # customer's event ledger to render a dashboard.
    requested = request.GET.getlist("retry")
    retry_available = bool(checkout_context(request))
    retry = {}
    if retry_available and len(requested) == 1:
        raw = requested[0]
        if raw.isascii() and raw.isdecimal() and 1 <= len(raw) <= 19:
            account_id = int(raw)
            if 0 < account_id <= 9223372036854775807 and str(account_id) == raw:
                retry = retry_checkout_page_context(request, account_id)
    response = render(request, "mojplaywin/moj_prop_simulation_dashboard.html",
                      {"invoices": invoices, "accounts": accounts,
                       "retry_available": retry_available, "retry_checkout": retry,
                       "retry_requested": bool(requested)})
    response["X-Robots-Tag"] = "noindex, nofollow"
    response["X-Frame-Options"] = "DENY"
    return response
