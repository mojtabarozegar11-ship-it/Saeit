"""Customer reconciliation: transaction IDs are untrusted hints, never payment proofs."""
import re
from hashlib import sha256
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from .models import PropPlan1Invoice
from .simulation_invoice_contract import PRODUCT_CODE, SUPPORTED_CONTRACT_VERSIONS
from .simulation_tron_reconcile import reconcile_simulation_invoice
from .simulation_checkout_views import checkout_context

def owned_invoice(request, order_ref):
    if request.get_host().lower() != "mojplaywin.com" or not request.is_secure():
        raise Http404
    if not request.user.is_authenticated or not request.user.is_active:
        raise Http404
    verifier = getattr(settings, "MPW_SIMULATION_EMAIL_VERIFIER", None)
    if not callable(verifier) or verifier(request.user) is not True:
        raise Http404
    return get_object_or_404(PropPlan1Invoice, order_ref=order_ref,
                             simulation_owner__owner=request.user, buyer_email=request.user.email, product_code=PRODUCT_CODE,
                             contract_version__in=SUPPORTED_CONTRACT_VERSIONS)

@never_cache
@csrf_protect
@require_http_methods(["GET", "HEAD", "POST"])
def simulation_invoice_detail(request, order_ref):
    invoice = owned_invoice(request, order_ref)
    enabled = getattr(settings, "MPW_SIMULATION_RECONCILIATION_ENABLED", False) is True
    error = ""
    if request.method == "POST":
        if not enabled or invoice.status not in {"pending", "paid"}:
            return HttpResponse("Reconciliation unavailable", status=503)
        if request.content_type != "application/x-www-form-urlencoded":
            return HttpResponse("Invalid form", status=400)
        values = request.POST.getlist("tx_hash")
        if len(values) != 1 or not re.fullmatch(r"[0-9a-fA-F]{64}", values[0]):
            return HttpResponse("Invalid transaction ID", status=400)
        bucket = "mojprop:reconcile:" + sha256(str(request.user.pk).encode()).hexdigest()
        try:
            if not cache.add(bucket, 1, timeout=600) and cache.incr(bucket) > 5:
                return HttpResponse("Please retry later", status=429)
        except Exception:
            return HttpResponse("Verification temporarily unavailable", status=503)
        try:
            reconcile_simulation_invoice(invoice_id=invoice.pk, owner=request.user,
                tx_hash=values[0].lower(), verified_owner_email=request.user.email)
        except ValidationError:
            error = "Payment not yet verified. Check your transaction ID and memo. Do not pay again."
        else:
            return redirect("moj_prop_simulation_invoice", order_ref=invoice.order_ref)
        invoice.refresh_from_db()
    # Preserve past buyer reconciliation even while new sales are suspended.
    context = checkout_context(request) if invoice.status == "pending" and enabled else {}
    contract = context.get("simulation_contract")
    payment_instructions = bool(contract and invoice.purchase_kind == "first"
        and contract.digest() == invoice.contract_digest
        and contract.recipient == invoice.recipient)
    return render(request, "mojplaywin/moj_prop_simulation_invoice.html", {
        "order_ref": invoice.order_ref, "network": invoice.network,
        "amount_sun": invoice.amount_sun, "recipient": invoice.recipient,
        "status": invoice.status, "reconciliation_enabled": enabled, "verification_error": error,
        "show_payment_instructions": payment_instructions,
    })
