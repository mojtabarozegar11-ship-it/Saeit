"""Prototype bridge to the REAL Django financial models.

Not installed in urls.py, Passenger or any periodic production command.
Execution is explicitly limited to a TEST database with legacy new issuance off.
All native payment evidence comes from independently pinned server adapters,
NEVER a request body or wallet callback. No fake wallet signatures are recorded.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone
from decimal import Decimal
import hashlib
import json
import re

from services.mpw_trx_walletless_core import (
    InvoiceIntent, PaymentHold, SolidifiedTransfer, verify_two_source_transfer,
)

_HEX64 = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True)
class TrustedNodePair:
    """Only initialized from server configuration, never from an HTTP parameter."""
    identifier_a: str
    identifier_b: str
    prove_a: object
    prove_b: object
    audited_as_independent: bool = False

    def verify(self, invoice: InvoiceIntent, transaction_hash: str, tx_used):
        if (self.audited_as_independent is not True
                or self.identifier_a == self.identifier_b
                or not self.identifier_a or not self.identifier_b
                or not callable(self.prove_a) or not callable(self.prove_b)
                or not isinstance(transaction_hash, str)
                or not _HEX64.fullmatch(transaction_hash)):
            raise PaymentHold("Untrusted independent nodes")
        a = self.prove_a(transaction_hash)
        b = self.prove_b(transaction_hash)
        if (not isinstance(a, SolidifiedTransfer)
                or not isinstance(b, SolidifiedTransfer)
                or a.source_id != self.identifier_a
                or b.source_id != self.identifier_b):
            raise PaymentHold("Node identity/evidence mismatch")
        return verify_two_source_transfer(
            invoice, a, b, tx_previously_consumed=tx_used
        )


def _test_only_guard(django_settings, db):
    """No merchant production ledger writes until real-chain acceptance."""
    if (getattr(django_settings, "MPW_WALLETLESS_TRX_TEST_ADAPTER", False) is not True
        or getattr(django_settings, "MPW_COMMERCE_INVOICING_ENABLED", True) is not False
        or getattr(django_settings, "MPW_WALLETLESS_TRX_PUBLIC_ENABLED", False) is not False
        or getattr(db, "vendor", "") != "mysql"):
        raise PaymentHold("Walletless real Django adapter is not approved for production")
    db_name = str(db.settings_dict.get("NAME", "")).lower()
    if not db_name.startswith("test_") or "production" in db_name:
        raise PaymentHold("Integration requires an isolated test database")


def settle_to_django_test_database(
    invoice_id: int, tx_hash: str, pair: TrustedNodePair,
    *, django_connection=None, django_settings=None,
) -> str:
    """Real Order/LedgerEntry/CommerceFulfillment writes in TEST MariaDB only.

    Only new walletless receipt is written to the walletless table. The real
    CommerceReceipt is NOT forged: that model's FK points at signed invoices.
    Caller must provision walletless reservation/receipt tables in the same
    isolated Django database, seed the allocator, and use a full test backup.
    """
    if type(invoice_id) is not int or invoice_id <= 0:
        raise PaymentHold("Missing valid invoice ID")
    if not isinstance(pair, TrustedNodePair):
        raise PaymentHold("Missing pinned server-side node pair")
    from django.conf import settings as default_settings
    from django.db import connection as default_connection, transaction
    from core.models import Order, LedgerEntry
    from mpw_commerce.models import CommerceInvoice, CommerceReceipt, CommerceFulfillment
    from mpw_commerce.settlement import order_snapshot
    from mpw_commerce.fulfillment import _private_file

    settings = django_settings or default_settings
    db = django_connection or default_connection
    _test_only_guard(settings, db)

    # Django model queries and raw SQL must share one atomic MariaDB connection.
    if db.alias != "default":
        raise PaymentHold("Only the default isolated Django test connection is supported")
    if getattr(CommerceInvoice.Status, "AWAITING", None) is None:
        raise PaymentHold("Existing invoice model has changed")

    with transaction.atomic(using=db.alias):
        with db.cursor() as cur:
            cur.execute(
                """SELECT id,order_id,customer_id,network,recipient,amount_sun,
                           total_usd,rate_usd_per_trx,issued_at,expires_at,status
                   FROM mpw_walletless_trx_reservation_v1
                   WHERE id=%s FOR UPDATE""",
                [invoice_id],
            )
            raw = cur.fetchone()
            if raw is None:
                raise PaymentHold("No reserved walletless invoice")
            (rid,order_id,buyer_id,network,recipient,amount_sun,usd,rate,
             issued_at,expires_at,status) = raw
            if status != "awaiting" or network != "tron-mainnet":
                raise PaymentHold("Not awaiting a mainnet payment")

            order = Order.objects.select_for_update().get(pk=order_id)
            if (order.customer_id != buyer_id or order.status != "pending"
                or order.currency != "USD"):
                raise PaymentHold("Order owner/status/currency mismatch")
            try:
                total, items = order_snapshot(order)
            except Exception as exc:
                raise PaymentHold("Order snapshot is no longer eligible") from exc
            if Decimal(total) != Decimal(str(usd)) or Decimal(order.total) != Decimal(str(usd)):
                raise PaymentHold("Amount changed since invoice reservation")
            if len(items) != 1 or items[0][1] != "digital":
                raise PaymentHold("Only one verified digital good in pilot")
            item, kind = items[0]
            # Resolve the actual private artifact before recognizing any payment.
            # The downloader will independently recheck ownership and file.
            source = _private_file(item)
            if source.is_symlink() or not source.is_file():
                raise PaymentHold("Digital artifact unavailable")
            if CommerceInvoice.objects.filter(order=order).exists():
                raise PaymentHold("Signed invoice already exists for order")
            if CommerceInvoice.objects.filter(status=CommerceInvoice.Status.AWAITING).exists():
                raise PaymentHold("Legacy in-flight invoices must be drained")

            invo = InvoiceIntent(
                order_id=int(order_id),customer_id=int(buyer_id),network=network,
                recipient=recipient,amount_sun=int(amount_sun),
                usd_total=Decimal(str(usd)),quote_usd_per_trx=Decimal(str(rate)),
                issued_at=issued_at.replace(tzinfo=timezone.utc),
                expires_at=expires_at.replace(tzinfo=timezone.utc),
            )
            def previously_used(chain, normalized):
                if CommerceReceipt.objects.filter(network=chain,tx_hash=normalized).exists():
                    return True
                cur.execute(
                    """SELECT invoice_id FROM mpw_walletless_trx_receipt_v1
                       WHERE network=%s AND tx_hash=%s LIMIT 1""",
                    [chain,normalized],
                )
                return cur.fetchone() is not None
            tx,sender = pair.verify(invo,tx_hash,previously_used)

            # A unique legacy LedgerEntry reference prevents duplicate real sale.
            reference = "walletless:"+network+":"+tx
            if LedgerEntry.objects.filter(reference=reference).exists():
                raise PaymentHold("Payment ledger reference already recorded")
            evidence = hashlib.sha256(json.dumps({
                "invoice":int(rid),"network":network,"hash":tx,
                "sender":sender,"recipient":recipient,"sun":int(amount_sun),
                "node_a":pair.identifier_a,"node_b":pair.identifier_b,
            },sort_keys=True,separators=(",",":")).encode("utf8")).hexdigest()
            cur.execute(
                """INSERT INTO mpw_walletless_trx_receipt_v1
                   (invoice_id,network,tx_hash,sender,evidence_sha256,confirmed_at)
                   VALUES (%s,%s,%s,%s,%s,UTC_TIMESTAMP(6))""",
                [rid,network,tx,sender,evidence],
            )
            LedgerEntry.objects.create(
                order=order,payment_intent=None,entry_type="credit",
                amount=total,currency="USD",reference=reference,
                metadata={"payment_method":"walletless_trx","invoice_id":int(rid),
                          "network":network,"tx_hash":tx,"evidence_digest":evidence},
            )
            CommerceFulfillment.objects.create(
                item=item,kind="digital",status=CommerceFulfillment.Status.READY,
            )
            cur.execute(
                """UPDATE mpw_walletless_trx_reservation_v1
                   SET status='paid',verified_tx_hash=%s
                   WHERE id=%s AND status='awaiting'""",
                [tx,rid],
            )
            if cur.rowcount != 1:
                raise PaymentHold("Concurrent settlement race")
            order.status = "paid"
            order.save(update_fields=["status","updated_at"])
    return "paid"


def unpaid_owner_safe_status(*, customer_id: int, order_owner_id: int,
                             invoice_status: str, has_verified_ledger: bool,
                             has_ready_fulfillment: bool) -> dict:
    """Pure status gate used before a real owner-scoped secure download URL."""
    if (type(customer_id) is not int or customer_id <= 0
        or type(order_owner_id) is not int or order_owner_id <= 0
        or customer_id != order_owner_id):
        return {"status":"unavailable","can_download":False}
    paid = (invoice_status == "paid" and has_verified_ledger is True
            and has_ready_fulfillment is True)
    return {"status":"paid" if paid else "awaiting","can_download":paid}
