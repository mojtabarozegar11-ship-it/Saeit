#!/usr/bin/env python3
"""Fix the staging search label's 9,999px horizontal overflow, with rollback."""

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
from urllib.request import Request, urlopen

HOME = Path("/home/zomorod2")
APP = HOME / "Saeit-staging"
CONF = HOME / "Saeit-staging-web/.htaccess"
TEMPLATE = APP / "core/templates/core/search.html"
RESTART = APP / "tmp/restart.txt"
BACKUPS = HOME / ".private/staging-search-label-backups"
OLD = '<label for="q" style="position:absolute;left:-9999px">عبارت جستجو</label>'
NEW = ('<label for="q" style="position:absolute;width:1px;height:1px;'
       'padding:0;overflow:hidden;clip:rect(0,0,0,0);'
       'clip-path:inset(50%);white-space:nowrap;border:0">عبارت جستجو</label>')


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def guard() -> None:
    if pwd.getpwuid(os.geteuid()).pw_name != "zomorod2":
        raise RuntimeError("WRONG_CPANEL_USER")
    if CONF.is_symlink() or not CONF.is_file() or APP.is_symlink() or not APP.is_dir():
        raise RuntimeError("STAGING_APP_ROOT_UNSAFE")
    config = CONF.read_text("utf-8", "strict")
    match = re.search(r"(?m)^PassengerAppRoot\s+([^\s]+)\s*$", config)
    if not match or match.group(1).strip('"') not in ("$ACCOUNT_HOME/Saeit-staging", str(APP)):
        raise RuntimeError("PASSENGER_ROOT_MISMATCH")
    if TEMPLATE.is_symlink() or TEMPLATE.parent.is_symlink() or not TEMPLATE.is_file():
        raise RuntimeError("STAGING_SEARCH_UNSAFE")
    if not TEMPLATE.is_relative_to(APP) or TEMPLATE.stat().st_size > 70000:
        raise RuntimeError("SEARCH_TEMPLATE_OUT_OF_SCOPE")
    if RESTART.is_symlink() or RESTART.parent.is_symlink() or not RESTART.is_file():
        raise RuntimeError("STAGING_RESTART_UNSAFE")
    if BACKUPS.parent.is_symlink() or not BACKUPS.parent.is_dir():
        raise RuntimeError("PRIVATE_BACKUP_PARENT_UNSAFE")


def prepare() -> tuple[bytes, bytes, int]:
    guard()
    original = TEMPLATE.read_bytes()
    source = original.decode("utf-8", "strict")
    if source.count(OLD) != 1 or NEW in source:
        raise RuntimeError("LABEL_ALREADY_FIXED_OR_TEMPLATE_CHANGED")
    if source.count('class="search-form"') != 1 or source.count('class="search-canonical-link"') != 1:
        raise RuntimeError("PREVIOUS_SEARCH_FIXES_MISSING")
    patched = source.replace(OLD, NEW, 1).encode("utf-8")
    if patched.replace(NEW.encode(), OLD.encode(), 1) != original:
        raise RuntimeError("PATCH_NOT_ISOLATED")
    return original, patched, stat.S_IMODE(TEMPLATE.stat().st_mode)


def destination(run: str) -> Path:
    if not re.fullmatch(r"\d{9,20}", run):
        raise RuntimeError("INVALID_RUN_ID")
    return BACKUPS / ("run-" + run)


