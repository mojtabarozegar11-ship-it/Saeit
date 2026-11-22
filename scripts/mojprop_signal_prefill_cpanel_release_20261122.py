#!/usr/bin/env python3
"""Exact-byte reversible source release for the FREE Moj Prop Signal Desk note.

SOURCE ONLY. No invocation from CI, import, or GitHub merge edits production.
--check is strictly read-only. --apply/--rollback require separate owner approval.
A successful write does NOT reload Passenger workers or attest a live release.
Never restart LiteSpeed, change .env, mutate DB, create invoices or send mail.
"""
from __future__ import annotations

import getpass
import hashlib
import json
import os
import stat
import sys
import tempfile
from pathlib import Path

TARGET = Path("/home/zomorod2/Saeit-mojplaywin-integrated-20261119/core/mojprop_accessible_intake.py")
PRIVATE_ROOT = Path("/home/zomorod2/.private_mojplaywin_main_agents")
BACKUP_DIR = PRIVATE_ROOT / "mojprop_signal_prefill_20261122"
BACKUP = BACKUP_DIR / "mojprop_accessible_intake.py.before"
MANIFEST = BACKUP_DIR / "manifest.json"

BASE_SIZE = 16742
NEXT_SIZE = 17434
BASE_SHA256 = "40760b1e95b37bc66e7676f2c7e1ff2432a54855b1bde85820025e66a22056af"
NEXT_SHA256 = "8624920c7bc317fdf8c9fb5428476e6fcab946085b7965d1003578ed863bbfc9"
BASE_BLOB = "ee4374977fa82cf80df1244f4617dc1a689c061b"
NEXT_BLOB = "c8e6de24ce4d9573395a64222d198be48d989f1b"

