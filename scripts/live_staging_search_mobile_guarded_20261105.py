#!/usr/bin/env python3
"""One-file, guarded, reversible staging search-form mobile layout correction."""

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
TARGET = APP / "core/templates/core/search.html"
RESTART = APP / "tmp/restart.txt"
BACKUPS = HOME / ".private/staging-search-mobile-backups"
OLD_FORM = '<form method="get" role="search" style="display:flex;gap:10px;max-width:900px;margin:30px 0">'
NEW_FORM = '<form class="search-form" method="get" role="search" style="display:flex;gap:10px;max-width:900px;margin:30px 0">'
OLD_INPUT = 'style="flex:1;padding:18px;border:1px solid #c9c0b1;font-size:16px"'
NEW_INPUT = 'style="flex:1;min-width:0;padding:18px;border:1px solid #c9c0b1;font-size:16px"'


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def guard() -> None:
    if pwd.getpwuid(os.geteuid()).pw_name != "zomorod2":
        raise RuntimeError("NOT_CPANEL_OWNER")
    if CONF.is_symlink() or not CONF.is_file() or APP.is_symlink() or not APP.is_dir():
        raise RuntimeError("STAGING_APP_ROOT_UNSAFE")
    cfg = CONF.read_text("utf-8", "strict")
    match = re.search(r"(?m)^PassengerAppRoot\s+([^\s]+)\s*$", cfg)
    if not match or match.group(1).strip('"') not in ("$ACCOUNT_HOME/Saeit-staging", str(APP)):
        raise RuntimeError("PASSENGER_ROOT_MISMATCH")
    if TARGET.is_symlink() or TARGET.parent.is_symlink() or not TARGET.is_file():
        raise RuntimeError("SEARCH_TEMPLATE_UNSAFE")
    if TARGET.stat().st_size > 70000 or not TARGET.is_relative_to(APP):
        raise RuntimeError("SEARCH_TEMPLATE_OUT_OF_SCOPE")
    if RESTART.is_symlink() or not RESTART.is_file() or RESTART.parent.is_symlink():
        raise RuntimeError("RESTART_MARKER_UNSAFE")
    if BACKUPS.parent.is_symlink() or not BACKUPS.parent.is_dir():
        raise RuntimeError("PRIVATE_BACKUP_PARENT_UNSAFE")


def prepared() -> tuple[bytes, bytes, int]:
    guard()
    before = TARGET.read_bytes()
    text = before.decode("utf-8", "strict")
    if any(text.count(x) != 1 for x in (OLD_FORM, OLD_INPUT)):
        raise RuntimeError("STAGING_SEARCH_TEMPLATE_CHANGED_OR_PATCH_PRESENT")
    if any(x in text for x in (NEW_FORM, NEW_INPUT)):
        raise RuntimeError("STAGING_SEARCH_ALREADY_PATCHED")
    if text.count('name="q"') != 1 or text.count('role="search"') != 1:
        raise RuntimeError("SEARCH_STRUCTURE_UNEXPECTED")
    after = text.replace(OLD_FORM, NEW_FORM, 1).replace(OLD_INPUT, NEW_INPUT, 1).encode("utf-8")
    restored = after.replace(NEW_FORM.encode(), OLD_FORM.encode(), 1).replace(
        NEW_INPUT.encode(), OLD_INPUT.encode(), 1)
    if restored != before:
        raise RuntimeError("PATCH_NOT_ISOLATED")
    return before, after, stat.S_IMODE(TARGET.stat().st_mode)


def folder(run: str) -> Path:
    if not re.fullmatch(r"\d{9,20}", run):
        raise RuntimeError("INVALID_RUN_ID")
    return BACKUPS / ("run-" + run)


