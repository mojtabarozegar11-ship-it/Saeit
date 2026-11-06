#!/usr/bin/env python3
"""Guarded staging-only link from local results to canonical public search."""

from __future__ import annotations

import hashlib
import html
import json
import os
import pwd
import re
import stat
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import unquote
from urllib.request import Request, urlopen

HOME = Path("/home/zomorod2")
APP = HOME / "Saeit-staging"
CONF = HOME / "Saeit-staging-web/.htaccess"
TEMPLATE = APP / "core/templates/core/search.html"
RESTART = APP / "tmp/restart.txt"
BACKUPS = HOME / ".private/staging-search-canonical-backups"
OLD = '{% if q %}<p>{{ results|length }} نتیجه برای «{{ q }}»</p>{% endif %}'
NEW = (OLD + '\n'
       '  {% if q %}<p class="search-canonical-link" style="line-height:1.9">'
       'این زیردامنه محتوای ثبت‌شده در پایگاه داده خود را جست‌وجو می‌کند. '
       '<a href="https://zomorodmelal.ir/search/?q={{ q|urlencode }}" '
       'target="_blank" rel="noopener noreferrer">'
       'جست‌وجوی محتوای منتشرشده در سایت اصلی ↗</a></p>{% endif %}')


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def guard() -> None:
    if pwd.getpwuid(os.geteuid()).pw_name != "zomorod2":
        raise RuntimeError("WRONG_CPANEL_USER")
    if CONF.is_symlink() or not CONF.is_file() or APP.is_symlink() or not APP.is_dir():
        raise RuntimeError("STAGING_APP_ROOT_UNSAFE")
    cfg = CONF.read_text("utf-8", "strict")
    match = re.search(r"(?m)^PassengerAppRoot\s+([^\s]+)\s*$", cfg)
    if not match or match.group(1).strip('"') not in ("$ACCOUNT_HOME/Saeit-staging", str(APP)):
        raise RuntimeError("PASSENGER_ROOT_MISMATCH")
    if TEMPLATE.is_symlink() or TEMPLATE.parent.is_symlink() or not TEMPLATE.is_file():
        raise RuntimeError("SEARCH_TEMPLATE_UNSAFE")
    if not TEMPLATE.is_relative_to(APP) or TEMPLATE.stat().st_size > 70000:
        raise RuntimeError("SEARCH_TEMPLATE_OUT_OF_SCOPE")
    if RESTART.is_symlink() or not RESTART.is_file() or RESTART.parent.is_symlink():
        raise RuntimeError("STAGING_RESTART_MARKER_UNSAFE")
    if BACKUPS.parent.is_symlink() or not BACKUPS.parent.is_dir():
        raise RuntimeError("PRIVATE_BACKUP_PARENT_UNSAFE")


def prepare() -> tuple[bytes, bytes, int]:
    guard()
    before = TEMPLATE.read_bytes()
    source = before.decode("utf-8", "strict")
    if source.count(OLD) != 1 or "search-canonical-link" in source:
        raise RuntimeError("SEARCH_CONTENT_CHANGED_OR_ALREADY_PATCHED")
    if source.count('class="search-form"') != 1 or source.count("min-width:0") != 1:
        raise RuntimeError("MOBILE_SEARCH_PREDECESSOR_MISSING")
    after = source.replace(OLD, NEW, 1).encode("utf-8")
    if after.replace(NEW.encode(), OLD.encode(), 1) != before:
        raise RuntimeError("PATCH_NOT_ISOLATED")
    return before, after, stat.S_IMODE(TEMPLATE.stat().st_mode)


def folder(run: str) -> Path:
    if not re.fullmatch(r"\d{9,20}", run):
        raise RuntimeError("INVALID_RUN_ID")
    return BACKUPS / ("run-" + run)


