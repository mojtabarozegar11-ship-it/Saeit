#!/usr/bin/env python3
"""Checksum-guarded EN content correction to existing AYAR-only Django assets.

Does not edit routes, views, settings, accounts, payments, other sites or DB.
Expects the original release bytes at the four exact AYAR file targets.
Provides a scoped backup for post-deploy health rollback. No Passenger restart.
"""
import hashlib
import json
import os
import pwd
import re
import stat
import sys
import tempfile
from pathlib import Path

HOME = Path("/home/zomorod2")
APP = HOME / "Saeit-staging"
DOCROOT = HOME / "mojplaywin.com"
TARGET = APP / "site_releases/mojplaywin/ayaar-20261027"
URLS = APP / "config/urls.py"
FILES = ("index.html", "methodology.html", "app.js", "hero.css")
EXPECTED_ALL = {
    "index.html", "methodology.html", "app.js", "styles.css",
    "hero.css", "favicon.svg", "hero-art.svg"
}
MARKER = "# MPW_AYAAR_EXACT_DJANGO_ROUTE_BEGIN_20261027"


def fail(message):
    raise RuntimeError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def parameters():
    if len(sys.argv) != 4:
        fail("mode_run_commit_required")
    mode, run, commit = sys.argv[1:]
    if mode not in ("preflight", "deploy", "rollback"):
        fail("unsupported_mode")
    if not re.fullmatch(r"[0-9]{5,25}_[0-9]{1,3}", run):
        fail("invalid_run_id")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        fail("invalid_commit")
    return mode, run, commit


def paths(run):
    return (
        HOME / (".mpw-ayaar-english-stage-" + run),
        HOME / (".mpw-ayaar-english-backup-" + run),
    )


def safe_file(path):
    if not path.is_file() or path.is_symlink():
        fail("missing_or_unsafe_ayaar_file")


def root_check():
    if pwd.getpwuid(os.getuid()).pw_name != "zomorod2":
        fail("wrong_cpanel_user")
    if not APP.is_dir() or APP.is_symlink() or APP.resolve() != APP:
        fail("unexpected_app_root")
    if not DOCROOT.is_dir() or DOCROOT.is_symlink():
        fail("unexpected_docroot")
    if not TARGET.is_dir() or TARGET.is_symlink() or TARGET.resolve() != TARGET:
        fail("unexpected_ayaar_release_dir")
    if {p.name for p in TARGET.iterdir()} != EXPECTED_ALL:
        fail("unexpected_live_ayaar_members")
    safe_file(URLS)
    if MARKER not in URLS.read_text("utf-8"):
        fail("ayaar_route_marker_missing")
    safe_file(APP / "core/ayaar_views.py")
    for name in EXPECTED_ALL:
        safe_file(TARGET / name)


def manifest(stage, run, commit):
    if not stage.is_dir() or stage.is_symlink() or stage.resolve() != stage:
        fail("unsafe_staging_dir")
    members = {p.name for p in stage.iterdir()}
    if members != set(FILES) | {"release.json"}:
        fail("unexpected_stage_members")
    meta = json.loads((stage / "release.json").read_text("utf-8"))
    if meta.get("identity") != "MPW_AYAAR_EN_CONTENT_ONLY_V1" or meta.get("run") != run or meta.get("sha") != commit:
        fail("incorrect_release_identity")
    old = meta.get("before")
    new = meta.get("after")
    if set(old or {}) != set(FILES) or set(new or {}) != set(FILES):
        fail("incomplete_asset_manifest")
    for name in FILES:
        safe_file(stage / name)
        if not 0 < (stage / name).stat().st_size < 350000:
            fail("bad_staged_asset_size")
        if sha((stage / name).read_bytes()) != new[name]:
            fail("staged_asset_checksum_mismatch")
        if not re.fullmatch(r"[0-9a-f]{64}", old[name]):
            fail("invalid_original_checksum")
    if '<html lang="en" dir="ltr">' not in (stage / "index.html").read_text("utf-8"):
        fail("english_main_document_required")
    if '<html lang="en" dir="ltr">' not in (stage / "methodology.html").read_text("utf-8"):
        fail("english_methodology_required")
    if "AYAR-PREASSESSMENT-v1" not in (stage / "app.js").read_text("utf-8"):
        fail("report_engine_integrity_marker_missing")
    return old, new


