#!/usr/bin/env python3
"""Pinned, single-static-page MOJ PROP Signal Desk discoverability and lead CTA.

SOURCE ONLY: GitHub merge never deploys this script. Run --check for a
strictly read-only origin audit. --apply/--rollback are separately authorised
operator actions requiring a trustworthy private backup and known live SHA.
Never touches Django, TRX, MojProp paid admissions, store, robot or factory.
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

TARGET = Path("/home/zomorod2/mojplaywin.com/moj-prop/signals/index.html")
BACKUP_ROOT = Path("/home/zomorod2/.private_mojplaywin_main_agents")
BUNDLE = BACKUP_ROOT / "signal-desk-hero-conversion-20261122"
BEFORE = BUNDLE / "signals-index.before.html"
MANIFEST = BUNDLE / "manifest.json"

BASE_SHA256 = "7ebd4931efb3594f334ee5867ab5974db4275742c11b277ae918b94dd32df4c6"
NEXT_SHA256 = "f60ea4b001e496d4e5c7536aa3b4036f9c0a106b032663039fbf621692fc74bf"
BASE_BYTES = 5544
NEXT_BYTES = 6228
H1_OLD = b"<h1>Signals without illusion.</h1>"
H1_NEW = b"<h1>Educational trading signal examples and market analysis</h1>"
EDGE_OLD = b'</div></section><section class="grid">'
EDGE_NEW = (
    b'</div><p class="note" id="signal-desk-primary-cta-20261122">'
    b'Ask for the current scope, a sample educational market brief and written terms. '
    b'No payment, active live signal feed, automatic subscription or delivery guarantee is offered. '
    b'The secure form requires your contact details, a short message and explicit consent. '
    b'Example message: &quot;Please send the educational Signal Desk scope, sample and pricing.&quot;'
    b'</p><p><a href="/moj-prop-intake/?format=html&amp;service=signals'
    b'&amp;utm_source=moj_prop&amp;utm_medium=onsite'
    b'&amp;utm_campaign=signals_education_lead_20261121&amp;utm_content=signal_nav">'
    b'Request written Signal Desk proposal - no payment</a></p></section>'
    b'<section class="grid">'
)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def candidate_bytes(raw: bytes) -> bytes:
    if len(raw) != BASE_BYTES or digest(raw) != BASE_SHA256:
        raise ValueError("LIVE_SIGNAL_DESK_DRIFT: source SHA changed; no apply allowed")
    if raw.count(H1_OLD) != 1 or raw.count(H1_NEW) != 0:
        raise ValueError("Signal Desk headline no longer uniquely matches")
    if raw.count(EDGE_OLD) != 1 or raw.count(EDGE_NEW) != 0:
        raise ValueError("Original section boundary no longer uniquely matches")
    if b'signal-desk-primary-cta-20261122' in raw:
        raise ValueError("Lead CTA already present; cannot apply twice")
    if b'/moj-prop-intake/?format=html&amp;service=signals' not in raw:
        raise ValueError("The original consent form destination is absent")
    changed = raw.replace(H1_OLD, H1_NEW, 1).replace(EDGE_OLD, EDGE_NEW, 1)
    if (len(changed) != NEXT_BYTES or digest(changed) != NEXT_SHA256
            or changed.replace(H1_NEW, H1_OLD, 1).replace(EDGE_NEW, EDGE_OLD, 1) != raw):
        raise ValueError("Unreviewed or irreversible candidate")
    return changed


def _read_target() -> tuple[bytes, int]:
    if getpass.getuser() != "zomorod2":
        raise PermissionError("Only the authenticated owner cPanel tenant may inspect the target")
    if TARGET.is_symlink() or TARGET.parent.is_symlink() or not TARGET.is_file():
        raise ValueError("Untrusted target or a symlink")
    metadata = TARGET.stat()
    if metadata.st_uid != os.geteuid() or metadata.st_nlink != 1:
        raise ValueError("Untrusted file ownership or link count")
    return TARGET.read_bytes(), stat.S_IMODE(metadata.st_mode)


def _read_verified_private_file(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing or untrusted private backup file")
    info = path.stat()
    if info.st_uid != os.geteuid() or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) & 0o077:
        raise ValueError("Private backup file permissions invalid")
    return path.read_bytes()


def _create_exclusive_private_file(path: Path, raw: bytes) -> None:
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "wb") as output:
        output.write(raw)
        output.flush()
        os.fsync(output.fileno())


def _atomic_replace(raw: bytes, mode: int) -> None:
    temp = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=".mojprop-signal-lead-", dir=TARGET.parent, delete=False
        ) as output:
            temp = Path(output.name)
            output.write(raw)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temp, mode)
        os.replace(temp, TARGET)
        temp = None
    finally:
        if temp is not None and temp.exists():
            temp.unlink()


def execute(mode: str) -> None:
    if mode not in ("--check", "--apply", "--rollback"):
        raise ValueError("Usage: --check | --apply | --rollback")
    current, permissions = _read_target()
    if mode == "--rollback":
        if BUNDLE.is_symlink() or not BUNDLE.is_dir():
            raise ValueError("Trusted independent rollback bundle absent")
        manifest = json.loads(_read_verified_private_file(MANIFEST).decode("utf8"))
        original = _read_verified_private_file(BEFORE)
        expected = {
            "target": str(TARGET),
            "before_sha256": BASE_SHA256,
            "after_sha256": NEXT_SHA256,
            "scope": "MojProp English Signal Desk hero headline and existing manual lead CTA",
        }
        if (manifest != expected or len(current) != NEXT_BYTES
                or digest(current) != NEXT_SHA256
                or len(original) != BASE_BYTES
                or digest(original) != BASE_SHA256):
            raise ValueError("Rollback would overwrite unknown newer public HTML")
        _atomic_replace(original, permissions)
        if digest(TARGET.read_bytes()) != BASE_SHA256:
            raise ValueError("Rollback readback failed")
        print("SIGNAL_DESK_ROLLBACK_VERIFIED", BASE_SHA256)
        return

    candidate = candidate_bytes(current)
    print("READ_ONLY_SOURCE_MATCH", BASE_SHA256, "CANDIDATE_MATCH", NEXT_SHA256)
    if mode == "--check":
        return

    if (BACKUP_ROOT.is_symlink() or not BACKUP_ROOT.is_dir()
            or BACKUP_ROOT.stat().st_uid != os.geteuid()
            or BUNDLE.exists() or BUNDLE.is_symlink()):
        raise ValueError("Untrusted or previously used private rollback target")
    BUNDLE.mkdir(mode=0o700)
    os.chmod(BUNDLE, 0o700)
    _create_exclusive_private_file(BEFORE, current)
    if len(_read_verified_private_file(BEFORE)) != BASE_BYTES or digest(
        _read_verified_private_file(BEFORE)
    ) != BASE_SHA256:
        raise ValueError("Backup byte-for-byte integrity not verified")
    manifest = {
        "target": str(TARGET),
        "before_sha256": BASE_SHA256,
        "after_sha256": NEXT_SHA256,
        "scope": "MojProp English Signal Desk hero headline and existing manual lead CTA",
    }
    _create_exclusive_private_file(
        MANIFEST, (json.dumps(manifest, sort_keys=True) + "\n").encode("utf8")
    )
    if digest(TARGET.read_bytes()) != BASE_SHA256:
        raise ValueError("Concurrently modified Signal Desk file; refuse to overwrite")
    _atomic_replace(candidate, permissions)
    if digest(TARGET.read_bytes()) != NEXT_SHA256:
        raise ValueError("Post-apply readback failed; controlled rollback required")
    print("SIGNAL_DESK_HERO_RELEASE_VERIFIED", NEXT_SHA256)


if __name__ == "__main__":
    execute(sys.argv[1] if len(sys.argv) == 2 else "")
