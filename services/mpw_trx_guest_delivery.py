"""Main-database guest TRX email outbox and time-limited email recovery.

Never grants payment or files: these remain governed by the existing verified
TRX intent, ledger and entitlement checks.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from datetime import timedelta
from decimal import Decimal

from django.core import signing
from django.core.cache import cache
from django.core.mail import EmailMessage, get_connection
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone

from core.models import PaymentIntent
from mpw_commerce.models import GuestTrxDelivery
from services.mpw_walletless_commercial_intent import (
    PROVIDER, WAITING, _decode, commercial_buyer_status,
)
from services.mpw_trx_walletless_core import PaymentHold

LOG = logging.getLogger(__name__)
MAIL_FROM = "support@mojplaywin.com"
TOKEN_SALT = "mpw.guest.email.recovery.v1"
TOKEN_MAX_AGE = 7 * 86400
MAX_EMAIL_ATTEMPTS = 5


def normalize_email(value):
    if not isinstance(value, str):
        raise ValueError("Email address required")
    address = value.strip().lower()
    if not address or len(address) > 254 or "\r" in address or "\n" in address:
        raise ValueError("Valid email address required")
    validate_email(address)
    return address


def _guest_user(user):
    return (bool(user and user.is_active and not user.has_usable_password())
            and str(user.get_username()).startswith("mpwguest_"))


def record_invoice(invoice_id, user):
    """Called only after an existing order and real payable intent are created."""
    if not _guest_user(user):
        return
    email = normalize_email(user.email)
    pi = PaymentIntent.objects.select_related("order").get(pk=invoice_id,
        order__customer_id=user.pk, provider=PROVIDER)
    obj, created = GuestTrxDelivery.objects.get_or_create(
        order=pi.order, defaults={"email": email})
    if obj.email != email:
        raise PaymentHold("Order email ownership mismatch")
    return created


def magic_link(row, intent_id, mode):
    if mode not in ("invoice", "download", "purchases"):
        raise ValueError("Unexpected recovery link purpose")
    fingerprint = hashlib.sha256(row.email.encode("utf-8")).hexdigest()[:32]
    token = signing.dumps({"o": row.order_id, "u": row.order.customer_id,
                           "e": fingerprint, "m": mode, "n": secrets.token_hex(8)},
                          salt=TOKEN_SALT, compress=True)
    return "https://mojplaywin.com/commerce/trx-easy/purchases/?token=" + token


def redeem_token(raw):
    if not isinstance(raw, str) or len(raw) > 900:
        return None
    try:
        payload = signing.loads(raw, salt=TOKEN_SALT, max_age=TOKEN_MAX_AGE)
        if not isinstance(payload, dict) or set(payload) != {"o", "u", "e", "m", "n"}:
            return None
        if type(payload["o"]) is not int or type(payload["u"]) is not int:
            return None
        if payload["m"] not in ("invoice", "download", "purchases"):
            return None
        row = GuestTrxDelivery.objects.select_related("order", "order__customer").get(
            order_id=payload["o"], order__customer_id=payload["u"])
        if not _guest_user(row.order.customer):
            return None
        expected = hashlib.sha256(row.email.encode("utf-8")).hexdigest()[:32]
        if not hmac.compare_digest(expected, str(payload["e"])):
            return None
        intent = PaymentIntent.objects.get(order_id=row.order_id, provider=PROVIDER)
        # Even an emailed download link cannot bypass server-side settlement.
        if payload["m"] == "download":
            state = commercial_buyer_status(intent.pk, row.order.customer_id)
            if state.get("can_download") is not True:
                return None
        return (row.order.customer, intent.pk, payload["m"])
    except (signing.BadSignature, signing.SignatureExpired, ValueError,
            TypeError, GuestTrxDelivery.DoesNotExist,
            PaymentIntent.DoesNotExist, PaymentHold):
        return None


def _email(to, subject, body, message_id):
    # This cPanel account has local Exim accepting support@mojplaywin.com.
    # Do not depend on global SMTP credentials, currently unset.
    connection = get_connection(
        backend="django.core.mail.backends.smtp.EmailBackend",
        host="127.0.0.1", port=25, username="", password="", use_tls=False,
        use_ssl=False, timeout=12,
    )
    msg = EmailMessage(subject, body, MAIL_FROM, [to], connection=connection,
                       headers={"Message-ID": message_id})
    if msg.send(fail_silently=False) != 1:
        raise OSError("Local SMTP refused delivery")


def _send_one(row_id, kind):
    from django.db.models import F
    field = kind + "_state"
    attempts = kind + "_attempts"
    with transaction.atomic():
        row = GuestTrxDelivery.objects.select_for_update().select_related("order").get(pk=row_id)
        if getattr(row, field) not in ("pending", "failed") or getattr(row, attempts) >= MAX_EMAIL_ATTEMPTS:
            return False
        pi = PaymentIntent.objects.get(order_id=row.order_id, provider=PROVIDER)
        if kind == "invoice":
            if pi.status != WAITING:
                return False
            invoice = _decode(pi)
            # Never email a payable amount or destination while the merchant
            # receiver is inactive, even for older queued guest invoices.
            from django.conf import settings
            from services.mpw_walletless_commercial_intent import require_active_merchant_wallet
            require_active_merchant_wallet(settings, invoice.recipient)
            if invoice.expires_at <= timezone.now() + timedelta(minutes=2):
                return False  # Do not mail expired or nearly-expired payment instructions.
            amount = format(Decimal(invoice.amount_sun) / Decimal(1_000_000), ".6f")
            body = (f"MojPlayWin order #{row.order_id} | invoice #{pi.pk}\n\n"
                    f"Amount: {amount} TRX on TRON mainnet only\n"
                    f"Receiving address: {invoice.recipient}\n"
                    f"Expires: {invoice.expires_at.isoformat()}\n\n"
                    "Pay exactly once. Network fees are separate. Never send USDT or another network.\n"
                    "Never share your wallet secret phrase.\n"
                    f"Open this secure invoice link: {magic_link(row, pi.pk, 'invoice')}\n"
                    "After verified blockchain settlement, a separate receipt and private download link will arrive.\n")
            subject = f"MojPlayWin TRX invoice #{pi.pk}"
        else:
            state = commercial_buyer_status(pi.pk, row.order.customer_id)
            if state.get("can_download") is not True:
                return False
            body = (f"Payment verified for MojPlayWin order #{row.order_id}.\n"
                    f"Invoice reference: {pi.pk}\n"
                    "TRON payment has been independently verified by the server.\n"
                    f"Your private download: {magic_link(row, pi.pk, 'download')}\n\n"
                    "This link expires in seven days; recover access again using your purchase email.\n")
            subject = f"MojPlayWin verified payment receipt #{pi.pk}"
        # 'sending' survives a crash and prevents an unproven duplicate receipt.
        setattr(row, field, "sending")
        setattr(row, attempts, getattr(row, attempts) + 1)
        row.save(update_fields=[field, attempts, "updated_at"])
        recipient = row.email
        msgid = f"<mpw-trx-{kind}-{pi.pk}@mojplaywin.com>"
    try:
        _email(recipient, subject, body, msgid)
    except Exception as exc:
        LOG.warning("Guest TRX %s delivery failed (%s)", kind, type(exc).__name__)
        GuestTrxDelivery.objects.filter(pk=row_id, **{field: "sending"}).update(
            **{field: "failed"})
        return False
    GuestTrxDelivery.objects.filter(pk=row_id, **{field: "sending"}).update(
        **{field: "sent"})
    return True


def flush_outbox(limit=12):
    sent = {"invoice": 0, "receipt": 0}
    # Existing order ledger remains sole source of truth; this is only an email queue.
    candidates = list(GuestTrxDelivery.objects.filter(
        invoice_state__in=("pending", "failed"), invoice_attempts__lt=MAX_EMAIL_ATTEMPTS
    ).order_by("pk").values_list("pk", flat=True)[:limit])
    for pk in candidates:
        try:
            sent["invoice"] += bool(_send_one(pk, "invoice"))
        except (PaymentHold, ValueError, PaymentIntent.DoesNotExist):
            pass
    candidates = list(GuestTrxDelivery.objects.filter(
        receipt_state__in=("pending", "failed"), receipt_attempts__lt=MAX_EMAIL_ATTEMPTS
    ).order_by("pk").values_list("pk", flat=True)[:limit])
    for pk in candidates:
        try:
            sent["receipt"] += bool(_send_one(pk, "receipt"))
        except (PaymentHold, ValueError, PaymentIntent.DoesNotExist):
            pass
    return sent


def request_recovery(email, ip):
    """Generic response; never reveals whether a buyer's address has orders."""
    address = normalize_email(email)
    if not ip or len(ip) > 80:
        raise ValueError("Invalid request origin")
    from django.conf import settings
    digest = hmac.new(settings.SECRET_KEY.encode(),
                      (ip + ":" + address).encode(), hashlib.sha256).hexdigest()
    key = "mpw:recovery:" + digest
    if not cache.add(key, 1, timeout=900):
        raise ValueError("Please wait before requesting another recovery email")
    rows = list(GuestTrxDelivery.objects.filter(email=address).select_related(
        "order").order_by("-pk")[:20])
    links = []
    for row in rows:
        pi = PaymentIntent.objects.filter(order_id=row.order_id, provider=PROVIDER).first()
        if pi:
            links.append(f"Order #{row.order_id}: {magic_link(row, pi.pk, 'purchases')}")
    if links:
        _email(address, "MojPlayWin private purchase recovery",
               "If you requested order recovery, use these private links within seven days:\n\n"
               + "\n".join(links) + "\n\nIf you did not request this, ignore the email.\n",
               "<mpw-trx-recovery-" + secrets.token_hex(12) + "@mojplaywin.com>")
