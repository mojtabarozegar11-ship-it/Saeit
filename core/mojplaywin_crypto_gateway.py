"""Fail-closed, host-isolated native ETH/TRX checkout for MojPlayWin only."""
import re
import secrets
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.views import LoginView
from django.db import IntegrityError, transaction
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST
from .models import LedgerEntry, Order, OrderItem, PaymentIntent
from .mojplaywin_crypto_models import MojCryptoInvoice, MojCryptoOffer
from .mojplaywin_chain_verify import VerificationError, _tron_address_hex, verify_eth, verify_trx


HOSTS = {"mojplaywin.com", "www.mojplaywin.com"}
DENOMINATORS = {"ETH": Decimal(10) ** 18, "TRX": Decimal(10) ** 6}
HASH_RE = re.compile(r"^(?:0x)?[0-9a-fA-F]{64}$")


def _guard(request):
    if request.get_host().split(":")[0].lower() not in HOSTS:
        raise Http404
    if not getattr(settings, "MOJPLAYWIN_CRYPTO_ENABLED", False):
        raise Http404


def configured(asset):
    if asset == "ETH":
        address = getattr(settings, "MOJPLAYWIN_ETH_ADDRESS", "").strip()
        rpc = getattr(settings, "MOJPLAYWIN_ETH_RPC_URL", "").strip()
        return bool(re.fullmatch(r"0x[0-9a-fA-F]{40}", address) and rpc.startswith("https://"))
    if asset == "TRX":
        address = getattr(settings, "MOJPLAYWIN_TRX_ADDRESS", "").strip()
        try:
            _tron_address_hex(address)
            return True
        except VerificationError:
            return False
    return False


def _address(asset):
    if not configured(asset):
        raise Http404("Merchant payment network is not configured.")
    return getattr(settings, "MOJPLAYWIN_" + asset + "_ADDRESS")


def _private_file(offer):
    root = getattr(settings, "MOJPLAYWIN_PRIVATE_ASSET_ROOT", "")
    rel = offer.private_file or ""
    if not root or not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
        raise Http404("Private product file is not configured.")
    root_path = Path(root).resolve()
    if not root_path.is_absolute():
        raise Http404
    path = (root_path / rel).resolve()
    if not path.is_relative_to(root_path) or not path.is_file():
        raise Http404("Private product file unavailable.")
    return path


def available_offers():
    if not getattr(settings, "MOJPLAYWIN_CRYPTO_ENABLED", False):
        return []
    offers = MojCryptoOffer.objects.select_related("product").filter(active=True, product__active=True, product__knowledge_article__published=True)
    return [x for x in offers if configured(x.asset) and _file_ready(x)]


def _file_ready(offer):
    try:
        _private_file(offer)
        return True
    except Http404:
        return False


def _buyer(request):
    if not request.user.is_authenticated:
        return redirect("/checkout/crypto/login/?next=" + request.path)
    return None


@require_http_methods(["GET", "POST"])
def signin(request):
    _guard(request)
    return LoginView.as_view(template_name="mojplaywin/crypto_login.html", redirect_authenticated_user=True, next_page="/store/")(request)


@require_http_methods(["GET", "POST"])
def signup(request):
    _guard(request)
    form = UserCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save()
        login(request, user)
        return redirect("/store/")
    return render(request, "mojplaywin/crypto_signup.html", {"form": form})


