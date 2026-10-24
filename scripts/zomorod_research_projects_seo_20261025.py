#!/usr/bin/env python3
"""Atomic, guarded SEO correction for the existing Zomorod research-projects page.

Only /research/projects/index.html and /sitemap.xml in the verified public_html
are eligible for changes. Preserves all other HTML and sitemap bytes, and stores
a private rollback manifest. No credentials or account integrations are touched.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from xml.etree import ElementTree as ET

HOME = Path.home()
ROOT = HOME / "public_html"
BACKUPS = HOME / ".backups" / "zm-research-projects-seo-20261025"
LOCK = HOME / ".locks" / "zm-research-projects-seo.lock"
FILES = ("research/projects/index.html", "sitemap.xml")
OLD = "https://zomorodmelal.ir/research/"
NEW = "https://zomorodmelal.ir/research/projects/"
TAG = re.compile(r"<link\b[^>]*>", re.I | re.S)
REL = re.compile(r"\brel\s*=\s*(['\"])canonical\1", re.I)
HREF = re.compile(r"(\bhref\s*=\s*['\"])([^'\"]+)(['\"])", re.I)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def path(rel: str) -> Path:
    p = ROOT / rel
    if not ROOT.is_dir() or ROOT.is_symlink():
        raise RuntimeError("DOCROOT_NOT_SAFE")
    for part in [ROOT, *list(p.parents)[:-1]]:
        if part.is_symlink():
            raise RuntimeError("SYMLINK_PARENT")
    if p.is_symlink() or not p.is_file():
        raise RuntimeError("MISSING_OR_SYMLINK: " + rel)
    if not str(p.resolve()).startswith(str(ROOT.resolve()) + os.sep):
        raise RuntimeError("OUTSIDE_DOCROOT")
    return p


def atomic_write(p: Path, data: bytes) -> None:
    fd, name = tempfile.mkstemp(prefix=".zm-seo-", dir=str(p.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(name, p.stat().st_mode & 0o777)
        os.replace(name, p)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def fix_page(original: bytes) -> bytes:
    s = original.decode("utf-8")
    if "شناسنامه" not in s or "research" not in s.lower():
        raise RuntimeError("UNEXPECTED_PROJECT_PAGE")
    matches = [m for m in TAG.finditer(s) if REL.search(m.group(0))]
    if len(matches) != 1:
        raise RuntimeError("CANONICAL_COUNT_NOT_ONE")
    m = matches[0]
    tag = m.group(0)
    href = HREF.search(tag)
    if not href or href.group(2) not in (OLD, NEW):
        raise RuntimeError("CANONICAL_UNEXPECTED")
    if href.group(2) == NEW:
        return original
    next_tag = tag[:href.start(2)] + NEW + tag[href.end(2):]
    next_html = s[:m.start()] + next_tag + s[m.end():]
    if next_html.count(NEW) < 1:
        raise RuntimeError("CANONICAL_PATCH_FAILED")
    return next_html.encode("utf-8")


def fix_sitemap(original: bytes) -> bytes:
    s = original.decode("utf-8")
    root = ET.fromstring(original)
    if not root.tag.endswith("urlset"):
        raise RuntimeError("NOT_SITEMAP")
    urls = [node.text for node in root.iter() if node.tag.endswith("loc")]
    if len(urls) != len(set(urls)):
        raise RuntimeError("EXISTING_DUPLICATE_SITEMAP_URLS")
    if NEW in urls:
        return original
    if "</urlset>" not in s:
        raise RuntimeError("SITEMAP_END_NOT_FOUND")
    addition = "  <url><loc>" + NEW + "</loc></url>\n"
    result = s.replace("</urlset>", addition + "</urlset>", 1).encode("utf-8")
    next_urls = [node.text for node in ET.fromstring(result).iter() if node.tag.endswith("loc")]
    if len(next_urls) != len(urls) + 1 or next_urls.count(NEW) != 1:
        raise RuntimeError("SITEMAP_PATCH_FAILED")
    return result


def run(action: str, run_id: str) -> None:
    if not re.fullmatch(r"[0-9]{6,20}", run_id):
        raise RuntimeError("INVALID_RUN_ID")
    LOCK.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    BACKUPS.mkdir(mode=0o700, parents=True, exist_ok=True)
    with LOCK.open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        backup = BACKUPS / run_id
        if action == "apply":
            if backup.exists():
                raise RuntimeError("RUN_BACKUP_ALREADY_EXISTS")
            original = {rel: path(rel).read_bytes() for rel in FILES}
            changed = {
                FILES[0]: fix_page(original[FILES[0]]),
                FILES[1]: fix_sitemap(original[FILES[1]]),
            }
            if all(original[k] == changed[k] for k in FILES):
                print("SEO_ALREADY_CORRECT_NO_CHANGE")
                return
            backup.mkdir(mode=0o700)
            for rel in FILES:
                (backup / rel.replace("/", "__")).write_bytes(original[rel])
            manifest = {
                "files": {rel: {"before": digest(original[rel]), "after": digest(changed[rel])} for rel in FILES},
                "state": "prepared",
            }
            (backup / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            try:
                for rel in FILES:
                    if path(rel).read_bytes() != original[rel]:
                        raise RuntimeError("CONCURRENT_FILE_CHANGE")
                    if original[rel] != changed[rel]:
                        atomic_write(path(rel), changed[rel])
                manifest["state"] = "installed"
                (backup / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
                print("RESEARCH_CANONICAL_AND_SITEMAP_INSTALLED")
                print("BACKUP=" + str(backup))
            except Exception:
                for rel in FILES:
                    current = path(rel).read_bytes()
                    if digest(current) == digest(changed[rel]) and original[rel] != changed[rel]:
                        atomic_write(path(rel), original[rel])
                raise
        elif action == "rollback":
            manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
            for rel in FILES:
                current = path(rel).read_bytes()
                expected = manifest["files"][rel]
                if digest(current) not in (expected["after"], expected["before"]):
                    raise RuntimeError("ROLLBACK_BLOCKED_CONCURRENT_CHANGE_" + rel)
            for rel in FILES:
                original = (backup / rel.replace("/", "__")).read_bytes()
                if digest(original) != manifest["files"][rel]["before"]:
                    raise RuntimeError("BACKUP_HASH_INVALID")
                if path(rel).read_bytes() != original:
                    atomic_write(path(rel), original)
            manifest["state"] = "rolled_back"
            (backup / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            print("RESEARCH_SEO_ROLLBACK_OK")
        else:
            raise RuntimeError("UNKNOWN_ACTION")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: script.py apply|rollback GITHUB_RUN_ID")
    run(sys.argv[1], sys.argv[2])
