"""Walletless TRX issuance on SAME Django/MariaDB transaction as real Order.

TEST-DB-ONLY. Never call this from active site routes. Production requires
independent approval, reversible schema deployment and shared legacy isolation.
"""
from __future__ import annotations
from decimal import Decimal
import secrets

from services.mpw_trx_walletless_core import PaymentHold, issue_intent
from services.mpw_walletless_django_test_bridge import _test_only_guard


def reserve_to_django_test_database(
    order_id: int, buyer_id: int, *,
    django_connection=None, django_settings=None,
    rate_provider=None, configured_receiver=None, now=None,
):
    if type(order_id) is not int or order_id <= 0 or type(buyer_id) is not int or buyer_id <= 0:
        raise PaymentHold("Authenticated order and buyer ID required")
    from django.conf import settings as default_settings
    from django.db import connection as default_connection, transaction
    from django.utils import timezone
    from core.models import Order
    from mpw_commerce.models import CommerceInvoice
    from mpw_commerce.settlement import order_snapshot
    from mpw_commerce.fulfillment import _private_file

    settings=django_settings or default_settings
    db=django_connection or default_connection
    _test_only_guard(settings,db)
    if db.alias!="default":
        raise PaymentHold("Wrong Django MariaDB connection")
    if not callable(rate_provider) or not callable(configured_receiver):
        raise PaymentHold("Trusted server rate and recipient not configured")

    from scripts.mojplaywin_native_chain_verify import tron_address_to_hex
    receiver=configured_receiver()
    try:tron_address_to_hex(receiver)
    except (ValueError,TypeError) as exc:
        raise PaymentHold("Invalid merchant TRON Base58Check recipient") from exc
    quote=rate_provider()
    if not isinstance(quote,(tuple,list)) or len(quote)!=2:
        raise PaymentHold("Expected trusted exchange rate and UTC observation time")
    usd_per_trx,observed=quote
    current=now or timezone.now()

    with transaction.atomic(using=db.alias):
        with db.cursor() as cur:
            cur.execute(
                """SELECT recipient FROM mpw_walletless_trx_allocator_v1
                   WHERE recipient=%s FOR UPDATE""",[receiver])
            if cur.fetchone() is None:
                raise PaymentHold("Recipient allocator not provisioned")
            order=Order.objects.select_for_update().get(pk=order_id)
            if order.customer_id!=buyer_id or order.status!="pending" or order.currency!="USD":
                raise PaymentHold("Order status/owner/currency invalid")
            total,items=order_snapshot(order)
            if len(items)!=1 or items[0][1]!="digital":
                raise PaymentHold("Test pilot is one digital item")
            source=_private_file(items[0][0])
            if source.is_symlink() or not source.is_file():
                raise PaymentHold("No distributable digital artifact")
            if CommerceInvoice.objects.filter(order=order).exists():
                raise PaymentHold("Order has a legacy signed invoice")
            if CommerceInvoice.objects.filter(status=CommerceInvoice.Status.AWAITING).exists():
                raise PaymentHold("Do not issue walletless during unresolved legacy invoices")
            cur.execute(
                """SELECT id,customer_id,amount_sun FROM mpw_walletless_trx_reservation_v1
                   WHERE order_id=%s FOR UPDATE""",[order_id])
            existing=cur.fetchone()
            if existing is not None:
                if int(existing[1])!=buyer_id:
                    raise PaymentHold("Existing walletless invoice belongs to another user")
                return int(existing[0]),int(existing[2]),False

            def used(sun):
                cur.execute(
                    """SELECT id FROM mpw_walletless_trx_reservation_v1
                       WHERE network='tron-mainnet' AND recipient=%s
                       AND amount_sun=%s LIMIT 1""",[receiver,sun])
                if cur.fetchone() is not None:
                    return True
                return CommerceInvoice.objects.filter(
                    network="tron-mainnet",recipient=receiver,amount_atomic=str(sun)
                ).exists()

            proposal=issue_intent(
                order_id=order_id,customer_id=buyer_id,recipient=receiver,
                usd_total=Decimal(total),usd_per_trx=Decimal(str(usd_per_trx)),
                quote_observed_at=observed,now=current,
                is_amount_reserved=used,random_below=secrets.randbelow)
            def utc_naive(d):
                return d.astimezone(__import__("datetime").timezone.utc).replace(tzinfo=None)
            cur.execute(
                """INSERT INTO mpw_walletless_trx_reservation_v1
                (order_id,customer_id,network,recipient,amount_sun,total_usd,
                 rate_usd_per_trx,issued_at,expires_at,status)
                VALUES (%s,%s,'tron-mainnet',%s,%s,%s,%s,%s,%s,'awaiting')""",
                [order_id,buyer_id,receiver,proposal.amount_sun,
                 str(proposal.usd_total),str(proposal.quote_usd_per_trx),
                 utc_naive(proposal.issued_at),utc_naive(proposal.expires_at)])
            return cur.lastrowid,proposal.amount_sun,True
