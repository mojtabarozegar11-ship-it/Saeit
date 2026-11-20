"""English simulation terminal, never accepts browser-supplied quotes."""
import re
import uuid
from decimal import Decimal, InvalidOperation
from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from .simulation_identity import is_verified_simulation_user
from .simulation_runtime import trading_runtime_ready
from .simulation_event_service import terminal_state, record_command
from .simulation_engine import OrderRequest

def _number(raw):
    if not isinstance(raw, str) or not re.fullmatch(r"[0-9]{1,9}(?:\.[0-9]{1,8})?", raw):
        raise ValueError("Invalid decimal")
    value = Decimal(raw)
    if not value.is_finite() or value <= 0:
        raise ValueError("Positive value required")
    return value

@never_cache
@csrf_protect
@require_http_methods(["GET", "HEAD", "POST"])
def simulation_terminal(request, account_id):
    if (request.get_host().lower() != "mojplaywin.com" or not request.is_secure()
            or not is_verified_simulation_user(request.user)):
        raise Http404
    try:
        state = terminal_state(account_id=account_id, owner=request.user)
    except ValidationError:
        raise Http404
    ready = trading_runtime_ready()
    error = ""
    if request.method == "POST":
        if not ready:
            return HttpResponse("Trading temporarily unavailable", status=503)
        if request.content_type != "application/x-www-form-urlencoded":
            return HttpResponse("Invalid request", status=400)
        data = request.POST
        if any(len(data.getlist(k)) != 1 for k in data):
            return HttpResponse("Invalid request", status=400)
        try:
            command_id = uuid.UUID(data.get("command_id", ""))
            action = data.get("operation")
            kwargs = dict(account_id=account_id, owner=request.user,
                          command_id=command_id, operation=action)
            if action == "submit":
                if not state["active"] or set(data) - {"csrfmiddlewaretoken", "command_id", "operation", "symbol", "side", "quantity", "stop_loss", "take_profit"}:
                    raise ValueError("Order unavailable")
                symbol = data.get("symbol")
                if symbol not in settings.MPW_SIMULATION_ALLOWED_SYMBOLS:
                    raise ValueError("Unsupported instrument")
                kwargs["order"] = OrderRequest(str(command_id), symbol, data.get("side"),
                    _number(data.get("quantity")), stop_loss=_number(data.get("stop_loss")),
                    take_profit=_number(data["take_profit"]) if data.get("take_profit") else None)
            elif action == "close":
                if set(data) - {"csrfmiddlewaretoken", "command_id", "operation", "order_id"}:
                    raise ValueError("Invalid close")
                kwargs["order_id"] = str(uuid.UUID(data.get("order_id", "")))
            else:
                raise ValueError("Unsupported operation")
            record_command(**kwargs)
        except (ValidationError, ValueError, InvalidOperation, KeyError, TypeError):
            error = "Order could not be processed. Check account status and risk limits."
        else:
            return redirect("moj_prop_simulation_terminal", account_id=account_id)
        state = terminal_state(account_id=account_id, owner=request.user)
    context = state | {"account_id": account_id, "runtime_ready": ready,
        "symbols": getattr(settings, "MPW_SIMULATION_ALLOWED_SYMBOLS", ()),
        "command_id": str(uuid.uuid4()), "close_rows": [(p, str(uuid.uuid4())) for p in state["positions"]],
        "error": error}
    response = render(request, "mojplaywin/moj_prop_simulation_terminal.html", context)
    response["X-Robots-Tag"] = "noindex, nofollow"
    response["X-Frame-Options"] = "DENY"
    return response
