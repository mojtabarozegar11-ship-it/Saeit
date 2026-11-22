#!/usr/bin/env python3
"""Exact-source MojPlayWin homepage signal enquiry CTA; SOURCE ONLY.

--check does absolutely no write. --apply / --rollback require separate
case-scoped authorization to the operator, plus a private verified backup.
No payment, TRX, Passenger, factory, customer identity, or email change.
The earlier home-free-signal script is now STALE and must never be applied
against this concurrently changed live homepage.
"""
from __future__ import annotations

import getpass
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile

TARGET = Path(
    "/home/zomorod2/mojplaywin.com/"
    "design-preview-20261017/production-home-20261017.html"
)
PRIVATE = Path("/home/zomorod2/.private_mojplaywin_main_agents")
BUNDLE = PRIVATE / "home-signal-proposal-currentsha-20261122"
BEFORE = BUNDLE / "production-home.before"
MANIFEST = BUNDLE / "manifest.json"

BASE_SHA256 = "eadc94648806f728cf6f559932277d45f61227246c6d4ab992e1949286b4766d"
CANDIDATE_SHA256 = "b76f16876d093900f6f855c5771f6ff3ebe374450a0c373dcb57f47635e0bc07"
BASE_BYTES = 266515
CANDIDATE_BYTES = 266520
OLD = (
    b'<a class="mpw-mojprop-secondary" href="/moj-prop-intake/?format=html'
    b'&amp;service=signals&amp;utm_source=moj_prop&amp;utm_medium=onsite'
    b'&amp;utm_campaign=signals_education_lead_20261121'
    b'&amp;utm_content=signal_nav">Signal Desk information</a>'
)
NEW = OLD.replace(b"Signal Desk information", b"Request Signal Desk proposal")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def derive(raw: bytes) -> bytes:
    if len(raw) != BASE_BYTES or digest(raw) != BASE_SHA256:
        raise ValueError("active source SHA changed; no write or rollback permitted")
    if raw.count(OLD) != 1 or raw.count(NEW) != 0:
        raise ValueError("original signal enquiry CTA is absent or repeated")
    if raw.count(b'id="mpw-mojprop-spotlight-20261121"') != 1:
        raise ValueError("active MojProp spotlight identity has drifted")
    changed = raw.replace(OLD, NEW, 1)
    if (len(changed) != CANDIDATE_BYTES
            or digest(changed) != CANDIDATE_SHA256
            or changed.replace(NEW, OLD, 1) != raw):
        raise ValueError("unreviewed candidate or nonreversible change")
    return changed


def read_owner_home() -> tuple[bytes, int]:
    if getpass.getuser() != "zomorod2":
        raise ValueError("owner cPanel tenant required")
    if TARGET.is_symlink() or TARGET.parent.is_symlink() or not TARGET.is_file():
        raise ValueError("unsafe live file")
    meta = TARGET.stat()
    if meta.st_uid != os.geteuid() or meta.st_nlink != 1:
        raise ValueError("unverified file owner or link count")
    return TARGET.read_bytes(), stat.S_IMODE(meta.st_mode)


def safe_private_file(path: Path) -> bytes:
    if not path.is_file() or path.is_symlink():
        raise ValueError("private rollback file missing or is symlink")
    meta = path.stat()
    if (meta.st_uid != os.geteuid() or meta.st_nlink != 1
            or stat.S_IMODE(meta.st_mode) & 0o077):
        raise ValueError("private rollback file permissions untrusted")
    return path.read_bytes()


def create_0600(path: Path, raw: bytes) -> None:
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
    handle = os.open(path, flags, 0o600)
    with os.fdopen(handle, "wb") as writer:
        writer.write(raw)
        writer.flush()
        os.fsync(writer.fileno())


def atomic_replace(raw: bytes, mode: int) -> None:
    candidate = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=".mpw-signal-proposal-", dir=TARGET.parent, delete=False
        ) as writer:
            candidate = Path(writer.name)
            writer.write(raw)
            writer.flush()
            os.fsync(writer.fileno())
        os.chmod(candidate, mode)
        os.replace(candidate, TARGET)
        candidate = None
    finally:
        if candidate is not None and candidate.exists():
            candidate.unlink()


def execute(mode: str) -> None:
    if mode not in ("--check", "--apply", "--rollback"):
        raise ValueError("Use --check; --apply and --rollback are owner-scoped only")
    raw, perms = read_owner_home()
    if mode == "--rollback":
        if BUNDLE.is_symlink() or not BUNDLE.is_dir():
            raise ValueError("no trusted private rollback directory")
        info = json.loads(safe_private_file(MANIFEST).decode("utf-8"))
        old = safe_private_file(BEFORE)
        if (info != {"source_sha256": BASE_SHA256,
                     "candidate_sha256": CANDIDATE_SHA256,
                     "target": str(TARGET)}
                or len(raw) != CANDIDATE_BYTES or digest(raw) != CANDIDATE_SHA256
                or len(old) != BASE_BYTES or digest(old) != BASE_SHA256):
            raise ValueError("cannot safely undo someone else's newer homepage")
        atomic_replace(old, perms)
        if digest(TARGET.read_bytes()) != BASE_SHA256:
            raise ValueError("rollback readback not verified")
        print("HOMEPAGE_ROLLBACK_VERIFIED", BASE_SHA256)
        return

    after = derive(raw)
    print("READ_ONLY_SOURCE_MATCH", BASE_SHA256, "CANDIDATE", CANDIDATE_SHA256)
    if mode == "--check":
        return

    # A private exact backup is mandatory for any separately authorized apply.
    if PRIVATE.is_symlink() or not PRIVATE.is_dir():
        raise ValueError("private backup root unavailable")
    if (BUNDLE.exists() or BUNDLE.is_symlink()
            or PRIVATE.stat().st_uid != os.geteuid()):
        raise ValueError("existing or untrusted rollback bundle")
    BUNDLE.mkdir(mode=0o700)
    os.chmod(BUNDLE, 0o700)
    create_0600(BEFORE, raw)
    if digest(safe_private_file(BEFORE)) != BASE_SHA256:
        raise ValueError("unverified private backup")
    manifest = {"source_sha256": BASE_SHA256,
                "candidate_sha256": CANDIDATE_SHA256,
                "target": str(TARGET)}
    create_0600(MANIFEST, (json.dumps(manifest, sort_keys=True) + "\n").encode())
    if digest(TARGET.read_bytes()) != BASE_SHA256:
        raise ValueError("homepage changed during backup; refuse overwrite")
    atomic_replace(after, perms)
    if digest(TARGET.read_bytes()) != CANDIDATE_SHA256:
        raise ValueError("post-apply readback failed")
    print("SCOPED_STATIC_SIGNAL_PROPOSAL_APPLIED", CANDIDATE_SHA256)


if __name__ == "__main__":
    execute(sys.argv[1] if len(sys.argv) == 2 else "")
