"""English-only public Starter30 checkout views."""
from __future__ import annotations

from html import escape

from django.conf import settings
from django.http import Http404, HttpResponse
from django.middleware.csrf import get_token
from django.views.decorators.http import require_http_methods

def _record_funnel_event(request, event_name: str) -> None:
    """Best-effort first-party funnel measurement; never block checkout."""
    try:
        from core.commerce_funnel import record_funnel_event
        record_funnel_event(request, event_name)
    except Exception:
        return


def _funnel_hidden_fields(request) -> str:
    fields = []
    for name in ("utm_source", "utm_medium", "utm_campaign", "utm_content"):
        value = request.GET.get(name, "") or request.POST.get(name, "")
        value = str(value).strip()[:80]
        fields.append(
            f"<input type='hidden' name='{name}' value='{escape(value, quote=True)}'>"
        )
    return "".join(fields)


def _buyer_portal_link() -> str:
    """Only show private learning access when all independent owner holds pass."""
    flags = (
        "MPW_MOJPROP_BUYER_PORTAL_APPROVED",
        "MPW_MOJPROP_BUYER_TRANSACTIONAL_EMAIL_APPROVED",
        "MPW_MOJPROP_BUYER_SHARED_RATE_LIMIT_VERIFIED",
        "MPW_MOJPROP_BUYER_DELIVERY_RECOVERY_VERIFIED",
    )
    if all(getattr(settings, flag, False) is True for flag in flags):
        return ("<p><a href='/mojprop-buyer-portal/'>"
                "Access your verified private Starter30 learning account</a></p>")
    return ""


from .starter30_live import (
    Starter30PaymentRejected,
    Starter30ReleaseClosed,
    invoice_status,
    issue_invoice,
    settle_invoice,
    verify_pre_invoice_configuration,
)


def _page(request, title: str, body: str) -> HttpResponse:
    token = escape(get_token(request))
    return HttpResponse(
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{escape(title)} | Moj Prop</title>"
        "<style>body{background:#080d13;color:#f7f3e9;font:16px/1.6 system-ui;max-width:820px;margin:40px auto;padding:0 20px}"
        "main{background:#131c27;border:1px solid #344251;border-radius:16px;padding:28px}"
        "label{display:block;margin:14px 0 6px}input:not([type=checkbox]){width:100%;padding:11px;border-radius:8px;border:1px solid #667;background:#0d141d;color:#fff;box-sizing:border-box}"
        "input[type=checkbox]{width:auto;vertical-align:middle;margin-right:8px;accent-color:#e9c57b}"
        "button{margin-top:18px;padding:12px 18px;border:0;border-radius:24px;background:#e9c57b;font-weight:800}"
        ".warn{background:#352621;padding:14px;border-left:4px solid #f7c3aa}.ok{background:#173b2c;padding:14px;border-left:4px solid #7de2a8}"
        "code{word-break:break-all}</style></head><body><main>"
        + body
        + "</main></body></html>"
    )


def _closed(request):
    return _page(
        request,
        "Starter30 unavailable",
        "<h1>Starter30 checkout</h1><div class='warn'>Payment is not available at this moment. No transfer should be sent.</div>",
    )


def _form(request, invoice_ref: str | None = None) -> str:
    token = escape(get_token(request))
    if invoice_ref:
        return (
            f"<form method='post' action='/mojprop-starter30-checkout/'>"
            f"<input type='hidden' name='csrfmiddlewaretoken' value='{token}'>"
            f"<input type='hidden' name='action' value='settle'>"
            f"<input type='hidden' name='invoice_ref' value='{escape(invoice_ref)}'>"
            + _funnel_hidden_fields(request)
            + "<label for='txid'>TRON transaction ID</label>"
            "<input id='txid' name='txid' required pattern='[A-Fa-f0-9]{64}' autocomplete='off'>"
            "<button type='submit'>Verify 30 TRX payment</button></form>"
        )
    return (
        "<form method='post' action='/mojprop-starter30-checkout/'>"
        f"<input type='hidden' name='csrfmiddlewaretoken' value='{token}'>"
        "<input type='hidden' name='action' value='issue'>"
        + _funnel_hidden_fields(request)
        + "<label for='email'>Email for the isolated simulation identity</label>"
        "<input id='email' name='email' type='email' required autocomplete='email'>"
        "<label for='payer_address'>Your sending TRON wallet address (optional)</label>"
        "<input id='payer_address' name='payer_address' autocomplete='off'>"
        "<small>If left blank, the verified on-chain sender is recorded after payment.</small>"
        "<label><input type='checkbox' name='terms' value='yes' required> "
        "I understand this is simulated trading: no customer capital or real broker account is involved. Every profit I earn after a successful pass is paid in full: 100% of my realized profit is transferred after verification under the published payout rules; no profit or pass result is guaranteed.</label>"
        "<p><a href='/moj-prop/rules/'>Full simulation rules</a> · "
        "<a href='/moj-prop/payment/'>Payment, reward and refund disclosures</a></p>"
        "<button type='submit'>Create 30 TRX invoice</button></form>"
    )


