#!/usr/bin/env python3
"""Guarded, reversible staging-only correction for the contact link and redirect."""

from __future__ import annotations

import hashlib
import json
import os
import pwd
import re
import stat
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen


HOME = Path("/home/zomorod2")
APP = HOME / "Saeit-staging"
WEB_CONF = HOME / "Saeit-staging-web/.htaccess"
BACKUPS = HOME / ".private/staging-contact-anchor-backups"
URLS = APP / "config/urls.py"
BASE = APP / "core/templates/base.html"
RESTART = APP / "tmp/restart.txt"
OLD_ROUTE = 'path("contact/", RedirectView.as_view(pattern_name="company", permanent=True), name="contact"),'
NEW_ROUTE = 'path("contact/", RedirectView.as_view(url="/company/#company-collaboration", permanent=False), name="contact"),'
OLD_LINK = '<a href="/contact/">تماس و همکاری</a>'
NEW_LINK = '<a href="/company/#company-collaboration">تماس و همکاری</a>'
FILES = ((URLS, OLD_ROUTE, NEW_ROUTE), (BASE, OLD_LINK, NEW_LINK))


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def guard() -> None:
    if pwd.getpwuid(os.geteuid()).pw_name != "zomorod2":
        raise RuntimeError("NOT_CPANEL_OWNER")
    if not WEB_CONF.is_file() or WEB_CONF.is_symlink() or APP.is_symlink() or not APP.is_dir():
        raise RuntimeError("STAGING_APP_LOCATION_UNSAFE")
    conf = WEB_CONF.read_text("utf-8", "strict")
    match = re.search(r"(?m)^PassengerAppRoot\s+([^\s]+)\s*$", conf)
    if not match or match.group(1).strip('"') not in ("$ACCOUNT_HOME/Saeit-staging", str(APP)):
        raise RuntimeError("STAGING_PASSENGER_ROOT_UNEXPECTED")
    if RESTART.parent.is_symlink() or not RESTART.is_file() or RESTART.is_symlink():
        raise RuntimeError("STAGING_RESTART_MARKER_UNSAFE")
    for file, _, _ in FILES:
        if not file.is_relative_to(APP) or file.is_symlink() or file.parent.is_symlink():
            raise RuntimeError("TARGET_OUT_OF_SCOPE")
        if not file.is_file() or file.stat().st_size > 130000:
            raise RuntimeError("TARGET_UNSAFE:" + file.name)
    if BACKUPS.parent.is_symlink() or not BACKUPS.parent.is_dir():
        raise RuntimeError("PRIVATE_BACKUP_PARENT_UNSAFE")


def prepare() -> list[tuple[Path, bytes, bytes, int]]:
    guard()
    prepared = []
    for path, old, new in FILES:
        before = path.read_bytes()
        source = before.decode("utf-8", "strict")
        if source.count(old) != 1 or new in source:
            raise RuntimeError("TARGET_DRIFT_OR_ALREADY_PATCHED:" + path.name)
        after = source.replace(old, new, 1).encode("utf-8")
        if after.replace(new.encode(), old.encode(), 1) != before:
            raise RuntimeError("PATCH_NOT_ISOLATED")
        prepared.append((path, before, after, stat.S_IMODE(path.stat().st_mode)))
    return prepared


def ident(run: str) -> Path:
    if not re.fullmatch(r"\d{9,20}", run):
        raise RuntimeError("INVALID_RUN_ID")
    return BACKUPS / ("run-" + run)


