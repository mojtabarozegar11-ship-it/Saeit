#!/usr/bin/env python3
"""Read-only, tenant-specific attestation for MOJ PROP's 17 branded Signal CTAs.

This tool DOES NOT deploy anything. It checks exact source bytes, an existing
private rollback/stage bundle, the tenant WSGI and rewrite boundaries, and
every running LiteSpeed worker's effective project root.

No root access, reload, secrets, database, wallet, email or factory changes.
A passing result is not permission to restart or to collect a payment.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import sys
from urllib.parse import parse_qs, urlsplit

TENANT_UID = 1371
ACTIVE_ROOT = Path("/home/zomorod2/Saeit-mojprop-candidate-20261122")
ACTIVE = ACTIVE_ROOT / "core/financial_brand_pages.py"
PUBLIC_ROOT = Path("/home/zomorod2/mojplaywin.com")
WSGI = PUBLIC_ROOT / "passenger_wsgi.py"
HTACCESS = PUBLIC_ROOT / ".htaccess"
BUNDLE = Path(
    "/home/zomorod2/separated-backups/20261122/"
    "brand-signal-17-canonical-intake-stage-20261122"
)
BEFORE_SHA256 = "a81c2977997a3f9199528d5851607c37869a89889ffa673ce7b2f0438157fd48"
CANDIDATE_SHA256 = "0099382d65de28e6ae2221e951b401e6a0578047ba202e13332985f1da7215a3"
WSGI_SHA256 = "1b6607db63a94678f2c067902616aed5fc294135d5f66008640f04318aaad25f"
HTACCESS_SHA256 = "7a6a28adb9e31623ad93f7f853108e686e956aaea8a98cc2e9ee3bd891e17c0b"
APPROVED_MAIN_COMMIT = "1dc67dc39952ecde2c5e32d2bf1dedef5cfb25d2"
OLD = {
    b'SIGNAL_INTAKE_PATH = "https://mojplaywin.com/moj-prop/?service=signals#request"':
    b'SIGNAL_INTAKE_PATH = "https://mojplaywin.com/moj-prop-intake/?format=html&service=signals"',
    b'SIGNAL_FREE_PREVIEW_PATH = "https://mojplaywin.com/moj-prop/signals/#free-preview"':
    b'SIGNAL_FREE_PREVIEW_PATH = "https://mojplaywin.com/moj-prop/signals/"',
}


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def exact_candidate(before: bytes, candidate: bytes, before_sha: str = BEFORE_SHA256,
                    candidate_sha: str = CANDIDATE_SHA256) -> bool:
    """A two-constant replacement; no hidden module or side-effect edits."""
    if digest(before) != before_sha or digest(candidate) != candidate_sha:
        raise ValueError("SOURCE_HASH_DRIFT")
    expected = before
    for old, new in OLD.items():
        if expected.count(old) != 1:
            raise ValueError("MISSING_OR_DUPLICATE_OLD_CONSTANT")
        expected = expected.replace(old, new, 1)
    if expected != candidate:
        raise ValueError("NON_TARGET_CODE_CHANGE")
    url = urlsplit(OLD[next(iter(OLD))].decode().split('"')[1])
    if (url.scheme != "https" or url.netloc != "mojplaywin.com"
            or url.path != "/moj-prop-intake/" or url.fragment
            or parse_qs(url.query, strict_parsing=True) !=
            {"format": ["html"], "service": ["signals"]}):
        raise ValueError("UNTRUSTED_CANONICAL_INTAKE")
    if b"checkout" in candidate.lower()[:7000]:
        # Only verify the modified lines, not unrelated vetted catalog copy.
        for line in candidate.splitlines():
            if line.startswith(b"SIGNAL_INTAKE_PATH") and b"checkout" in line.lower():
                raise ValueError("SIGNALS_CTA_MUST_NOT_CHECKOUT")
    return True


def owner_regular(path: Path, *, private: bool) -> bytes:
    metadata = os.lstat(path)
    if (not stat.S_ISREG(metadata.st_mode) or path.is_symlink()
            or metadata.st_uid != TENANT_UID or metadata.st_nlink != 1):
        raise ValueError("UNTRUSTED_FILE:" + str(path))
    mode = stat.S_IMODE(metadata.st_mode)
    if private and mode & 0o077:
        raise ValueError("PRIVATE_BACKUP_PERMISSIONS")
    return path.read_bytes()


def active_wsgi_workers() -> list[int]:
    matches = []
    for proc in Path("/proc").iterdir():
        if not proc.name.isdecimal():
            continue
        try:
            executable = os.readlink(str(proc / "exe"))
            if not executable.endswith("/lswsgi"):
                continue
            cmd = (proc / "cmdline").read_bytes()
            if str(WSGI).encode() not in cmd:
                continue
            actual_root = (proc / "cwd").resolve(strict=True)
        except (PermissionError, FileNotFoundError, ProcessLookupError, OSError):
            continue
        if actual_root != ACTIVE_ROOT:
            raise ValueError("WORKER_PROJECT_ROOT_DRIFT:" + proc.name)
        matches.append(int(proc.name))
    if not matches:
        raise ValueError("NO_TRUSTED_LSWSGI_WORKERS")
    return sorted(matches)


def attest() -> dict:
    if os.geteuid() != TENANT_UID:
        raise PermissionError("REQUIRES_AUTHORIZED_CPANEL_TENANT")
    directory = os.lstat(BUNDLE)
    if (not stat.S_ISDIR(directory.st_mode) or BUNDLE.is_symlink()
            or directory.st_uid != TENANT_UID or
            stat.S_IMODE(directory.st_mode) != 0o700):
        raise ValueError("UNTRUSTED_PRIVATE_STAGE")
    main = owner_regular(ACTIVE, private=False)
    old = owner_regular(BUNDLE / "financial_brand_pages.before.py", private=True)
    new = owner_regular(BUNDLE / "financial_brand_pages.candidate.py", private=True)
    manifest = json.loads(owner_regular(BUNDLE / "manifest.json", private=True))
    if (main != old or manifest["source_file"] != str(ACTIVE)
            or manifest["main_git_commit"] != APPROVED_MAIN_COMMIT
            or manifest["before_sha256"] != BEFORE_SHA256
            or manifest["candidate_sha256"] != CANDIDATE_SHA256
            or manifest["status"] != "PREPARED_ONLY_NOT_DEPLOYED"
            or manifest["production_mutated"] is not False):
        raise ValueError("STAGED_PRODUCTION_IDENTITY_DRIFT")
    exact_candidate(old, new)
    if digest(owner_regular(WSGI, private=False)) != WSGI_SHA256:
        raise ValueError("WSGI_ENTRYPOINT_CHANGED")
    if digest(owner_regular(HTACCESS, private=False)) != HTACCESS_SHA256:
        raise ValueError("TENANT_REWRITE_RULES_CHANGED")
    workers = active_wsgi_workers()
    return {
        "decision": "PREPARED_NOT_DEPLOYED",
        "read_only": True,
        "main_commit": APPROVED_MAIN_COMMIT,
        "effective_root": str(ACTIVE_ROOT),
        "worker_count": len(workers),
        "before_sha256": BEFORE_SHA256,
        "candidate_sha256": CANDIDATE_SHA256,
        "two_constant_edit_only": True,
        "production_source_modified": False,
        "production_recovery_approval_verified": False,
    }


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] != "--verify-stage":
        raise SystemExit("Usage: python scripts/mojprop_signal_brand_stage_preflight.py --verify-stage")
    print(json.dumps(attest(), sort_keys=True))
