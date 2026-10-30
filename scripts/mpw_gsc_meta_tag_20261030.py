#!/usr/bin/env python3
"""One-HTML-head-only Google Search Console verification for the MPW root.

A scoped, reversible change. Does not touch DNS, .htaccess, app routes, or child sites.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import sys
import tempfile

HOME = Path("/home/zomorod2")
DOCROOT = HOME / "mojplaywin.com"
TARGET = DOCROOT / "design-preview-20261017" / "production-home-20261017.html"
BACKUPS = HOME / ".mojplaywin-backups" / "gsc-meta-20261030"
TOKEN = "Ohs-EoudyKpuUQwxEZogMAPkJ9QhQeMKvaF-yXFXwCg"
META = f'<meta name="google-site-verification" content="{TOKEN}" />'.encode()
TITLE = b"<title>Moj Play Win | Games, AI, Research & Digital Products</title>"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def patch(content: bytes) -> bytes:
    if META in content:
        if content.count(META) != 1:
            raise ValueError("Duplicate matching verification tag")
        return content
    if b"google-site-verification" in content.lower():
        raise ValueError("Foreign Google verification tag already exists; refuse overwrite")
    if TITLE not in content:
        raise ValueError("Active homepage fingerprint not recognized")
    starts = list(re.finditer(rb"<head(?:\s[^>]*)?>", content, flags=re.I))
    ends = list(re.finditer(rb"</head\s*>", content, flags=re.I))
    if len(starts) != 1 or len(ends) != 1 or starts[0].end() >= ends[0].start():
        raise ValueError("Unrecognized HTML head")
    if content.count(b"<body") != 1:
        raise ValueError("Unrecognized HTML body")
    insertion = b"\n  " + META
    return content[: starts[0].end()] + insertion + content[starts[0].end() :]


def guard():
    if pwd.getpwuid(os.getuid()).pw_name != "zomorod2":
        raise RuntimeError("Wrong cPanel identity")
    for path in (HOME, DOCROOT, TARGET.parent, TARGET, BACKUPS.parent, BACKUPS):
        if path.is_symlink():
            raise RuntimeError("Symlink path rejected")
    if not DOCROOT.is_dir() or not TARGET.is_file():
        raise RuntimeError("Expected exact document-root source file missing")
    if not TARGET.resolve().is_relative_to(DOCROOT.resolve()):
        raise RuntimeError("Target outside exact document root")
    rewrite = DOCROOT / ".htaccess"
    if rewrite.is_symlink() or not rewrite.is_file():
        raise RuntimeError("Active root rewrite missing or symlink")
    rules = rewrite.read_text(encoding="utf-8", errors="replace")
    if "RewriteRule ^.*$ /design-preview-20261017/production-home-20261017.html [END,QSD]" not in rules:
        raise RuntimeError("Active root homepage routing changed; refuse patch")


def atomic(path: Path, data: bytes, mode: int):
    fd, name = tempfile.mkstemp(prefix=".gsc-verify-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def location(run_id: str) -> Path:
    if not re.fullmatch(r"[0-9]{1,20}", run_id):
        raise ValueError("Unsafe run id")
    return BACKUPS / run_id


def install(run_id: str):
    guard()
    previous = TARGET.read_bytes()
    proposed = patch(previous)
    if proposed == previous:
        print("MPW_GSC_META=ALREADY_PRESENT")
        return
    backup_dir = location(run_id)
    if backup_dir.exists() or backup_dir.is_symlink():
        raise RuntimeError("Backup run already exists")
    backup_dir.mkdir(parents=True, mode=0o700)
    os.chmod(backup_dir, 0o700)
    mode = TARGET.stat().st_mode & 0o777
    (backup_dir / "original.html").write_bytes(previous)
    os.chmod(backup_dir / "original.html", 0o600)
    manifest = {"before": sha(previous), "after": sha(proposed), "mode": mode}
    (backup_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    os.chmod(backup_dir / "manifest.json", 0o600)
    if sha((backup_dir / "original.html").read_bytes()) != manifest["before"]:
        raise RuntimeError("Backup verification failed")
    atomic(TARGET, proposed, mode)
    if TARGET.read_bytes() != proposed:
        raise RuntimeError("Post-write bytes mismatch")
    print("MPW_GSC_META=INSTALLED")


def rollback(run_id: str):
    guard()
    backup_dir = location(run_id)
    if not backup_dir.is_dir() or backup_dir.is_symlink():
        print("MPW_GSC_ROLLBACK=NOT_REQUIRED")
        return
    source = backup_dir / "original.html"
    manifest_file = backup_dir / "manifest.json"
    if source.is_symlink() or manifest_file.is_symlink():
        raise RuntimeError("Unsafe backup")
    manifest = json.loads(manifest_file.read_text())
    original = source.read_bytes()
    if sha(original) != manifest["before"]:
        raise RuntimeError("Backup changed; no rollback")
    live = TARGET.read_bytes()
    if sha(live) == manifest["before"]:
        print("MPW_GSC_ROLLBACK=ALREADY_ORIGINAL")
        return
    if sha(live) != manifest["after"]:
        raise RuntimeError("Unknown intervening edit; refuse rollback")
    atomic(TARGET, original, manifest["mode"])
    if TARGET.read_bytes() != original:
        raise RuntimeError("Rollback checksum mismatch")
    print("MPW_GSC_ROLLBACK=RESTORED")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("install", "rollback"):
        raise SystemExit("Usage: script.py install|rollback RUN_ID")
    {"install": install, "rollback": rollback}[sys.argv[1]](sys.argv[2])
