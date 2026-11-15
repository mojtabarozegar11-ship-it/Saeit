#!/usr/bin/env python3
"""Atomically update only the live Moj Prop index and commercial catalog."""
from __future__ import annotations

import hashlib
import json
import os
import pwd
import re
import sys
import tempfile
from pathlib import Path

HOME = Path("/home/zomorod2")
DOCROOT = HOME / "mojplaywin.com"
ROUTE = DOCROOT / "moj-prop"
BACKUPS = HOME / ".mojplaywin-backups"
FILES = (Path("index.html"), Path("catalog/index.html"))


def safe_id(value: str) -> str:
    if not re.fullmatch(r"[0-9]{1,20}", value):
        raise ValueError("Invalid deployment run ID")
    return value


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def atomic_write(path: Path, content: bytes, mode: int = 0o644) -> None:
    path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb", dir=path.parent, prefix=f".{path.name}.moj-prop-update-", delete=False
    ) as stream:
        temporary = Path(stream.name)
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(temporary, mode)
    os.replace(temporary, path)


def staged_root(run_id: str) -> Path:
    root = HOME / f".mojplaywin-moj-prop-catalog-{run_id}" / "templates" / "moj-prop-v4"
    if root.is_symlink() or not root.is_dir():
        raise RuntimeError("Moj Prop catalog staged directory is missing or unsafe")
    for relative in FILES:
        source = root / relative
        if source.is_symlink() or not source.is_file():
            raise RuntimeError(f"Missing or unsafe staged file: {relative}")
    index = (root / "index.html").read_text(encoding="utf-8")
    catalog = (root / "catalog/index.html").read_text(encoding="utf-8")
    for required in ('<title>Moj Prop', 'href="/moj-prop/catalog/"', 'See service prices', 'mojtaba.bot.ai'):
        if required not in index:
            raise RuntimeError(f"Moj Prop index validation failed: {required}")
    for required in ('<title>Moj Prop Catalog', 'From US$149', 'From US$249'):
        if required not in catalog:
            raise RuntimeError(f"Moj Prop catalog validation failed: {required}")
    return root


def deploy(run_id: str, commit_sha: str) -> None:
    run_id = safe_id(run_id)
    if not re.fullmatch(r"[0-9a-f]{40}", commit_sha):
        raise ValueError("Invalid source commit SHA")
    if pwd.getpwuid(os.getuid()).pw_name != "zomorod2":
        raise RuntimeError("Unexpected cPanel account")
    if DOCROOT.is_symlink() or not DOCROOT.is_dir():
        raise RuntimeError("MojPlayWin document root is missing or redirected")
    for name in ("passenger_wsgi.py", ".htaccess"):
        target = DOCROOT / name
        if target.is_symlink() or not target.is_file():
            raise RuntimeError(f"MojPlayWin root file is missing or unsafe: {name}")
    if ROUTE.is_symlink() or not ROUTE.is_dir():
        raise RuntimeError("Existing Moj Prop route is missing or unsafe")
    old_index = ROUTE / "index.html"
    catalog = ROUTE / "catalog/index.html"
    if old_index.is_symlink() or not old_index.is_file():
        raise RuntimeError("Existing Moj Prop index is missing or unsafe")
    previous = old_index.read_bytes()
    if '<title>Moj Prop | Risk-first prop trading and market intelligence</title>' not in previous.decode("utf-8"):
        raise RuntimeError("Existing Moj Prop index identity changed; update refused")
    source = staged_root(run_id)
    new_index = (source / "index.html").read_bytes()
    new_catalog = (source / "catalog/index.html").read_bytes()
    if catalog.exists() or catalog.is_symlink():
        if catalog.is_symlink() or not catalog.is_file():
            raise RuntimeError("Moj Prop catalog exists but is unsafe")
        current_catalog = catalog.read_bytes()
        marker = b"<!-- MOJ_PROP_CATALOG_RELEASE_V4 -->\n"
        index_matches = previous == new_index or previous == new_index.replace(marker, b"", 1)
        if index_matches and current_catalog == new_catalog:
            print("MOJ_PROP_CATALOG_ALREADY_LIVE")
            print("MOJ_PROP_CATALOG_ROUTE=https://mojplaywin.com/moj-prop/catalog/")
            return
        raise RuntimeError("Moj Prop catalog exists but differs from the approved payload; refusing to replace it")
    backup = BACKUPS / f"moj-prop-catalog-{run_id}"
    if backup.exists() or backup.is_symlink():
        raise RuntimeError("Moj Prop catalog backup already exists")
    backup.mkdir(mode=0o700, parents=True)
    manifest = {
        "run_id": run_id,
        "commit_sha": commit_sha,
        "route": "/moj-prop/",
        "index_before": digest(previous),
        "index_after": digest(new_index),
        "catalog_after": digest(new_catalog),
        "catalog_created": True,
        "root_files_modified": False,
    }
    (backup / "index.before").write_bytes(previous)
    (backup / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    changed = False
    try:
        atomic_write(old_index, new_index)
        atomic_write(catalog, new_catalog)
        changed = True
        if digest(old_index.read_bytes()) != manifest["index_after"]:
            raise RuntimeError("Moj Prop index verification failed")
        if digest(catalog.read_bytes()) != manifest["catalog_after"]:
            raise RuntimeError("Moj Prop catalog verification failed")
    except Exception:
        if changed and catalog.is_file() and not catalog.is_symlink():
            catalog.unlink()
        if digest(old_index.read_bytes()) == manifest["index_after"]:
            atomic_write(old_index, previous)
        raise
    print(f"MOJ_PROP_CATALOG_UPDATED commit={commit_sha}")
    print("MOJ_PROP_CATALOG_ROUTE=https://mojplaywin.com/moj-prop/catalog/")
    print(f"MOJ_PROP_CATALOG_BACKUP={backup}")


def rollback(run_id: str) -> None:
    run_id = safe_id(run_id)
    backup = BACKUPS / f"moj-prop-catalog-{run_id}"
    manifest_path = backup / "manifest.json"
    previous_path = backup / "index.before"
    if not manifest_path.is_file() or not previous_path.is_file():
        raise RuntimeError("Moj Prop catalog rollback backup is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("catalog_created") is not True:
        raise RuntimeError("Rollback manifest is not a Moj Prop catalog update")
    index = ROUTE / "index.html"
    catalog = ROUTE / "catalog/index.html"
    if index.is_symlink() or catalog.is_symlink() or not index.is_file() or not catalog.is_file():
        raise RuntimeError("Moj Prop live files are missing or unsafe")
    if digest(index.read_bytes()) != manifest["index_after"] or digest(catalog.read_bytes()) != manifest["catalog_after"]:
        raise RuntimeError("Moj Prop live files changed; refusing rollback")
    previous = previous_path.read_bytes()
    if digest(previous) != manifest["index_before"]:
        raise RuntimeError("Moj Prop backup checksum mismatch")
    catalog.unlink()
    atomic_write(index, previous)
    if digest(index.read_bytes()) != manifest["index_before"] or catalog.exists():
        raise RuntimeError("Moj Prop catalog rollback verification failed")
    manifest["rolled_back"] = True
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("MOJ_PROP_CATALOG_ROLLBACK_COMPLETE")


def main() -> None:
    if len(sys.argv) == 4 and sys.argv[1] == "deploy":
        deploy(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 3 and sys.argv[1] == "rollback":
        rollback(sys.argv[2])
    else:
        raise SystemExit("Usage: update_mojplaywin_moj_prop_catalog.py deploy RUN_ID COMMIT_SHA | rollback RUN_ID")


if __name__ == "__main__":
    main()