@require_http_methods(["GET", "POST"])
def buy(request, offer_id):
    _guard(request)
    auth = _buyer(request)
    if auth:
        return auth
    offer = get_object_or_404(
        MojCryptoOffer.objects.select_related("product"),
        pk=offer_id, active=True, product__active=True, product__knowledge_article__published=True,
    )
    destination = _address(offer.asset)
    _private_file(offer)  # Never sell a missing digital download.
    if request.method == "GET":
        return render(request, "mojplaywin/crypto_buy.html", {
            "offer": offer, "amount": f"{int(offer.atomic_amount) / DENOMINATORS[offer.asset]:f}",
        })
    if int(offer.atomic_amount) <= 0 or offer.product.price <= 0:
        return HttpResponse("Product pricing is invalid.", status=409)
    with transaction.atomic():
        order = Order.objects.create(
            customer=request.user, total=offer.product.price,
            currency=offer.product.currency, status="pending",
        )
        OrderItem.objects.create(
            order=order, product=offer.product, quantity=1,
            unit_price=offer.product.price, currency=offer.product.currency,
        )
        # A small unique atomic suffix binds the on-chain transfer to an invoice,
        # preventing accidental allocation when buyers purchase similarly priced items.
        # At most 0.009999 TRX or 9999 wei is added, disclosed on the invoice.
        quote = int(offer.atomic_amount) + (order.pk % 9999) + 1
        if MojCryptoInvoice.objects.filter(
            asset=offer.asset, atomic_amount=quote,
            status__in=["awaiting_payment", "confirming"],
            expires_at__gt=timezone.now(),
        ).exists():
            transaction.set_rollback(True)
            return HttpResponse("Checkout collision. Try again later.", status=409)
        invoice = MojCryptoInvoice.objects.create(
            order=order, offer=offer, asset=offer.asset,
            atomic_amount=str(quote), merchant_address=destination,
            expires_at=timezone.now() + timedelta(minutes=30),
        )
        PaymentIntent.objects.create(
            order=order, amount=order.total, currency=order.currency,
            status="gateway_pending", provider="onchain-" + offer.asset.lower(),
            idempotency_key="moj-crypto-" + str(invoice.token),
        )
    return redirect("moj_crypto_invoice", token=invoice.token)


def _owner_invoice(request, token):
    _guard(request)
    auth = _buyer(request)
    if auth:
        return None, auth
    return get_object_or_404(
        MojCryptoInvoice.objects.select_related("order", "offer__product"),
        token=token, order__customer=request.user,
    ), None


@require_http_methods(["GET"])
def invoice_view(request, token):
    invoice, auth = _owner_invoice(request, token)
    if auth:
        return auth
    amount = Decimal(invoice.atomic_amount) / DENOMINATORS[invoice.asset]
    return render(request, "mojplaywin/crypto_invoice.html", {
        "invoice": invoice, "amount": f"{amount:f}", "expired": timezone.now() > invoice.expires_at,
    })


def _verify_invoice(invoice, tx_hash):
    if invoice.asset == "ETH":
        return verify_eth(
            tx_hash, invoice.merchant_address, invoice.atomic_amount,
            settings.MOJPLAYWIN_ETH_RPC_URL,
            min_conf=1,
        )
    if invoice.asset == "TRX":
        return verify_trx(
            tx_hash, invoice.merchant_address, invoice.atomic_amount,
            api_key=settings.MOJPLAYWIN_TRONGRID_API_KEY,
            min_conf=1,
        )
    raise VerificationError("Unsupported payment asset.")


