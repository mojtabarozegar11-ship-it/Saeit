#!/usr/bin/env python3
"""Private, one-order TRON Mainnet merchant canary. Not a public checkout.

Run only from the pinned cPanel relay through an isolated Python process.
preflight has NO writes; issue needs server-only opt-in and makes ONE real
pending order; verify checks finality, accounting, entitlement and bytes.
The permanent public acceptance and merchant-canary flags remain OFF.
Never handles a signing key or broadcasts funds.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

APP = Path("/home/zomorod2/Saeit-staging")
sys.path.insert(0, str(APP))
from services.mpw_trx_walletless_core import PaymentHold
RECEIPTS = Path("/home/zomorod2/.local/share/mpw-trx-private-canary")
ARMED = "merchant-one-time-mainnet-canary-20261023"
MAX_PRICE_USD = Decimal("0.10")
MAX_ASSET_BYTES = 64 * 1024 * 1024


class _CanarySettings:
    """Only the private reservation receives these overrides; Django does not."""
    def __init__(self, original):
        self.original = original

    def __getattr__(self, name):
        if name in (
            "MPW_WALLETLESS_TRX_PUBLIC_ENABLED",
            "MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED",
        ):
            return True
        return getattr(self.original, name)


def scoped_canary_settings(settings, connection):
    from services.mpw_walletless_commercial_intent import _paid_read_db, _commercial_db

    _paid_read_db(settings, connection)
    if (getattr(settings, "MPW_WALLETLESS_TRX_PUBLIC_ENABLED", False) is not False
            or getattr(settings, "MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED", False) is not False):
        raise PaymentHold("Canary only runs with BOTH permanent public gates closed")
    private = _CanarySettings(settings)
    _commercial_db(private, connection)
    return private


def _configured_ids():
    def exact_id(key):
        value = os.environ.get(key, "")
        if not value.isascii() or not value.isdecimal() or not 0 < len(value) <= 12:
            raise PaymentHold("Private canary buyer and product must be explicitly configured")
        parsed = int(value)
        if not 0 < parsed < 2**31:
            raise PaymentHold("Private canary ID is outside permitted range")
        return parsed
    return exact_id("MPW_TRX_CANARY_BUYER_ID"), exact_id("MPW_TRX_CANARY_PRODUCT_ID")



def _expected_sender():
    from services.mpw_trx_walletless_core import ADDRESS
    from scripts.mojplaywin_native_chain_verify import tron_address_to_hex
    sender = os.environ.get("MPW_TRX_CANARY_EXPECTED_SENDER", "")
    if not isinstance(sender, str) or ADDRESS.fullmatch(sender) is None:
        raise PaymentHold("Expected independent Mainnet sender is not configured")
    try:
        tron_address_to_hex(sender)  # Base58Check, not just T-prefix
    except (ValueError, TypeError) as exc:
        raise PaymentHold("Invalid trusted merchant canary sender address") from exc
    return sender

def _private_receipt_dir():
    if RECEIPTS.is_symlink():
        raise PaymentHold("Unsafe private canary receipt directory")
    RECEIPTS.mkdir(parents=True, exist_ok=True, mode=0o700)
    if RECEIPTS.is_symlink() or not RECEIPTS.is_dir():
        raise PaymentHold("Unsafe private canary receipt directory")
    os.chmod(RECEIPTS, 0o700)
    return RECEIPTS


def _receipt_path(invoice_id):
    if type(invoice_id) is not int or not 0 < invoice_id < 2**63:
        raise PaymentHold("Unsafe canary invoice identifier")
    return _private_receipt_dir() / ("invoice-" + str(invoice_id) + ".json")


def _read_receipt(invoice_id):
    path = _receipt_path(invoice_id)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 4096:
        raise PaymentHold("Private canary invoice receipt is unavailable")
    record = json.loads(path.read_text("utf-8"))
    if (type(record) is not dict or record.get("invoice_id") != invoice_id
            or record.get("network") != "tron-mainnet"):
        raise PaymentHold("Corrupt private canary invoice receipt")
    return record


def _write_receipt(invoice_id, record):
    path = _receipt_path(invoice_id)
    encoded = (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode()
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(encoded)
            f.flush()
            os.fsync(f.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path


def _asset_hash(source):
    if source.is_symlink() or not source.is_file():
        raise PaymentHold("Merchant canary requires existing private product bytes")
    size = source.stat().st_size
    if not 0 < size <= MAX_ASSET_BYTES:
        raise PaymentHold("Merchant canary product file outside safe size range")
    digest = hashlib.sha256()
    with source.open("rb") as f:
        for part in iter(lambda: f.read(262144), b""):
            digest.update(part)
    return digest.hexdigest(), size


def _preflight(*, nodes=True):
    from django.conf import settings
    from django.db import connection
    from services.mpw_walletless_commercial_intent import _commercial_db
    secure = scoped_canary_settings(settings, connection)
    try:
        _commercial_db(settings, connection)
    except PaymentHold:
        pass
    else:
        raise PaymentHold("Public checkout unexpectedly writable")
    if nodes:
        from services.mpw_trx_commercial_chain import read_only_independent_pair
        read_only_independent_pair()
    return secure


def _validate_buyer_product(buyer_id, product_id):
    from django.contrib.auth import get_user_model
    from core.models import Product
    from mpw_commerce.buyer_orders import _eligible
    from mpw_commerce.downloads import _private_file
    from types import SimpleNamespace

    buyer = get_user_model().objects.get(pk=buyer_id)
    if (getattr(buyer, "is_active", False) is not True
            or getattr(buyer, "is_staff", False) is not True):
        raise PaymentHold("Canary buyer must be an active merchant staff account")
    product = Product.objects.get(pk=product_id, active=True, currency="USD")
    price = Decimal(str(product.price))
    if (not price.is_finite() or not Decimal("0") < price <= MAX_PRICE_USD
            or not _eligible(product)):
        raise PaymentHold("Canary requires an eligible, sub-10-cent private digital SKU")
    checksum, size = _asset_hash(_private_file(SimpleNamespace(product=product)))
    return price, checksum, size


def issue():
    if os.environ.get("MPW_TRX_CANARY_ISSUE_ACK", "") != ARMED:
        raise PaymentHold("Private merchant order issuance has not been explicitly armed")
    buyer_id, product_id = _configured_ids()
    expected_sender = _expected_sender()
    secure = _preflight(nodes=True)
    from django.db import connection, transaction
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from core.models import Product, Order, OrderItem, PaymentIntent
    from services.mpw_walletless_commercial_intent import (
        PROVIDER, WAITING, _decode, reserve_commercial_intent,
    )
    from services.mpw_trx_commercial_web import _configured_receiver, _rate_provider
    price, asset_sha, size = _validate_buyer_product(buyer_id, product_id)
    written = None
    try:
        with transaction.atomic(using=connection.alias):
            locked_buyer = get_user_model().objects.select_for_update().get(pk=buyer_id)
            if (getattr(locked_buyer, "is_active", False) is not True
                    or getattr(locked_buyer, "is_staff", False) is not True):
                raise PaymentHold("Merchant staff buyer changed while reserving")
            # Repeated operator invocations reuse the same live invoice; this
            # prevents accidental repeated micro-charges and order inflation.
            existing = None
            for old in Order.objects.select_for_update().filter(
                customer_id=buyer_id, status="pending", currency="USD",
                created_at__gte=timezone.now() - timedelta(minutes=9),
            ).order_by("-id")[:10]:
                items = list(OrderItem.objects.filter(order=old)[:2])
                if len(items) != 1 or items[0].product_id != product_id:
                    continue
                pi = PaymentIntent.objects.filter(
                    order=old, provider=PROVIDER, status=WAITING).first()
                if pi is not None and _decode(pi).expires_at > timezone.now():
                    existing = pi
                    break
            if existing is not None:
                record = _read_receipt(existing.pk)
                return {"status": "EXISTING_PRIVATE_CANARY", "invoice_id": existing.pk,
                        "private_receipt": True, "public_enabled": False,
                        "broadcasts": 0, "expires_at": record["expires_at"]}
            product = Product.objects.select_for_update().get(
                pk=product_id, active=True, currency="USD")
            if Decimal(str(product.price)) != price:
                raise PaymentHold("Product price changed during canary reservation")
            order = Order.objects.create(
                customer_id=buyer_id, status="pending", total=price, currency="USD")
            OrderItem.objects.create(
                order=order, product=product, quantity=1,
                unit_price=price, currency="USD")
            invoice_id, invoice, created = reserve_commercial_intent(
                order.pk, buyer_id, rate_provider=_rate_provider,
                configured_receiver=_configured_receiver, db=connection,
                settings=secure,
            )
            if not created:
                raise PaymentHold("New canary must create one immutable invoice")
            record = {
                "v": 1, "network": "tron-mainnet", "invoice_id": invoice_id,
                "order_id": order.pk, "buyer_id": buyer_id, "product_id": product_id,
                "recipient": invoice.recipient, "expected_sender": expected_sender,
                "amount_sun": invoice.amount_sun,
                "usd_total": str(invoice.usd_total),
                "issued_at": invoice.issued_at.isoformat(),
                "expires_at": invoice.expires_at.isoformat(),
                "file_sha256": asset_sha, "file_size": size,
                "public_payment_enabled": False, "broadcasts": 0,
            }
            written = _write_receipt(invoice_id, record)
        return {"status": "PRIVATE_CANARY_INVOICE_CREATED", "invoice_id": invoice_id,
                "private_receipt": True, "public_enabled": False, "broadcasts": 0,
                "expires_at": record["expires_at"]}
    except BaseException:
        if written is not None:
            written.unlink(missing_ok=True)
        raise


def verify(invoice_id):
    from django.db import connection
    from core.models import PaymentIntent, PaymentWebhookEvent
    from services.mpw_walletless_commercial_intent import (
        PROVIDER, _decode, commercial_buyer_status, open_commercial_paid_file,
    )
    from services.mpw_trx_commercial_chain import read_only_independent_pair
    _preflight(nodes=False)
    record = _read_receipt(invoice_id)
    buyer_id, product_id = _configured_ids()
    expected_sender = _expected_sender()
    if record.get("expected_sender") != expected_sender:
        raise PaymentHold("Canary sender identity does not match the original invoice")
    if record.get("buyer_id") != buyer_id or record.get("product_id") != product_id:
        raise PaymentHold("Canary receipt not owned by the designated merchant buyer")
    intent = PaymentIntent.objects.select_related("order").get(pk=invoice_id, provider=PROVIDER)
    invoice = _decode(intent)
    if (invoice.customer_id != buyer_id
            or invoice.recipient != record.get("recipient")
            or invoice.amount_sun != record.get("amount_sun")
            or str(invoice.usd_total) != record.get("usd_total")):
        raise PaymentHold("Private canary invoice immutable fields mismatch")
    state = commercial_buyer_status(invoice_id, buyer_id)
    if state.get("can_download") is not True or state.get("status") != "paid":
        return {"status": "WAITING_FOR_REAL_MAINNET_SETTLEMENT",
                "invoice_id": invoice_id, "public_enabled": False}
    receipt = PaymentWebhookEvent.objects.get(
        provider=PROVIDER, payment_intent=intent, event_type="tron_finalized",
        status="processed",
    )
    # Reconfirm the historical tx directly against both live solidity nodes.
    confirmed = read_only_independent_pair().verify(
        invoice, receipt.event_id, lambda *_: False)
    if confirmed[0] != receipt.event_id or confirmed[1] != expected_sender:
        raise PaymentHold("Independent live transfer or designated sender does not match")
    digest = hashlib.sha256()
    total = 0
    with open_commercial_paid_file(invoice_id, buyer_id) as f:
        for chunk in iter(lambda: f.read(262144), b""):
            total += len(chunk)
            if total > MAX_ASSET_BYTES:
                raise PaymentHold("Canary delivered file exceeds safe limit")
            digest.update(chunk)
    if digest.hexdigest() != record.get("file_sha256") or total != record.get("file_size"):
        raise PaymentHold("Delivered customer file differs from reserved private product")
    acceptance = {"status": "PRIVATE_CANARY_PAYMENT_AND_DOWNLOAD_PASSED",
                  "invoice_id": invoice_id, "tx_sha256": hashlib.sha256(receipt.event_id.encode()).hexdigest(),
                  "file_sha256": digest.hexdigest(), "public_enabled": False}
    target = _private_receipt_dir() / ("accept-" + str(invoice_id) + ".json")
    if target.exists():
        if target.is_symlink() or target.stat().st_size > 4096:
            raise PaymentHold("Unsafe previous acceptance receipt")
        previous = json.loads(target.read_text("utf-8"))
        if previous != acceptance:
            raise PaymentHold("A previous independent acceptance proof differs")
    else:
        _write_receipt_file(target, acceptance)
    return acceptance


def _write_receipt_file(path, record):
    encoded = (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode()
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "wb") as file:
        file.write(encoded)
        file.flush()
        os.fsync(file.fileno())



def inventory():
    """Read-only merchant eligibility inventory; never disclose buyer identities."""
    from django.contrib.auth import get_user_model
    from core.models import Product
    from mpw_commerce.buyer_orders import _eligible
    from mpw_commerce.downloads import _private_file

    _preflight(nodes=False)
    staff = get_user_model().objects.filter(is_active=True, is_staff=True).count()
    candidates = []
    for product in Product.objects.filter(
        active=True, currency="USD",
        price__gt=Decimal("0"), price__lte=MAX_PRICE_USD,
    ).order_by("pk")[:100]:
        try:
            if _eligible(product):
                _, byte_count = _asset_hash(_private_file(SimpleNamespace(product=product)))
                if byte_count > 0:
                    candidates.append(product.pk)
        except (OSError, ValueError, PaymentHold):
            continue
    return {"status": "PRIVATE_CANARY_READONLY_INVENTORY",
            "eligible_micro_sku_ids": candidates[:10],
            "eligible_micro_sku_count_capped": len(candidates),
            "active_staff_account_count": staff,
            "financial_writes": 0, "public_enabled": False, "broadcasts": 0}

def main(argv=None):
    parser = argparse.ArgumentParser(description="Merchant-only, no-public-release TRX canary")
    parser.add_argument("action", choices=("preflight", "inventory", "issue", "verify"))
    parser.add_argument("--invoice-id", type=int)
    args = parser.parse_args(argv)
    if args.action == "verify" and args.invoice_id is None:
        parser.error("verify requires --invoice-id")
    if args.action != "verify" and args.invoice_id is not None:
        parser.error("--invoice-id is valid for verify only")
    if not APP.is_dir() or APP.is_symlink():
        raise PaymentHold("Unexpected trusted cPanel application")
    domain = Path("/home/zomorod2/mojplaywin.com/passenger_wsgi.py")
    if not domain.is_file() or domain.is_symlink() or "APP='/home/zomorod2/Saeit-staging'" not in domain.read_text("utf8", "replace"):
        raise PaymentHold("Unexpected live Passenger app identity")
    os.chdir(APP)
    sys.path.insert(0, str(APP))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    if args.action == "preflight":
        _preflight(nodes=True)
        result = {"status": "PRIVATE_CANARY_MAINNET_NODES_READY",
                  "financial_writes": 0, "public_enabled": False, "broadcasts": 0}
    elif args.action == "inventory":
        result = inventory()
    elif args.action == "issue":
        result = issue()
    else:
        result = verify(args.invoice_id)
    print("MPW_PRIVATE_MAINNET_CANARY=" + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("MPW_PRIVATE_MAINNET_CANARY=" + json.dumps({
            "status": "FAIL_CLOSED", "error_type": type(exc).__name__,
            "public_enabled": False, "broadcasts": 0,
        }, sort_keys=True))
        raise SystemExit(2)