def atomic(path, data, mode):
    if path.is_symlink():
        fail("unsafe_target_symlink")
    fd, temporary = tempfile.mkstemp(prefix=".ayaar-lang-safe-", dir=str(path.parent))
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def check_before(old):
    for name in FILES:
        safe_file(TARGET / name)
        if sha((TARGET / name).read_bytes()) != old[name]:
            fail("live_file_changed_since_original_release_" + name)


def preflight(run, commit):
    root_check()
    stage, backup = paths(run)
    if stage.exists() or stage.is_symlink() or backup.exists() or backup.is_symlink():
        fail("run_specific_collision")
    print("AYAR_ENGLISH_SCOPED_PREFLIGHT=PASS")


def deploy(run, commit):
    root_check()
    stage, backup = paths(run)
    old, new = manifest(stage, run, commit)
    if backup.exists() or backup.is_symlink():
        fail("backup_collision")
    check_before(old)
    backup.mkdir(mode=0o700)
    originals = {}
    modes = {}
    for name in FILES:
        target = TARGET / name
        originals[name] = target.read_bytes()
        modes[name] = stat.S_IMODE(target.stat().st_mode)
        (backup / name).write_bytes(originals[name])
    (backup / "release.json").write_text(json.dumps({
        "identity": "MPW_AYAAR_EN_CONTENT_ONLY_V1", "run": run,
        "sha": commit, "before": old, "after": new, "modes": modes
    }, sort_keys=True), encoding="utf-8")
    try:
        check_before(old)
        for name in FILES:
            atomic(TARGET / name, (stage / name).read_bytes(), modes[name])
        for name in FILES:
            if sha((TARGET / name).read_bytes()) != new[name]:
                fail("postwrite_asset_mismatch")
    except BaseException:
        rollback(run, commit)
        raise
    print("AYAR_ENGLISH_CONTENT_REPLACED=TRUE")
    print("AYAR_OTHER_SITE_FILES_CHANGED=FALSE")
    print("AYAR_SHARED_APP_RESTART=FALSE")


def rollback(run, commit):
    root_check()
    _, backup = paths(run)
    if not backup.is_dir() or backup.is_symlink():
        fail("missing_scoped_backup")
    meta = json.loads((backup / "release.json").read_text("utf-8"))
    if meta.get("identity") != "MPW_AYAAR_EN_CONTENT_ONLY_V1" or meta.get("run") != run or meta.get("sha") != commit:
        fail("rollback_identity_mismatch")
    for name in FILES:
        safe_file(backup / name)
        if sha((backup / name).read_bytes()) != meta["before"][name]:
            fail("corrupted_backup_" + name)
        current = sha((TARGET / name).read_bytes())
        if current not in (meta["before"][name], meta["after"][name]):
            fail("concurrent_change_refuse_rollback_" + name)
    for name in FILES:
        atomic(TARGET / name, (backup / name).read_bytes(), int(meta["modes"][name]))
    print("AYAR_ENGLISH_CONTENT_ROLLED_BACK=TRUE")


if __name__ == "__main__":
    try:
        mode, run, commit = parameters()
        if mode == "preflight":
            preflight(run, commit)
        elif mode == "deploy":
            deploy(run, commit)
        else:
            rollback(run, commit)
    except Exception as exc:
        print("AYAR_ENGLISH_SCOPED_ABORT=" + str(exc), file=sys.stderr)
        sys.exit(1)
