"""Unified Persian/English native-TRX merchant checkout on the existing core ledger.

No wallet custody, no spending, no client-controlled amounts and no payments
without two independent solidified TRON receipts. Guest ownership is proven
through the email link, never from simply entering somebody else's email.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import hmac
import secrets
import smtplib
import time

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.utils import timezone as dj_timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from .models import LedgerEntry, Order, OrderItem, PaymentIntent, PaymentWebhookEvent, Product
from .tron_gateway_invoice import TronGatewayInvoice
from .tron_gateway_verify import MAINNET_RECEIVER, PaymentNotFinal, TX_PATTERN, verify_native_trx

PROVIDER = "zomorod_tron_mainnet_v1"
LINK_TTL = 1800
RECEIPT_RECOVERY_TTL = 900
SESSION_EMAIL_TTL = 900
SHARED_CACHE_BACKENDS = frozenset((
    "django.core.cache.backends.redis.RedisCache",
    "django.core.cache.backends.memcached.PyMemcacheCache",
    "django.core.cache.backends.memcached.PyLibMCCache",
    "django_redis.cache.RedisCache",
))


def _shared_rate_limit_ready():
    """Refuse per-worker LocMemCache even if a flag was accidentally enabled."""
    configured = getattr(settings, "CACHES", {}).get("default", {})
    return (isinstance(configured, dict) and
            configured.get("BACKEND") in SHARED_CACHE_BACKENDS)



def _host(request):
    # get_host() enforces Django's ALLOWED_HOSTS before any invoice is generated.
    host = request.get_host().split(":")[0].lower().rstrip(".")
    roots = ("zomorodmelal.ir", "mojplaywin.com")
    if (not request.is_secure() or
            getattr(settings, "TRON_UNIFIED_PUBLIC_ENABLED", False) is not True or
            getattr(settings, "TRON_UNIFIED_SHARED_RATE_LIMIT_READY", False) is not True or
            not _shared_rate_limit_ready() or
            getattr(settings, "TRON_UNIFIED_RECEIVER", "") != MAINNET_RECEIVER):
        raise Http404("Checkout is not yet available")
    permitted = getattr(settings, "TRON_UNIFIED_ALLOWED_HOSTS", ())
    if type(permitted) not in (tuple, list) or host not in permitted:
        raise Http404("Host not permitted for TRON checkout")
    if host == roots[0] or host.endswith("." + roots[0]):
        return host, "fa"
    if host == roots[1] or host.endswith("." + roots[1]):
        return host, "en"
    raise Http404("Unknown merchant brand")


def _private(response):
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["X-Content-Type-Options"] = "nosniff"
    response["Referrer-Policy"] = "no-referrer"
    return response


def _email_key(email):
    return hmac.new(str(settings.SECRET_KEY).encode(),
                    ("tron:buyer:v1:" + email.lower()).encode(), hashlib.sha256).hexdigest()


def _valid_email(raw):
    if type(raw) is not str:
        raise ValueError("Email required")
    email = raw.strip().lower()
    if len(email) > 254 or len(email) < 6 or "\n" in email or "\r" in email:
        raise ValueError("Email invalid")
    try:
        validate_email(email)
    except ValidationError as exc:
        raise ValueError("Email invalid") from exc
    return email


def _limit(request, email, purpose="email"):
    # Deployment requires a verified multi-worker shared cache, not LocMemCache.
    ip = request.META.get("REMOTE_ADDR", "")
    if not isinstance(ip, str) or not ip or len(ip) > 80:
        raise Http404("Rate limit unavailable")
    now = int(time.time() // 3600)
    # Independent counters prevent spraying random emails from one IP or
    # attacking one address across many different IPs.
    limit = 12 if purpose == "verify" else 4
    counters = (
        ("pair:" + ip + "|" + email, limit),
        ("ip:" + ip, 100 if purpose == "verify" else 40),
        ("email:" + email, 30 if purpose == "verify" else 10),
    )
    try:
        for scope, ceiling in counters:
            identity = hmac.new(str(settings.SECRET_KEY).encode(),
                (purpose + "|" + scope + "|" + str(now)).encode(), hashlib.sha256).hexdigest()
            key = "tron:rate:" + identity
            count = 1 if cache.add(key, 1, timeout=3600) else cache.incr(key)
            if count > ceiling:
                raise Http404("Rate limit")
    except Http404:
        raise
    except Exception as exc:
        raise Http404("Rate limit unavailable") from exc


def _read_product(product_id, locale):
    query = Product.objects.filter(pk=product_id, active=True)
    product = query.first()
    if product is None or not Decimal("0") < product.price:
        raise Http404("Product unavailable")
    md = product.metadata if type(product.metadata) is dict else {}
    # Assets, legitimate rights and service fulfillment remain the catalogue
    # owner's responsibility; never infer eligibility solely from active=True.
    required = ("rights_cleared", "publication_approved", "sales_enabled",
                "in_stock", "fulfillment_ready")
    if any(md.get(k) is not True for k in required):
        raise Http404("Product not approved for sale")
    kind = md.get("fulfillment_type")
    if kind not in ("digital", "physical", "service"):
        raise Http404("Fulfillment type missing")
    if kind == "digital":
        for key in ("rights_document_sha256", "rights_asset_sha256", "sha256"):
            value = md.get(key)
            if type(value) is not str or len(value) != 64 or any(c not in "0123456789abcdef" for c in value.lower()):
                raise Http404("Asset rights not established")
        if md["rights_asset_sha256"].lower() != md["sha256"].lower():
            raise Http404("Approved asset has changed")
    # Never allow a perpetually stale merchant fiat/crypto quote.
    expires = md.get("tron_quote_valid_until_ms")
    current_ms = int(time.time() * 1000)
    if (type(expires) is not int or
            not current_ms < expires <= current_ms + 24 * 3600 * 1000):
        raise Http404("Merchant TRX quote expired or unreviewed")
    if locale == "en" and product.currency != "USD":
        raise Http404("English checkout requires USD catalogue price")
    if locale == "fa" and product.currency not in ("TOMAN", "IRT", "IRR"):
        raise Http404("Persian price unit missing")
    base_sun = md.get("tron_price_sun")
    if (type(base_sun) is not int or not 0 < base_sun < 10**17 or
            md.get("tron_price_currency") != product.currency or
            md.get("tron_price_reference_amount") != str(product.price)):
        raise Http404("Current TRX quotation not approved")
    # Approved fixed merchant quote prevents speculative or invented FX rates.
    fingerprint = hashlib.sha256(
        f"{product.pk}|{product.price}|{product.currency}|{base_sun}|{expires}|{md.get('sha256','')}|{md.get('rights_document_sha256','')}".encode()
    ).hexdigest()
    return product, base_sun, fingerprint


def _guest(email):
    model = get_user_model()
    if model.USERNAME_FIELD != "username" or not model._meta.get_field("username").unique:
        raise ValueError("Guest user schema is not supported")
    name = "trxguest_" + _email_key(email)[:40]
    user = model.objects.filter(username=name).first()
    if user is None:
        try:
            with transaction.atomic():
                user = model(username=name, email=email, is_active=True)
                user.set_unusable_password()
                user.save(force_insert=True)
        except IntegrityError:
            user = model.objects.filter(username=name).first()
    if (user is None or user.email.lower() != email or
            not user.is_active or user.has_usable_password()):
        raise ValueError("Guest identity conflict")
    return user


def _new_invoice(email, host, language, product_id):
    # All database writes are atomic and rolling back a full cart on failure.
    with transaction.atomic():
        product, base_sun, fingerprint = _read_product(product_id, language)
        # No payable invoice for a nonexistent/mutated digital product.
        # Validate the actual private bytes before asking for real money.
        if product.metadata.get("fulfillment_type") == "digital":
            from .tron_gateway_delivery import _file_from_private_root
            with _file_from_private_root(product.metadata.get("asset_relpath"),
                                         product.metadata.get("sha256")):
                pass
        user = _guest(email)
        order = Order.objects.create(customer=user, status="pending",
                                     total=product.price, currency=product.currency)
        OrderItem.objects.create(order=order, product=product, quantity=1,
                                 unit_price=product.price, currency=product.currency)
        intent = PaymentIntent.objects.create(
            order=order, amount=product.price, currency=product.currency,
            idempotency_key="tronquote:" + secrets.token_hex(20),
            status="awaiting_payment", provider=PROVIDER)
        now_ms = int(time.time() * 1000)
        token = secrets.token_urlsafe(30)
        claim_sha = hashlib.sha256(token.encode("ascii")).hexdigest()
        invoice = None
        # Globally unique amount at this one receiver, across ALL historical
        # invoices; never recycle a quote for a later payment.
        for _ in range(48):
            amount_sun = base_sun + 1 + secrets.randbelow(10000)
            # Legacy walletless invoices reserve this receiver+SUN under an
            # older global idempotency fingerprint. Reuse would be unsafe.
            legacy_key = "wltrx1:" + hashlib.sha256(MAINNET_RECEIVER.encode("ascii")).hexdigest() + ":" + str(amount_sun)
            if PaymentIntent.objects.filter(idempotency_key=legacy_key).exists():
                continue
            try:
                with transaction.atomic():
                    invoice = TronGatewayInvoice.objects.create(
                        order=order, payment_intent=intent, buyer_email=email,
                        source_host=host, language=language,
                        buyer_email_sha=_email_key(email), receiver=MAINNET_RECEIVER,
                        amount_sun=amount_sun,
                        issued_ms=now_ms, expires_ms=now_ms + LINK_TTL * 1000,
                        claim_sha256=claim_sha, quote_fingerprint=fingerprint,
                        fulfillment_kind=product.metadata["fulfillment_type"],
                        asset_relpath_snapshot=(product.metadata.get("asset_relpath") or "")
                        if product.metadata["fulfillment_type"] == "digital" else "",
                        asset_sha256_snapshot=(product.metadata.get("sha256") or "")
                        if product.metadata["fulfillment_type"] == "digital" else "",
                        rights_document_sha256_snapshot=(product.metadata.get("rights_document_sha256") or "")
                        if product.metadata["fulfillment_type"] == "digital" else "")
                break
            except IntegrityError:
                continue
        if invoice is None:
            raise ValueError("Unique TRX quotation capacity exhausted")
        return invoice, token


def _mail_link(request, invoice, token):
    host = invoice.source_host
    link = f"https://{host}/pay/tron/email/{token}/"
    if invoice.language == "fa":
        subject = "تأیید ایمیل و دریافت صورتحساب TRON — زمرد ملل"
        body = "برای دریافت صورتحساب پرداخت خود روی نشانی زیر بروید:\n" + link + "\nدر صورت عدم ثبت سفارش، این پیام را نادیده بگیرید."
    else:
        subject = "Confirm your email for your TRON invoice — MojPlayWin"
        body = "Open your secure TRON invoice using this link:\n" + link + "\nIf you did not request this, ignore this email."
    sent = send_mail(subject, body, settings.DEFAULT_FROM_EMAIL,
                     [invoice.buyer_email], fail_silently=False)
    if sent != 1:
        raise RuntimeError("Invoice confirmation email was not accepted")


def _owner(request, invoice_id, host):
    invoice = TronGatewayInvoice.objects.select_related(
        "order", "payment_intent").filter(pk=invoice_id, source_host=host).first()
    when = request.session.get("tron_verified_at")
    if (invoice is None or request.session.get("tron_verified_email") != _email_key(invoice.buyer_email)
            or request.session.get("tron_verified_host") != host
            or type(when) is not int or not 0 <= int(time.time()) - when <= SESSION_EMAIL_TTL):
        raise Http404("Invoice access requires verified email")
    return invoice


def _context(invoice, stage, language, **extra):
    ctx = {"stage": stage, "language": language, "invoice": invoice,
           "trx_amount": f"{Decimal(invoice.amount_sun)/Decimal(1000000):.6f}" if invoice else None,
           "recipient": MAINNET_RECEIVER,
           "invoice_expired": bool(invoice and invoice.expires_ms < int(time.time() * 1000))}
    ctx.update(extra)
    return ctx


def _page(request, ctx, *, status=200):
    return _private(render(request, "core/tron_gateway.html", ctx, status=status))


@never_cache
@csrf_protect
@require_http_methods(["GET", "POST"])
def checkout(request, product_id):
    host, language = _host(request)
    product, base_sun, _ = _read_product(product_id, language)
    if request.method == "GET":
        return _page(request, _context(None, "start", language, product=product,
                       minimum_trx=f"{Decimal(base_sun)/Decimal(1000000):.6f}"))
    try:
        email = _valid_email(request.POST.get("email", ""))
        _limit(request, email)
        invoice, token = _new_invoice(email, host, language, product_id)
        _mail_link(request, invoice, token)
    except (ValueError, IntegrityError, OSError, ConnectionError,
            smtplib.SMTPException, RuntimeError):
        # No wallet instructions were exposed. Email or quote failure never
        # masquerades as successful ordering.
        return _page(request, _context(None, "start", language, product=product,
                     error="Could not issue a secure invoice. Do not transfer TRX."), status=503)
    return _page(request, _context(None, "sent", language))


@never_cache
@require_http_methods(["GET"])
def email_claim(request, token):
    host, _ = _host(request)
    if len(token) > 100 or len(token) < 30:
        raise Http404
    try:
        key = hashlib.sha256(token.encode("ascii")).hexdigest()
    except UnicodeEncodeError:
        raise Http404("Invalid email claim")
    invoice = TronGatewayInvoice.objects.filter(claim_sha256=key, source_host=host).first()
    if invoice is None or invoice.expires_ms < int(time.time() * 1000):
        raise Http404("Email link expired")
    request.session.cycle_key()
    request.session["tron_verified_email"] = _email_key(invoice.buyer_email)
    request.session["tron_verified_host"] = host
    request.session["tron_verified_at"] = int(time.time())
    if invoice.status == "email_pending":
        TronGatewayInvoice.objects.filter(pk=invoice.pk, status="email_pending").update(
            status="awaiting_payment")
    return _private(HttpResponseRedirect(f"/pay/tron/invoice/{invoice.pk}/"))


def _record_paid(invoice_id, proof):
    # The payer's browser cannot write a credit without proof from BOTH nodes.
    with transaction.atomic():
        invoice = TronGatewayInvoice.objects.select_for_update().select_related(
            "order", "payment_intent").get(pk=invoice_id)
        if invoice.status == "paid":
            return invoice.txid == proof["txid"]
        if (invoice.status != "awaiting_payment" or invoice.order.status != "pending"
                or invoice.payment_intent.status != "awaiting_payment"
                or invoice.payment_intent.provider != PROVIDER
                or invoice.payment_intent.order_id != invoice.order_id
                or invoice.payment_intent.amount != invoice.order.total
                or invoice.payment_intent.currency != invoice.order.currency):
            return False
        # Old MojPlayWin's independent walletless provider may already have
        # attributed the same on-chain hash. Never knowingly credit twice.
        if (PaymentWebhookEvent.objects.filter(event_id=proof["txid"]).exists()
                or LedgerEntry.objects.filter(reference__endswith=":" + proof["txid"]).exists()):
            return False
        event = PaymentWebhookEvent.objects.create(
            provider=PROVIDER, event_id=proof["txid"], event_type="tron_finalized",
            payment_intent=invoice.payment_intent, payload_hash=proof["proof_digest"],
            status="processed", processed_at=dj_timezone.now())
        LedgerEntry.objects.create(
            order=invoice.order, payment_intent=invoice.payment_intent,
            entry_type="credit", amount=invoice.order.total, currency=invoice.order.currency,
            reference="tron-mainnet:" + proof["txid"],
            metadata={"asset": "TRX", "network": "tron-mainnet",
                      "amount_sun": invoice.amount_sun,
                      "receiver": MAINNET_RECEIVER,
                      "sender_hex": proof["sender_hex"],
                      "block_height": proof["block_height"],
                      "proof_digest": proof["proof_digest"],
                      "source_host": invoice.source_host,
                      "language": invoice.language,
                      "merchant_invoice_id": invoice.pk,
                      "fulfillment_kind": invoice.fulfillment_kind,
                      "webhook_event_id": event.pk})
        invoice.txid = proof["txid"]
        invoice.proof_digest = proof["proof_digest"]
        invoice.status = "paid"
        invoice.verified_at = dj_timezone.now()
        invoice.save(update_fields=("txid", "proof_digest", "status", "verified_at"))
        invoice.payment_intent.status = "paid"
        invoice.payment_intent.provider_reference = proof["txid"]
        invoice.payment_intent.save(update_fields=("status", "provider_reference"))
        invoice.order.status = "paid"
        invoice.order.save(update_fields=("status",))
        return True


@never_cache
@csrf_protect
@require_http_methods(["GET", "POST"])
def invoice_page(request, invoice_id):
    host, language = _host(request)
    invoice = _owner(request, invoice_id, host)
    error = None
    if request.method == "POST":
        _limit(request, invoice.buyer_email, purpose="verify")
        txid = request.POST.get("txid", "").strip().lower()
        if invoice.status == "awaiting_payment":
            try:
                if not TX_PATTERN.fullmatch(txid):
                    raise PaymentNotFinal("Invalid transaction candidate")
                TronGatewayInvoice.objects.filter(pk=invoice.pk, status="awaiting_payment").update(candidate_txid=txid)
                proof = verify_native_trx(
                    txid, invoice.receiver, invoice.amount_sun,
                    invoice.issued_ms, invoice.expires_ms)
                if not _record_paid(invoice.pk, proof):
                    error = "Payment already processed or invoice closed"
            except (PaymentNotFinal, IntegrityError, ValueError, OSError):
                error = "Payment not independently confirmed; do not pay twice"
            invoice.refresh_from_db()
        else:
            error = "Invoice is not payable" if invoice.status != "paid" else None
    item = OrderItem.objects.filter(order=invoice.order).select_related("product").first()
    digital = bool(item and invoice.fulfillment_kind == "digital")
    return _page(request, _context(invoice, "invoice", language, error=error,
                                  is_digital=digital))


@never_cache
@csrf_protect
@require_http_methods(["GET", "POST"])
def recovery(request):
    host, language = _host(request)
    if request.method == "GET":
        return _page(request, _context(None, "recovery", language))
    try:
        email = _valid_email(request.POST.get("email", ""))
        _limit(request, email)
        has_invoices = TronGatewayInvoice.objects.filter(
            buyer_email=email, source_host=host).exists()
        if has_invoices:
            payload = {"h": host, "e": _email_key(email)}
            token = signing.dumps(payload, salt="tron:recovery:v1")
            message = (f"https://{host}/pay/tron/recovery/{token}/")
            sent = send_mail("TRON invoice recovery" if language == "en" else "بازیابی صورتحساب TRON",
                             message, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)
            if sent != 1:
                raise RuntimeError("Recovery email was not accepted")
    except (ValueError, OSError, ConnectionError, smtplib.SMTPException, RuntimeError):
        pass
    # Identical response prevents user enumeration by email.
    return _page(request, _context(None, "recovery_sent", language))


@never_cache
@require_http_methods(["GET"])
def recovery_link(request, token):
    host, language = _host(request)
    try:
        payload = signing.loads(token, salt="tron:recovery:v1",
                                max_age=RECEIPT_RECOVERY_TTL)
        if type(payload) is not dict or payload.get("h") != host or type(payload.get("e")) is not str:
            raise ValueError
    except (signing.BadSignature, signing.SignatureExpired, ValueError):
        raise Http404("Recovery link invalid")
    request.session.cycle_key()
    request.session["tron_verified_email"] = payload["e"]
    request.session["tron_verified_host"] = host
    request.session["tron_verified_at"] = int(time.time())
    TronGatewayInvoice.objects.filter(
        source_host=host, buyer_email_sha=payload["e"],
        status="email_pending", expires_ms__gte=int(time.time()*1000)
    ).update(status="awaiting_payment")
    invoices = list(TronGatewayInvoice.objects.filter(
        source_host=host, buyer_email_sha=payload["e"]).order_by("-created_at")[:20])
    return _page(request, _context(None, "recovery_list", language, invoices=invoices))


@never_cache
@require_http_methods(["GET"])
def catalog(request):
    """Ready-to-sell products only; no hardcoded fake SKU inventory."""
    host, language = _host(request)
    try:
        page = int(request.GET.get("page", "1"))
    except (ValueError, TypeError):
        raise Http404("Invalid page")
    if not 1 <= page <= 100:
        raise Http404("Invalid page")
    # Small, bounded server-side slice; no direct HTML rendering of metadata.
    start = (page - 1) * 50
    products = []
    for product in Product.objects.filter(active=True).order_by("id")[start:start + 50]:
        try:
            p, sun, _ = _read_product(product.pk, language)
            products.append((p, f"{Decimal(sun)/Decimal(1000000):.6f}"))
        except Http404:
            continue
    return _page(request, _context(None, "catalog", language,
                                    products=products, next_page=page + 1,
                                    has_more=Product.objects.filter(active=True).count() > start + 50))