def atomic(data: bytes, mode: int) -> None:
    fd, temp = tempfile.mkstemp(prefix=".search-label-", dir=TEMPLATE.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if TEMPLATE.is_symlink() or not TEMPLATE.is_file():
            raise RuntimeError("TARGET_CHANGED")
        os.replace(temp, TEMPLATE)
    finally:
        Path(temp).unlink(missing_ok=True)


def restart() -> None:
    RESTART.touch(exist_ok=True)
    print("STAGING_PASSENGER_RESTART_MARKER_ONLY=1", flush=True)


def preview() -> None:
    original, patched, _ = prepare()
    print("SEARCH_SR_LABEL_PREVIEW=" + json.dumps({
        "old_sha": digest(original), "new_sha": digest(patched),
        "files": 1, "outside_staging_writes": False,
    }), flush=True)


def publish(run: str) -> None:
    original, patched, mode = prepare()
    folder = destination(run)
    if folder.exists() or folder.is_symlink():
        raise RuntimeError("BACKUP_COLLISION")
    BACKUPS.mkdir(mode=0o700, exist_ok=True)
    folder.mkdir(mode=0o700)
    with (folder / "original.html").open("xb") as backup:
        os.fchmod(backup.fileno(), 0o600)
        backup.write(original)
        backup.flush()
        os.fsync(backup.fileno())
    with (folder / "manifest.json").open("x") as manifest:
        os.fchmod(manifest.fileno(), 0o600)
        json.dump({"run": run, "old": digest(original), "new": digest(patched), "mode": mode}, manifest)
        manifest.flush()
        os.fsync(manifest.fileno())
    if TEMPLATE.read_bytes() != original:
        raise RuntimeError("CONCURRENT_TEMPLATE_EDIT")
    try:
        atomic(patched, mode)
        restart()
        if TEMPLATE.read_bytes() != patched:
            raise RuntimeError("PUBLISH_SHA_MISMATCH")
    except BaseException:
        if TEMPLATE.is_file() and TEMPLATE.read_bytes() == patched:
            atomic(original, mode)
            restart()
        raise
    print("SEARCH_SR_LABEL_PUBLISHED=" + json.dumps({
        "private_backup": str(folder), "files_changed": 1,
        "factory_main_store_changed": False,
    }), flush=True)


def rollback(run: str) -> None:
    guard()
    folder = destination(run)
    if folder.is_symlink() or not folder.is_dir():
        raise RuntimeError("BACKUP_MISSING")
    meta = json.loads((folder / "manifest.json").read_text("utf-8"))
    original = (folder / "original.html").read_bytes()
    if meta["run"] != run or digest(original) != meta["old"]:
        raise RuntimeError("BACKUP_INTEGRITY_FAILED")
    current = digest(TEMPLATE.read_bytes())
    if current not in (meta["old"], meta["new"]):
        raise RuntimeError("CONCURRENT_EDIT_BLOCKS_ROLLBACK")
    if current == meta["new"]:
        atomic(original, int(meta["mode"]))
        restart()
    print("SEARCH_SR_LABEL_ROLLBACK_DONE=1", flush=True)


def verify_origin(run: str) -> None:
    guard()
    meta = json.loads((destination(run) / "manifest.json").read_text("utf-8"))
    if digest(TEMPLATE.read_bytes()) != meta["new"]:
        raise RuntimeError("PUBLISHED_TEMPLATE_NOT_PRESENT")
    for attempt in range(12):
        try:
            req = Request("https://staging.zomorodmelal.ir/search/?q=%DA%AF%D9%86%D8%AF%D9%85&srlabel="
                          + run + "-" + str(attempt), headers={"Cache-Control": "no-cache, no-store"})
            with urlopen(req, timeout=12) as response:
                body = response.read(250000).decode("utf-8", "replace")
                if (response.status == 200 and
                    "noindex" in response.headers.get("X-Robots-Tag", "").lower() and
                    NEW in body and OLD not in body and
                    'class="search-form"' in body and
                    'class="search-canonical-link"' in body and
                    "نتیجه برای «گندم»" in body):
                    print("SEARCH_SR_LABEL_ORIGIN_VERIFIED=1", flush=True)
                    return
        except Exception as exc:
            print("VERIFY_RETRY=" + type(exc).__name__, flush=True)
        time.sleep(5)
    raise RuntimeError("SEARCH_SR_LABEL_NOT_VISIBLE")


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
