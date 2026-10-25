#!/usr/bin/env python3
"""Safely add already-live, canonical, indexable free resources to two public sitemaps.

Changes ONLY the known MojPlayWin PHP sitemap source or Zomorod Melal XML sitemap.
No account, product, payment, application, or page template is touched.
Fail closed on path drift; hash-pinned backups and guarded rollback.
"""
from __future__ import annotations
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET

HOME = Path("/home/zomorod2")
MPW_ROOT = HOME / "mojplaywin.com"
ZM_ROOT = HOME / "public_html"
MPW_PHP = MPW_ROOT / "design-preview-20261017/_mpw_sitemap_three_indexable_20261017.php"
ZM_XML = ZM_ROOT / "sitemap.xml"
BACKUP_ROOT = HOME / ".backups/free-resources-sitemap-20261025"
LOCK_ROOT = HOME / ".locks"
MPW_SIGNATURE = "// 2026-10-25: indexable free-tool and evergreen learning hubs (18 URL two-site release)"
MPW_ANCHOR = "// 2026-10-25: verified canonical MPW learning resources, isolated sitemap registration"

MPW_PATHS = (
    "/mpw-free-tools/20261025/",
    "/mpw-free-tools/20261025/chess-calendar/",
    "/mpw-free-tools/20261025/taniya-storytime/",
    "/mpw-free-tools/20261025/atelier-seo/",
    "/mpw-free-tools/20261025/atelier-contrast/",
    "/mpw-free-tools/20261025/browser-game-qa/",
    "/mpw-free-tools/20261025/research-evidence/",
    "/mpw-learning/20261025/",
    "/mpw-learning/20261025/chess-baseline/",
    "/mpw-learning/20261025/family-storytime/",
    "/mpw-learning/20261025/website-client-brief/",
    "/mpw-learning/20261025/research-methods/",
)
ZM_PATHS = (
    "/agriculture/free-tools/20261025/",
    "/agriculture/free-tools/20261025/farm-break-even/",
    "/agriculture/free-tools/20261025/import-landed-cost/",
    "/resources/20261025/",
    "/resources/20261025/trade-rfq/",
    "/resources/20261025/farm-risk/",
)
ZM_URLS = tuple("https://zomorodmelal.ir" + p for p in ZM_PATHS)