def settle(invoice_id, tx_hash):
    """Reconcile an order only after independently validating settled chain data."""
    candidate = MojCryptoInvoice.objects.select_related("order").get(pk=invoice_id)
    if not HASH_RE.fullmatch(tx_hash):
        raise VerificationError("Transaction hash must be 64 hex digits.")
    tx_hash = tx_hash.lower().removeprefix("0x")
    canonical = ("0x" if candidate.asset == "ETH" else "") + tx_hash
    if candidate.status == "paid":
        if candidate.tx_hash == canonical:
            return candidate
        raise VerificationError("Order already settled by another transfer.")
    if candidate.tx_hash and candidate.tx_hash != canonical:
        raise VerificationError("Order already bound to another transfer.")
    proof = _verify_invoice(candidate, canonical)
    with transaction.atomic():
        invoice = MojCryptoInvoice.objects.select_for_update().select_related("order").get(pk=invoice_id)
        if invoice.status == "paid":
            if invoice.tx_hash == canonical:
                return invoice
            raise VerificationError("Order already settled.")
        if invoice.tx_hash and invoice.tx_hash != canonical:
            raise VerificationError("Transaction changed.")
        # Reconcile by MINED TIME, not by when the buyer submits the hash.
        # This also stops claims made with an old transaction at a recycled quote.
        if not isinstance(proof.timestamp_ms, int) or proof.timestamp_ms <= 0:
            raise VerificationError("On-chain block timestamp could not be verified.")
        window_start = int(invoice.created_at.timestamp() * 1000) - 60000
        window_end = int(invoice.expires_at.timestamp() * 1000) + 60000
        now_ms = int(timezone.now().timestamp() * 1000)
        if not window_start <= proof.timestamp_ms <= window_end or proof.timestamp_ms > now_ms + 120000:
            raise VerificationError("Transfer was not mined during the invoice payment window.")
        if MojCryptoInvoice.objects.filter(tx_hash=canonical).exclude(pk=invoice.pk).exists():
            raise VerificationError("This transfer was already used.")
        required = (
            settings.MOJPLAYWIN_ETH_CONFIRMATIONS if invoice.asset == "ETH"
            else settings.MOJPLAYWIN_TRX_CONFIRMATIONS
        )
        if not isinstance(required, int) or required < 1:
            raise VerificationError("Confirmation policy is not configured safely.")
        if proof.confirmations < required:
            invoice.tx_hash = canonical
            invoice.status = "confirming"
            invoice.confirmed_block = proof.height
            invoice.last_error = "Awaiting additional network confirmations."
            invoice.save(update_fields=["tx_hash", "status", "confirmed_block", "last_error", "updated_at"])
            return invoice
        invoice.tx_hash = canonical
        invoice.status = "paid"
        invoice.verified_at = timezone.now()
        invoice.confirmed_block = proof.height
        invoice.last_error = ""
        invoice.save(update_fields=["tx_hash", "status", "verified_at", "confirmed_block", "last_error", "updated_at"])
        order = invoice.order
        if order.status != "pending":
            raise VerificationError("Order is no longer awaiting payment.")
        order.status = "paid"
        order.save(update_fields=["status", "updated_at"])
        intent = PaymentIntent.objects.select_for_update().get(order=order, provider="onchain-" + invoice.asset.lower())
        intent.status = "succeeded"
        intent.provider_reference = canonical
        intent.save(update_fields=["status", "provider_reference", "updated_at"])
        LedgerEntry.objects.create(
            order=order, payment_intent=intent, entry_type="payment",
            amount=order.total, currency=order.currency,
            reference=f"onchain:{invoice.asset}:{canonical}",
            metadata={"network": invoice.asset, "atomic_amount": str(invoice.atomic_amount), "tx_hash": canonical, "block": proof.height},
        )
    return invoice


@require_POST
def submit_tx(request, token):
    invoice, auth = _owner_invoice(request, token)
    if auth:
        return auth
    tx_hash = str(request.POST.get("tx_hash", "")).strip()
    if not HASH_RE.fullmatch(tx_hash):
        return HttpResponse("Invalid transaction identifier.", status=400)
    try:
        settle(invoice.pk, tx_hash)
    except VerificationError as exc:
        # No payment is credited from browser input, a screenshot, or an unconfirmed transfer.
        return render(request, "mojplaywin/crypto_invoice.html", {
            "invoice": invoice, "amount": f"{Decimal(invoice.atomic_amount) / DENOMINATORS[invoice.asset]:f}",
            "expired": timezone.now() > invoice.expires_at, "error": str(exc),
        }, status=409)
    except IntegrityError:
        return HttpResponse("Transaction is already assigned. Contact support.", status=409)
    return redirect("moj_crypto_invoice", token=invoice.token)


@require_http_methods(["GET"])
def download(request, token):
    invoice, auth = _owner_invoice(request, token)
    if auth:
        return auth
    if invoice.status != "paid" or invoice.order.status != "paid":
        raise Http404
    path = _private_file(invoice.offer)
    response = FileResponse(path.open("rb"), as_attachment=True, filename=path.name)
    response["Cache-Control"] = "private, no-store"
    return response
