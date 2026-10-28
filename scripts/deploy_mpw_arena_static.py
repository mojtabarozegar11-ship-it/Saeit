#!/usr/bin/env python3
"""Atomic, fail-closed static-only MOJ Arena release; never alters shared Django/Passenger."""
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
    if TARGET.is_symlink() or TARGET.exists():
        raise RuntimeError("Arena route already exists: refuse overwrite or collision")
    for name in ("games", "store", "game-releases"):
        if (SITE / name).is_symlink():
            raise RuntimeError("Protected sibling is symlink: " + name)
    return True

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

def deploy(run_id, sha):
    validate_identifiers(run_id, sha)
    site_preflight()
    stage = HOME / (".mpw-arena-" + run_id)
    source = stage / "site_releases/mojplaywin/arena"
    if stage.is_symlink() or source.is_symlink() or not source.is_dir():
        raise RuntimeError("Missing owned staging directory")
    if {p.name for p in source.iterdir()} != {"index.html", "README.md"}:
        raise RuntimeError("Unexpected source release content")
    digest = payload_preflight(source / "index.html")
    pending = SITE / (".arena-pending-" + run_id)
    if pending.exists() or pending.is_symlink():
        raise RuntimeError("Pending release collision")
    pending.mkdir(mode=0o755)
    try:
        shutil.copyfile(source / "index.html", pending / "index.html")
        (pending / ".htaccess").write_text(
            "PassengerEnabled off\nDirectoryIndex index.html\nOptions -Indexes\n",
            encoding="utf-8",
        )
        (pending / OWNER_FILE).write_text(
            json.dumps({"owner":"moj-arena-free-static-v1",
                        "run_id":run_id,"git_sha":sha,"sha256":digest}, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.chmod(pending / "index.html", 0o644)
        os.chmod(pending / ".htaccess", 0o644)
        os.chmod(pending / OWNER_FILE, 0o600)
        if hashlib.sha256((pending / "index.html").read_bytes()).hexdigest() != digest:
            raise RuntimeError("Staged release checksum mismatch")
        site_preflight()
        os.rename(pending, TARGET)
        print("ARENA_FREE_STATIC_INSTALLED sha256=" + digest)
    except Exception:
        if pending.is_dir() and not pending.is_symlink():
            destination = HOME / (".mpw-arena-failed-pending-" + run_id)
            if not destination.exists() and not destination.is_symlink():
                os.rename(pending, destination)
        raise

def rollback(run_id, sha):
    validate_identifiers(run_id, sha)
    if SITE.is_symlink() or not SITE.is_dir() or TARGET.is_symlink() or not TARGET.is_dir():
        raise RuntimeError("Unexpected target for rollback")
    marker = TARGET / OWNER_FILE
    if marker.is_symlink() or not marker.is_file():
        raise RuntimeError("Unowned Arena target: refuse rollback")
    meta = json.loads(marker.read_text(encoding="utf-8"))
    if (meta.get("owner"), meta.get("run_id"), meta.get("git_sha")) != (
        "moj-arena-free-static-v1", run_id, sha
    ):
        raise RuntimeError("Ownership marker mismatch; refuse rollback")
    if hashlib.sha256((TARGET / "index.html").read_bytes()).hexdigest() != meta.get("sha256"):
        raise RuntimeError("Arena modified since release; refuse rollback")
    BACKUPS.mkdir(mode=0o700, exist_ok=True)
    dest = BACKUPS / ("failed-live-" + run_id)
    if dest.exists() or dest.is_symlink():
        raise RuntimeError("Backup collision")
    os.rename(TARGET, dest)
    print("ARENA_FAILED_RELEASE_RETAINED_OFFLINE run_id=" + run_id)

if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] not in ("deploy", "rollback"):
        raise SystemExit("Usage: deploy|rollback RUN_ID COMMIT_SHA")
    globals()[sys.argv[1]](sys.argv[2], sys.argv[3])
