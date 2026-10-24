"""Crown Defender native-TRX payment adapter.

No custody, no private keys, no trial payments, no client-provided prices.
All functions fail closed until separately audited *mainnet* configuration,
merchant ownership, unique recipient and two independent operators are confirmed.
A TxID submitted by a buyer is a lookup hint, never proof of payment.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import secrets

from django.conf import settings
from django.core.cache import cache
from django.db import connection, transaction
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.middleware.csrf import get_token
from django.utils.html import format_html
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from services.mpw_trx_walletless_core import (
    ADDRESS, INVOICE_TTL, NETWORK, TX_ID, PaymentHold, InvoiceIntent,
    issue_intent, verify_two_source_transfer,
)
from services.mpw_tron_independent_solidified_rpc import (
    RpcProvider, verify_distinct_provider_config, query_solidified_transfer,
    query_solidified_head,
)
from services.mpw_crown_trx_discovery import discover_native_candidates

PROVIDER = "mpw_walletless_trx_v1"
AWAITING = "awaiting_chain"
_LOCK = "crown-tron-mainnet-invoices-v1"
SKUS = frozenset(("cd-spectre", "cd-valkyrie", "cd-tempest",
                  "cd-phoenix", "cd-sovereign"))


def _address(value):
    """Validate mainnet address including Base58Check checksum."""
    abc = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    if not isinstance(value, str) or ADDRESS.fullmatch(value) is None:
        raise PaymentHold("Recipient address invalid")
    n = 0
    for char in value:
        n = n * 58 + abc.index(char)
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
    raw = b"\0" * (len(value) - len(value.lstrip("1"))) + raw
    if (len(raw) != 25 or raw[0] != 0x41
            or hashlib.sha256(hashlib.sha256(raw[:21]).digest()).digest()[:4] != raw[21:]):
        raise PaymentHold("Merchant address checksum invalid")
    return value


def _quote_sources():
    first = getattr(settings, "CROWN_TRX_RATE_SOURCE_A", None)
    second = getattr(settings, "CROWN_TRX_RATE_SOURCE_B", None)
    if not callable(first) or not callable(second) or first is second:
        raise PaymentHold("Two independent audited exchange-rate sources are required")
    return first, second


def _quote():
    now = datetime.now(timezone.utc)
    rates = []
    for source in _quote_sources():
        try:
            data = source()  # Must return (Decimal USD/TRX, aware observed_at).
            value, observed = data
            rate = Decimal(str(value))
            age = now - observed.astimezone(timezone.utc)
            if (not rate.is_finite() or rate <= 0 or observed.utcoffset() is None
                    or not timedelta(0) <= age <= timedelta(seconds=90)):
                raise ValueError("bad quote")
            rates.append(rate)
        except (TypeError, ValueError, ArithmeticError, AttributeError) as exc:
            raise PaymentHold("Unavailable or stale independent market quote") from exc
    if (max(rates) - min(rates)) / min(rates) > Decimal("0.02"):
        raise PaymentHold("Independent market quotes disagree")
    return min(rates), now


def _providers():
    data = getattr(settings, "CROWN_TRX_RPC_PROVIDERS", None)
    if type(data) not in (tuple, list) or len(data) != 2:
        raise PaymentHold("Two private mainnet RPC configurations required")
    try:
        a, b = (RpcProvider(**row) for row in data)
        verify_distinct_provider_config(a, b)
        return a, b
    except (TypeError, ValueError, AttributeError) as exc:
        raise PaymentHold("Invalid RPC provider configuration") from exc


def _configuration():
    if not all(getattr(settings, flag, False) is True for flag in (
        "CROWN_STORE_ENABLED", "CROWN_PAYMENT_GATEWAY_APPROVED",
        "CROWN_TRX_INDEPENDENT_OPERATORS_REVIEWED",
        "CROWN_TRX_DEDICATED_RECEIVER_ATTESTED",
        "CROWN_TRX_PAID_END_TO_END_ACCEPTED",
    )):
        raise PaymentHold("Financial release has not been approved")
    if connection.vendor != "mysql" or connection.alias != "default":
        raise PaymentHold("Existing MariaDB is required")
    recipient = _address(getattr(settings, "CROWN_TRX_MERCHANT_RECEIVER", ""))
    if getattr(settings, "CROWN_TRX_AUTO_DISCOVERY_ENABLED", False) is not True:
        raise PaymentHold("Automatic reconciliation requires explicit approval")
    key = getattr(settings, "CROWN_TRX_INDEXER_KEY", "")
    if not isinstance(key, str) or not 10 <= len(key) <= 512:
        raise PaymentHold("Authenticated deposit indexer required")
    providers = _providers()
    _quote_sources()
    return recipient, providers


def mainnet_checkout_ready():
    """A gate, not a claim that a transaction settled."""
    try:
        _configuration()
        return True
    except Exception:
        return False


@contextmanager
def _exclusive_allocation():
    """MariaDB named lock held through the transaction COMMIT."""
    if connection.vendor != "mysql":
        raise PaymentHold("Unique invoice allocation requires MariaDB")
    with connection.cursor() as cursor:
        cursor.execute("SELECT GET_LOCK(%s, 4)", [_LOCK])
        if cursor.fetchone() != (1,):
            raise PaymentHold("Cannot acquire exclusive invoice lock")
        try:
            yield
        finally:
            cursor.execute("SELECT RELEASE_LOCK(%s)", [_LOCK])


def _amount_key(recipient, amount_sun):
    return "wltrx1:" + hashlib.sha256(recipient.encode("ascii")).hexdigest() + ":" + str(amount_sun)


def _pack(invoice):
    doc = {"v": 1, "to": invoice.recipient, "sun": invoice.amount_sun,
           "rate": str(invoice.quote_usd_per_trx),
           "at": invoice.issued_at.astimezone(timezone.utc).isoformat()}
    value = json.dumps(doc, sort_keys=True, separators=(",", ":"))
    if len(value) > 200:
        raise PaymentHold("Invoice exceeds existing financial column")
    return value


def _unpack(intent):
    try:
        if intent.provider != PROVIDER or intent.currency != "USD":
            raise PaymentHold("Wrong invoice provider")
        doc = json.loads(intent.provider_reference)
        if (type(doc) is not dict or set(doc) != {"v", "to", "sun", "rate", "at"}
                or type(doc["v"]) is not int or doc["v"] != 1
                or type(doc["sun"]) is not int or doc["sun"] <= 0):
            raise PaymentHold("Invalid saved invoice")
        receiver = _address(doc["to"])
        issued = datetime.fromisoformat(doc["at"])
        quote = Decimal(str(doc["rate"]))
        if (not issued.tzinfo or issued.utcoffset() is None or not quote.is_finite()
                or quote <= 0 or intent.idempotency_key != _amount_key(receiver, doc["sun"])):
            raise PaymentHold("Invoice fingerprint mismatch")
        return InvoiceIntent(
            order_id=intent.order_id, customer_id=intent.order.customer_id,
            network=NETWORK, recipient=receiver, amount_sun=doc["sun"],
            usd_total=intent.amount, issued_at=issued,
            expires_at=issued + INVOICE_TTL, quote_usd_per_trx=quote,
        )
    except PaymentHold:
        raise
    except (KeyError, TypeError, ValueError, ArithmeticError, OverflowError, AttributeError) as exc:
        raise PaymentHold("Corrupted persisted invoice") from exc


def _product(product_id):
    from core.models import Product
    from core.crown_fleet import SKUS as game_skus
    product = Product.objects.filter(
        pk=product_id, active=True, product_type="game_cosmetic", currency="USD",
    ).first()
    md = product.metadata if product and isinstance(product.metadata, dict) else {}
    if (not product or md.get("crown_sku") not in SKUS
            or md.get("crown_sku") not in game_skus
            or md.get("crown_checkout_verified") is not True
            or md.get("rights_cleared") is not True
            or product.price < Decimal("4.00")
            or Product.objects.filter(active=True, product_type="game_cosmetic",
                   metadata__crown_sku=md["crown_sku"]).count() != 1):
        raise PaymentHold("Game cosmetic not independently approved")
    return product, md["crown_sku"]


def _validate_order(order, intent):
    from core.models import OrderItem
    if (order.customer_id != intent.order.customer_id or order.currency != "USD"
            or intent.amount != order.total or order.total <= 0):
        raise PaymentHold("Payment/order mismatch")
    parts = list(OrderItem.objects.select_related("product").filter(order=order)[:2])
    if len(parts) != 1 or parts[0].quantity != 1:
        raise PaymentHold("Invoice must contain exactly one jet")
    item = parts[0]
    if item.currency != "USD" or item.unit_price != order.total:
        raise PaymentHold("Invoice line-item value mismatch")
    product, _ = _product(item.product_id)
    if product.pk != item.product_id:
        raise PaymentHold("Invoice product invalid")
    return item


def start_crown_checkout(*, buyer_id, product_id):
    """Issue a fresh MariaDB-unique invoice; never trust HTTP price or address."""
    from django.contrib.auth import get_user_model
    from core.models import Order, OrderItem, PaymentIntent
    from core.crown_fleet import owned_skus

    receiver, (node_a, node_b) = _configuration()
    if type(buyer_id) is not int or buyer_id <= 0 or type(product_id) is not int:
        raise PaymentHold("Authenticated buyer and product required")
    product, sku = _product(product_id)
    buyer = get_user_model().objects.get(pk=buyer_id)
    if sku in owned_skus(buyer):
        raise PaymentHold("Jet has already been purchased")
    # Do not issue a payment instruction if either solidity provider is stale.
    query_solidified_head(node_a)
    query_solidified_head(node_b)
    rate, observed_at = _quote()

    with _exclusive_allocation():
        with transaction.atomic():
            # Re-check ownership under the buyer row lock.
            get_user_model().objects.select_for_update().get(pk=buyer_id)
            if sku in owned_skus(buyer):
                raise PaymentHold("Jet already owned")
            # Retry-safe: return the same unexpired pending invoice for this jet.
            pending = PaymentIntent.objects.select_for_update().select_related("order").filter(
                order__customer_id=buyer_id, order__status="pending",
                order__items__product_id=product_id, provider=PROVIDER,
                status=AWAITING,
            ).order_by("-id")[:30]
            for previous in pending:
                try:
                    old = _unpack(previous)
                    if (old.recipient == receiver
                            and datetime.now(timezone.utc) < old.expires_at):
                        return "/commerce/crown/invoice/{}/".format(previous.pk)
                except PaymentHold:
                    continue
            # Prevent unbounded abandoned invoices from authenticated bots.
            if PaymentIntent.objects.filter(
                order__customer_id=buyer_id, provider=PROVIDER,
                created_at__gte=datetime.now(timezone.utc)-timedelta(hours=24),
            ).count() >= 20:
                raise PaymentHold("Daily Crown invoice limit reached")
            product, checked_sku = _product(product_id)
            if checked_sku != sku:
                raise PaymentHold("Product changed")
            order = Order.objects.create(
                customer_id=buyer_id, total=product.price,
                currency="USD", status="pending",
            )
            OrderItem.objects.create(
                order=order, product=product, quantity=1,
                unit_price=product.price, currency="USD",
            )
            inv = issue_intent(
                order_id=order.pk, customer_id=buyer_id, recipient=receiver,
                usd_total=product.price, usd_per_trx=rate, quote_observed_at=observed_at,
                now=datetime.now(timezone.utc),
                is_amount_reserved=lambda x: PaymentIntent.objects.filter(
                    idempotency_key=_amount_key(receiver, x)).exists(),
                random_below=secrets.randbelow,
            )
            intent = PaymentIntent.objects.create(
                order=order, amount=product.price, currency="USD",
                status=AWAITING, provider=PROVIDER,
                idempotency_key=_amount_key(receiver, inv.amount_sun),
                provider_reference=_pack(inv),
            )
            return "/commerce/crown/invoice/{}/".format(intent.pk)


def _settle(intent_id, buyer_id, txid):
    from core.models import LedgerEntry, Order, PaymentIntent, PaymentWebhookEvent
    if not isinstance(txid, str) or TX_ID.fullmatch(txid) is None:
        raise PaymentHold("Transaction identifier format invalid")
    _, (a, b) = _configuration()
    # Read-only RPC calls happen outside SQL row locks; mandatory finality.
    first = query_solidified_transfer(a, txid)
    second = query_solidified_transfer(b, txid)
    with _exclusive_allocation(), transaction.atomic():
        intent = PaymentIntent.objects.select_for_update().select_related("order").get(
            pk=intent_id, order__customer_id=buyer_id, provider=PROVIDER,
        )
        order = Order.objects.select_for_update().get(pk=intent.order_id)
        if intent.status != AWAITING or order.status != "pending":
            raise PaymentHold("Invoice already consumed or cancelled")
        _validate_order(order, intent)
        invoice = _unpack(intent)
        if invoice.recipient != _configuration()[0]:
            raise PaymentHold("Merchant receiver changed")
        def previously_used(network, tx_hash):
            return (PaymentWebhookEvent.objects.filter(event_id=tx_hash).exists()
                or LedgerEntry.objects.filter(
                    reference="walletless:" + network + ":" + tx_hash).exists())
        verified_tx, sender = verify_two_source_transfer(
            invoice, first, second, tx_previously_consumed=previously_used,
        )
        evidence = hashlib.sha256(json.dumps({
            "intent": intent.pk, "network": NETWORK, "txid": verified_tx,
            "sender": sender, "to": invoice.recipient, "sun": invoice.amount_sun,
            "a": a.source_id, "b": b.source_id,
        }, sort_keys=True, separators=(",", ":")).encode("utf8")).hexdigest()
        event = PaymentWebhookEvent.objects.create(
            provider=PROVIDER, event_id=verified_tx, event_type="tron_finalized",
            payment_intent=intent, payload_hash=evidence, status="processed",
        )
        LedgerEntry.objects.create(
            order=order, payment_intent=intent, entry_type="credit",
            amount=order.total, currency="USD",
            reference="walletless:" + NETWORK + ":" + verified_tx,
            metadata={
                "payment_method": PROVIDER, "network": NETWORK,
                "tx_hash": verified_tx, "sender": sender,
                "evidence_digest": evidence,
                "walletless_receipt_event_id": event.pk,
            },
        )
        intent.status = "paid"
        intent.save(update_fields=["status", "updated_at"])
        order.status = "paid"
        order.save(update_fields=["status", "updated_at"])
    return True


def _secure(response):
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = (
        "default-src 'none'; style-src 'unsafe-inline'; "
        "form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
    )
    return response


@never_cache
@csrf_protect
@require_http_methods(["GET", "POST"])
def crown_invoice(request, intent_id):
    """Owner-only native TRX invoice. A submitted TxID is never self-attested."""
    from core.models import PaymentIntent
    if request.get_host().split(":")[0].lower() not in ("mojplaywin.com", "www.mojplaywin.com"):
        raise Http404
    if not request.user.is_authenticated:
        return _secure(HttpResponse("Sign in to view your invoice.", status=401))
    intent = PaymentIntent.objects.select_related("order").filter(
        pk=intent_id, order__customer=request.user, provider=PROVIDER,
    ).first()
    if intent is None:
        raise Http404
    if intent.status == "paid" and intent.order.status == "paid":
        from core.crown_fleet import owned_skus
        from core.models import OrderItem
        item = OrderItem.objects.select_related("product").filter(order=intent.order).first()
        if item and (item.product.metadata or {}).get("crown_sku") in owned_skus(request.user):
            return _secure(HttpResponse(
                "Payment verified and your jet is now owned. Return to Crown Defender.",
                content_type="text/plain; charset=utf-8",
            ))
        return _secure(HttpResponse("Payment review needed.", status=409))
    try:
        invoice = _unpack(intent)
        if intent.status != AWAITING or intent.order.status != "pending":
            raise PaymentHold("Order is not awaiting settlement")
        expired = datetime.now(timezone.utc) > invoice.expires_at
        _validate_order(intent.order, intent)
        if invoice.recipient != _configuration()[0]:
            raise PaymentHold("Merchant recipient changed")
    except PaymentHold:
        return _secure(HttpResponse(
            "This invoice is unavailable or expired. Do not pay it.",
            status=410, content_type="text/plain; charset=utf-8",
        ))
    if request.method == "GET":
        # Invoice-page driven discovery; the indexer NEVER grants ownership.
        # Settlement is always confirmed by both independent solidified nodes.
        if (datetime.now(timezone.utc) < invoice.expires_at + timedelta(hours=1)
                and cache.add("crown-tron-autoscan:" + str(intent.pk), 1, timeout=25)):
            try:
                candidates = discover_native_candidates(
                    invoice, settings.CROWN_TRX_INDEXER_KEY,
                )
                for candidate in candidates:
                    try:
                        _settle(intent.pk, request.user.pk, candidate)
                    except Exception:
                        continue
                    return _secure(HttpResponseRedirect(request.path))
            except Exception:
                pass
    if request.method == "POST":
        txid = request.POST.get("txid", "").strip().lower()
        try:
            _settle(intent.pk, request.user.pk, txid)
        except Exception:
            # Never expose RPC credentials or claim payment settled prematurely.
            return _secure(HttpResponse(
                "Payment not yet independently confirmed. Check your transaction and retry.",
                status=409, content_type="text/plain; charset=utf-8",
            ))
        return _secure(HttpResponseRedirect(request.path))
    if expired:
        # Late verification remains possible if the on-chain transfer was mined on time.
        # Never show expired payment instructions that invite new transfers.
        token = get_token(request)
        notice = format_html(
            '<meta http-equiv="refresh" content="30">'
            '<h3>Invoice expired — do not send funds.</h3>'
            '<p>If you already paid within the valid window, submit the '
            'transaction hash below for independent verification.</p>'
            '<form method="post"><input type="hidden" name="csrfmiddlewaretoken" value="{}">'
            '<input name="txid" maxlength="64" required autocomplete="off">'
            '<button>Verify my earlier payment</button></form>', token,
        )
        return _secure(HttpResponse(notice, content_type="text/html; charset=utf-8"))
    exact = Decimal(invoice.amount_sun) / Decimal(1_000_000)
    token = get_token(request)
    body = format_html(
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="refresh" content="30">'
        '<title>Crown Defender · TRX invoice</title>'
        '<style>body{{background:#080d1b;color:#fff;font:16px system-ui;'
        'display:grid;place-items:center;min-height:95vh}}main{{max-width:420px;'
        'padding:26px;border:1px solid #42516d;border-radius:20px;'
        'background:#141e32}}input,button{{font:inherit;padding:12px;'
        'max-width:95%;margin:8px 0}}code{{overflow-wrap:anywhere}}'
        'p{{line-height:1.5}}</style><main>'
        '<h2>Crown Defender · native TRX</h2>'
        '<p>Network: TRON Mainnet (TRX only, NOT USDT).</p>'
        '<p>Amount: <strong>{} TRX</strong> (exactly).</p>'
        '<p>Recipient: <code>{}</code></p>'
        '<p>Valid until: {}</p>'
        '<p>Send with your own wallet. Wait for chain finality;'
        ' do not send funds after expiry. A wrong amount cannot be credited.</p>'
        '<form method="post"><input type="hidden" name="csrfmiddlewaretoken" value="{}">'
        '<label>Transaction hash (64 hex characters)</label>'
        '<input name="txid" maxlength="64" required autocomplete="off">'
        '<button type="submit">Verify confirmed payment</button></form>'
        '<p><a style="color:#94f3d8" href="/games/crown-defender/">Return to game</a></p>'
        '</main></html>',
        format(exact, ".6f"), invoice.recipient,
        invoice.expires_at.isoformat(), token,
    )
    return _secure(HttpResponse(body, content_type="text/html; charset=utf-8"))
