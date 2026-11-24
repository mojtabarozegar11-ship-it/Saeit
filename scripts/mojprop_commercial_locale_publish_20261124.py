#!/usr/bin/env python3
"""Publish only existing Moj Prop locale HTML using the authorized host account.

Run on cPanel as the existing account owner, from the reviewed repository root:
python3 scripts/mojprop_commercial_locale_publish_20261124.py

No payment, Django, migration, worker, cron, sitemap, or other site changes.
"""
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
from html.parser import HTMLParser

from mojprop_commercial_locale_seo_20261124 import COPY, BASE, MARKER, transform

ROOT = Path("/home/zomorod2/mojplaywin.com/moj-prop/languages")
BACKUPS = Path("/home/zomorod2/.private_mojplaywin_main_agents")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class Links(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.links = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        if tag in ("a", "link", "script"):
            self.links.append((tag, tuple(attrs)))


def atomic(path, raw, mode):
    fd, name = tempfile.mkstemp(prefix=".mojprop-seo-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            os.fchmod(f.fileno(), mode)
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def publish():
    if ROOT.resolve() != ROOT or not ROOT.is_dir():
        raise RuntimeError("Unexpected locale directory")
    if BACKUPS.resolve() != BACKUPS or not BACKUPS.is_dir():
        raise RuntimeError("Existing private backup directory is unavailable")
    plan = {}
    for code in COPY:
        path = ROOT / code / "index.html"
        if path.resolve() != path or not path.is_file():
            raise RuntimeError("Unsafe or missing locale file: " + code)
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        if MARKER in text:
            # Only permit a complete prior release; mixed states require review.
            plan[code] = (path, raw, raw, stat.S_IMODE(path.stat().st_mode))
            continue
        updated = transform(text, code)
        before_links = Links(text).links
        after_links = Links(updated).links
        if sorted(before_links) != sorted(after_links):
            raise RuntimeError("Link or script attributes changed: " + code)
        plan[code] = (path, raw, updated.encode("utf-8"), stat.S_IMODE(path.stat().st_mode))
    unchanged = sum(before == after for _, before, after, _ in plan.values())
    if unchanged == len(plan):
        print("ALL_LOCALES_ALREADY_MARKED; verify public metadata")
        return
    if unchanged:
        raise RuntimeError("Mixed prior-release state; no files written")
    backup = Path(tempfile.mkdtemp(prefix="mojprop-commercial-seo-", dir=BACKUPS))
    receipt = {}
    for code, (path, before, after, mode) in plan.items():
        original = backup / (code + ".html")
        atomic(original, before, 0o600)
        if original.read_bytes() != before:
            raise RuntimeError("Backup readback mismatch: " + code)
        receipt[code] = {"before_sha256": digest(before), "after_sha256": digest(after), "mode": mode}
    atomic(backup / "manifest.json", json.dumps(receipt, indent=2).encode(), 0o600)
    written = []
    try:
        for code, (path, before, after, mode) in plan.items():
            if path.resolve() != path or path.read_bytes() != before:
                raise RuntimeError("Concurrent source change: " + code)
            atomic(path, after, mode)
            written.append(code)
            if path.read_bytes() != after:
                raise RuntimeError("Release readback mismatch: " + code)
    except BaseException:
        for code in reversed(written):
            path, before, after, mode = plan[code]
            if path.read_bytes() == after:
                atomic(path, before, mode)
            else:
                print("MANUAL_RESTORE_REQUIRED", code)
        raise
    print("LOCALE_FILES_PUBLISHED", len(written), "PRIVATE_BACKUP", backup.name)
    print("Verify public titles and links via HTTPS; disk readback alone is not Google indexing.")


if __name__ == "__main__":
    publish()