@require_http_methods(["GET", "POST"])
def starter30_checkout(request):
    if request.method == "GET":
        try:
            from .starter30_live import release_is_open
            if not release_is_open():
                return _closed(request)
            verify_pre_invoice_configuration()  # no DB write or remote RPC call
            _record_funnel_event(request, "begin_checkout")
            return _page(
                request,
                "Starter30 checkout",
                "<h1>Moj Prop Starter30</h1><p>Exact price: <strong>30 TRX</strong>. "
                "This remains a simulated challenge with a virtual 1,000 USD balance. Every profit earned after a successful pass is paid in full: 100% of the trader's realized profit is transferred after verification under the published payout rules.</p>"
                "<div class='warn'>Send only after this server issues your unique invoice. "
                "The receiver is owner-approved. Binding your sending wallet is optional; if omitted, the verified on-chain sender is recorded after payment.</div>"
                "<p><strong>Cancellation and refund:</strong> before transaction verification, no payment is credited. "
                "A verified payment that cannot be matched because of a server failure remains in manual review; "
                "if the service cannot be delivered, refund is sent to the verified sending wallet.</p>"
                + _form(request)
            )
        except Exception:
            return _closed(request)
    try:
        action = request.POST.get("action")
        if action == "issue":
            issued = issue_invoice(
                email=request.POST.get("email", ""),
                payer_address=request.POST.get("payer_address", "").strip(),
                terms_accepted=request.POST.get("terms") == "yes",
            )
            _record_funnel_event(request, "invoice_created")
            return _page(
                request,
                "Starter30 invoice",
                "<h1>Invoice issued</h1><div class='ok'><p>Exact amount: <strong>30 TRX</strong></p>"
                f"<p>Send to: <code>{escape(issued.recipient)}</code></p>"
                f"<p>Invoice: <code>{escape(issued.invoice_ref)}</code></p>"
                f"<p>Expires: <code>{escape(issued.expires_at.isoformat())}</code></p></div>"
                "<p>After the transfer is solidified, submit its transaction ID below. "
                "The account is created only after two independent provider proofs agree.</p>"
                + _form(request, issued.invoice_ref)
            )
        if action == "settle":
            result = settle_invoice(
                invoice_ref=request.POST.get("invoice_ref", ""),
                txid=request.POST.get("txid", ""),
            )
            _record_funnel_event(request, "payment_confirmed")
            # A paid and activated database row is NOT proof that the buyer
            # authenticated or received their learning journal/scorecard.
            # Do not manufacture delivery_success before actual delivery.
            return _page(
                request,
                "Starter30 activated",
                "<h1>Simulation activated</h1><div class='ok'>"
                f"<p>Account: <code>{escape(result['account_ref'])}</code></p>"
                f"<p>Virtual balance: <strong>USD {escape(result['simulation_balance_usd'])}</strong></p>"
                f"<p>Transaction: <code>{escape(result['txid'])}</code></p>"
                "</div><p>This account is simulated only; no customer capital or real broker account was created. Every profit earned after a successful pass is paid in full: 100% of the trader's realized profit is transferred after verification under the published payout rules.</p>"
                + _buyer_portal_link(),
            )
        raise Starter30PaymentRejected("unsupported checkout action")
    except (Starter30PaymentRejected, Starter30ReleaseClosed, LookupError, ValueError) as error:
        return _page(
            request,
            "Starter30 payment review",
            f"<h1>Payment not credited</h1><div class='warn'>{escape(str(error))}</div>"
            "<p>No simulation account was created. Check the invoice and transaction ID.</p>",
        )


@require_http_methods(["GET"])
def starter30_status(request):
    invoice_ref = request.GET.get("invoice", "")
    try:
        result = invoice_status(invoice_ref)
    except Exception:
        raise Http404
    return _page(
        request,
        "Starter30 payment status",
        f"<h1>Payment status</h1><p>Invoice: <code>{escape(result['invoice_ref'])}</code></p>"
        f"<p>Status: <strong>{escape(result['status'])}</strong></p>"
        f"<p>Amount: <strong>{result['amount_sun'] / 1000000:g} TRX</strong></p>"
        + (f"<p>Transaction: <code>{escape(result['txid'])}</code></p>" if result["txid"] else ""),
    )
