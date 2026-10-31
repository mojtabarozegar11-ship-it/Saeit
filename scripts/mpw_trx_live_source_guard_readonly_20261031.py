#!/usr/bin/env python3
"""S-01 TRX checkout source identity comparison, on-host READ ONLY.

The references are source snapshots from DIFFERENT review branches, not a
deployable bundle. A match is evidence only; release always stays blocked.
No remote source bytes, private values, DB rows, wallet or customer data emitted.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import sys

REFERENCE_SHA256 = {
    "rate": "1a9e03ccb643e9a8af71fe5ce75e7d30510952164a8a2fad35a504c48c31c05e",
    "buyer": "001f981881ce09adf18092f67dd9ba1dc4cb3bf8b3d778f90b5786e704d2fbb3",
    "web": "286eaadd92d070aa7694852752cd0ac8d8444d594d5be79e157588b9a5084180",
    "guest": "7693254e4ed72141b6de7fc283c5a3214159ea49d838318337e47e86953f5f2f",
    "wallet": "b1812f31d3a4f8db15aed5897f3c62133a2870483684cb302bc4d8b52d3e411c",
}
RELATIVE_PATHS = {
    "rate": "Saeit-staging/scripts/mojplaywin_direct_wallet_rates.py",
    "buyer": "Saeit-staging/mpw_commerce/buyer_wallets.py",
    "web": "Saeit-staging/services/mpw_trx_commercial_web.py",
    "guest": "Saeit-staging/services/mpw_trx_guest_commerce.py",
    "wallet": "Saeit-staging/services/mpw_trx_walletless_one_tap_ui.py",
}
MAX_FILE = 2 * 1024 * 1024


def secure_digest(path: Path, owner_uid: int):
    """Descriptor-relative O_NOFOLLOW traversal; no unsafe ancestor or file."""
    path = Path(path)
    if not path.is_absolute() or any(x in (".", "..") for x in path.parts):
        return None
    dirfd = filefd = None
    try:
        dflags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        dirfd = os.open("/", dflags)
        for part in path.parts[1:-1]:
            nxt = os.open(part, dflags, dir_fd=dirfd)
            os.close(dirfd)
            dirfd = nxt
        filefd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                         dir_fd=dirfd)
        before = os.fstat(filefd)
        if (not stat.S_ISREG(before.st_mode) or before.st_uid != owner_uid
                or before.st_nlink != 1 or not 0 < before.st_size <= MAX_FILE
                or stat.S_IMODE(before.st_mode) & 0o022):
            return None
        digest = hashlib.sha256()
        total = 0
        with os.fdopen(os.dup(filefd), "rb") as src:
            while True:
                chunk = src.read(65536)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_FILE:
                    return None
                digest.update(chunk)
        after = os.fstat(filefd)
        stable = (before.st_dev, before.st_ino, before.st_size,
                  before.st_mtime_ns, before.st_ctime_ns) == (
                  after.st_dev, after.st_ino, after.st_size,
                  after.st_mtime_ns, after.st_ctime_ns)
        return digest.hexdigest() if stable and total == before.st_size else None
    except (OSError, ValueError, OverflowError):
        return None
    finally:
        if filefd is not None:
            os.close(filefd)
        if dirfd is not None:
            os.close(dirfd)


def classify(digests: dict) -> dict:
    """No DB or release assertions; only exact identity classifications."""
    if set(digests) != set(REFERENCE_SHA256):
        raise ValueError("Unexpected source identity manifest")
    states = {}
    for key in RELATIVE_PATHS:
        value = digests[key]
        if value is None:
            states[key] = "UNAVAILABLE_OR_UNSAFE"
        elif isinstance(value, str) and len(value) == 64 and all(
                c in "0123456789abcdef" for c in value):
            states[key] = "REFERENCE_MATCH" if value == REFERENCE_SHA256[key] else "SHA_DRIFT"
        else:
            states[key] = "INVALID_DIGEST"
    return {
        "scope": "S01_TRX_LIVE_SOURCE_READONLY",
        "source_states": states,
        "source_identity_all_match": all(x == "REFERENCE_MATCH" for x in states.values()),
        "release_permitted": False,
        "passenger_db_authority_verified": False,
        "offhost_full_restore_verified": False,
        "wallet_return_verified": False,
        "orders_created": 0,
        "payments_created": 0,
        "cpanel_writes": False,
    }


def probe(root: Path = Path("/home/zomorod2")) -> dict:
    uid = os.getuid()
    observed = {key: secure_digest(root / path, uid)
                for key, path in RELATIVE_PATHS.items()}
    result = classify(observed)
    wsgi = secure_digest(root / "mojplaywin.com/passenger_wsgi.py", uid)
    result["passenger_wsgi_regular_owned"] = wsgi is not None
    # WSGI file identity is not the effective running process/DB configuration.
    result["passenger_effective_runtime_verified"] = False
    return result


if __name__ == "__main__":
    if len(sys.argv) != 1:
        raise SystemExit("No runtime arguments permitted")
    print("S01_TRX_SOURCE_GUARD=" + json.dumps(probe(), sort_keys=True))
