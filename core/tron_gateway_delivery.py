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
from .tron_gateway_web import PROVIDER, _host, _owner, _private, _read_product
from .tron_gateway_verify import MAINNET_RECEIVER

_SAFE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,220}\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_TXID = re.compile(r"[0-9a-f]{64}\Z")
MAX_DIGITAL_FILE_BYTES = 128 * 1024 * 1024
MAX_PRIVATE_SEGMENTS = 8


def _private_asset_parts(relative):
    """Never treat buyer/product metadata as a filesystem path without checks."""
    if (type(relative) is not str or _SAFE.fullmatch(relative) is None
            or relative.startswith("/") or "\\" in relative):
        raise Http404("Private asset path invalid")
    parts = relative.split("/")
    if (not 1 <= len(parts) <= MAX_PRIVATE_SEGMENTS
            or any(part in ("", ".", "..") or part.startswith(".") for part in parts)
            or any(len(part) > 96 for part in parts)):
        raise Http404("Private asset path invalid")
    if not relative.lower().endswith((".pdf", ".epub", ".zip")):
        raise Http404("Unsupported private digital file")
    return parts


def _safe_root():
    raw = getattr(settings, "TRON_UNIFIED_PRIVATE_DIGITAL_ROOT", None)
    if type(raw) not in (str, Path):
        raise Http404("Private digital root not configured")
    root = Path(raw)
    if (not root.is_absolute() or ".." in root.parts
            or str(root) == "/" or not getattr(os, "O_NOFOLLOW", 0)
            or not getattr(os, "O_DIRECTORY", 0)):
        raise Http404("Private digital root not configured")
    for p in (root, *root.parents):
        if p.is_symlink():
            raise Http404("Private digital root unavailable")
    return root


def _check_private_stat(st, *, directory=False):
    if not (stat.S_ISDIR(st.st_mode) if directory else stat.S_ISREG(st.st_mode)):
        raise Http404("Private file type invalid")
    if (st.st_uid != os.geteuid() or (stat.S_IMODE(st.st_mode) & 0o077) != 0):
        raise Http404("Private file permissions invalid")
    if not directory and (st.st_nlink != 1 or
                          not 0 < st.st_size <= MAX_DIGITAL_FILE_BYTES):
        raise Http404("Private asset size or link count invalid")


def _file_from_private_root(relative, expected_digest):
    """Read owner-private bytes once; stream from the same verified descriptor.

    A match is a local byte-integrity check, NOT a paid delivery receipt or
    legal-rights/settlement verification.
    """
    parts = _private_asset_parts(relative)
    if type(expected_digest) is not str or _DIGEST.fullmatch(expected_digest) is None:
        raise Http404("Approved file digest unavailable")
    root = _safe_root()
    dirs = []
    asset_fd = None
    stream = None
    flags_dir = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    flags_file = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        folder_fd = os.open(str(root), flags_dir)
        dirs.append(folder_fd)
        _check_private_stat(os.fstat(folder_fd), directory=True)
        for part in parts[:-1]:
            folder_fd = os.open(part, flags_dir, dir_fd=folder_fd)
            dirs.append(folder_fd)
            _check_private_stat(os.fstat(folder_fd), directory=True)
        asset_fd = os.open(parts[-1], flags_file, dir_fd=folder_fd)
        before = os.fstat(asset_fd)
        _check_private_stat(before)
        stream = os.fdopen(asset_fd, "rb", buffering=0)
        asset_fd = None   # Ownership passed to stream, including failure paths
        digest = hashlib.sha256()
        count = 0
        start = b""
        while True:
            chunk = stream.read(min(65536, MAX_DIGITAL_FILE_BYTES + 1 - count))
            if not chunk:
                break
            count += len(chunk)
            if count > MAX_DIGITAL_FILE_BYTES:
                raise Http404("Private digital asset exceeds limit")
            if not start:
                start = chunk[:8]
            digest.update(chunk)
        after = os.fstat(stream.fileno())
        if (count != before.st_size or any(getattr(before, key) != getattr(after, key)
            for key in ("st_dev", "st_ino", "st_size", "st_mode",
                        "st_nlink", "st_mtime_ns", "st_ctime_ns"))):
            raise Http404("Private file changed during inspection")
        extension = parts[-1].rsplit(".", 1)[-1].lower()
        if ((extension == "pdf" and not start.startswith(b"%PDF-")) or
                (extension in ("zip", "epub") and not start.startswith(b"PK\x03\x04"))):
            raise Http404("Private digital file signature invalid")
        if digest.hexdigest() != expected_digest:
            raise Http404("Published asset hash no longer matches")
        stream.seek(0)
        result = stream
        stream = None    # Caller / Django FileResponse closes after streaming
        return result
    except (OSError, ValueError, OverflowError) as exc:
        raise Http404("Private file not available") from None
    finally:
        if stream is not None:
            stream.close()
        if asset_fd is not None:
            os.close(asset_fd)
        for fd in reversed(dirs):
            os.close(fd)


