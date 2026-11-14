#!/usr/bin/env python3
"""Add a customer-support notice to MojPlayWin's *existing* static store fallback.

Owner-approved production installation only; no edits to .htaccess, Django,
checkouts, payment records, wallets, or other web pages. Source preparation and
unit tests do not touch production or send external requests.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pwd
import re
import stat
import tempfile
from pathlib import Path

PUBLIC = Path("/home/zomorod2/mojplaywin.com")
TARGET = PUBLIC / "store/index.html"
BACKUP_ROOT = Path("/home/zomorod2/.backups/mpw-store-customer-support")
MARKER = "MPW_STATIC_STORE_FALLBACK_V1"
SUPPORT_ID = 'id="mpw-static-shop-support-20261113"'
EMAIL = "mojplaywin@gmail.com"
HEAD_ANCHOR = "</style></head><body>"
CATALOG_ANCHOR = '<section class="grid" aria-label="MojPlayWin products">'
CSS = (
    ".mpw-static-shop-support{margin:24px 0 4px;padding:20px 22px;"
    "border:1px solid #d6ad5580;border-radius:14px;background:#15140f}"
    ".mpw-static-shop-support h2{margin:0 0 8px;color:#f0cf82}"
    ".mpw-static-shop-support p{margin:0;color:#f5f0e4}"
    ".mpw-static-shop-support a{color:#f0cf82;font-weight:700}"
    "@media(max-width:800px){.mpw-static-shop-support{padding:16px}}"
)
BANNER = (
    '<section class="mpw-static-shop-support" '
    + SUPPORT_ID
    + ' aria-labelledby="mpw-static-support-heading">'
    '<h2 id="mpw-static-support-heading">Questions about buying or need help?</h2>'
    '<p>For purchase questions, order or payment problems, digital download help, '
    'or any other issue with MojPlayWin, email '
    '<a href="mailto:mojplaywin@gmail.com?subject=MojPlayWin%20Store%20Support">'
    'mojplaywin@gmail.com</a>. Include the product name and order reference '
    'if available. Never send passwords, verification codes or wallet recovery phrases.</p>'
    '</section>'
)
# SKU 879 final rights/delivery are not yet established for public checkout.
# Keep its details route and invite a buyer inquiry; do not create an invoice.
SKU879_OLD_CHECKOUT_CTA = (
    '<a class="button" href="/store/product/879/checkout/">Guest checkout with TRX</a>'
)
SKU879_INQUIRY_CTA = (
    '<a class="button" href="mailto:mojplaywin@gmail.com?subject=SKU%20879%20Availability">'
    'Ask about availability before buying</a>'
)

RUN_PATTERN = re.compile(r"^[0-9]{9,20}$")
SHA_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def patched_html(original: bytes) -> bytes:
    if len(original) > 200_000 or not original:
        raise RuntimeError("STATIC_STORE_SIZE_UNSAFE")
    html = original.decode("utf-8", "strict")
    if html.count(MARKER) != 1:
        raise RuntimeError("NOT_EXACT_OWNED_FALLBACK")
    if html.count(SUPPORT_ID) == 1:
        if (html.count(BANNER) != 1 or html.count(CSS) != 1 or
                html.count(CATALOG_ANCHOR) != 1 or
                html.index(SUPPORT_ID) >= html.index(CATALOG_ANCHOR) or
                html.count(SKU879_OLD_CHECKOUT_CTA) != 0 or
                html.count(SKU879_INQUIRY_CTA) != 1):
            raise RuntimeError("PARTIAL_SUPPORT_EDIT")
        return original
    if SUPPORT_ID in html or "mpw-static-shop-support" in html or EMAIL in html:
        raise RuntimeError("UNEXPECTED_PRIOR_SUPPORT_CHANGE")
    if html.count(HEAD_ANCHOR) != 1 or html.count(CATALOG_ANCHOR) != 1:
        raise RuntimeError("UNRECOGNIZED_STORE_STRUCTURE")
    if not html.lstrip().lower().startswith("<!doctype html>"):
        raise RuntimeError("STORE_DOCTYPE_CHANGED")
    required = (
        "Digital Store | MojPlayWin",
        "The Science and Practice of Chess Improvement",
        "Taniya and the Little Baker Worms",
        "Atelier Interior",
        "/store/product/72/checkout/",
        "/store/product/225/checkout/",
        SKU879_OLD_CHECKOUT_CTA,
        "Product details, payment verification and delivery remain server-controlled.",
    )
    if (any(html.count(part) != 1 for part in required)
            or SKU879_INQUIRY_CTA in html):
        raise RuntimeError("STORE_PRODUCT_OR_PAYMENT_GUARD_MISMATCH")
    out = html.replace(HEAD_ANCHOR, CSS + HEAD_ANCHOR, 1)
    out = out.replace(CATALOG_ANCHOR, BANNER + CATALOG_ANCHOR, 1)
    out = out.replace(SKU879_OLD_CHECKOUT_CTA, SKU879_INQUIRY_CTA, 1)
    if out.index(SUPPORT_ID) >= out.index(CATALOG_ANCHOR):
        raise RuntimeError("SUPPORT_BANNER_NOT_BEFORE_CATALOG")
    return out.encode("utf-8")


def _assert_target_is_safe() -> os.stat_result:
    if pwd.getpwuid(os.geteuid()).pw_name != "zomorod2":
        raise RuntimeError("WRONG_CPANEL_ACCOUNT")
    for path in (PUBLIC, PUBLIC / "store", TARGET):
        if path.is_symlink():
            raise RuntimeError("SYMLINK_REFUSED")
    if not PUBLIC.is_dir() or not (PUBLIC / "store").is_dir() or not TARGET.is_file():
        raise RuntimeError("EXPECTED_STATIC_STORE_MISSING")
    status = TARGET.stat()
    if status.st_uid != os.geteuid() or status.st_nlink != 1:
        raise RuntimeError("UNSAFE_STATIC_FILE_OWNERSHIP")
    if status.st_size > 200_000:
        raise RuntimeError("EXCESSIVE_FILE_SIZE")
    return status


def _atomic_write(target: Path, payload: bytes, mode: int) -> None:
    fd, tmp = tempfile.mkstemp(prefix=".mpw-support-", dir=str(target.parent))
    try:
        with os.fdopen(fd, "wb") as sink:
            os.fchmod(sink.fileno(), mode)
            sink.write(payload)
            sink.flush()
            os.fsync(sink.fileno())
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def inspect(expected_live_sha256: str | None = None) -> dict:
    _assert_target_is_safe()
    original = TARGET.read_bytes()
    candidate = patched_html(original)
    before = digest(original)
    if expected_live_sha256 and before != expected_live_sha256:
        raise RuntimeError("LIVE_BASELINE_HASH_MISMATCH")
    return {
        "target": str(TARGET),
        "current_sha256": before,
        "proposed_sha256": digest(candidate),
        "needs_change": candidate != original,
        "customer_contact": EMAIL,
        "writes_performed": False,
        "production_release_authorized": False,
    }


def install(run_id: str, expected_live_sha256: str, owner_approved: bool) -> dict:
    if not owner_approved:
        raise RuntimeError("EXPLICIT_OWNER_APPROVAL_REQUIRED")
    if not RUN_PATTERN.fullmatch(run_id) or not SHA_PATTERN.fullmatch(expected_live_sha256):
        raise RuntimeError("INVALID_RELEASE_IDENTIFIERS")
    status = _assert_target_is_safe()
    original = TARGET.read_bytes()
    if digest(original) != expected_live_sha256:
        raise RuntimeError("LIVE_BASELINE_HASH_MISMATCH")
    changed = patched_html(original)
    if changed == original:
        raise RuntimeError("ALREADY_PATCHED")
    if BACKUP_ROOT.exists() and BACKUP_ROOT.is_symlink():
        raise RuntimeError("UNSAFE_BACKUP_ROOT")
    BACKUP_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    if BACKUP_ROOT.stat().st_uid != os.geteuid():
        raise RuntimeError("BACKUP_OWNER_MISMATCH")
    record = BACKUP_ROOT / run_id
    record.mkdir(mode=0o700, exist_ok=False)
    original_backup = record / "previous.html"
    manifest = record / "manifest.json"
    fd = os.open(original_backup, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(original)
        f.flush()
        os.fsync(f.fileno())
    metadata = {"target": str(TARGET), "previous_sha256": digest(original),
                "new_sha256": digest(changed), "mode": stat.S_IMODE(status.st_mode),
                "run_id": run_id}
    with manifest.open("x", encoding="utf-8") as f:
        os.chmod(manifest, 0o600)
        json.dump(metadata, f, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    if digest(TARGET.read_bytes()) != expected_live_sha256:
        raise RuntimeError("CONCURRENT_STATIC_STORE_CHANGE")
    _atomic_write(TARGET, changed, metadata["mode"])
    if digest(TARGET.read_bytes()) != metadata["new_sha256"]:
        raise RuntimeError("POSTWRITE_HASH_MISMATCH_REQUIRES_MANUAL_RECOVERY")
    return {"installed": True, "backup": str(record),
            "before_sha256": metadata["previous_sha256"],
            "after_sha256": metadata["new_sha256"]}


def rollback(run_id: str, owner_approved: bool) -> dict:
    if not owner_approved:
        raise RuntimeError("EXPLICIT_OWNER_APPROVAL_REQUIRED")
    if not RUN_PATTERN.fullmatch(run_id):
        raise RuntimeError("INVALID_RELEASE_ID")
    _assert_target_is_safe()
    if BACKUP_ROOT.is_symlink():
        raise RuntimeError("UNSAFE_BACKUP_ROOT")
    record = BACKUP_ROOT / run_id
    if record.is_symlink() or (record / "previous.html").is_symlink() or (record / "manifest.json").is_symlink():
        raise RuntimeError("UNSAFE_BACKUP_SYMLINK")
    metadata = json.loads((record / "manifest.json").read_text("utf-8"))
    if metadata.get("target") != str(TARGET) or metadata.get("run_id") != run_id:
        raise RuntimeError("INVALID_BACKUP_METADATA")
    prior = (record / "previous.html").read_bytes()
    if digest(prior) != metadata["previous_sha256"]:
        raise RuntimeError("BACKUP_HASH_MISMATCH")
    if digest(TARGET.read_bytes()) != metadata["new_sha256"]:
        raise RuntimeError("CONCURRENT_LIVE_CHANGE_ROLLBACK_REFUSED")
    _atomic_write(TARGET, prior, metadata["mode"])
    if digest(TARGET.read_bytes()) != metadata["previous_sha256"]:
        raise RuntimeError("ROLLBACK_VERIFICATION_FAILED")
    return {"rollback_verified": True, "restored_sha256": metadata["previous_sha256"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("inspect", "install", "rollback"))
    parser.add_argument("--run-id", default="")
    parser.add_argument("--expected-live-sha256", default="")
    parser.add_argument("--owner-approved", action="store_true", default=False)
    options = parser.parse_args()
    if options.operation == "inspect":
        result = inspect(options.expected_live_sha256 or None)
    elif options.operation == "install":
        result = install(options.run_id, options.expected_live_sha256, options.owner_approved)
    else:
        result = rollback(options.run_id, options.owner_approved)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
