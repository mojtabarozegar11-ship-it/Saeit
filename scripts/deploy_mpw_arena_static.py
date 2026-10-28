#!/usr/bin/env python3
"""Guarded one-path free-play Arena publication, owned update and reversible rollback.

Never edits Django, the shared Passenger entry, protected sites, databases, or finance.
An existing /arena/ can only be replaced when its exact owner, hash and contents
match the previously installed free-only Arena release.
"""
import hashlib
import json
import os
import pwd
import re
import shutil
import sys
from pathlib import Path

HOME = Path("/home/zomorod2")
SITE = HOME / "mojplaywin.com"
TARGET = SITE / "arena"
PROVEN_STATIC = SITE / "game-releases" / "20261020" / "index.html"
OWNER_FILE = ".mojplaywin-arena-owner.json"
BACKUPS = HOME / ".mojplaywin-arena-failed-releases"
OWNER = "moj-arena-free-static-v1"
STATIC_DIRECTIVES = "PassengerEnabled off\nDirectoryIndex index.html\nOptions -Indexes\n"
EXPECTED_MARKERS = (
    'id="game-grid"',
    'id="dice-game-grid"',
    'id="classic-game-grid"',
    "chessBoard.id='chess-board'",
    "backBoard.id='back-board'",
    'id="age-gate"',
    'id="language"',
    'NO CASH VALUE',
)


def validate_identifiers(run_id, sha):
    if not re.fullmatch(r"[0-9]{1,20}", run_id):
        raise RuntimeError("Invalid GitHub Actions run ID")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise RuntimeError("Invalid commit SHA")


def read_owner(target):
    """Refuse an unowned or modified Arena. No accidental overwrite or rollback."""
    if target.is_symlink() or not target.is_dir():
        raise RuntimeError("Arena target is not a regular directory")
    expected = {"index.html", ".htaccess", OWNER_FILE}
    if {p.name for p in target.iterdir()} != expected:
        raise RuntimeError("Arena target contains unowned additions or missing files")
    for name in expected:
        file = target / name
        if file.is_symlink() or not file.is_file():
            raise RuntimeError("Unsafe owned file: " + name)
    if (target / ".htaccess").read_text(encoding="utf-8") != STATIC_DIRECTIVES:
        raise RuntimeError("Arena Passenger configuration has changed")
    meta = json.loads((target / OWNER_FILE).read_text(encoding="utf-8"))
    if meta.get("owner") != OWNER:
        raise RuntimeError("Arena ownership marker mismatch")
    validate_identifiers(str(meta.get("run_id", "")), str(meta.get("git_sha", "")))
    digest = hashlib.sha256((target / "index.html").read_bytes()).hexdigest()
    if meta.get("sha256") != digest:
        raise RuntimeError("Arena live content was modified outside release")
    return meta


def site_preflight():
    if pwd.getpwuid(os.getuid()).pw_name != "zomorod2":
        raise RuntimeError("Unexpected account")
    if SITE.is_symlink() or not SITE.is_dir():
        raise RuntimeError("Unexpected document root")
    for name in ("passenger_wsgi.py", ".htaccess"):
        entry = SITE / name
        if entry.is_symlink() or not entry.is_file():
            raise RuntimeError("Protected site entry missing: " + name)
    if PROVEN_STATIC.is_symlink() or not PROVEN_STATIC.is_file():
        raise RuntimeError("Previously proven isolated static route missing")
    if "Five Original Browser Games" not in PROVEN_STATIC.read_text(encoding="utf-8"):
        raise RuntimeError("Prior static release marker differs")
    for name in ("games", "store", "game-releases"):
        if (SITE / name).is_symlink():
            raise RuntimeError("Protected sibling is symlink: " + name)
    if TARGET.is_symlink():
        raise RuntimeError("Arena symlink is forbidden")
    return read_owner(TARGET) if TARGET.exists() else None