def digest(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def regular_within(root: Path, path: Path) -> None:
    if root.is_symlink() or not root.is_dir():
        raise RuntimeError("UNSAFE_ROOT")
    if not path.is_relative_to(root):
        raise RuntimeError("OUTSIDE_ROOT")
    current = path
    while current != root:
        if current.is_symlink():
            raise RuntimeError("SYMLINK_PATH:" + str(current))
        current = current.parent
    if not path.is_file():
        raise RuntimeError("MISSING_FILE:" + str(path))


def guarded_paths(site: str) -> tuple[Path, Path]:
    if site == "mpw":
        root, target, paths = MPW_ROOT, MPW_PHP, MPW_PATHS
        regular_within(root, root / ".htaccess")
    elif site == "zm":
        root, target, paths = ZM_ROOT, ZM_XML, ZM_PATHS
    else:
        raise RuntimeError("INVALID_SITE")
    regular_within(root, target)
    for path in paths:
        regular_within(root, root / path.lstrip("/") / "index.html")
    return root, target


def patch_mpw(before: bytes) -> bytes:
    source = before.decode("utf-8")
    if source.count(MPW_SIGNATURE) == 1:
        print("MPW_FREE_RESOURCES_ALREADY_REGISTERED")
        return before
    if source.count(MPW_ANCHOR) != 1 or MPW_SIGNATURE in source:
        raise RuntimeError("MPW_ANCHOR_DRIFT")
    entries = ",".join("'" + path + "'" for path in MPW_PATHS)
    addition = MPW_SIGNATURE + "\n$paths = array_merge($paths, [" + entries + "]);"
    after = source.replace(MPW_ANCHOR, MPW_ANCHOR + "\n" + addition, 1)
    if after.replace(MPW_ANCHOR + "\n" + addition, MPW_ANCHOR, 1) != source:
        raise RuntimeError("MPW_PATCH_NOT_EXACT")
    return after.encode("utf-8")


def patch_zm(before: bytes) -> bytes:
    tree = ET.fromstring(before)
    if not tree.tag.endswith("urlset"):
        raise RuntimeError("ZM_INVALID_XML_ROOT")
    locations = [n.text for n in tree.iter() if n.tag.endswith("loc")]
    if len(locations) != len(set(locations)):
        raise RuntimeError("ZM_PREEXISTING_DUPLICATE_URL")
    missing = [url for url in ZM_URLS if url not in locations]
    if not missing:
        print("ZM_FREE_RESOURCES_ALREADY_REGISTERED")
        return before
    source = before.decode("utf-8")
    if source.count("</urlset>") != 1:
        raise RuntimeError("ZM_XML_ANCHOR_DRIFT")
    addition = "".join("  <url><loc>" + url + "</loc></url>\n" for url in missing)
    after = source.replace("</urlset>", addition + "</urlset>", 1).encode("utf-8")
    locations_after = [n.text for n in ET.fromstring(after).iter() if n.tag.endswith("loc")]
    if len(locations_after) != len(locations) + len(missing):
        raise RuntimeError("ZM_XML_COUNT_INVALID")
    if any(locations_after.count(url) != 1 for url in ZM_URLS):
        raise RuntimeError("ZM_XML_NEW_URL_INVALID")
    return after


def php_lint(data: bytes, parent: Path) -> None:
    fd, tmp = tempfile.mkstemp(prefix=".free-resources-php-lint-", suffix=".php", dir=str(parent))
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(data)
        result = subprocess.run(["php", "-l", tmp], text=True, capture_output=True, timeout=20)
        if result.returncode:
            raise RuntimeError("PHP_LINT_FAILED:" + result.stderr[-200:])
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def atomic_write(target: Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(prefix=".free-resources-sitemap-", dir=str(target.parent))
    try:
        os.fchmod(fd, target.stat().st_mode & 0o777)
        with os.fdopen(fd, "wb") as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def apply(site: str, run: str, target: Path) -> None:
    before = target.read_bytes()
    after = patch_mpw(before) if site == "mpw" else patch_zm(before)
    if after == before:
        return
    if site == "mpw":
        php_lint(after, target.parent)
    folder = BACKUP_ROOT / (site + "-" + run)
    if folder.exists() or folder.is_symlink():
        raise RuntimeError("BACKUP_COLLISION")
    folder.mkdir(parents=True, mode=0o700)
    (folder / "before.bin").write_bytes(before)
    (folder / "manifest.json").write_text(
        json.dumps({"before": digest(before), "after": digest(after), "site": site}),
        encoding="utf-8",
    )
    if target.read_bytes() != before:
        raise RuntimeError("CONCURRENT_SITEMAP_EDIT")
    atomic_write(target, after)
    if digest(target.read_bytes()) != digest(after):
        raise RuntimeError("POSTWRITE_HASH_MISMATCH")
    print("FREE_RESOURCES_SITEMAP_PATCH_APPLIED", site, len(MPW_PATHS if site == "mpw" else ZM_PATHS))


def rollback(site: str, run: str, target: Path) -> None:
    folder = BACKUP_ROOT / (site + "-" + run)
    if not folder.is_dir() or folder.is_symlink():
        print("NO_OWN_PATCH_TO_ROLLBACK", site)
        return
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    before = (folder / "before.bin").read_bytes()
    if manifest["site"] != site or digest(before) != manifest["before"]:
        raise RuntimeError("BACKUP_MANIFEST_INVALID")
    current = target.read_bytes()
    if digest(current) == manifest["before"]:
        print("ALREADY_ROLLED_BACK", site)
        return
    if digest(current) != manifest["after"]:
        raise RuntimeError("CONCURRENT_CHANGE_ROLLBACK_REFUSED")
    atomic_write(target, before)
    print("FREE_RESOURCES_SITEMAP_ROLLBACK_OK", site)


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("usage: apply|rollback mpw|zm numeric_run_id")
    action, site, run = sys.argv[1:]
    if action not in ("apply", "rollback") or site not in ("mpw", "zm") or not re.fullmatch(r"[0-9]{6,20}", run):
        raise SystemExit("INVALID_ARGUMENTS")
    LOCK_ROOT.mkdir(mode=0o700, exist_ok=True)
    BACKUP_ROOT.mkdir(mode=0o700, exist_ok=True)
    with (LOCK_ROOT / ("free-resources-sitemap-" + site + ".lock")).open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        _, target = guarded_paths(site)
        (apply if action == "apply" else rollback)(site, run, target)


if __name__ == "__main__":
    main()
