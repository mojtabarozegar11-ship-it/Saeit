#!/usr/bin/env python3
"""Read-only, secret-free production evidence for Moj Prop Starter30.

Designed for stdin streaming to the existing verified cPanel account through a
factory-VPS runner. NEVER modifies the filesystem, Django, databases, wallets,
payment state or customer information. The JSON contains no directory path,
hostname, username, secret or buyer data.

This is not a backup/restore or tenant-isolation attestation. Those must be
demonstrated separately; consequently this script NEVER permits a release.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import pwd
import stat
import sys

KNOWN_DOCROOT = Path("/home/zomorod2/mojplaywin.com")
EXPECTED_OWNER = "zomorod2"
MAX_FILE_BYTES = 512_000
PUBLIC_ASSETS = ("index.html", "journal-template.csv", "journal-guide.txt")
COLLECTION_ROOT = "moj-prop"
PRODUCT = "starter-30-trx"


def _metadata(root: Path, path: Path, expected_kind: str) -> dict:
    """lstat (never follow symlinks); return only booleans, never raw paths."""
    result = {"exists": False, "regular": False, "directory": False,
              "symlink": False, "owner_matches": False, "world_writable": False}
    try:
        info = path.lstat()
    except (FileNotFoundError, PermissionError, OSError):
        return result
    result["exists"] = True
    result["symlink"] = stat.S_ISLNK(info.st_mode)
    result["regular"] = stat.S_ISREG(info.st_mode)
    result["directory"] = stat.S_ISDIR(info.st_mode)
    result["owner_matches"] = info.st_uid == os.geteuid()
    result["world_writable"] = bool(info.st_mode & stat.S_IWOTH)
    if expected_kind == "file" and info.st_size > MAX_FILE_BYTES:
        result["size_blocked"] = True
    return result


def _safe_content(root: Path, path: Path) -> bytes | None:
    """Refuse symlink ancestors, missing files, large files and out-of-root paths."""
    # Python 3.8 factory runners lack Path.is_relative_to (added in 3.9).
    # relative_to itself is available and retains the same fail-closed check.
    try:
        if path == root:
            return None
        path.relative_to(root)
    except ValueError:
        return None
    cursor = path
    while cursor != root:
        m = _metadata(root, cursor, "file" if cursor == path else "dir")
        if m["symlink"] or not m["exists"] or not m["owner_matches"] or m["world_writable"]:
            return None
        if cursor != path and not m["directory"]:
            return None
        cursor = cursor.parent
    root_m = _metadata(root, root, "dir")
    m = _metadata(root, path, "file")
    if (not root_m["directory"] or root_m["symlink"] or not root_m["owner_matches"]
            or not m["regular"] or m.get("size_blocked")):
        return None
    try:
        # O_NOFOLLOW refuses late symlink swaps; fstat catches non-regular files.
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(fd, "rb") as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FILE_BYTES:
                return None
            return handle.read(MAX_FILE_BYTES + 1)
    except (OSError, PermissionError):
        return None


def snapshot(root: Path = KNOWN_DOCROOT, *, owner: str = EXPECTED_OWNER) -> dict:
    """Only sanitized evidence. Truthful default is fail-closed."""
    user_ok = False
    try:
        user_ok = pwd.getpwuid(os.geteuid()).pw_name == owner
    except (KeyError, OSError):
        pass
    root_info = _metadata(root, root, "dir")
    route = root / COLLECTION_ROOT
    package = route / PRODUCT
    route_info = _metadata(root, route, "dir")
    package_info = _metadata(root, package, "dir")
    root_accepted = bool(
        user_ok and root_info["directory"] and not root_info["symlink"]
        and root_info["owner_matches"] and not root_info["world_writable"]
        and route_info["directory"] and not route_info["symlink"]
        and route_info["owner_matches"] and not route_info["world_writable"]
        and (not package_info["exists"] or
             (package_info["directory"] and not package_info["symlink"]
              and package_info["owner_matches"] and not package_info["world_writable"]))
    )

    assets = {}
    for name in PUBLIC_ASSETS:
        value = _safe_content(root, package / name) if root_accepted else None
        assets[name] = {
            "readable": value is not None,
            "sha256_prefix": hashlib.sha256(value).hexdigest()[:16] if value is not None else None,
        }

    home = _safe_content(root, route / "index.html") if root_accepted else None
    catalog = _safe_content(root, route / "catalog" / "index.html") if root_accepted else None
    main_html = assets["index.html"]["readable"]
    template = _safe_content(root, package / "journal-template.csv") if root_accepted else None
    page = _safe_content(root, package / "index.html") if root_accepted else None
    report = {
        "schema": "mojprop.starter30.live_readonly.v1",
        "read_only": True,
        "owner_account_verified": user_ok,
        "docroot_and_route_ownership_verified": root_accepted,
        "candidate_package_directory_present": package_info["directory"],
        "assets": assets,
        "product_content": {
            "discloses_30_native_trx": bool(page and b"30 TRX" in page),
            "payment_disabled": bool(page and b"Payment not enabled" in page and b"Do not send TRX" in page),
            "educational_only": bool(page and b"No funded account is included" in page),
            "free_journal_valid_shape": bool(template and template.startswith(b"session,closing_equity_usd,risk_plan_recorded,reflection_recorded\n")),
            "linked_from_home": bool(home and b"starter-30-trx" in home),
            "linked_from_catalog": bool(catalog and b"starter-30-trx" in catalog),
        },
        "disk_free_at_least_512mb": None,
        # Neither Passenger list nor this filesystem inspection proves these:
        "effective_http_route_verified": False,
        "domain_tenant_isolation_proven": False,
        "independent_backup_restored_in_isolation": False,
        "approved_verified_trx_merchant": False,
        "customer_specific_invoice_and_solidified_settlement": False,
        "release_permitted": False,
        "revenue_proven": False,
    }
    try:
        if root_accepted:
            f = os.statvfs(root)
            report["disk_free_at_least_512mb"] = (f.f_bavail * f.f_frsize >= 512 * 1024 * 1024)
    except (OSError, ValueError):
        pass
    # Do not print e-mail addresses, filenames outside fixed allowlist,
    # account names, hostnames, environment or arbitrary HTTP content.
    return report


def main() -> int:
    result = snapshot()
    print(json.dumps(result, sort_keys=True, ensure_ascii=True))
    return 0 if result["read_only"] else 1


if __name__ == "__main__":
    sys.exit(main())
