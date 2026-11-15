"""Internal-only sitewide blockchain settlement, never an HTTP view.

A trusted RPC/indexer verifier is REQUIRED; callers cannot mark an order paid
using a browser-supplied tx hash or a settings flag. Database writes (receipt,
ledger, paid order, fulfillment outbox) commit atomically. Merchant does not
approve individual purchases. All public integrations remain disabled.
"""
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
import json
import re

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.models import LedgerEntry
from .invoicing import RECEIVERS
from .models import CommerceInvoice, CommerceReceipt, CommerceFulfillment
from .policy import CommercePolicyError, order_snapshot

# Compatibility export used by the walletless producer.


class SettlementRejected(ValueError):
    pass


def _normalized_transaction(invoice,tx_hash):
    if type(tx_hash) is not str:
        raise SettlementRejected("Invalid transaction identifier")
    normalized=tx_hash.lower()
    pattern=(r"0x[0-9a-f]{64}" if invoice.asset=="ETH"
             else r"[0-9a-f]{64}")
    if re.fullmatch(pattern,normalized) is None:
        raise SettlementRejected("Invalid mainnet transaction identifier")
    return normalized


def _address_matches(asset, actual, expected):
    # TRON Base58Check addresses are case-sensitive; EVM hex is not.
    if type(actual) is not str or type(expected) is not str:
        return False
    return (actual.lower() == expected.lower()
            if asset == "ETH" else actual == expected)


def _verify_evidence(invoice,normalized,proof):
    """Recheck independent evidence against every immutable invoice field."""
    if type(proof) is not dict:
        raise SettlementRejected("No independent final-chain evidence")
    expected=RECEIVERS.get(invoice.asset)
    if not expected:
        raise SettlementRejected("Unsupported asset")
    network,recipient,_=expected
    # A forged or corrupted on-disk invoice must never become a paid order,
    # even when a chain transfer exists for the same numeric amount.
    raw_amount = invoice.amount_atomic
    if (type(raw_amount) is not str
            or re.fullmatch(r"[1-9][0-9]{0,49}", raw_amount) is None):
        raise SettlementRejected("Invalid immutable atomic payment amount")
    if (invoice.network!=network
        or not _address_matches(invoice.asset, invoice.recipient, recipient)
        or type(invoice.total_usd) is not Decimal
        or not invoice.total_usd.is_finite() or invoice.total_usd<=0
        or type(invoice.quote_usd_per_asset) is not Decimal
        or not invoice.quote_usd_per_asset.is_finite()
        or invoice.quote_usd_per_asset<=0
        or type(invoice.quote_source) is not str
        or invoice.quote_source not in ("coingecko","coinbase")
        or type(invoice.sender_challenge_id) is not str
        or not 8<=len(invoice.sender_challenge_id)<=128
        or any(not 33<=ord(ch)<=126 for ch in invoice.sender_challenge_id)):
        raise SettlementRejected("Unsupported or altered payment invoice")
    # A compromised or legacy persisted invoice cannot bypass the *original*
    # fresh independent rate and verified sender challenge at settlement time.
    # Guard types first so malformed DB rows fail closed as domain errors.
    stamps = (
        invoice.issued_at, invoice.expires_at,
        invoice.quote_observed_at, invoice.sender_signature_verified_at,
    )
    if any(type(stamp) is not datetime or timezone.is_naive(stamp)
           for stamp in stamps):
        raise SettlementRejected("Invoice timestamps are not independently trustworthy")
    if not (invoice.issued_at<invoice.expires_at
            <=invoice.issued_at+timedelta(minutes=10)
            and timedelta(0)<=invoice.issued_at-invoice.quote_observed_at
            <=timedelta(seconds=90)
            and timedelta(0)<=invoice.issued_at-invoice.sender_signature_verified_at
            <=timedelta(minutes=5)):
        raise SettlementRejected("Locked payment window or issuance evidence is invalid")
    block_time=proof.get("block_timestamp")
    if (type(block_time) is not datetime or timezone.is_naive(block_time)
        or not invoice.issued_at<=block_time<=invoice.expires_at):
        raise SettlementRejected("Transfer was not mined within the quote window")
    if (
        proof.get("finalized") is not True
        or type(proof.get("order_id")) is not int
        or proof.get("order_id")!=invoice.order_id
        or proof.get("network")!=invoice.network
        or proof.get("tx_hash")!=normalized
        or not _address_matches(
            invoice.asset, proof.get("sender"), invoice.expected_sender)
        or not _address_matches(
            invoice.asset, proof.get("recipient"), recipient)
        or type(proof.get("amount_atomic")) is not int
        or proof.get("amount_atomic")!=int(invoice.amount_atomic)
        or proof.get("backend")!=network+"-verified"
    ):
        raise SettlementRejected("Unverified, wrong-chain, or mismatched transfer")
    normalized_proof={
        "network":invoice.network, "tx_hash":normalized,
        "order_id":invoice.order_id, "sender":invoice.expected_sender,
        "recipient":recipient, "amount_atomic":invoice.amount_atomic,
        "block_timestamp":block_time.isoformat(),
        "finalized":True,"backend":proof["backend"],
    }
    digest=hashlib.sha256(
        json.dumps(normalized_proof,sort_keys=True,separators=(",",":"))
        .encode("utf-8")
    ).hexdigest()
    return digest,block_time


