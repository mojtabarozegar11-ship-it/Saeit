#!/usr/bin/env python3
"""Exact-source, optional operator-scoped static homepage free Signal Desk CTA.

CHECK is read-only. APPLY/ROLLBACK require separately approved production scope.
This file is SOURCE ONLY: importing, running tests, or merging cannot deploy it.
Never touches Django/Passenger, invoices, TRX, factory, emails or customer data.
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

TARGET = Path("/home/zomorod2/mojplaywin.com/design-preview-20261017/production-home-20261017.html")
PRIVATE_DIR = Path("/home/zomorod2/.private_mojplaywin_main_agents")
BACKUP_DIR = PRIVATE_DIR / "home-free-signal-cta-20261122"
BACKUP = BACKUP_DIR / "production-home.before"
MANIFEST = BACKUP_DIR / "manifest.json"
BASE_SHA256 = "2f9c70c182833bb9a81f6eda3fba399463c36e70a13a51e2ee599fa3f04b5884"
CANDIDATE_SHA256 = "e637c5d6a73fc5a55f1c04d13adc2fb1ab5d15c79e4b9bce1714f656d6e812fe"
BASE_SIZE = 265821
CANDIDATE_SIZE = 266074
ANCHOR = (
    '      <a class="mpw-mojprop-secondary" '
    'href="/moj-prop/languages/">MOJ PROP · 20 languages</a>\n'
).encode("utf-8")
CTA = (
    '      <a class="mpw-mojprop-secondary" '
    'href="/moj-prop-intake/?format=html&amp;service=signals'
    '&amp;utm_source=moj_prop&amp;utm_medium=onsite'
    '&amp;utm_campaign=signals_education_lead_20261121'
    '&amp;utm_content=signal_nav">'
    'Request free Signal Desk terms</a>\n'
).encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def candidate_bytes(before: bytes) -> bytes:
    """Make the reviewed single-link addition and preserve every other byte."""
    if before.count(ANCHOR) != 1 or before.count(CTA) != 0:
        raise ValueError("Unexpected source anchor, existing CTA or duplicate")
    if before.count(b'id="mpw-mojprop-spotlight-20261121"') != 1:
        raise ValueError("Missing verified active Moj Prop spotlight")
    if before.count(b'/moj-prop/starter-30-trx/') != 1:
        raise ValueError("Unexpected existing Starter30 navigation")
    return before.replace(ANCHOR, ANCHOR + CTA, 1)


def strict_source(before: bytes) -> bytes:
    if len(before) != BASE_SIZE or digest(before) != BASE_SHA256:
        raise RuntimeError("LIVE_SOURCE_SHA_MISMATCH; no operation permitted")
    after = candidate_bytes(before)
    if len(after) != CANDIDATE_SIZE or digest(after) != CANDIDATE_SHA256:
        raise RuntimeError("CANDIDATE_SHA_MISMATCH")
    if after.replace(ANCHOR + CTA, ANCHOR, 1) != before:
        raise RuntimeError("Exact reversal was not possible")
    return after


def _safe_target() -> tuple[bytes, int]:
    if getpass.getuser() != "zomorod2":
        raise RuntimeError("Owner cPanel user only")
    if TARGET.is_symlink() or not TARGET.is_file() or TARGET.parent.is_symlink():
        raise RuntimeError("Unsafe target path")
    current = TARGET.stat()
    if current.st_uid != os.getuid() or current.st_nlink != 1:
        raise RuntimeError("Target ownership/link count not verified")
    return TARGET.read_bytes(), stat.S_IMODE(current.st_mode)


def _atomic_replace(data: bytes, mode: int) -> None:
    temp = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".mpw-signal-cta-", dir=TARGET.parent, delete=False) as f:
            temp = Path(f.name)
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temp, mode)
        os.replace(temp, TARGET)
        temp = None
    finally:
        if temp is not None and temp.exists():
            temp.unlink()


def _new_private_file(path: Path, data: bytes) -> None:
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
    except BaseException:
        if path.exists():
            path.unlink()
        raise


def execute(mode: str) -> None:
    if mode not in ("--check", "--apply", "--rollback"):
        raise ValueError("Usage: --check | --apply | --rollback")
    before, permissions = _safe_target()
    if mode == "--rollback":
        if BACKUP_DIR.is_symlink() or not BACKUP.is_file() or not MANIFEST.is_file():
            raise RuntimeError("No trusted rollback bundle")
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        previous = BACKUP.read_bytes()
        if (manifest.get("before_sha256") != BASE_SHA256
                or manifest.get("after_sha256") != CANDIDATE_SHA256
                or manifest.get("target") != str(TARGET)
                or len(previous) != BASE_SIZE or digest(previous) != BASE_SHA256
                or len(before) != CANDIDATE_SIZE or digest(before) != CANDIDATE_SHA256):
            raise RuntimeError("ROLLBACK_PROOF_MISMATCH; refuse unrelated source overwrite")
        _atomic_replace(previous, permissions)
        if digest(TARGET.read_bytes()) != BASE_SHA256:
            raise RuntimeError("ROLLBACK_VERIFY_FAILED")
        print("ROLLBACK_VERIFIED", BASE_SHA256)
        return

    after = strict_source(before)
    print("SOURCE_VERIFIED", BASE_SHA256, "CANDIDATE_VERIFIED", CANDIDATE_SHA256)
    if mode == "--check":
        return  # genuinely read-only: no directories, backups or files created

    if PRIVATE_DIR.is_symlink() or not PRIVATE_DIR.is_dir():
        raise RuntimeError("Private root unavailable or symlink")
    if BACKUP_DIR.exists() or BACKUP_DIR.is_symlink():
        raise RuntimeError("Existing rollback bundle; refuse duplicate release")
    BACKUP_DIR.mkdir(mode=0o700)
    os.chmod(BACKUP_DIR, 0o700)
    _new_private_file(BACKUP, before)
    if digest(BACKUP.read_bytes()) != BASE_SHA256:
        raise RuntimeError("Private rollback failed readback")
    info = {
        "before_sha256": BASE_SHA256,
        "after_sha256": CANDIDATE_SHA256,
        "target": str(TARGET),
        "scope": "single extra free educational Signal Desk href on static homepage",
        "creates_invoice_or_payment": False,
    }
    _new_private_file(MANIFEST, (json.dumps(info, sort_keys=True, indent=2) + "\n").encode())
    if digest(TARGET.read_bytes()) != BASE_SHA256:
        raise RuntimeError("Source changed after backup; refuse release")
    _atomic_replace(after, permissions)
    if digest(TARGET.read_bytes()) != CANDIDATE_SHA256:
        raise RuntimeError("POST_WRITE_VERIFY_FAILED; use reviewed --rollback")
    print("SINGLE_STATIC_CTA_RELEASE_VERIFIED", CANDIDATE_SHA256)


if __name__ == "__main__":
    execute(sys.argv[1] if len(sys.argv) == 2 else "")