def atomic(path: Path, data: bytes, mode: int) -> None:
    fd, temporary = tempfile.mkstemp(prefix=".contact-anchor-", dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if path.is_symlink() or not path.is_file():
            raise RuntimeError("TARGET_CHANGED")
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def restart_staging() -> None:
    RESTART.touch(exist_ok=True)
    print("ONLY_STAGING_PASSENGER_RESTART_MARKER=1", flush=True)


def preview() -> None:
    pairs = prepare()
    print("CONTACT_ANCHOR_PREVIEW=" + json.dumps({
        "files": [str(item[0]) for item in pairs],
        "old_sha256": [digest(item[1]) for item in pairs],
        "new_sha256": [digest(item[2]) for item in pairs],
        "production_or_factory_write": False,
        "process_signals": 0,
    }), flush=True)


def publish(run: str) -> None:
    pairs = prepare()
    folder = ident(run)
    if folder.exists() or folder.is_symlink():
        raise RuntimeError("BACKUP_COLLISION")
    BACKUPS.mkdir(mode=0o700, exist_ok=True)
    folder.mkdir(mode=0o700)
    manifest = {"run": run, "files": []}
    for idx, (path, before, after, mode) in enumerate(pairs):
        backup = folder / ("original-" + str(idx) + ".bin")
        with backup.open("xb") as output:
            os.fchmod(output.fileno(), 0o600)
            output.write(before)
            output.flush()
            os.fsync(output.fileno())
        manifest["files"].append({
            "path": str(path), "old": digest(before), "new": digest(after),
            "mode": mode, "backup": backup.name,
        })
    with (folder / "manifest.json").open("x") as output:
        os.fchmod(output.fileno(), 0o600)
        json.dump(manifest, output)
        output.flush()
        os.fsync(output.fileno())
    if any(path.read_bytes() != before for path, before, _, _ in pairs):
        raise RuntimeError("CONCURRENT_EDIT_BEFORE_WRITE")
    try:
        for path, _, after, mode in pairs:
            atomic(path, after, mode)
        restart_staging()
        if any(path.read_bytes() != after for path, _, after, _ in pairs):
            raise RuntimeError("POST_WRITE_SHA_MISMATCH")
    except BaseException:
        restored = False
        for path, before, after, mode in pairs:
            if path.is_file() and path.read_bytes() == after:
                atomic(path, before, mode)
                restored = True
        if restored:
            restart_staging()
        raise
    print("CONTACT_ANCHOR_STAGING_PUBLISHED=" + json.dumps({
        "private_backup": str(folder), "files": len(pairs),
        "main_site_vps_factory_payments_changed": False,
    }), flush=True)


def rollback(run: str) -> None:
    guard()
    folder = ident(run)
    if folder.is_symlink() or not folder.is_dir():
        raise RuntimeError("PRIVATE_BACKUP_NOT_FOUND")
    manifest = json.loads((folder / "manifest.json").read_text("utf-8"))
    if manifest.get("run") != run or len(manifest.get("files", [])) != len(FILES):
        raise RuntimeError("BACKUP_MANIFEST_INVALID")
    restored = 0
    for row, (path, _, _) in zip(manifest["files"], FILES):
        if row.get("path") != str(path):
            raise RuntimeError("BACKUP_TARGET_MISMATCH")
        original = (folder / row["backup"]).read_bytes()
        if digest(original) != row["old"]:
            raise RuntimeError("BACKUP_CORRUPT")
        now = path.read_bytes()
        current = digest(now)
        if current not in (row["new"], row["old"]):
            raise RuntimeError("CONCURRENT_EDIT_BLOCKS_ROLLBACK")
        if current == row["new"]:
            atomic(path, original, int(row["mode"]))
            restored += 1
    if restored:
        restart_staging()
    print("STAGING_CONTACT_ROLLBACK_RESTORED=" + str(restored), flush=True)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def verify_origin(run: str) -> None:
    guard()
    folder = ident(run)
    manifest = json.loads((folder / "manifest.json").read_text("utf-8"))
    if any(digest(path.read_bytes()) != row["new"]
           for (path, _, _), row in zip(FILES, manifest["files"])):
        raise RuntimeError("ORIGIN_FILES_DIFFER_FROM_PUBLISHED")
    opener = build_opener(NoRedirect())
    for attempt in range(12):
        try:
            req = Request("https://staging.zomorodmelal.ir/contact/?contact_anchor="
                          + run + "-" + str(attempt),
                          headers={"Cache-Control": "no-cache, no-store"})
            try:
                response = opener.open(req, timeout=12)
                status, location = response.status, response.headers.get("Location")
                response.close()
            except HTTPError as error:
                status, location = error.code, error.headers.get("Location")
                error.close()
            with urlopen(Request("https://staging.zomorodmelal.ir/?contact_link="
                                 + run + "-" + str(attempt),
                                 headers={"Cache-Control": "no-cache, no-store"}), timeout=12) as page:
                html = page.read(220000).decode("utf-8", "replace")
                visible = (page.status == 200 and
                           "noindex" in page.headers.get("X-Robots-Tag", "").lower() and
                           NEW_LINK in html)
            if status == 302 and location == "/company/#company-collaboration" and visible:
                print("STAGING_CONTACT_ORIGIN_VERIFIED=1 STATUS=302 ANCHOR=1", flush=True)
                return
        except Exception as exc:
            print("ORIGIN_RETRY=" + type(exc).__name__, flush=True)
        time.sleep(5)
    raise RuntimeError("STAGING_CONTACT_ANCHOR_NOT_VISIBLE")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "preview":
        preview()
    elif len(sys.argv) == 3 and sys.argv[1] == "publish":
        publish(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == "rollback":
        rollback(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == "verify-origin":
        verify_origin(sys.argv[2])
    else:
        raise SystemExit("USAGE: preview | publish RUN_ID | rollback RUN_ID | verify-origin RUN_ID")