def atomic(data: bytes, mode: int) -> None:
    fd, temp = tempfile.mkstemp(prefix=".search-mobile-", dir=TARGET.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if TARGET.is_symlink() or not TARGET.is_file():
            raise RuntimeError("TARGET_CHANGED")
        os.replace(temp, TARGET)
    finally:
        Path(temp).unlink(missing_ok=True)


def restart() -> None:
    RESTART.touch(exist_ok=True)
    print("STAGING_ONLY_PASSENGER_MARKER_TOUCHED=1", flush=True)


def preview() -> None:
    before, after, _ = prepared()
    print("STAGING_SEARCH_MOBILE_PREVIEW=" + json.dumps({
        "old_sha": sha(before), "new_sha": sha(after),
        "files": 1, "outside_staging_writes": False, "process_signals": 0,
    }), flush=True)


def publish(run: str) -> None:
    before, after, mode = prepared()
    dest = folder(run)
    if dest.exists() or dest.is_symlink():
        raise RuntimeError("BACKUP_COLLISION")
    BACKUPS.mkdir(mode=0o700, exist_ok=True)
    dest.mkdir(mode=0o700)
    with (dest / "original.html").open("xb") as out:
        os.fchmod(out.fileno(), 0o600)
        out.write(before)
        out.flush()
        os.fsync(out.fileno())
    with (dest / "manifest.json").open("x") as out:
        os.fchmod(out.fileno(), 0o600)
        json.dump({"run": run, "old": sha(before), "new": sha(after), "mode": mode}, out)
        out.flush()
        os.fsync(out.fileno())
    if TARGET.read_bytes() != before:
        raise RuntimeError("CONCURRENT_STAGING_TEMPLATE_CHANGE")
    try:
        atomic(after, mode)
        restart()
        if TARGET.read_bytes() != after:
            raise RuntimeError("POST_WRITE_TEMPLATE_CHECK_FAILED")
    except BaseException:
        if TARGET.is_file() and TARGET.read_bytes() == after:
            atomic(before, mode)
            restart()
        raise
    print("STAGING_SEARCH_MOBILE_PUBLISHED=" + json.dumps({
        "private_backup": str(dest), "files_changed": 1,
        "main_site_vps_factory_payments_changed": False,
    }), flush=True)


def rollback(run: str) -> None:
    guard()
    dest = folder(run)
    if dest.is_symlink() or not dest.is_dir():
        raise RuntimeError("BACKUP_NOT_FOUND")
    meta = json.loads((dest / "manifest.json").read_text("utf-8"))
    original = (dest / "original.html").read_bytes()
    if meta["run"] != run or sha(original) != meta["old"]:
        raise RuntimeError("BACKUP_INTEGRITY_FAILURE")
    now = sha(TARGET.read_bytes())
    if now not in (meta["old"], meta["new"]):
        raise RuntimeError("CONCURRENT_EDIT_PREVENTS_ROLLBACK")
    if now == meta["new"]:
        atomic(original, int(meta["mode"]))
        restart()
    print("STAGING_SEARCH_MOBILE_ROLLBACK_READY=1", flush=True)


def verify_origin(run: str) -> None:
    guard()
    meta = json.loads((folder(run) / "manifest.json").read_text("utf-8"))
    if sha(TARGET.read_bytes()) != meta["new"]:
        raise RuntimeError("STAGING_TEMPLATE_NOT_PUBLISHED")
    for attempt in range(12):
        try:
            req = Request("https://staging.zomorodmelal.ir/search/?q=%DA%AF%D9%86%D8%AF%D9%85&mobile="
                          + run + "-" + str(attempt), headers={"Cache-Control": "no-cache, no-store"})
            with urlopen(req, timeout=12) as res:
                html = res.read(250000).decode("utf-8", "replace")
                if (res.status == 200 and "noindex" in res.headers.get("X-Robots-Tag", "").lower()
                        and html.count(NEW_FORM) == 1 and html.count(NEW_INPUT) == 1
                        and 'name="q"' in html):
                    print("STAGING_SEARCH_MOBILE_ORIGIN_VERIFIED=1", flush=True)
                    return
        except Exception as exc:
            print("ORIGIN_RETRY=" + type(exc).__name__, flush=True)
        time.sleep(5)
    raise RuntimeError("MOBILE_SEARCH_MARKUP_NOT_VISIBLE")


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
