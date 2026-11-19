"""Private simulation dashboard; no representation of live brokerage balances."""
from django.http import Http404
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe
from .simulation_identity import is_verified_simulation_user
from .models import PropSimulationAccount, PropPlan1Invoice
from .simulation_invoice_contract import PRODUCT_CODE, CONTRACT_VERSION

@never_cache
@require_safe
def simulation_dashboard(request):
    if (request.get_host().lower() != "mojplaywin.com" or not request.is_secure()
            or not is_verified_simulation_user(request.user)):
        raise Http404
    invoices = PropPlan1Invoice.objects.filter(
        simulation_owner__owner=request.user, buyer_email=request.user.email,
        product_code=PRODUCT_CODE, contract_version=CONTRACT_VERSION,
    ).order_by("-created_at")[:50]
    accounts = PropSimulationAccount.objects.filter(
        owner=request.user, invoice__simulation_owner__owner=request.user,
        invoice__buyer_email=request.user.email, invoice__product_code=PRODUCT_CODE,
        invoice__contract_version=CONTRACT_VERSION, invoice__status="paid",
    ).order_by("-created_at")[:50]
    response = render(request, "mojplaywin/moj_prop_simulation_dashboard.html",
                      {"invoices": invoices, "accounts": accounts})
    response["X-Robots-Tag"] = "noindex, nofollow"
    response["X-Frame-Options"] = "DENY"
    return response
