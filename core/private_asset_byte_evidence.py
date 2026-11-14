"""Read-only private digital-file byte/manifest evidence for mojtaba.bot.ai.

Proves that *currently readable local bytes* match an owner-provided metadata
digest and an adjacent bounded manifest. DOES NOT prove rights, buyer identity,
external payment finality, commercial release, download or customer receipt.
No network, email, token issuance, DB mutation, writes or delivery side effects.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat

BOT_ID = "mojtaba.bot.ai"
SCHEMA = "mojtaba.private-asset.v1"
FILE_FORMATS = frozenset({"pdf", "epub", "zip"})
ASSET_REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{15,95}\Z")
VERSION = re.compile(r"(0|[1-9][0-9]{0,3})\.(0|[1-9][0-9]{0,3})\.(0|[1-9][0-9]{0,3})\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
MANIFEST_FIELDS = frozenset({
    "schema", "asset_ref", "format", "version", "asset_sha256", "asset_size",
})
MAX_ASSET_BYTES = 128 * 1024 * 1024
MAX_MANIFEST_BYTES = 8192
BLOCK = 64 * 1024
_PRIVATE_READ_FLAGS = (
    os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
)


class _Rejected(Exception):
    def __init__(self, code: str):
        self.code = code


def _result(code: str, *, verified: bool = False) -> dict:
    """Fixed-category, non-sensitive output only; never include paths/bytes."""
    return {
        "bot_id": BOT_ID,
        "schema": SCHEMA,
        "state": "local_bytes_matched_private_manifest_only" if verified else "blocked",
        "reason": "LOCAL_BYTES_MATCHED" if verified else code,
        "private_file_bytes_verified": verified,
        "private_manifest_bytes_verified": verified,
        "rights_independently_verified": False,
        "buyer_email_verified": False,
        "independent_settlement_verified": False,
        "delivery_allowed": False,
        "customer_download_receipt_verified": False,
        "read_only": True,
    }


def _validate_metadata(metadata):
    if type(metadata) is not dict:
        raise _Rejected("METADATA_NOT_OBJECT")
    fmt = metadata.get("delivery_format")
    ref = metadata.get("delivery_asset_ref")
    version = metadata.get("delivery_version")
    asset_sha = metadata.get("delivery_asset_sha256")
    manifest_sha = metadata.get("delivery_manifest_sha256")
    if type(fmt) is not str or fmt not in FILE_FORMATS:
        raise _Rejected("NOT_A_PRIVATE_FILE_FORMAT")
    if type(ref) is not str or ASSET_REF.fullmatch(ref) is None:
        raise _Rejected("ASSET_REF_INVALID")
    if type(version) is not str or VERSION.fullmatch(version) is None:
        raise _Rejected("VERSION_INVALID")
    if type(asset_sha) is not str or DIGEST.fullmatch(asset_sha) is None or asset_sha == "0" * 64:
        raise _Rejected("ASSET_DIGEST_INVALID")
    if type(manifest_sha) is not str or DIGEST.fullmatch(manifest_sha) is None or manifest_sha == "0" * 64:
        raise _Rejected("MANIFEST_DIGEST_INVALID")
    if asset_sha == manifest_sha:
        raise _Rejected("ASSET_MANIFEST_DIGEST_IDENTICAL")
    for field in ("rights_cleared", "independent_qc_reviewed", "buyer_terms_approved"):
        if metadata.get(field) is not True:
            raise _Rejected("PRODUCT_APPROVAL_INCOMPLETE")
    return ref, fmt, version, asset_sha, manifest_sha


def _open_private_root(root):
    if not isinstance(root, (str, Path)):
        raise _Rejected("ROOT_NOT_CONFIGURED")
    p = Path(root)
    if (not p.is_absolute() or ".." in p.parts or not p.parts
            or str(p) == "/"):
        raise _Rejected("ROOT_UNSAFE")
    # Catch symlinked ancestors as well as the final component.
    for part in (p, *p.parents):
        if part.is_symlink():
            raise _Rejected("ROOT_UNSAFE")
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(p, flags)
    except OSError:
        raise _Rejected("ROOT_UNAVAILABLE") from None
    try:
        st = os.fstat(fd)
        if (not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid()
                or (stat.S_IMODE(st.st_mode) & 0o077) != 0):
            raise _Rejected("ROOT_PERMISSIONS_UNSAFE")
    except BaseException:
        os.close(fd)
        raise
    return fd


def _read_verified_regular(root_fd, name: str, limit: int):
    """Use dirfd + O_NOFOLLOW, fstat, read bounds and same-fd stability."""
    if not isinstance(name, str) or name in ("", ".", "..") or "/" in name or "\\" in name:
        raise _Rejected("LEAF_NAME_UNSAFE")
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise _Rejected("NOFOLLOW_UNAVAILABLE")
    try:
        fd = os.open(name, _PRIVATE_READ_FLAGS, dir_fd=root_fd)
    except OSError:
        raise _Rejected("PRIVATE_FILE_UNAVAILABLE") from None
    try:
        before = os.fstat(fd)
        if (not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1
                or before.st_uid != os.geteuid()
                or stat.S_IMODE(before.st_mode) & 0o077):
            raise _Rejected("PRIVATE_FILE_PERMISSIONS_UNSAFE")
        if not 0 < before.st_size <= limit:
            raise _Rejected("PRIVATE_FILE_SIZE_INVALID")
        digest = hashlib.sha256()
        count = 0
        first = b""
        payload = bytearray() if limit == MAX_MANIFEST_BYTES else None
        while True:
            part = os.read(fd, min(BLOCK, limit + 1 - count))
            if not part:
                break
            count += len(part)
            if count > limit:
                raise _Rejected("PRIVATE_FILE_SIZE_INVALID")
            if not first:
                first = part[:8]
            digest.update(part)
            if payload is not None:
                payload.extend(part)
        after = os.fstat(fd)
        stable = all(getattr(before, name) == getattr(after, name) for name in (
            "st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns",
            "st_nlink", "st_mode",
        ))
        if not stable or count != before.st_size:
            raise _Rejected("PRIVATE_FILE_CHANGED_DURING_READ")
        return digest.hexdigest(), count, first, bytes(payload) if payload is not None else None
    except OSError:
        raise _Rejected("PRIVATE_FILE_READ_FAILED") from None
    finally:
        os.close(fd)


def _no_duplicate_keys(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise _Rejected("MANIFEST_DUPLICATE_FIELDS")
        obj[key] = value
    return obj


def _reject_json_constant(_value):
    raise _Rejected("MANIFEST_NONFINITE")


def _validate_manifest(payload, ref, fmt, version, expected_sha, size):
    try:
        manifest = json.loads(
            payload.decode("utf-8", "strict"),
            object_pairs_hook=_no_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except _Rejected:
        raise
    except (UnicodeError, ValueError, TypeError):
        raise _Rejected("MANIFEST_INVALID_JSON") from None
    if type(manifest) is not dict or set(manifest) != MANIFEST_FIELDS:
        raise _Rejected("MANIFEST_SCHEMA_INVALID")
    if manifest["schema"] != SCHEMA:
        raise _Rejected("MANIFEST_SCHEMA_INVALID")
    if (manifest["asset_ref"] != ref or manifest["format"] != fmt
            or manifest["version"] != version or manifest["asset_sha256"] != expected_sha):
        raise _Rejected("MANIFEST_SOURCE_MISMATCH")
    if type(manifest["asset_size"]) is not int or manifest["asset_size"] != size:
        raise _Rejected("MANIFEST_SIZE_MISMATCH")


def verify_private_asset_readonly(metadata, *, private_root=None) -> dict:
    """Verify bounded on-disk bytes only. Never authorizes buyer fulfillment.

    private_root must be a separately configured absolute owner-private root.
    A missing root fails closed. No raw filesystem paths ever escape.
    """
    try:
        ref, fmt, version, asset_sha, manifest_sha = _validate_metadata(metadata)
        if private_root is None:
            raise _Rejected("ROOT_NOT_CONFIGURED")
        root_fd = _open_private_root(private_root)
        try:
            asset_digest, size, first, _ = _read_verified_regular(
                root_fd, f"{ref}.{fmt}", MAX_ASSET_BYTES,
            )
            if (fmt == "pdf" and first[:5] != b"%PDF-") or (fmt != "pdf" and first[:4] != b"PK\x03\x04"):
                raise _Rejected("ASSET_SIGNATURE_INVALID")
            if asset_digest != asset_sha:
                raise _Rejected("ASSET_SHA256_MISMATCH")
            manifest_digest, _, _, manifest_bytes = _read_verified_regular(
                root_fd, f"{ref}.manifest.json", MAX_MANIFEST_BYTES,
            )
            if manifest_digest != manifest_sha:
                raise _Rejected("MANIFEST_SHA256_MISMATCH")
            _validate_manifest(manifest_bytes, ref, fmt, version, asset_sha, size)
            return _result("LOCAL_BYTES_MATCHED", verified=True)
        finally:
            os.close(root_fd)
    except _Rejected as exc:
        return _result(exc.code)
    except (OSError, UnicodeError, ValueError, TypeError, OverflowError):
        # Never put exception strings, paths, metadata or credentials in output.
        return _result("LOCAL_EVIDENCE_UNAVAILABLE")
