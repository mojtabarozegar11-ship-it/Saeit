"""English MojPlayWin checkout; disabled unless all trusted gates pass."""
import json
from hashlib import sha256
from uuid import uuid4
from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError
from django.http import JsonResponse, HttpResponseNotFound
from django.shortcuts import redirect
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.cache import never_cache
from .simulation_invoice_contract import SimulationInvoiceContract, REQUIRED_GATES
from .simulation_invoice_persistence import persist_simulation_invoice

SALT = "mojprop.sim.checkout.v2"

def checkout_context(request):
    if (request.get_host().lower() != "mojplaywin.com" or not request.is_secure()
            or getattr(settings, "MPW_SIMULATION_CHECKOUT_ENABLED", False) is not True
            or not request.user.is_authenticated or not request.user.is_active):
        return {}
    verifier = getattr(settings, "MPW_SIMULATION_EMAIL_VERIFIER", None)
    if not callable(verifier) or verifier(request.user) is not True:
        return {}
    terms = getattr(settings, "MPW_SIMULATION_TERMS_TEXT", "")
    digest = getattr(settings, "MPW_SIMULATION_TERMS_DIGEST", "")
    if not isinstance(terms, str) or not terms.strip() or sha256(terms.encode()).hexdigest() != digest:
        return {}
    contract = SimulationInvoiceContract(getattr(settings, "MPW_SIMULATION_RECIPIENT", ""), digest)
    gates = {key: getattr(settings, "MPW_SIMULATION_" + key.upper(), False) for key in REQUIRED_GATES}
    try:
        contract.release(gates)
    except ValueError:
        return {}
    return {"simulation_checkout_ready": True, "simulation_terms": terms,
            "simulation_terms_digest": digest, "simulation_contract": contract,
            "simulation_gates": gates}

def checkout_page_context(request):
    ctx = checkout_context(request)
    if not ctx:
        return {}
    token = signing.dumps({"owner": str(request.user.pk), "contract": ctx["simulation_contract"].digest(),
                           "order_ref": "SIM-" + uuid4().hex}, salt=SALT)
    return {key: ctx[key] for key in ("simulation_checkout_ready", "simulation_terms",
                                     "simulation_terms_digest")} | {"simulation_checkout_token": token}

@never_cache
@require_POST
@csrf_protect
def start_simulation_checkout(request):
    ctx = checkout_context(request)
    if not ctx:
        return HttpResponseNotFound()
    try:
        if request.content_type == "application/json":
            if len(request.body) > 8192:
                raise ValueError()
            data = json.loads(request.body)
        elif request.content_type == "application/x-www-form-urlencoded":
            data = request.POST
            if any(len(data.getlist(k)) != 1 for k in data):
                raise ValueError()
        else:
            raise ValueError()
        if not hasattr(data, "get") or data.get("accept_terms") not in (True, "yes"):
            raise ValueError()
        contract = ctx["simulation_contract"]
        if data.get("terms_digest") != contract.terms_digest:
            raise ValueError()
        token = signing.loads(data.get("checkout_token", ""), salt=SALT, max_age=1800)
        if token.get("owner") != str(request.user.pk) or token.get("contract") != contract.digest():
            raise ValueError()
        invoice = persist_simulation_invoice(order_ref=token["order_ref"],
                    buyer_email=request.user.email, contract=contract, gates=ctx["simulation_gates"],
                    buyer_terms_acceptance=True)
    except (ValueError, ValidationError, UnicodeError, signing.BadSignature, TypeError, KeyError):
        return JsonResponse({"error": "Checkout unavailable or invalid request"}, status=400)
    result = {"order_ref": invoice.order_ref, "network": invoice.network,
              "amount_sun": invoice.amount_sun, "recipient": invoice.recipient,
              "status": invoice.status}
    if request.content_type == "application/x-www-form-urlencoded":
        return redirect("moj_prop_simulation_invoice", order_ref=invoice.order_ref)
    return JsonResponse(result, status=201)
