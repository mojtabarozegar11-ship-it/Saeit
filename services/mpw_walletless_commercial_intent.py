"""MojPlayWin native TRX payment adapter using existing MariaDB tables.

No public route imports this before release, and every write is gated on
independently verified merchant canary and two-provider solidified proof.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from decimal import Decimal
from contextlib import contextmanager
import hashlib
import json
import os
import secrets
import stat

from services.mpw_trx_walletless_core import (
    ADDRESS, NETWORK, TX_ID, INVOICE_TTL, InvoiceIntent, PaymentHold, issue_intent,
)
from services.mpw_walletless_django_test_bridge import TrustedNodePair

PROVIDER = "mpw_walletless_trx_v1"
WAITING = "awaiting_chain"
LOCK = "mpw-walletless-trx-amount-v1"


def _key(address: str, amount_sun: int) -> str:
    """Existing unique PaymentIntent.idempotency_key is an exact amount claim."""
    if not isinstance(address, str) or not ADDRESS.fullmatch(address):
        raise PaymentHold("Invalid merchant recipient")
    if type(amount_sun) is not int or not 0 < amount_sun < 10**18:
        raise PaymentHold("Invalid TRX atomic amount")
    # Hash the full address; the network is fixed by this provider.
    return "wltrx1:" + hashlib.sha256(address.encode("ascii")).hexdigest() + ":" + str(amount_sun)


def _encode(invoice: InvoiceIntent) -> str:
    if not isinstance(invoice, InvoiceIntent) or invoice.network != NETWORK:
        raise PaymentHold("Invalid invoice intent")
    doc = {"v": 1, "to": invoice.recipient, "sun": invoice.amount_sun,
           "rate": str(invoice.quote_usd_per_trx),
           "at": invoice.issued_at.astimezone(timezone.utc).isoformat()}
    encoded = json.dumps(doc, separators=(",", ":"), sort_keys=True)
    if len(encoded) > 200 or _key(invoice.recipient, invoice.amount_sun) == "":
        raise PaymentHold("Existing provider_reference column too short")
    return encoded


def _decode(intent) -> InvoiceIntent:
    """Rehydrate from one immutable row, never from client-submitted data."""
    try:
        if intent.provider != PROVIDER:
            raise PaymentHold("Wrong gateway provider")
        doc = json.loads(intent.provider_reference)
        if type(doc) is not dict or set(doc) != {"v", "to", "sun", "rate", "at"}:
            raise PaymentHold("Unrecognized invoice envelope")
        if type(doc["v"]) is not int or doc["v"] != 1:
            raise PaymentHold("Unsupported invoice version")
        at = datetime.fromisoformat(doc["at"])
        rate = Decimal(doc["rate"])
        sun = doc["sun"]
        if at.tzinfo is None or at.utcoffset() is None or not rate.is_finite() or rate <= 0:
            raise PaymentHold("Untrusted quote data")
        if intent.idempotency_key != _key(doc["to"], sun):
            raise PaymentHold("Invoice atomic amount key mismatch")
        if intent.currency != "USD" or Decimal(intent.amount) <= 0:
            raise PaymentHold("Invalid intent price")
        return InvoiceIntent(
            order_id=int(intent.order_id), customer_id=int(intent.order.customer_id),
            network=NETWORK, recipient=doc["to"], amount_sun=sun,
            usd_total=Decimal(intent.amount), quote_usd_per_trx=rate,
            issued_at=at, expires_at=at + INVOICE_TTL,
        )
    except PaymentHold:
        raise
    except (TypeError, ValueError, KeyError, OverflowError, ArithmeticError, AttributeError) as exc:
        raise PaymentHold("Corrupt persisted walletless invoice") from exc


def _ready_order(order, *, buyer_id: int):
    from mpw_commerce.settlement import order_snapshot
    from mpw_commerce.downloads import _private_file

    if (order.customer_id != buyer_id or order.status != "pending"
            or order.currency != "USD"):
        raise PaymentHold("Order ownership/currency/state invalid")
    try:
        total, items = order_snapshot(order)
    except Exception as exc:
        raise PaymentHold("Order snapshot cannot be verified") from exc
    if len(items) != 1 or items[0][1] != "digital":
        raise PaymentHold("Pilot requires one downloadable digital product")
    item = items[0][0]
    source = _private_file(item)
    if source.is_symlink() or not source.is_file():
        raise PaymentHold("Digital product not safely available")
    if Decimal(total) != Decimal(order.total) or Decimal(total) <= 0:
        raise PaymentHold("Order price mismatch")
    return Decimal(total), item


def _commercial_db(settings, db):
    if (getattr(settings,"DEBUG",True) is not False
        or getattr(settings,"MPW_COMMERCE_RELEASE_READY",False) is not True
        or getattr(settings,"MPW_COMMERCE_DOWNLOADS_ENABLED",False) is not True
        or getattr(settings,"MPW_WALLETLESS_TRX_PUBLIC_ENABLED",False) is not True
        or getattr(settings,"MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED",False) is not True
        or getattr(db,"vendor","") != "mysql" or db.alias != "default"):
        raise PaymentHold("Public merchant TRX payment activation has not passed release gate")


def _named_lock(db):
    """MySQL lock must be held until after the atomic amount reservation."""
    cur = db.cursor()
    cur.execute("SELECT GET_LOCK(%s, 3)", [LOCK])
    if cur.fetchone() != (1,):
        cur.close()
        raise PaymentHold("Cannot safely allocate a unique amount")
    return cur


@contextmanager
def _allocation_lock(db):
    cur = _named_lock(db)
    try:
        yield
    finally:
        try:
            cur.execute("SELECT RELEASE_LOCK(%s)", [LOCK])
        finally:
            cur.close()


def reserve_commercial_intent(order_id: int, buyer_id: int, *, rate_provider,
                                  configured_receiver, now=None,
                                  random_below=secrets.randbelow,
                                  db=None, settings=None):
    """Issue once using existing PaymentIntent uniqueness, never alter schema."""
    if type(order_id) is not int or order_id <= 0 or type(buyer_id) is not int or buyer_id <= 0:
        raise PaymentHold("Valid buyer and order required")
    from django.conf import settings as django_settings
    from django.db import connection, transaction
    from django.utils import timezone as django_timezone
    from core.models import Order, PaymentIntent
    from mpw_commerce.models import CommerceInvoice

    db = db or connection
    settings = settings or django_settings
    _commercial_db(settings, db)
    if not callable(rate_provider) or not callable(configured_receiver):
        raise PaymentHold("Trusted quote and merchant address are missing")
    recipient = configured_receiver()
    from scripts.mojplaywin_native_chain_verify import tron_address_to_hex
    try:
        tron_address_to_hex(recipient)  # validates Base58Check, not merely shape
    except (TypeError, ValueError) as exc:
        raise PaymentHold("Invalid merchant-owned TRON address") from exc
    current = now or django_timezone.now()

    # Other payment rails are disabled in this controlled test. This check
    # also avoids ambiguous reuse of CommerceInvoice's signed invoice table.
    # Acquire before the transaction; release only after its COMMIT/ROLLBACK.
    with _allocation_lock(db), transaction.atomic(using=db.alias):
            order = Order.objects.select_for_update().get(pk=order_id)
            total, _ = _ready_order(order, buyer_id=buyer_id)
            existing = PaymentIntent.objects.select_for_update().filter(order=order).first()
            if existing is not None:
                if existing.provider != PROVIDER or existing.status != WAITING:
                    raise PaymentHold("Order already belongs to another payment flow")
                invoice = _decode(existing)
                if invoice.recipient != recipient or invoice.usd_total != total:
                    raise PaymentHold("Merchant or amount changed")
                return existing.pk, invoice, False
            # Unrelated buyers' pending legacy invoices must not freeze checkout.
            # Cross-order reuse is checked below by exact address+amount and
            # again during atomic settlement by globally unique tx references.
            if CommerceInvoice.objects.filter(order=order).exists():
                raise PaymentHold("In-flight signed invoice must be resolved")
            quote = rate_provider()
            # The quote may be observed milliseconds after the transaction starts.
            # Re-read the trusted clock AFTER fetching it (unless a test supplied now).
            # Otherwise fresh merchant quotes incorrectly fail as future-dated.
            if now is None:
                current = django_timezone.now()
            if not isinstance(quote, (tuple, list)) or len(quote) != 2:
                raise PaymentHold("Rate source did not return an observed quote")

            def used(sun):
                return (PaymentIntent.objects.filter(idempotency_key=_key(recipient, sun)).exists()
                        or CommerceInvoice.objects.filter(
                            network=NETWORK, recipient=recipient, amount_atomic=str(sun)
                        ).exists())

            invoice = issue_intent(
                order_id=order_id, customer_id=buyer_id, recipient=recipient,
                usd_total=total, usd_per_trx=Decimal(str(quote[0])),
                quote_observed_at=quote[1], now=current,
                is_amount_reserved=used, random_below=random_below,
            )
            created = PaymentIntent.objects.create(
                order=order, amount=total, currency="USD", status=WAITING,
                provider=PROVIDER, idempotency_key=_key(recipient, invoice.amount_sun),
                provider_reference=_encode(invoice),
            )
            return created.pk, invoice, True


def settle_commercial_intent(intent_id: int, tx_hash: str,
                                pair: TrustedNodePair, *, db=None, settings=None):
    """Atomic independent-chain evidence -> webhook receipt/ledger/grant.

    No CommerceReceipt is synthesized: its FK is to signed CommerceInvoice.
    Instead the EXISTING unique PaymentWebhookEvent event and unique LedgerEntry
    reference own the walletless proof, with one-time Order/PaymentIntent locks.
    """
    if type(intent_id) is not int or intent_id <= 0 or not isinstance(pair, TrustedNodePair):
        raise PaymentHold("Invalid payment intent or proof verifiers")
    from django.conf import settings as django_settings
    from django.db import connection, transaction
    from core.models import Order, PaymentIntent, LedgerEntry, PaymentWebhookEvent
    from mpw_commerce.models import CommerceInvoice, CommerceReceipt, CommerceFulfillment

    db = db or connection
    settings = settings or django_settings
    _commercial_db(settings, db)
    with transaction.atomic(using=db.alias):
        intent = PaymentIntent.objects.select_for_update().select_related("order").get(pk=intent_id)
        if intent.status != WAITING:
            raise PaymentHold("Intent is no longer awaiting payment")
        invoice = _decode(intent)
        order = Order.objects.select_for_update().get(pk=intent.order_id)
        total, item = _ready_order(order, buyer_id=invoice.customer_id)
        if total != invoice.usd_total:
            raise PaymentHold("Order price changed after quote")
        # Protect this order from competing legacy settlement, without
        # rejecting unrelated customers' outstanding signed invoices.
        if CommerceInvoice.objects.filter(order=order).exists():
            raise PaymentHold("Cannot mix new settlement with signed invoices")

        def already_used(network, normalized):
            if CommerceReceipt.objects.filter(tx_hash=normalized).exists():
                return True
            try:
                from django.apps import apps
                native = apps.get_model("mpw_native_checkout", "NativeChainTransfer")
            except LookupError:
                native = None
            if native is not None and native.objects.filter(tx_hash=normalized).exists():
                return True
            if PaymentWebhookEvent.objects.filter(provider=PROVIDER,event_id=normalized).exists():
                return True
            return LedgerEntry.objects.filter(reference="walletless:"+network+":"+normalized).exists()

        tx, sender = pair.verify(invoice, tx_hash, already_used)
        digest = hashlib.sha256(json.dumps({
            "intent_id":intent_id, "tx_hash":tx,"network":NETWORK,
            "recipient":invoice.recipient,"sender":sender,"sun":invoice.amount_sun,
            "source_a":pair.identifier_a,"source_b":pair.identifier_b,
        },sort_keys=True,separators=(",", ":")).encode()).hexdigest()
        event = PaymentWebhookEvent.objects.create(
            provider=PROVIDER, event_id=tx, event_type="tron_finalized",
            payment_intent=intent, payload_hash=digest, status="processed",
        )
        reference = "walletless:"+NETWORK+":"+tx
        LedgerEntry.objects.create(
            order=order, payment_intent=intent, entry_type="credit",
            amount=total, currency="USD", reference=reference,
            metadata={"payment_method":PROVIDER,"network":NETWORK,
                      "tx_hash":tx,"sender":sender,"evidence_digest":digest,
                      "walletless_receipt_event_id":event.pk},
        )
        CommerceFulfillment.objects.create(
            item=item, kind="digital", status=CommerceFulfillment.Status.READY,
        )
        intent.status="paid"
        intent.save(update_fields=["status", "updated_at"])
        order.status="paid"
        order.save(update_fields=["status", "updated_at"])
    return "paid"


def reconcile_commercial_intent_from_candidates(intent_id: int, buyer_id: int,
                                                   *, server_lookup, pair,
                                                   db=None, settings=None) -> str:
    """Buyer status event -> independently proved settlement in TEST MariaDB.

    The merchant-owned indexer returns transaction IDs only. Neither browser
    callbacks nor wallet responses can supply a payment proof. Any ambiguity
    is held for review; no background timer or public route is installed.
    """
    if (type(intent_id) is not int or intent_id<=0 or type(buyer_id) is not int
            or buyer_id<=0 or not callable(server_lookup)
            or not isinstance(pair,TrustedNodePair)
            or pair.audited_as_independent is not True):
        raise PaymentHold("Untrusted event-driven reconciliation adapter")
    from django.conf import settings as django_settings
    from django.db import connection
    from core.models import PaymentIntent

    db=db or connection
    settings=settings or django_settings
    _commercial_db(settings,db)
    intent=PaymentIntent.objects.select_related("order").filter(
        pk=intent_id,order__customer_id=buyer_id,provider=PROVIDER,
    ).first()
    if intent is None:
        raise PaymentHold("Invoice does not belong to buyer")
    if intent.status!=WAITING:
        return "unchanged"
    invoice=_decode(intent)
    candidates=server_lookup(invoice.recipient,invoice.amount_sun,
                             invoice.issued_at,invoice.expires_at)
    if not isinstance(candidates,(list,tuple)) or len(candidates)>16:
        raise PaymentHold("Unbounded or untrusted chain indexer response")
    if any(not isinstance(tx,str) or TX_ID.fullmatch(tx) is None
           for tx in candidates):
        raise PaymentHold("Invalid candidate transaction identity")
    unique=set(candidates)
    if not unique:
        return "awaiting"
    if len(unique)!=1:
        raise PaymentHold("Ambiguous invoice transfer; requires review")
    # Full solidity body and receipt are re-read from both authenticated
    # operators, and the receipt, ledger and fulfillment commit atomically.
    return settle_commercial_intent(intent_id,next(iter(unique)),pair,
                                       db=db,settings=settings)


def commercial_buyer_status(intent_id: int, buyer_id: int, *, db=None,
                               settings=None) -> dict:
    """Read-only owner-scoped entitlement check; never trusts payment browser UI."""
    if type(intent_id) is not int or intent_id <= 0 or type(buyer_id) is not int or buyer_id <= 0:
        raise PaymentHold("Invalid buyer or invoice")
    from django.conf import settings as django_settings
    from django.db import connection
    from core.models import PaymentIntent, LedgerEntry, PaymentWebhookEvent, OrderItem
    from mpw_commerce.models import CommerceFulfillment
    from mpw_commerce.downloads import _private_file

    db = db or connection
    settings = settings or django_settings
    _commercial_db(settings, db)
    intent = PaymentIntent.objects.select_related("order").filter(
        pk=intent_id, order__customer_id=buyer_id, provider=PROVIDER,
    ).first()
    if intent is None:
        raise PaymentHold("Buyer has no such payment intent")
    invoice = _decode(intent)
    if (intent.status != "paid" or intent.order.status != "paid"
            or Decimal(intent.order.total) != invoice.usd_total):
        return {"status": "awaiting", "can_download": False}
    receipt = PaymentWebhookEvent.objects.filter(
        provider=PROVIDER, payment_intent=intent,
        event_type="tron_finalized", status="processed",
    ).first()
    if receipt is None or not receipt.payload_hash:
        return {"status": "review", "can_download": False}
    ledger = LedgerEntry.objects.filter(
        order=intent.order, payment_intent=intent, entry_type="credit",
        currency="USD", amount=invoice.usd_total,
        reference="walletless:"+NETWORK+":"+receipt.event_id,
    ).first()
    if (ledger is None or not isinstance(ledger.metadata, dict)
            or ledger.metadata.get("network") != NETWORK
            or ledger.metadata.get("tx_hash") != receipt.event_id
            or ledger.metadata.get("evidence_digest") != receipt.payload_hash
            or ledger.metadata.get("walletless_receipt_event_id") != receipt.pk):
        return {"status": "review", "can_download": False}
    items = list(OrderItem.objects.filter(order=intent.order)[:2])
    if len(items) != 1 or not CommerceFulfillment.objects.filter(
        item=items[0], kind="digital", status=CommerceFulfillment.Status.READY,
    ).exists():
        return {"status": "review", "can_download": False}
    try:
        source = _private_file(items[0])
        private_file_ready = not source.is_symlink() and source.is_file()
    except (OSError, ValueError):
        private_file_ready = False
    if not private_file_ready:
        return {"status": "review", "can_download": False}
    return {"status": "paid", "can_download": True,
            "download_path": f"/commerce/trx-easy/download/{intent_id}/"}


def open_commercial_paid_file(intent_id: int, buyer_id: int, *, db=None,
                                 settings=None):
    """Open a real private artifact ONLY after ownership and ledger verification.

    Caller owns the returned file object and MUST close it or use FileResponse.
    Uses O_NOFOLLOW and fstat so symlink swaps cannot expose arbitrary files.
    """
    state = commercial_buyer_status(intent_id, buyer_id,db=db,settings=settings)
    if state.get("can_download") is not True:
        raise PaymentHold("No independently verified buyer entitlement")
    from core.models import PaymentIntent, OrderItem
    from mpw_commerce.downloads import _private_file
    intent=PaymentIntent.objects.select_related("order").get(pk=intent_id)
    if intent.order.customer_id != buyer_id or intent.provider != PROVIDER:
        raise PaymentHold("Payment intent is not owned by buyer")
    item=OrderItem.objects.get(order=intent.order)
    source=_private_file(item)
    if source.is_symlink() or not source.is_file():
        raise PaymentHold("Private product unavailable")
    flags=os.O_RDONLY | getattr(os,"O_CLOEXEC",0) | getattr(os,"O_NOFOLLOW",0)
    fd=os.open(str(source),flags)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise PaymentHold("Not a regular downloadable file")
        return os.fdopen(fd,"rb")
    except BaseException:
        os.close(fd)
        raise
