#!/usr/bin/env python3
"""Fail-closed READ-ONLY production source attestation for MojPlayWin cPanel.

Stream this trusted source to the existing pinned cPanel SSH relay using the
hosting Python interpreter and -B. Do not copy it into the live application.
No Django import, SQL, network request, email, payment, shell command, writes
or browser interaction. Output contains only allowlisted filenames, hashes,
sizes and boolean static markers; never source content or credentials.
"""
from __future__ import annotations

import hashlib
import json
import os
import pwd
import stat
import sys
from pathlib import Path

HOME = Path("/home/zomorod2")
APP = HOME / "Saeit-staging"
SITE = HOME / "mojplaywin.com"
WSGI = SITE / "passenger_wsgi.py"
MAX_SOURCE_BYTES = 2_000_000

SOURCE_MARKERS = {
    "services/mpw_trx_guest_delivery.py": {
        "recovery_signed_exact_intent": 'pk=payload["i"]',
        "recovery_token_v2": 'mpw.guest.email.recovery.v2',
        "mail_uses_bounded_multi_intent_policy": "paid_receipt_intent(",
        "email_from_expected_storefront": "support@mojplaywin.com",
    },
    "services/mpw_trx_outbox_intent_policy.py": {
        "bounded_historic_intent_count": "MAX_OUTBOX_INTENTS = 64",
        "fail_closed_unknown_paid_status": 'type(state.get("can_download")) is not bool',
    },
    "services/mpw_trx_guest_commerce.py": {
        "guest_public_recovery_page": "def recovery_page(",
        "guest_email_required": 'normalize_email(request.POST.get("email", ""))',
        "secure_guest_cookie": "secure=True, httponly=True",
    },
    "services/mpw_trx_commercial_web.py": {
        "opened_file_sha256_guard": "verified_private_stream_sha256(stream, expected)",
        "atomic_order_outbox": "record_invoice(invoice_id, request.user)",
    },
    "services/mpw_trx_public_pages.py": {
        "trx_public_catalog": "public_trx_catalog(",
    },
    "services/mpw_trx_public_catalog.py": {
        "catalog_rights_guard": "rights_cleared_for_sale(product)",
    },
    "services/mpw_trx_reconcile_cursor.py": {
        "durable_mail_cursor": '"invoice-mail":',
        "receipt_mail_cursor": '"receipt-mail":',
    },
    "mpw_commerce/models.py": {
        "order_delivery_table": "class GuestTrxDelivery(",
    },
    "config/urls.py": {
        "public_trx_catalog_route": 'path("commerce/trx-easy/",',
    },
    "scripts/mpw_trx_commercial_reconcile_cron.py": {
        "outbox_in_cron": "flush_outbox()",
    },
}


def _trusted_directory(path):
    return (path.is_dir() and not path.is_symlink()
            and path.stat().st_uid == os.geteuid())


def _measure(path, markers):
    """Hash a regular, owner-owned file opened without following symlinks."""
    if not hasattr(os, "O_NOFOLLOW"):
        raise ValueError("SYMLINK_SAFE_OPEN_NOT_SUPPORTED")
    flags = os.O_RDONLY | os.O_NOFOLLOW
    fd = os.open(str(path), flags)
    try:
        before = os.fstat(fd)
        if (not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1
                or before.st_uid != os.geteuid()
                or not 0 < before.st_size <= MAX_SOURCE_BYTES):
            raise ValueError("UNTRUSTED_SOURCE_METADATA")
        sha = hashlib.sha256()
        chunks = []
        with os.fdopen(fd, "rb", closefd=False) as stream:
            while True:
                piece = stream.read(65536)
                if not piece:
                    break
                sha.update(piece)
                chunks.append(piece)
        after = os.fstat(fd)
        if (after.st_size != before.st_size
                or after.st_mtime_ns != before.st_mtime_ns
                or after.st_ino != before.st_ino):
            raise ValueError("SOURCE_CHANGED_DURING_READ")
        body = b"".join(chunks)
        result = {
            "status": "present",
            "sha256": sha.hexdigest(),
            "bytes": before.st_size,
            "markers": {name: needle.encode("utf-8") in body
                        for name, needle in markers.items()},
        }
        return result
    finally:
        os.close(fd)


def run():
    result = {
        "scope": "LIVE_CPANEL_READ_ONLY",
        "production_release_authorized": False,
        "paid_transfer_executed": False,
        "customer_data_read": False,
        "mail_sent": False,
        "db_connected": False,
        "files_modified": False,
        "observations": {},
        "blockers": [],
    }
    if pwd.getpwuid(os.geteuid()).pw_name != "zomorod2":
        result["blockers"].append("WRONG_CPANEL_USER")
        return result
    if not all(_trusted_directory(p) for p in (HOME, APP, SITE)):
        result["blockers"].append("CPANEL_ROOT_OR_SITE_UNTRUSTED")
        return result
    wanted = dict(SOURCE_MARKERS)
    for rel in wanted:
        if ".." in Path(rel).parts or Path(rel).is_absolute():
            raise ValueError("INVALID_ALLOWLIST_ENTRY")
        parent = APP / Path(rel).parent
        if not _trusted_directory(parent):
            result["observations"][rel] = {"status": "parent_untrusted"}
            result["blockers"].append("SOURCE_PARENT_UNTRUSTED:" + rel)
            continue
        path = APP / rel
        try:
            result["observations"][rel] = _measure(path, wanted[rel])
        except FileNotFoundError:
            result["observations"][rel] = {"status": "missing"}
            result["blockers"].append("SOURCE_MISSING:" + rel)
        except (OSError, ValueError, UnicodeError) as exc:
            result["observations"][rel] = {
                "status": "held", "error_class": type(exc).__name__}
            result["blockers"].append("SOURCE_UNSAFE_OR_UNREADABLE:" + rel)
    try:
        result["observations"]["passenger_wsgi.py"] = _measure(
            WSGI, {"references_active_shared_root": "Saeit-staging"})
    except (FileNotFoundError, OSError, ValueError, UnicodeError) as exc:
        result["observations"]["passenger_wsgi.py"] = {
            "status": "held", "error_class": type(exc).__name__}
        result["blockers"].append("PASSENGER_ENTRY_UNVERIFIED")
    if any(not all(v.get("markers", {}).values())
           for k, v in result["observations"].items()
           if v.get("status") == "present"):
        result["blockers"].append("SOME_SOURCE_CAPABILITIES_NOT_INSTALLED")
    return result


if __name__ == "__main__":
    try:
        answer = run()
    except Exception as exc:
        answer = {"scope": "LIVE_CPANEL_READ_ONLY",
                  "production_release_authorized": False,
                  "error_class": type(exc).__name__,
                  "blockers": ["SOURCE_ATTESTATION_FAILED_CLOSED"]}
    print("MPW_CPANEL_SOURCE_ATTESTATION=" +
          json.dumps(answer, sort_keys=True, ensure_ascii=True))
    sys.exit(1 if answer.get("blockers") else 0)
