#!/usr/bin/env python3
"""Fail-closed deployment of one owned, static MojPlayWin games directory.

Does NOT edit live Django templates, Passenger config, root .htaccess, or
any existing games, stores, databases or microsites.
"""
import json
import os
import pwd
import re
import shutil
import sys
from pathlib import Path

HOME = Path("/home/zomorod2")
SITE = HOME / "mojplaywin.com"
PARENT = SITE / "game-releases"
DEST = PARENT / "20261021"
BACKUP = HOME / ".mojplaywin-game-backups"
MARKER = ".mojplaywin-five-games-owner.json"
SLUGS = ("pulse-forge", "beacon-labyrinth", "cipher-garden", "skyline-keeper", "nebula-salvage")

def check_id(run_id, sha=None):
    if not re.fullmatch(r"[0-9]{1,20}", run_id):
        raise RuntimeError("Invalid run ID")
    if sha is not None and not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise RuntimeError("Invalid git SHA")

def site_check():
    if pwd.getpwuid(os.getuid()).pw_name != "zomorod2":
        raise RuntimeError("Unexpected cPanel account")
    if SITE.is_symlink() or not SITE.is_dir():
        raise RuntimeError("Unverified MojPlayWin document root")
    if not (SITE / ".htaccess").is_file() or not (SITE / "passenger_wsgi.py").is_file():
        raise RuntimeError("Missing verified MojPlayWin entry files")
    if PARENT.is_symlink() or (PARENT.exists() and not PARENT.is_dir()):
        raise RuntimeError("Unsafe games parent")
    if DEST.is_symlink():
        raise RuntimeError("Destination is symlink")

def validate_payload(root):
    if root.is_symlink() or not root.is_dir():
        raise RuntimeError("Release payload missing")
    expected = {"index.html", "sitemap.xml", *SLUGS}
    if {p.name for p in root.iterdir()} != expected:
        raise RuntimeError("Unexpected release paths")
    index = (root / "index.html")
    if index.is_symlink() or not index.is_file():
        raise RuntimeError("Catalog missing")
    text = index.read_text(encoding="utf-8")
    sitemap = (root / "sitemap.xml").read_text(encoding="utf-8")
    if sitemap.count("<loc>") != 6 or "https://mojplaywin.com/game-releases/20261021/" not in sitemap:
        raise RuntimeError("Release sitemap invalid")
    for slug in SLUGS:
        p = root / slug
        f = p / "index.html"
        if p.is_symlink() or not p.is_dir() or f.is_symlink() or not f.is_file() or set(x.name for x in p.iterdir()) != {"index.html"}:
            raise RuntimeError("Game path invalid: " + slug)
        code = f.read_text(encoding="utf-8")
        if not (2500 < len(code) < 100000 and "<html lang=\"en\">" in code and "localStorage" in code
                and 'role="status"' in code and "<script src=" not in code
                and "fetch(" not in code and "XMLHttpRequest" not in code):
            raise RuntimeError("Game safety check failed: " + slug)
        if f"./{slug}/index.html" not in text:
            raise RuntimeError("Catalog link missing: " + slug)

def deploy(run_id, sha):
    check_id(run_id, sha)
    site_check()
    if DEST.exists():
        raise RuntimeError("Existing game release is preserved; will not overwrite")
    stage = HOME / (".mpw-games-" + run_id)
    src = stage / "site_releases/mojplaywin/games-20261021"
    validate_payload(src)
    if not PARENT.exists():
        PARENT.mkdir(mode=0o755)
    pending = PARENT / (".pending-five-games-" + run_id)
    if pending.exists() or pending.is_symlink():
        raise RuntimeError("Pending directory collision")
    pending.mkdir(mode=0o755)
    try:
        for relative in ("index.html", "sitemap.xml"):
            shutil.copyfile(src / relative, pending / relative)
        for slug in SLUGS:
            (pending / slug).mkdir(mode=0o755)
            shutil.copyfile(src / slug / "index.html", pending / slug / "index.html")
        (pending / ".htaccess").write_text(
            "PassengerEnabled off\nDirectoryIndex index.html\nOptions -Indexes\n",
            encoding="utf-8",
        )
        (pending / MARKER).write_text(
            json.dumps({"run_id": run_id, "git_sha": sha, "owner": "mojplaywin-five-games-v2"}) + "\n",
            encoding="utf-8",
        )
        validate_payload(src)
        if DEST.exists() or DEST.is_symlink():
            raise RuntimeError("Concurrent directory collision")
        os.rename(pending, DEST)
    except Exception:
        if pending.exists() and not pending.is_symlink():
            shutil.rmtree(pending)
        raise
    print("ISOLATED_FIVE_GAMES_INSTALLED " + sha)

def rollback(run_id, sha):
    check_id(run_id, sha)
    site_check()
    if not DEST.is_dir() or DEST.is_symlink():
        raise RuntimeError("No owned destination to roll back")
    marker = DEST / MARKER
    if not marker.is_file() or marker.is_symlink():
        raise RuntimeError("No valid release ownership marker")
    owner = json.loads(marker.read_text(encoding="utf-8"))
    if owner != {"run_id": run_id, "git_sha": sha, "owner": "mojplaywin-five-games-v2"}:
        raise RuntimeError("Ownership mismatch; refuse rollback")
    BACKUP.mkdir(mode=0o700, exist_ok=True)
    target = BACKUP / ("failed-release-" + run_id)
    if target.exists() or target.is_symlink():
        raise RuntimeError("Rollback backup collision")
    os.rename(DEST, target)
    print("OWNED_RELEASE_RETAINED_OFFLINE " + str(target))

if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "deploy":
        deploy(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 4 and sys.argv[1] == "rollback":
        rollback(sys.argv[2], sys.argv[3])
    else:
        raise SystemExit("Usage: deploy|rollback RUN_ID SHA")
