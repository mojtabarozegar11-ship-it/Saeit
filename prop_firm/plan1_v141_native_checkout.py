"""TRON-mainnet native 30 TRX settled-order / customer delivery service.

This is a PRIVATE BACKEND service; it exposes no public write route. The only
transaction data accepted come from HTTPS-configured SolidityNodes. The buyer
never controls wallet recipient, price, contract version or legal approvals.
This module cannot create legal clearance or substitute for regulator approval.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone as utc
from hashlib import sha256
import hmac
import json
import re
import secrets
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from .plan1_v141_native_payment_models import (
    PropV141NativeOrder, PropV141NativeReceipt, PropGlobalTRXSettlement,
)
from .plan1_v141_persistence_models import PropV141SimState
from .plan1_v141_virtual_tenant_models import PropV141VirtualBook


PRODUCT = "MOJ-PROP-01"
AMOUNT_SUN = 30_000_000
NETWORK = "tron-mainnet"
RECEIVER = "THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73"  # owner's known QR
REX_TX = re.compile(r"[0-9a-f]{64}\Z")
REX_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
REX_PAYER = re.compile(r"41[0-9a-f]{40}\Z")
REX_COUNTRY = re.compile(r"[A-Z]{2}\Z")
BASE58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
BODY_PATH = "/walletsolidity/gettransactionbyid"
INFO_PATH = "/walletsolidity/gettransactioninfobyid"


class CheckoutRejected(ValueError):
    pass


def _digest(s):
    if type(s) is not str or not REX_DIGEST.fullmatch(s) or s == "0" * 64:
        raise CheckoutRejected("Missing independently persisted signed proof")
    return s


def _addr_hex(value):
    if type(value) is not str or len(value) != 34 or not value.startswith("T"):
        raise CheckoutRejected("Invalid TRON receiving wallet")
    number = 0
    for ch in value:
        if ch not in BASE58:
            raise CheckoutRejected("Bad TRON Base58 alphabet")
        number = number * 58 + BASE58.index(ch)
    try:
        raw = number.to_bytes(25, "big")
    except OverflowError as exc:
        raise CheckoutRejected("TRON wallet overflow") from exc
    if (raw[0] != 0x41 or
            not hmac.compare_digest(
                raw[21:], sha256(sha256(raw[:21]).digest()).digest()[:4])):
        raise CheckoutRejected("TRON wallet checksum does not match")
    return raw[:21].hex()


def _release_enabled():
    return getattr(settings, "MOJPROP_V141_NATIVE_TRX_RELEASE_ENABLED", False) is True


def issue_private_foreign_invoice(*, operator, buyer, foreign_country,
                                  payer_hex41, wallet_owner_attestation_sha256,
                                  buyer_contract_acceptance_sha256,
                                  compliance_document_sha256, compliance_ref,
                                  terms_version, terms_sha256, clearance_verified):
    """Issue DB-bound invoice only after independent reviewed merchant evidence.

    Caller must be a private audited admin integration, NOT an HTTP customer.
    Terms must be *published* (not the current v1.4.1 DRAFT terms).
    """
    if not _release_enabled():
        raise CheckoutRejected("No lawful merchant release was configured")
    if (operator is None or operator.is_authenticated is not True
            or operator.is_active is not True or operator.is_superuser is not True
            or buyer is None or buyer.is_active is not True
            or buyer.pk is None or operator.pk == buyer.pk):
        raise CheckoutRejected("Trusted independent back-office operator required")
    if (clearance_verified is not True or
            type(foreign_country) is not str or not REX_COUNTRY.fullmatch(foreign_country)
            or foreign_country in ("IR", "US")
            or type(payer_hex41) is not str or not REX_PAYER.fullmatch(payer_hex41)
            or type(compliance_ref) is not str or len(compliance_ref.strip()) < 12
            or type(terms_version) is not str
            or not 8 <= len(terms_version) <= 96 or "DRAFT" in terms_version.upper()
            or type(getattr(settings, "MOJPROP_V141_NATIVE_TERMS_VERSION", None)) is not str
            or terms_version != settings.MOJPROP_V141_NATIVE_TERMS_VERSION
            or terms_sha256 != getattr(settings, "MOJPROP_V141_NATIVE_TERMS_SHA256", None)):
        raise CheckoutRejected("Customer and export payment eligibility not verified")
    _digest(wallet_owner_attestation_sha256)
    _digest(buyer_contract_acceptance_sha256)
    _digest(compliance_document_sha256)
    _digest(terms_sha256)
    if getattr(settings, "MOJPROP_V141_TRON_RECEIVER", None) != RECEIVER:
        raise CheckoutRejected("Merchant recipient differs from verified owner QR")
    _addr_hex(RECEIVER)
    if not getattr(buyer, "email", "").strip():
        raise CheckoutRejected("Identifiable buyer with valid email required")
    with transaction.atomic():
        now = timezone.now()
        return PropV141NativeOrder.objects.create(
            reference="MOJPROP01-" + secrets.token_hex(16).upper(),
            buyer=buyer,
            product_code=PRODUCT,
            country_of_residence=foreign_country,
            recipient=RECEIVER,
            payer_hex41=payer_hex41,
            amount_sun=AMOUNT_SUN,
            terms_version=terms_version,
            terms_sha256=terms_sha256,
            consent_digest=buyer_contract_acceptance_sha256,
            legal_clearance_digest=compliance_document_sha256,
            clearance_document_ref=compliance_ref,
            issued_at=now,
            expires_at=now + timedelta(hours=2),
        )


def _solidity_base_urls():
    bases = getattr(settings, "MOJPROP_V141_TRON_SOLIDITY_PROVIDERS", ())
    if type(bases) not in (tuple, list) or len(bases) != 2:
        raise CheckoutRejected("Two independent audited RPC providers required")
    hosts = []
    for b in bases:
        if type(b) is not str:
            raise CheckoutRejected("Invalid RPC provider")
        u = urlsplit(b)
        if (u.scheme != "https" or u.path not in ("", "/") or u.query or
                u.fragment or u.username or u.password or u.port is not None or
                not u.hostname or u.hostname.lower() in ("localhost", "127.0.0.1")):
            raise CheckoutRejected("Trusted HTTPS root provider required")
        hosts.append(u.hostname.lower())
    if hosts[0] == hosts[1]:
        raise CheckoutRejected("Two truly distinct RPC operators required")
    return tuple(b.rstrip("/") for b in bases)


def _query_solidified(base, path, txid):
    """Only caller-configured HTTPS provider + fixed Solidity API path."""
    data = json.dumps({"value": txid}).encode("ascii")
    req = Request(base + path, data=data, method="POST",
                  headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=8) as resp:
        if resp.geturl() != base + path or resp.status != 200:
            raise CheckoutRejected("RPC redirect or HTTP failure")
        raw = resp.read(256_001)
        if len(raw) > 256_000:
            raise CheckoutRejected("Oversized RPC response")
    try:
        obj = json.loads(raw.decode("utf8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CheckoutRejected("Malformed verified node response") from exc
    if not isinstance(obj, dict) or "Error" in obj:
        raise CheckoutRejected("SolidityNode returned a failure")
    return obj


def _proof(invoice, txid, body, receipt):
    if body.get("txID") != txid or receipt.get("id") != txid:
        raise CheckoutRejected("Transaction ID mismatch")
    raw = body.get("raw_data", {})
    contracts = raw.get("contract") if isinstance(raw, dict) else None
    if type(contracts) is not list or len(contracts) != 1:
        raise CheckoutRejected("Not exactly one native transfer")
    c = contracts[0]
    if not isinstance(c, dict) or c.get("type") != "TransferContract":
        raise CheckoutRejected("Not native TRX")
    param = c.get("parameter")
    value = param.get("value") if isinstance(param, dict) else None
    if not isinstance(value, dict):
        raise CheckoutRejected("Missing native transfer parameters")
    sender, recipient, amount = (
        value.get("owner_address"), value.get("to_address"), value.get("amount")
    )
    if (sender != invoice.payer_hex41 or recipient != _addr_hex(invoice.recipient)
            or type(amount) is not int or amount != AMOUNT_SUN or sender == recipient):
        raise CheckoutRejected("Sender/recipient/30 TRX binding mismatch")
    ret = body.get("ret")
    if (type(ret) is not list or len(ret) != 1 or
            not isinstance(ret[0], dict) or ret[0].get("contractRet") != "SUCCESS"):
        raise CheckoutRejected("Transfer execution was not successful")
    receipt_meta = receipt.get("receipt")
    if (receipt.get("result") not in (None, "SUCCESS") or
            not isinstance(receipt_meta, dict) or
            receipt_meta.get("result") not in (None, "SUCCESS")):
        raise CheckoutRejected("Execution receipt indicates failure")
    block, millis = receipt.get("blockNumber"), receipt.get("blockTimeStamp")
    if type(block) is not int or block < 1 or type(millis) is not int or millis < 1:
        raise CheckoutRejected("Solidified block evidence absent")
    dt = datetime.fromtimestamp(millis / 1000, tz=utc.utc)
    if dt < invoice.issued_at or dt >= invoice.expires_at or dt > timezone.now():
        raise CheckoutRejected("Block outside order lifetime")
    return (txid, sender, recipient, amount, block, millis)


def confirm_native_trx_and_deliver(*, reference, txid):
    """Verify TWO independent finality nodes then atomic DB record + book.

    The function is internal, never a web endpoint. A returned payment receipt
    means a real customer-specific virtual DEMO book was created in the SAME
    DB commit; it never creates a funded broker account or payout.
    """
    if not _release_enabled():
        raise CheckoutRejected("Native TRX collection remains disabled")
    if type(txid) is not str or not REX_TX.fullmatch(txid):
        raise CheckoutRejected("Invalid transaction identifier")
    if type(reference) is not str or len(reference) > 56:
        raise CheckoutRejected("Invalid invoice reference")
    try:
        order = PropV141NativeOrder.objects.get(reference=reference)
    except PropV141NativeOrder.DoesNotExist as exc:
        raise CheckoutRejected("Unrecognized merchant-issued invoice") from exc
    if order.status == "settled":
        stored = PropV141NativeReceipt.objects.select_related("settlement").get(order=order)
        if stored.settlement.txid == txid:
            return stored  # idempotency never grants two assessments
        raise CheckoutRejected("One order cannot settle twice")
    if (order.product_code != PRODUCT or order.amount_sun != AMOUNT_SUN or
            order.country_of_residence in ("IR", "US") or
            order.recipient != RECEIVER or "DRAFT" in order.terms_version.upper()):
        raise CheckoutRejected("Order/terms not authorized for foreign TRX")
    bases = _solidity_base_urls()
    observations = []
    for base in bases:
        body = _query_solidified(base, BODY_PATH, txid)
        receipt = _query_solidified(base, INFO_PATH, txid)
        observations.append(_proof(order, txid, body, receipt))
    if observations[0] != observations[1]:
        raise CheckoutRejected("Independent SolidityNodes disagree")
    txid, sender, recipient, amount, block, millis = observations[0]
    proof_payload = json.dumps(
        {"txid": txid, "network": NETWORK, "sender": sender,
         "recipient": recipient, "amount": amount,
         "block": block, "millis": millis}, sort_keys=True,
        separators=(",", ":"),
    )
    proof_digest = sha256(proof_payload.encode()).hexdigest()
    confirmed_at = datetime.fromtimestamp(millis / 1000, tz=utc.utc)
    with transaction.atomic():
        order = PropV141NativeOrder.objects.select_for_update().get(reference=reference)
        if order.status == "settled":
            existing = PropV141NativeReceipt.objects.select_related("settlement").get(order=order)
            if existing.settlement.txid == txid:
                return existing
            raise CheckoutRejected("Order already settled to another transaction")
        # Race-safe global unique reservation: no double-selling one txid.
        try:
            claim = PropGlobalTRXSettlement.objects.create(
                network=NETWORK, txid=txid, product_code=PRODUCT,
                order_reference=order.reference,
                evidence_sha256=proof_digest, solidified_block=block,
            )
        except IntegrityError as exc:
            raise CheckoutRejected("TXID already consumed by another order or SKU") from exc
        state = PropV141SimState.objects.create(
            challenge_ref=order.reference,
            terms_sha256=order.terms_sha256,
            trusted_source="pending-operator-signed-simulator",
            trusted_key_id="pending-independent-feed",
            trusted_feed_source="pending-independent-simulator",
        )
        book = PropV141VirtualBook.objects.create(
            state=state, owner=order.buyer, trader_ref=order.reference,
            terms_sha256=order.terms_sha256,
            trusted_feed_source="pending-independent-simulator",
            evaluation_started_at=confirmed_at, max_unlocked_stage=1,
        )
        result = PropV141NativeReceipt.objects.create(
            order=order, settlement=claim, state=state,
            book=book, confirmed_at=confirmed_at,
        )
        order.status = "settled"
        order.settled_at = confirmed_at
        order.save(update_fields=["status", "settled_at"])
        return result