ANCHOR = b'    return service, ""\n\n\n# Campaign IDs'
ADDITION = (
    b'    if service == "signals" and not packages:\n'
    b'        # This is user-editable suggested copy for a FREE enquiry only.\n'
    b'        # The submitted CRM request still requires explicit consent,\n'
    b'        # real contact details, CSRF, validation and server-side acceptance.\n'
    b'        return service, (\n'
    b'            "Please send the free written terms for the educational Signal Desk: "\n'
    b'            "covered markets, market-scenario examples, risk disclosures, "\n'
    b'            "delivery frequency, proposed pricing and cancellation conditions. "\n'
    b'            "I understand this is only a request for information, not a paid "\n'
    b'            "subscription, executed trade or guaranteed trading result."\n'
    b'        )\n'
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def candidate(before: bytes) -> bytes:
    if not (len(before) == BASE_SIZE and sha256(before) == BASE_SHA256
            and git_blob(before) == BASE_BLOB):
        raise RuntimeError("PINNED_MAINLINE_SOURCE_DRIFT")
    if len(ADDITION) != 692 or before.count(ANCHOR) != 1 or before.count(ADDITION) != 0:
        raise RuntimeError("PRECISE_PREFILL_ANCHOR_NOT_UNIQUE")
    after = before.replace(ANCHOR, ADDITION + ANCHOR, 1)
    if not (len(after) == NEXT_SIZE and sha256(after) == NEXT_SHA256
            and git_blob(after) == NEXT_BLOB):
        raise RuntimeError("CANDIDATE_MISMATCH_WITH_REVIEWED_GITHUB_BLOB")
    if after.replace(ADDITION + ANCHOR, ANCHOR, 1) != before:
        raise RuntimeError("REVERSAL_PROOF_FAILED")
    return after


def _target_read() -> tuple[bytes, int]:
    if getpass.getuser() != "zomorod2":
        raise RuntimeError("INVALID_CPANEL_OWNER")
    if TARGET.is_symlink() or TARGET.parent.is_symlink() or not TARGET.is_file():
        raise RuntimeError("INVALID_EFFECTIVE_SOURCE_TARGET")
    info = TARGET.stat()
    if info.st_uid != os.getuid() or info.st_nlink != 1:
        raise RuntimeError("UNEXPECTED_EFFECTIVE_SOURCE_OWNERSHIP")
    return TARGET.read_bytes(), stat.S_IMODE(info.st_mode)


def _private_blob(path: Path, raw: bytes) -> None:
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as dst:
            dst.write(raw)
            dst.flush()
            os.fsync(dst.fileno())
    except BaseException:
        if path.exists():
            path.unlink()
        raise


def _replace_atomic(raw: bytes, mode: int) -> None:
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(
                dir=TARGET.parent, prefix=".mpw-signal-intake-", delete=False) as fd:
            tmp = Path(fd.name)
            fd.write(raw)
            fd.flush()
            os.fsync(fd.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, TARGET)
        tmp = None
    finally:
        if tmp is not None and tmp.exists():
            tmp.unlink()


def execute(action: str) -> None:
    if action not in ("--check", "--apply", "--rollback"):
        raise ValueError("Usage: --check | --apply | --rollback")
    current, mode = _target_read()
    if action == "--rollback":
        if BACKUP_DIR.is_symlink() or BACKUP.is_symlink() or MANIFEST.is_symlink():
            raise RuntimeError("UNSAFE_ROLLBACK_SYMLINK")
        if not BACKUP.is_file() or not MANIFEST.is_file():
            raise RuntimeError("ROLLBACK_BUNDLE_MISSING")
        doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
        original = BACKUP.read_bytes()
        if (doc.get("target") != str(TARGET)
                or doc.get("before_sha256") != BASE_SHA256
                or doc.get("after_sha256") != NEXT_SHA256
                or len(current) != NEXT_SIZE or sha256(current) != NEXT_SHA256
                or len(original) != BASE_SIZE or sha256(original) != BASE_SHA256
                or git_blob(original) != BASE_BLOB):
            raise RuntimeError("ROLLBACK_BUNDLE_OR_EFFECTIVE_SOURCE_CHANGED")
        _replace_atomic(original, mode)
        if sha256(TARGET.read_bytes()) != BASE_SHA256:
            raise RuntimeError("ROLLBACK_POSTWRITE_HASH_FAILURE")
        print("ORIGINAL_SOURCE_RESTORED", BASE_SHA256)
        print("PASSENGER_WORKER_PARITY_NOT_ATTESTED")
        return

    next_source = candidate(current)
    print("SOURCE_PIN_VERIFIED", BASE_SHA256, "NEXT_BLOB", NEXT_BLOB)
    if action == "--check":
        print("READ_ONLY_NO_LIVE_CHANGES")
        return

    if PRIVATE_ROOT.is_symlink() or not PRIVATE_ROOT.is_dir():
        raise RuntimeError("PRIVATE_BACKUP_ROOT_NOT_VERIFIED")
    if BACKUP_DIR.exists() or BACKUP_DIR.is_symlink():
        raise RuntimeError("EXISTING_ROLLBACK_BUNDLE_REFUSE_DUPLICATE")
    BACKUP_DIR.mkdir(mode=0o700)
    os.chmod(BACKUP_DIR, 0o700)
    _private_blob(BACKUP, current)
    if sha256(BACKUP.read_bytes()) != BASE_SHA256:
        raise RuntimeError("PRIVATE_BACKUP_READBACK_FAILURE")
    manifest = {
        "target": str(TARGET),
        "before_sha256": BASE_SHA256,
        "after_sha256": NEXT_SHA256,
        "intention": "free Signal Desk enquiry prefill only",
        "passenger_reloaded": False,
        "invoice_or_payment_enabled": False,
    }
    _private_blob(MANIFEST, (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode())
    if sha256(TARGET.read_bytes()) != BASE_SHA256:
        raise RuntimeError("CONCURRENT_SOURCE_CHANGE_ABORT")
    _replace_atomic(next_source, mode)
    if sha256(TARGET.read_bytes()) != NEXT_SHA256:
        raise RuntimeError("POSTWRITE_SHA_MISMATCH_ROLLBACK_REQUIRED")
    print("SOURCE_FILE_UPDATED", NEXT_SHA256)
    print("NOT_PROOF_OF_DEPLOYED_PASSENGER_WORKERS_NO_RESTART_PERFORMED")


if __name__ == "__main__":
    execute(sys.argv[1] if len(sys.argv) == 2 else "")
