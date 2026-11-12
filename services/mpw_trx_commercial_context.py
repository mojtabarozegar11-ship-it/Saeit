"""Minimal customer-facing TRX feature switch; no network or database access."""
from __future__ import annotations


def checkout_flags(request):
    from django.conf import settings
    from services.mpw_walletless_commercial_intent import public_release_authorized
    try:
        host=request.get_host().split(":")[0].lower()
    except Exception:
        host=""
    released=bool(
        host in ("mojplaywin.com","www.mojplaywin.com")
        and request.is_secure()
        and getattr(settings,"MPW_WALLETLESS_TRX_PUBLIC_ENABLED",False) is True
        and public_release_authorized(settings)
    )
    return {"mpw_trx_easy_enabled":released}


def _sha256_hex(value):
    return (type(value) is str and len(value)==64
            and all(character in "0123456789abcdef" for character in value.lower()))


def public_product_ids(settings):
    """One fail-closed public SKU policy for catalogue, guest GET and invoice POST.

    Malformed configuration must not create an HTTP 500 or widen the sale list.
    This identifier filter is separate from product quality and rights checks.
    """
    listed=getattr(settings,"MPW_TRX_PUBLIC_PRODUCT_IDS",())
    if type(listed) not in (tuple,list,set,frozenset):
        return ()
    if any(type(value) is not int or value<=0 for value in listed):
        return ()
    return tuple(sorted(set(listed)))


def rights_cleared_for_sale(product):
    """Validate declared approval and exact artifact/document digest linkage.

    This is a metadata consistency gate, NOT independent legal certification.
    It must not be used to generate, infer, or set any approval flags.
    """
    metadata=getattr(product,"metadata",None)
    if type(metadata) is not dict:
        return False
    if (metadata.get("rights_cleared") is not True
            or metadata.get("publication_approved") is not True):
        return False
    catalog_sha=metadata.get("sha256")
    rights_sha=metadata.get("rights_asset_sha256")
    document_sha=metadata.get("rights_document_sha256")
    return (_sha256_hex(catalog_sha)
            and _sha256_hex(rights_sha)
            and _sha256_hex(document_sha)
            and catalog_sha.lower()==rights_sha.lower())


def private_artifact_sha_matches_approved(product, path):
    """Check the real private file's bytes against the approved version.

    This supplements, but cannot substitute for, independent rights evidence.
    It is used when issuing an invoice, not when accessing an old paid order.
    """
    import hashlib
    import hmac
    import os
    import stat

    if not rights_cleared_for_sale(product):
        return False
    expected=product.metadata["sha256"].lower()
    try:
        flags=os.O_RDONLY | getattr(os,"O_NOFOLLOW",0) | getattr(os,"O_CLOEXEC",0)
        descriptor=os.open(os.fspath(path),flags)
        with os.fdopen(descriptor,"rb") as stream:
            before=os.fstat(stream.fileno())
            if (not stat.S_ISREG(before.st_mode)
                    or before.st_nlink != 1 or before.st_size <= 0):
                return False
            digest=hashlib.sha256()
            for chunk in iter(lambda: stream.read(1024*1024),b""):
                digest.update(chunk)
            after=os.fstat(stream.fileno())
            # A file replaced or edited during verification is not verified.
            if ((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)
                    != (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns)):
                return False
            return hmac.compare_digest(digest.hexdigest(),expected)
    except (OSError,TypeError,ValueError):
        return False


def private_paid_stream_matches_approved(product, stream):
    """Verify the exact opened file descriptor before any paid download.

    The path may be replaced between catalogue inspection and opening the
    download. Checking this descriptor prevents serving different bytes even
    when a valid on-chain receipt and earlier checkout hash both exist.
    This does not replace immutable storage or independent rights evidence.
    """
    import hashlib
    import hmac
    import os
    import stat

    metadata=getattr(product,"metadata",None)
    # Previously paid orders survive storefront withdrawal. Publishing a new
    # offer requires publication_approved; delivering an already-paid item
    # requires continuing rights clearance and the exact rights-bound bytes.
    if (type(metadata) is not dict or metadata.get("rights_cleared") is not True
        or not _sha256_hex(metadata.get("sha256"))
        or not _sha256_hex(metadata.get("rights_asset_sha256"))
        or not _sha256_hex(metadata.get("rights_document_sha256"))
        or metadata["sha256"].lower()!=metadata["rights_asset_sha256"].lower()):
        return False
    expected=metadata["sha256"].lower()
    try:
        before=os.fstat(stream.fileno())
        if (not stat.S_ISREG(before.st_mode)
                or before.st_nlink!=1 or before.st_size<=0):
            return False
        stream.seek(0)
        digest=hashlib.sha256()
        for chunk in iter(lambda:stream.read(1024*1024),b""):
            digest.update(chunk)
        after=os.fstat(stream.fileno())
        snapshot=lambda st:(st.st_dev,st.st_ino,st.st_mode,st.st_nlink,
                            st.st_size,st.st_mtime_ns,st.st_ctime_ns)
        if snapshot(before)!=snapshot(after):
            return False
        if not hmac.compare_digest(digest.hexdigest(),expected):
            return False
        stream.seek(0)
        return True
    except (OSError,TypeError,ValueError,AttributeError):
        return False