def atomic(data: bytes, mode: int) -> None:
    fd, temporary = tempfile.mkstemp(prefix=".search-canonical-", dir=TEMPLATE.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if TEMPLATE.is_symlink() or not TEMPLATE.is_file():
            raise RuntimeError("TARGET_CHANGED")
        os.replace(temporary, TEMPLATE)
    finally:
        Path(temporary).unlink(missing_ok=True)


def restart() -> None:
    RESTART.touch(exist_ok=True)
    print("STAGING_PASSENGER_RESTART_MARKER_ONLY=1", flush=True)


def preview() -> None:
    before, after, _ = prepare()
    print("SEARCH_CANONICAL_PREVIEW=" + json.dumps({
        "old_sha": sha(before), "new_sha": sha(after),
        "files": 1, "outside_staging_writes": False,
    }), flush=True)


def publish(run: str) -> None:
    before, after, mode = prepare()
    dest = folder(run)
    if dest.exists() or dest.is_symlink():
        raise RuntimeError("BACKUP_COLLISION")
    BACKUPS.mkdir(mode=0o700, exist_ok=True)
    dest.mkdir(mode=0o700)
    with (dest / "original.html").open("xb") as backup:
        os.fchmod(backup.fileno(), 0o600)
        backup.write(before)
        backup.flush()
        os.fsync(backup.fileno())
    with (dest / "manifest.json").open("x") as output:
        os.fchmod(output.fileno(), 0o600)
        json.dump({"run": run, "old": sha(before), "new": sha(after), "mode": mode}, output)
        output.flush()
        os.fsync(output.fileno())
    if TEMPLATE.read_bytes() != before:
        raise RuntimeError("CONCURRENT_TEMPLATE_EDIT")
    try:
        atomic(after, mode)
        restart()
        if TEMPLATE.read_bytes() != after:
            raise RuntimeError("PUBLISHED_TEMPLATE_SHA_FAILED")
    except BaseException:
        if TEMPLATE.is_file() and TEMPLATE.read_bytes() == after:
            atomic(before, mode)
            restart()
        raise
    print("SEARCH_CANONICAL_PUBLISHED=" + json.dumps({
        "private_backup": str(dest), "files_changed": 1,
        "factory_main_store_changed": False,
    }), flush=True)


def rollback(run: str) -> None:
    guard()
    dest = folder(run)
    if dest.is_symlink() or not dest.is_dir():
        raise RuntimeError("BACKUP_MISSING")
    meta = json.loads((dest / "manifest.json").read_text("utf-8"))
    original = (dest / "original.html").read_bytes()
    if meta["run"] != run or sha(original) != meta["old"]:
        raise RuntimeError("BACKUP_INTEGRITY_FAILED")
    current = sha(TEMPLATE.read_bytes())
    if current not in (meta["old"], meta["new"]):
        raise RuntimeError("CONCURRENT_EDIT_BLOCKS_ROLLBACK")
    if current == meta["new"]:
        atomic(original, int(meta["mode"]))
        restart()
    print("SEARCH_CANONICAL_ROLLBACK_DONE=1", flush=True)


def verify_origin(run: str) -> None:
    guard()
    meta = json.loads((folder(run) / "manifest.json").read_text("utf-8"))
    if sha(TEMPLATE.read_bytes()) != meta["new"]:
        raise RuntimeError("PUBLISHED_TEMPLATE_NOT_PRESENT")
    for attempt in range(12):
        try:
            req = Request("https://staging.zomorodmelal.ir/search/?q=%DA%AF%D9%86%D8%AF%D9%85&canonical="
                          + run + "-" + str(attempt),
                          headers={"Cache-Control": "no-cache, no-store"})
            with urlopen(req, timeout=12) as result:
                body = result.read(250000).decode("utf-8", "replace")
                found = re.search(r'href="https://zomorodmelal\.ir/search/\?q=([^"]+)"', body)
                valid_target = bool(found and unquote(html.unescape(found.group(1))) == "گندم")
                if (result.status == 200 and
                    "noindex" in result.headers.get("X-Robots-Tag", "").lower() and
                    'class="search-canonical-link"' in body and valid_target and
                    'class="search-form"' in body and "نتیجه برای «گندم»" in body):
                    print("SEARCH_CANONICAL_ORIGIN_VERIFIED=1", flush=True)
                    return
        except Exception as exc:
            print("VERIFY_RETRY=" + type(exc).__name__, flush=True)
        time.sleep(5)
    raise RuntimeError("CANONICAL_SEARCH_LINK_NOT_VISIBLE")


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
