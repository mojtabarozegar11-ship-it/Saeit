#!/usr/bin/env python3
"""Safely stop publishing thirteen confirmed 404 revenue routes in main-site sitemap.

Changes exactly one PHP array-merge statement; does not delete content, touch
any child site, checkout, .htaccess, Django, database, or shared Passenger.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

HOME = Path("/home/zomorod2")
SITE = HOME / "mojplaywin.com/design-preview-20261017/_mpw_sitemap_three_indexable_20261017.php"
BACKUPS = HOME / ".mpw-sitemap-dead-links-20261025"
OLD = "$paths = array_merge($paths, $mpwRevenuePages20261020);"
NEW = "// 2026-10-25: verified 13 revenue URLs return 404; do not append to sitemap."
MARKER = "MPW_REVENUE_SITEMAP_LINKS_20261020"


def sha(b):
    return hashlib.sha256(b).hexdigest()


def guard():
    root = HOME / "mojplaywin.com"
    if root.is_symlink() or not root.is_dir():
        raise RuntimeError("INVALID_MAIN_DOMAIN_ROOT")
    if SITE.is_symlink() or SITE.parent.is_symlink() or not SITE.is_file():
        raise RuntimeError("INVALID_MAIN_DOMAIN_SITEMAP_SOURCE")
    if not (root / ".htaccess").is_file():
        raise RuntimeError("MAIN_DOMAIN_IDENTITY_NOT_VERIFIED")


def patch(old):
    s = old.decode("utf-8")
    if s.count(MARKER) != 1 or s.count(OLD) != 1:
        raise RuntimeError("SITEMAP_SOURCE_DRIFT_OR_ALREADY_PATCHED")
    if s.count("'/mpw-editorial/revenue/") != 13:
        raise RuntimeError("UNEXPECTED_REVENUE_URL_COUNT")
    next_s = s.replace(OLD, NEW, 1)
    if next_s.replace(NEW, OLD, 1) != s:
        raise RuntimeError("NOT_EXACT_REPLACEMENT")
    return next_s.encode("utf-8")


def lint(b):
    fd, tmp = tempfile.mkstemp(suffix=".php", prefix=".mpw-sitemap-lint-", dir=str(SITE.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(b)
        r = subprocess.run(["php", "-l", tmp], capture_output=True, text=True, timeout=15)
        if r.returncode:
            raise RuntimeError("PHP_LINT_FAILED: " + r.stderr[-300:])
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def atomic(b):
    fd, tmp = tempfile.mkstemp(prefix=".mpw-sitemap-atomic-", dir=str(SITE.parent))
    try:
        os.fchmod(fd, SITE.stat().st_mode & 0o777)
        with os.fdopen(fd, "wb") as f:
            f.write(b)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, SITE)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main(action, run):
    if not re.fullmatch(r"[0-9]{6,20}", run):
        raise RuntimeError("INVALID_RUN_ID")
    guard()
    d = BACKUPS / run
    if action == "apply":
        old = SITE.read_bytes()
        new = patch(old)
        lint(new)
        if d.exists() or d.is_symlink():
            raise RuntimeError("BACKUP_ALREADY_EXISTS")
        d.mkdir(parents=True, mode=0o700)
        (d / "sitemap.php.bak").write_bytes(old)
        m = {"before": sha(old), "after": sha(new), "state": "prepared"}
        (d / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
        if SITE.read_bytes() != old:
            raise RuntimeError("CONCURRENT_MODIFICATION")
        atomic(new)
        if sha(SITE.read_bytes()) != m["after"]:
            raise RuntimeError("WRITE_HASH_MISMATCH")
        m["state"] = "installed"
        (d / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
        print("MAIN_DOMAIN_SITEMAP_13_BROKEN_LINKS_EXCLUDED")
    elif action == "rollback":
        m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
        old = (d / "sitemap.php.bak").read_bytes()
        if sha(old) != m["before"] or sha(SITE.read_bytes()) != m["after"]:
            raise RuntimeError("ROLLBACK_BLOCKED_BY_CONCURRENT_EDIT")
        atomic(old)
        if sha(SITE.read_bytes()) != m["before"]:
            raise RuntimeError("ROLLBACK_HASH_MISMATCH")
        print("MAIN_DOMAIN_SITEMAP_ROLLBACK_VERIFIED")
    else:
        raise RuntimeError("UNKNOWN_ACTION")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: script.py apply|rollback RUN_ID")
    main(sys.argv[1], sys.argv[2])