def settle_order_invoice(invoice_id,tx_hash,*,trusted_chain_verifier):
    """Atomic settlement for any configured USD multi-item order.

    trusted_chain_verifier is installed server-side and MUST fetch verified
    finalized receipts. The function has no public URL, and production flags
    default to False; no caller-provided evidence dictionary is accepted.
    """
    if getattr(settings,"MPW_COMMERCE_SETTLEMENT_ENABLED",False) is not True:
        raise SettlementRejected("Sitewide settlement is not released")
    if type(invoice_id) is not int or invoice_id<=0 or not callable(trusted_chain_verifier):
        raise SettlementRejected("Missing trusted settlement parameters")
    invoice=(CommerceInvoice.objects.select_related("order")
             .filter(pk=invoice_id).first())
    if invoice is None:
        raise SettlementRejected("Invoice missing")
    tx=_normalized_transaction(invoice,tx_hash)
    ref="mpw-commerce:"+invoice.network+":"+tx
    if invoice.status==CommerceInvoice.Status.PAID:
        if (invoice.order.status=="paid"
            and CommerceReceipt.objects.filter(invoice=invoice,network=invoice.network,tx_hash=tx).exists()
            and LedgerEntry.objects.filter(order=invoice.order,reference=ref).exists()):
            return "already_paid"
        raise SettlementRejected("Invoice already paid with another transaction")
    if invoice.status!=CommerceInvoice.Status.AWAITING:
        raise SettlementRejected("Invoice not payable")
    proof=trusted_chain_verifier(invoice,tx)
    digest,finalized_at=_verify_evidence(invoice,tx,proof)

    with transaction.atomic():
        current=(CommerceInvoice.objects.select_for_update()
                 .select_related("order","order__customer").get(pk=invoice_id))
        order=(current.order.__class__.objects.select_for_update()
               .get(pk=current.order_id))
        if current.status!=CommerceInvoice.Status.AWAITING or order.status!="pending":
            raise SettlementRejected("Order payment changed during verification")
        fixed=("asset","network","recipient","expected_sender","amount_atomic",
               "total_usd","quote_usd_per_asset","quote_observed_at",
               "issued_at","expires_at","sender_challenge_id",
               "sender_signature_verified_at")
        if any(getattr(current,f)!=getattr(invoice,f) for f in fixed):
            raise SettlementRejected("Payment invoice changed during verification")
        try:
            total,items=order_snapshot(order)
        except CommercePolicyError as exc:
            raise SettlementRejected(str(exc)) from exc
        if total!=current.total_usd or order.currency!="USD":
            raise SettlementRejected("Order total or currency mismatch")
        CommerceReceipt.objects.create(
            invoice=current,network=current.network,tx_hash=tx,
            sender=current.expected_sender,recipient=current.recipient,
            amount_atomic=current.amount_atomic,evidence_digest=digest,
            backend=proof["backend"],finalized_at=finalized_at,
        )
        LedgerEntry.objects.create(
            order=order,payment_intent=None,entry_type="payment",amount=total,
            currency="USD",reference=ref,
            metadata={"commerce_invoice_id":current.pk,
                      "network":current.network,"tx_hash":tx,
                      "evidence_digest":digest},
        )
        for item,kind in items:
            status={
                "digital":CommerceFulfillment.Status.READY,
                "subscription":CommerceFulfillment.Status.QUEUED,
                "service":CommerceFulfillment.Status.QUEUED,
                "physical":CommerceFulfillment.Status.DISPATCH,
            }[kind]
            CommerceFulfillment.objects.create(item=item,kind=kind,status=status)
        current.status=CommerceInvoice.Status.PAID
        current.save(update_fields=["status"])
        order.status="paid"
        order.save(update_fields=["status","updated_at"])
    return "paid"
