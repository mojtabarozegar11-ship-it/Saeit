#!/usr/bin/env python3
"""Fail-closed Moj Prop catalog and two sample pages release.

Source changes never directly modify the live site. A separately approved
manual workflow must install the secured backend before this static release.
All existing files are compared with the source-controlled approved baseline.
"""
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
FILES = (
    Path("index.html"),
    Path("samples/prop-blueprint/index.html"),
    Path("samples/gold-market-brief/index.html"),
    Path("samples/educational-signal/index.html"),
    Path("samples/commercial-gate-audit/index.html"),
    Path("catalog/index.html"),
)
BASELINE_CATALOG = Path("baselines/catalog-index-v4.html")
BASELINE_HOME = Path("baselines/index-v4.html")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_id(value: str) -> str:
    if not re.fullmatch(r"[0-9]{1,20}", value):
        raise ValueError("Invalid deployment run ID")
    return value


def assert_file(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("Expected a regular file: " + str(path))


def assert_safe_destination(path: Path) -> None:
    if ROUTE.is_symlink() or not ROUTE.is_dir():
        raise RuntimeError("Moj Prop route is missing or is a symlink")
    current = path.parent
    while current != ROUTE.parent:
        if current.is_symlink():
            raise RuntimeError("Symlink parent refused: " + str(current))
        if current == ROUTE:
            return
        current = current.parent
    raise RuntimeError("Destination is outside the Moj Prop route")


def atomic_write(path: Path, data: bytes, mode: int = 0o644) -> None:
    assert_safe_destination(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    fd, name = tempfile.mkstemp(prefix="." + path.name + ".mojprop-", dir=str(path.parent))
    temp = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp, mode)
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def source_root(run_id: str) -> Path:
    path = HOME / (".mojplaywin-moj-prop-catalog-" + safe_id(run_id)) / "templates/moj-prop-v4"
    if path.is_symlink() or not path.is_dir():
        raise RuntimeError("Invalid staged Moj Prop source")
    for relative in FILES + (BASELINE_CATALOG, BASELINE_HOME):
        assert_file(path / relative)
    html = {str(relative): (path / relative).read_text("utf-8") for relative in FILES}
    if ("const endpoint='/moj-prop-intake/';" not in html["index.html"]
            or '<option value="week">This week</option>' not in html["index.html"]
            or "href=\"/moj-prop/catalog/\"" not in html["index.html"]):
        raise RuntimeError("Staged homepage lacks working intake contract")
    catalog = html["catalog/index.html"]
    if ("/moj-prop/samples/prop-blueprint/" not in catalog
            or "/moj-prop/samples/gold-market-brief/" not in catalog
            or "/moj-prop/samples/educational-signal/" not in catalog
            or "/moj-prop/samples/commercial-gate-audit/" not in catalog):
        raise RuntimeError("Staged catalog sample links missing")
    for sample in FILES[1:5]:
        doc = html[str(sample)]
        if "<title>" not in doc or "Sample" not in doc:
            raise RuntimeError("Staged commercial sample invalid: " + str(sample))
    return path


def validate_host() -> None:
    if pwd.getpwuid(os.getuid()).pw_name != "zomorod2":
        raise RuntimeError("Wrong cPanel account")
    if DOCROOT.is_symlink() or not DOCROOT.is_dir():
        raise RuntimeError("MojPlayWin document root invalid")
    for relative in ("passenger_wsgi.py", ".htaccess"):
        assert_file(DOCROOT / relative)


def plan(root: Path) -> list[dict]:
    old_catalog = (root / BASELINE_CATALOG).read_bytes()
    old_home = (root / BASELINE_HOME).read_bytes()
    marker = b"<!-- MOJ_PROP_CATALOG_RELEASE_V4 -->\n"
    old_home_without_marker = old_home.replace(marker, b"", 1)
    intended = []
    for relative in FILES:
        target = ROUTE / relative
        assert_safe_destination(target)
        exists = target.exists() or target.is_symlink()
        if exists:
            assert_file(target)
        before = target.read_bytes() if exists else None
        after = (root / relative).read_bytes()
        if relative == Path("index.html"):
            if not exists or before not in (after, old_home, old_home_without_marker):
                raise RuntimeError("Live home differs from approved baseline; refusing replacement")
        elif relative == Path("catalog/index.html") and exists:
            if before != after and before != old_catalog:
                raise RuntimeError("Live catalog differs from both approved baseline and release; refusing replacement")
        elif exists and before != after:
            raise RuntimeError("A sample page exists with unexpected content; refusing replacement")
        intended.append({
            "path": str(relative), "existed": exists,
            "before_sha": digest(before) if exists else None,
            "after_sha": digest(after), "changed": before != after,
            "mode": (target.stat().st_mode & 0o777) if exists else 0o644,
        })
    return intended


def verified_manifest(path: Path) -> dict:
    """Treat even a local backup manifest as untrusted rollback instructions."""
    if path.parent.is_symlink() or not path.parent.is_dir():
        raise RuntimeError("Symlinked or missing rollback directory")
    assert_file(path)
    value = json.loads(path.read_text("utf-8"))
    expected = [str(item) for item in FILES]
    if type(value) is not dict or type(value.get("files")) is not list:
        raise RuntimeError("Unrecognized Moj Prop rollback manifest")
    entries = value["files"]
    if len(entries) != len(expected) or [item.get("path") for item in entries if type(item) is dict] != expected:
        raise RuntimeError("Rollback manifest file list is incomplete or out of order")
    if value.get("rolled_back") not in (True, False):
        raise RuntimeError("Rollback status is invalid")
    if not isinstance(value.get("run_id"), str):
        raise RuntimeError("Missing rollback run ID")
    safe_id(value["run_id"])
    if not re.fullmatch(r"[0-9a-f]{40}", str(value.get("commit_sha", ""))):
        raise RuntimeError("Rollback commit identity is invalid")
    for item in entries:
        if type(item.get("existed")) is not bool or type(item.get("changed")) is not bool:
            raise RuntimeError("Invalid before/after backup flags")
        if type(item.get("mode")) is not int or not 0 <= item["mode"] <= 0o777:
            raise RuntimeError("Unsafe rollback file mode")
        before = item.get("before_sha")
        if (item["existed"] and not isinstance(before, str)) or (not item["existed"] and before is not None):
            raise RuntimeError("Invalid previous-file digest")
        if before is not None and not re.fullmatch(r"[0-9a-f]{64}", before):
            raise RuntimeError("Previous-file digest malformed")
        if not isinstance(item.get("after_sha"), str) or not re.fullmatch(r"[0-9a-f]{64}", item["after_sha"]):
            raise RuntimeError("Deployed-file digest malformed")
    return value


def restore(backup: Path, *, automated: bool = False) -> None:
    manifest = verified_manifest(backup / "manifest.json")
    if manifest.get("rolled_back") is True:
        print("MOJ_PROP_ALREADY_ROLLED_BACK")
        return
    # Check every changed file before modifying any, preventing rollback over
    # another operator's edits.
    for item in manifest["files"]:
        target = ROUTE / item["path"]
        assert_safe_destination(target)
        if not item["changed"]:
            continue
        assert_file(target)
        if digest(target.read_bytes()) != item["after_sha"]:
            raise RuntimeError("Refusing to roll back a subsequently modified file: " + item["path"])
    for item in reversed(manifest["files"]):
        if not item["changed"]:
            continue
        target = ROUTE / item["path"]
        if item["existed"]:
            previous = backup / "files" / item["path"]
            assert_file(previous)
            data = previous.read_bytes()
            if digest(data) != item["before_sha"]:
                raise RuntimeError("Backup checksum mismatch: " + item["path"])
            atomic_write(target, data, int(item["mode"]))
        else:
            target.unlink()
        if item["existed"] and digest(target.read_bytes()) != item["before_sha"]:
            raise RuntimeError("Rollback verification failed: " + item["path"])
    manifest["rolled_back"] = True
    (backup / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("MOJ_PROP_CATALOG_ROLLBACK_COMPLETE")


def deploy(run_id: str, commit: str) -> None:
    safe_id(run_id)
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Unverified release commit")
    validate_host()
    root = source_root(run_id)
    changes = plan(root)
    if not any(item["changed"] for item in changes):
        print("MOJ_PROP_SAMPLES_AND_CATALOG_ALREADY_LIVE")
        return
    backup = BACKUPS / ("moj-prop-catalog-" + run_id)
    if backup.exists() or backup.is_symlink():
        raise RuntimeError("Backup ID already used")
    backup.mkdir(parents=True, mode=0o700)
    manifest = {"run_id": run_id, "commit_sha": commit, "files": changes, "rolled_back": False}
    for item in changes:
        if item["existed"]:
            previous = ROUTE / item["path"]
            saved = backup / "files" / item["path"]
            saved.parent.mkdir(parents=True, exist_ok=True)
            saved.write_bytes(previous.read_bytes())
            os.chmod(saved, 0o600)
    (backup / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    applied = []
    try:
        for item in changes:
            if not item["changed"]:
                continue
            target = ROUTE / item["path"]
            # Double-check source and destination after backup before writes.
            if item["existed"] and digest(target.read_bytes()) != item["before_sha"]:
                raise RuntimeError("Live content changed after backup: " + item["path"])
            data = (root / item["path"]).read_bytes()
            if digest(data) != item["after_sha"]:
                raise RuntimeError("Staged content changed after validation")
            atomic_write(target, data, int(item["mode"]))
            applied.append(item)
            if digest(target.read_bytes()) != item["after_sha"]:
                raise RuntimeError("Post-install hash mismatch: " + item["path"])
    except Exception:
        # Roll back only files this run actually installed, not untouched files.
        for item in reversed(applied):
            target = ROUTE / item["path"]
            if not target.is_symlink() and target.is_file() and digest(target.read_bytes()) == item["after_sha"]:
                if item["existed"]:
                    atomic_write(target, (backup / "files" / item["path"]).read_bytes(), int(item["mode"]))
                else:
                    target.unlink()
        raise
    print("MOJ_PROP_CATALOG_SAMPLES_DEPLOYED commit=" + commit)
    print("MOJ_PROP_CATALOG_BACKUP=" + str(backup))


def main() -> None:
    if len(sys.argv) == 4 and sys.argv[1] == "deploy":
        deploy(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 3 and sys.argv[1] == "rollback":
        validate_host()
        restore(BACKUPS / ("moj-prop-catalog-" + safe_id(sys.argv[2])))
    else:
        raise SystemExit("Usage: catalog.py deploy RUN_ID SHA | rollback RUN_ID")


if __name__ == "__main__":
    main()
