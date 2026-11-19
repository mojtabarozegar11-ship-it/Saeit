"""English MojPlayWin checkout; not enabled or mounted by default."""
import json
from uuid import uuid4
from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import JsonResponse, HttpResponseNotFound
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from .simulation_invoice_contract import SimulationInvoiceContract, REQUIRED_GATES
from .simulation_invoice_persistence import persist_simulation_invoice

@require_POST
@csrf_protect
def start_simulation_checkout(request):
    if (request.get_host().lower() != "mojplaywin.com" or not request.is_secure()
            or getattr(settings, "MPW_SIMULATION_CHECKOUT_ENABLED", False) is not True):
        return HttpResponseNotFound()
    if not request.user.is_authenticated or not request.user.is_active:
        return JsonResponse({"error": "Authentication required"}, status=403)
    # No checkout until a trusted email ownership integration is installed.
    verifier = getattr(settings, "MPW_SIMULATION_EMAIL_VERIFIER", None)
    if not callable(verifier) or verifier(request.user) is not True:
        return JsonResponse({"error": "Verified email required"}, status=403)
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict) or data.get("accept_terms") is not True:
            raise ValueError()
        contract = SimulationInvoiceContract(
            getattr(settings, "MPW_SIMULATION_RECIPIENT", ""),
            getattr(settings, "MPW_SIMULATION_TERMS_DIGEST", ""))
        if data.get("terms_digest") != contract.terms_digest:
            raise ValueError()
        gates = {key: getattr(settings, "MPW_SIMULATION_" + key.upper(), False)
                 for key in REQUIRED_GATES}
        invoice = persist_simulation_invoice(order_ref="SIM-" + uuid4().hex,
                    buyer_email=request.user.email, contract=contract, gates=gates,
                    buyer_terms_acceptance=True)
    except (ValueError, ValidationError, UnicodeError):
        return JsonResponse({"error": "Checkout unavailable or invalid request"}, status=400)
    return JsonResponse({"order_ref": invoice.order_ref, "network": invoice.network,
                         "amount_sun": invoice.amount_sun, "recipient": invoice.recipient,
                         "status": invoice.status}, status=201)
