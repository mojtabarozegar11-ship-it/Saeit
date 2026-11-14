"""Rights-gated, buyer-owned digital delivery with descriptor-based file access."""
from __future__ import annotations
import hashlib
import os
import re
import stat
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .models import LedgerEntry, OrderItem, PaymentWebhookEvent
from .tron_gateway_settlement_claim import TronMainnetSettlementClaim
from .tron_gateway_web import PROVIDER, _host, _owner, _private

_SAFE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,220}\Z")


def _file_from_private_root(relative, expected_digest):
    """Open each segment O_NOFOLLOW; verify SHA256 on the very same open FD."""
    if (not isinstance(relative, str) or not _SAFE.fullmatch(relative)
            or relative.startswith("/") or "\\" in relative or
            any(x in ("", ".", "..") for x in relative.split("/"))):
        raise Http404("Private asset path invalid")
    root = Path(getattr(settings, "TRON_UNIFIED_PRIVATE_DIGITAL_ROOT", ""))
    if not root.is_absolute() or root.is_symlink() or not root.is_dir():
        raise Http404("Private digital root not configured")
    if not isinstance(expected_digest, str) or not re.fullmatch("[0-9a-fA-F]{64}", expected_digest):
        raise Http404("Approved file digest unavailable")
    parts = relative.split("/")
    handles = []
    try:
        folder_fd = os.open(str(root), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        handles.append(folder_fd)
        for part in parts[:-1]:
            folder_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                dir_fd=folder_fd)
            handles.append(folder_fd)
        asset_fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW,
                           dir_fd=folder_fd)
        st = os.fstat(asset_fd)
        if not stat.S_ISREG(st.st_mode) or not 0 < st.st_size <= 2**31:
            os.close(asset_fd)
            raise Http404("Digital asset not safe")
        stream = os.fdopen(asset_fd, "rb")
        try:
            digest = hashlib.sha256()
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
            if digest.hexdigest() != expected_digest.lower():
                raise Http404("Published asset hash no longer matches")
            stream.seek(0)
            return stream
        except BaseException:
            stream.close()
            raise
    except (OSError, ValueError) as exc:
        raise Http404("Private file not available") from exc
    finally:
        for fd in reversed(handles):
            os.close(fd)


@never_cache
@require_GET
def download_paid(request, invoice_id):
    host, language = _host(request)
    invoice = _owner(request, invoice_id, host)
    intent = invoice.payment_intent
    order = invoice.order
    if (invoice.status != "paid" or intent.status != "paid"
            or intent.provider != PROVIDER or order.status != "paid"
            or not invoice.txid or not invoice.proof_digest
            or invoice.txid != intent.provider_reference):
        raise Http404("Paid receipt not verified")
    if (not TronMainnetSettlementClaim.objects.filter(
            txid=invoice.txid, provider=PROVIDER, invoice=invoice,
            payment_intent=intent, proof_digest=invoice.proof_digest,
        ).exists()
            or PaymentWebhookEvent.objects.filter(
            provider=PROVIDER, event_id=invoice.txid,
            payment_intent=intent, status="processed",
            payload_hash=invoice.proof_digest).count() != 1
            or LedgerEntry.objects.filter(
                reference="tron-mainnet:" + invoice.txid,
                payment_intent=intent, order=order,
                entry_type="credit", amount=order.total,
                currency=order.currency).count() != 1):
        raise Http404("Merchant credit evidence incomplete")
    items = list(OrderItem.objects.filter(order=order).select_related("product")[:2])
    if len(items) != 1:
        raise Http404("Unrecognized invoice items")
    # Paid entitlement is pinned to the invoice snapshot. Later catalogue
    # price changes, re-quoting or an inactive listing must not erase a
    # customer's valid existing purchase.
    product = items[0].product
    md = product.metadata if type(product.metadata) is dict else {}
    if invoice.fulfillment_kind != "digital":
        raise Http404("No digital entitlement for this invoice")
    if md.get("rights_revoked") is True or md.get("delivery_suspended") is True:
        raise Http404("Purchased asset is under rights review")
    if (not invoice.asset_relpath_snapshot or
            not invoice.asset_sha256_snapshot or
            not invoice.rights_document_sha256_snapshot):
        raise Http404("Original digital entitlement is incomplete")
    stream = _file_from_private_root(
        invoice.asset_relpath_snapshot, invoice.asset_sha256_snapshot)
    resp = FileResponse(stream, as_attachment=True,
                        filename=Path(invoice.asset_relpath_snapshot).name)
    return _private(resp)