@never_cache
@require_GET
def download_paid(request, invoice_id):
    host, language = _host(request)
    invoice = _owner(request, invoice_id, host)
    intent = invoice.payment_intent
    order = invoice.order
    # Invoice fields and proof must remain bound to the original buyer/order.
    if (invoice.source_host != host or
            invoice.payment_intent_id != intent.pk or
            invoice.order_id != order.pk or
            intent.order_id != order.pk or
            invoice.status != "paid" or intent.status != "paid"
            or intent.provider != PROVIDER or order.status != "paid"
            or invoice.verified_at is None
            or invoice.receiver != MAINNET_RECEIVER
            or intent.amount != order.total
            or intent.currency != order.currency
            or type(invoice.amount_sun) is not int
            or invoice.amount_sun <= 0
            or type(invoice.txid) is not str
            or _TXID.fullmatch(invoice.txid) is None
            or type(invoice.proof_digest) is not str
            or _DIGEST.fullmatch(invoice.proof_digest) is None
            or invoice.txid != intent.provider_reference):
        raise Http404("Paid receipt not verified")
    events = list(PaymentWebhookEvent.objects.filter(
        provider=PROVIDER, event_id=invoice.txid,
        payment_intent=intent, event_type="tron_finalized", status="processed",
        payload_hash=invoice.proof_digest,
        processed_at__isnull=False,
    )[:2])
    credits = list(LedgerEntry.objects.filter(
        reference="tron-mainnet:" + invoice.txid,
        payment_intent=intent, order=order,
        entry_type="credit", amount=order.total,
        currency=order.currency,
    )[:2])
    if (len(events) != 1 or len(credits) != 1
            or LedgerEntry.objects.filter(
                order=order,
                entry_type__in=("refund", "chargeback", "reversal"),
            ).exists()):
        raise Http404("Merchant credit evidence incomplete")
    meta = credits[0].metadata
    if (type(meta) is not dict or meta.get("network") != "tron-mainnet"
            or meta.get("asset") != "TRX"
            or meta.get("amount_sun") != invoice.amount_sun
            or meta.get("receiver") != invoice.receiver
            or meta.get("proof_digest") != invoice.proof_digest
            or meta.get("webhook_event_id") != events[0].pk):
        raise Http404("Merchant credit provenance mismatch")
    items = list(OrderItem.objects.filter(order=order).select_related("product")[:2])
    if len(items) != 1:
        raise Http404("Unrecognized invoice items")
    item = items[0]
    if (item.quantity != 1 or item.unit_price != order.total
            or item.currency != order.currency):
        raise Http404("Order line does not match paid quote")
    product, _, fingerprint = _read_product(item.product_id, language)
    if (product.pk != item.product_id or
            product.currency != order.currency or
            product.price != order.total or
            fingerprint != invoice.quote_fingerprint):
        # Never substitute the current catalogue item for an older paid quote.
        raise Http404("Paid item changed; private purchase recovery required")
    md = product.metadata
    if type(md) is not dict or md.get("fulfillment_type") != "digital":
        raise Http404("This purchase has no digital download")
    stream = _file_from_private_root(md.get("asset_relpath"), md.get("sha256"))
    resp = FileResponse(stream, as_attachment=True, filename=Path(md["asset_relpath"]).name)
    resp["Content-Security-Policy"] = "default-src 'none'; sandbox"
    resp["X-Download-Options"] = "noopen"
    return _private(resp)