def payload_preflight(index):
    if index.is_symlink() or not index.is_file():
        raise RuntimeError("Missing or unsafe Arena payload")
    data = index.read_bytes()
    if not 50_000 < len(data) < 300_000:
        raise RuntimeError("Unexpected Arena payload size")
    text = data.decode("utf-8")
    if not all(marker in text for marker in EXPECTED_MARKERS):
        raise RuntimeError("Missing playable Arena component")
    if text.count("<script>") != 1 or "<script src=" in text or "fetch(" in text or "XMLHttpRequest" in text:
        raise RuntimeError("Not a self-contained offline game release")
    if any(s in text.lower() for s in ("walletconnect", "window.ethereum", "tronweb", "metamask", "paymentgateway")):
        raise RuntimeError("Financial wallet integration forbidden in free release")
    return hashlib.sha256(data).hexdigest()


def park_owned(directory, name):
    if BACKUPS.is_symlink() or (BACKUPS.exists() and not BACKUPS.is_dir()):
        raise RuntimeError("Unsafe private release history")
    BACKUPS.mkdir(mode=0o700, exist_ok=True)
    dest = BACKUPS / name
    if dest.exists() or dest.is_symlink():
        raise RuntimeError("Owned release history collision")
    os.rename(directory, dest)
    return dest


def deploy(run_id, sha):
    validate_identifiers(run_id, sha)
    previous = site_preflight()
    stage = HOME / (".mpw-arena-" + run_id)
    source = stage / "site_releases/mojplaywin/arena"
    if stage.is_symlink() or source.is_symlink() or not source.is_dir():
        raise RuntimeError("Missing owned staging directory")
    if {p.name for p in source.iterdir()} != {"index.html", "README.md"}:
        raise RuntimeError("Unexpected source release content")
    digest = payload_preflight(source / "index.html")
    if previous and digest == previous["sha256"]:
        raise RuntimeError("No content change; refusing redundant public replacement")
    pending = SITE / (".arena-pending-" + run_id)
    if pending.exists() or pending.is_symlink():
        raise RuntimeError("Pending release collision")
    pending.mkdir(mode=0o755)
    backed_up = None
    try:
        shutil.copyfile(source / "index.html", pending / "index.html")
        (pending / ".htaccess").write_text(STATIC_DIRECTIVES, encoding="utf-8")
        (pending / OWNER_FILE).write_text(
            json.dumps({"owner": OWNER, "run_id": run_id, "git_sha": sha, "sha256": digest},
                       sort_keys=True) + "\n", encoding="utf-8",
        )
        os.chmod(pending / "index.html", 0o644)
        os.chmod(pending / ".htaccess", 0o644)
        os.chmod(pending / OWNER_FILE, 0o600)
        if hashlib.sha256((pending / "index.html").read_bytes()).hexdigest() != digest:
            raise RuntimeError("Staged checksum mismatch")
        if site_preflight() != previous:
            raise RuntimeError("Arena changed during staging")
        if previous:
            backed_up = park_owned(TARGET, "prior-" + run_id)
        try:
            os.rename(pending, TARGET)
        except Exception:
            if backed_up is not None and not TARGET.exists():
                os.rename(backed_up, TARGET)
            raise
        print("ARENA_FREE_STATIC_PUBLISHED sha256=" + digest +
              (" (previous release retained)" if backed_up else " (new route)"))
    except Exception:
        if pending.is_dir() and not pending.is_symlink():
            parking = HOME / (".mpw-arena-failed-pending-" + run_id)
            if not parking.exists() and not parking.is_symlink():
                os.rename(pending, parking)
        raise


def rollback(run_id, sha):
    validate_identifiers(run_id, sha)
    if SITE.is_symlink() or not SITE.is_dir():
        raise RuntimeError("Unexpected site on rollback")
    current = read_owner(TARGET)
    if current["run_id"] != run_id or current["git_sha"] != sha:
        raise RuntimeError("Do not roll back another release")
    previous = BACKUPS / ("prior-" + run_id)
    if previous.exists() or previous.is_symlink():
        read_owner(previous)
    failed = park_owned(TARGET, "failed-live-" + run_id)
    if previous.exists():
        try:
            os.rename(previous, TARGET)
        except Exception:
            if not TARGET.exists():
                os.rename(failed, TARGET)
            raise
        print("ARENA_PRIOR_VERSION_RESTORED")
    else:
        print("ARENA_NEW_RELEASE_REMOVED_AND_RETAINED_OFFLINE")


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] not in ("deploy", "rollback"):
        raise SystemExit("Usage: deploy|rollback RUN_ID COMMIT_SHA")
    globals()[sys.argv[1]](sys.argv[2], sys.argv[3])
