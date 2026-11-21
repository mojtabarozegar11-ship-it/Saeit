#!/usr/bin/env python3
"""Atomic, scoped installer of MojPlayWin measurement onto STATIC public routes.

It does not touch .htaccess, Django, Passenger, database, factory, payment code,
cron, emails, other sites or source repositories. Requires explicit --apply.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile

WEBROOT = Path("/home/zomorod2/mojplaywin.com")
BACKUPS = Path("/home/zomorod2/separated-backups")
PRIVATE = Path("/home/zomorod2/.mpw-measure")
PAGES = (
    "store/index.html",
    "moj-prop/index.html",
    "moj-prop/starter-30-trx/index.html",
    "moj-prop/catalog/index.html",
    "moj-prop/rules/index.html",
    "moj-prop/payment/index.html",
    "moj-prop/contact/index.html",
    "moj-prop/signals/index.html",
)
ASSETS = ("collect.php", "tracker.js", "privacy.html")
MARKER = '<script defer src="/mpw-measure/tracker.js"></script>'


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def regular(path: Path) -> bool:
    return path.is_file() and not path.is_symlink()


def inspect(webroot: Path, source: Path):
    if not webroot.is_dir() or webroot.is_symlink():
        raise RuntimeError("WEBROOT_MISSING_OR_SYMLINK")
    prepared = {}
    for name in ASSETS:
        path = source / name
        if not regular(path) or path.stat().st_size > 64 * 1024:
            raise RuntimeError("BAD_SOURCE_ASSET:" + name)
        prepared["mpw-measure/" + name] = path.read_bytes()
    if shutil.which("php"):
        p = subprocess.run(["php", "-l", str(source / "collect.php")],
                           capture_output=True, text=True, timeout=10)
        if p.returncode != 0:
            raise RuntimeError("PHP_LINT_FAILED:" + p.stderr[:200])
    if shutil.which("node"):
        p = subprocess.run(["node", "--check", str(source / "tracker.js")],
                           capture_output=True, text=True, timeout=10)
        if p.returncode != 0:
            raise RuntimeError("JS_LINT_FAILED:" + p.stderr[:200])
    for name in PAGES:
        path = webroot / name
        if not regular(path) or path.stat().st_size > 256 * 1024:
            raise RuntimeError("PAGE_UNSAFE_OR_MISSING:" + name)
        data = path.read_bytes()
        text = data.decode("utf-8")
        if text.count(MARKER) == 1:
            updated = data
        else:
            if MARKER in text or len(re.findall("</body>", text, re.I)) != 1:
                raise RuntimeError("AMBIGUOUS_BODY:" + name)
            updated = re.sub("</body>", MARKER + "\n</body>",
                             text, count=1, flags=re.I).encode("utf-8")
        prepared[name] = updated
    return prepared


def atomic_replace(path: Path, data: bytes, mode: int):
    fd, temp = tempfile.mkstemp(prefix=".mpw-measure-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp, mode)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def apply(webroot: Path, source: Path, backups: Path, private: Path):
    prepared = inspect(webroot, source)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = backups / stamp[:8] / ("mpw-measure-" + stamp)
    if backup.exists():
        raise RuntimeError("BACKUP_ALREADY_EXISTS")
    backup.mkdir(parents=True, mode=0o700)
    os.chmod(backup, 0o700)
    original = {}
    for name in prepared:
        target = webroot / name
        if target.exists():
            if not regular(target):
                raise RuntimeError("EXISTING_ASSET_NOT_REGULAR:" + name)
            data = target.read_bytes()
            original[name] = sha(data)
            destination = backup / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
            os.chmod(destination, 0o600)
    (backup / "manifest.json").write_text(json.dumps({
        "schema": "mpw.measure.backup.v1", "original_sha256": original,
        "targets": list(prepared), "new_assets": [
            name for name in prepared if name not in original
        ],
        "restore_note": "Restoring a prior version requires owner-approved, scoped rollback.",
    }, indent=2), encoding="utf-8")
    os.chmod(backup / "manifest.json", 0o600)
    if private.exists() and private.is_symlink():
        raise RuntimeError("PRIVATE_DIR_IS_SYMLINK")
    private.mkdir(mode=0o700, exist_ok=True)
    (private / "events").mkdir(mode=0o700, exist_ok=True)
    os.chmod(private, 0o700)
    os.chmod(private / "events", 0o700)
    asset_dir = webroot / "mpw-measure"
    if asset_dir.exists() and asset_dir.is_symlink():
        raise RuntimeError("ASSET_DIR_IS_SYMLINK")
    asset_dir.mkdir(mode=0o755, exist_ok=True)
    # Put collector and tracker in place before enabling them in HTML.
    files = [n for n in prepared if n.startswith("mpw-measure/")]
    files += [n for n in prepared if not n.startswith("mpw-measure/")]
    for name in files:
        dest = webroot / name
        original_mode = stat.S_IMODE(dest.stat().st_mode) if dest.exists() else 0o644
        atomic_replace(dest, prepared[name], original_mode)
        if sha(dest.read_bytes()) != sha(prepared[name]):
            raise RuntimeError("INSTALL_HASH_MISMATCH:" + name)
    return {
        "status": "installed",
        "pages_instrumented": len(PAGES),
        "assets_installed": len(ASSETS),
        "private_events": str(private / "events"),
        "backup_dir": str(backup),
        "sha256": {name: sha(prepared[name]) for name in prepared},
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--apply", action="store_true", help="Actually install after secure backup")
    p.add_argument("--webroot", type=Path, default=WEBROOT)
    p.add_argument("--source", type=Path, default=Path(__file__).resolve().parent)
    p.add_argument("--backups", type=Path, default=BACKUPS)
    p.add_argument("--private", type=Path, default=PRIVATE)
    args = p.parse_args()
    if args.webroot.resolve() != WEBROOT or args.private.resolve() != PRIVATE:
        p.error("Installation scope is pinned to the designated MojPlayWin host")
    if args.apply:
        print(json.dumps(apply(args.webroot, args.source, args.backups, args.private), indent=2))
    else:
        files = inspect(args.webroot, args.source)
        print(json.dumps({"status": "preflight_passed", "page_count": len(PAGES),
                          "asset_count": len(ASSETS),
                          "no_live_mutation": True, "paths": list(files)}, indent=2))


if __name__ == "__main__":
    main()
