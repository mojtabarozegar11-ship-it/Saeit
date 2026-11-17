#!/usr/bin/env python3
"""Atomic, additive and reversible cPanel release of numbered auction RFQs 350–421.

Modes: check, apply, verify, rollback. Never touches original 346–349 or supplier kit.
This script is only executed on the verified Zomorod cPanel host. All files are
staged outside public_html, and the live domain document root must be the
expected single real directory. No access to databases/payments/emails.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys

FIRST, LAST = 350, 421
NUMBERS = tuple(range(FIRST, LAST + 1))
ORIGINALS = tuple(range(346, 350))
HOME = Path.home()
ROOT = HOME / "public_html"
LOCK = HOME / ".locks" / "zomorod-auctions-350-421.lock"


def insist(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def regular(path):
    return path.is_file() and not path.is_symlink()


def stage_for(sha):
    insist(re.fullmatch(r"[0-9a-f]{40}", sha) is not None, "Invalid Git commit SHA")
    return HOME / (".zm-auctions-72-stage-" + sha)


def check_environment():
    insist(os.geteuid() != 0, "No root execution")
    insist(HOME.as_posix() == "/home/zomorod2", "Wrong cPanel account")
    insist(ROOT.is_dir() and not ROOT.is_symlink(), "Root absent or symlink")
    insist(ROOT.resolve() == Path("/home/zomorod2/public_html"), "Unexpected document root")
    insist(regular(ROOT / ".htaccess"), "Root .htaccess must exist and stay untouched")
    area = ROOT / "auctions"
    insist(area.is_dir() and not area.is_symlink(), "Auctions directory absent/unsafe")
    for n in ORIGINALS:
        p = area / str(n) / "index.html"
        insist(regular(p), "Existing official auction missing: " + str(n))
        insist(len(p.read_bytes()) > 1000, "Existing official auction unexpectedly small")
    insist(regular(area / "supplier-kit" / "index.html"), "Supplier kit missing")
    for rel in ("auctions/index.html", "sitemap-auctions.xml"):
        insist(regular(ROOT / rel), "Original public index/sitemap missing: " + rel)
    original_index = (ROOT / "auctions/index.html").read_text(encoding="utf-8")
    for n in ORIGINALS:
        insist(f"/auctions/{n}/" in original_index, "Old notice omitted in current index")
    insist("/auctions/supplier-kit/" in original_index, "Original supplier kit link missing")
    current_sitemap = (ROOT / "sitemap-auctions.xml").read_text(encoding="utf-8")
    for n in ORIGINALS:
        insist(f"/auctions/{n}/" in current_sitemap, "Old sitemap notice missing")
    insist("/auctions/supplier-kit/" in current_sitemap, "Old sitemap kit missing")


def valid_source(stage):
    public = stage / "public"
    assert public.is_dir() and not public.is_symlink()
    index = public / "auctions/index.html"
    root_map = public / "sitemap-auctions.xml"
    insist(regular(index) and regular(root_map), "Staged index/sitemap absent")
    text = index.read_text(encoding="utf-8")
    links = root_map.read_text(encoding="utf-8")
    insist("zm-auctions-72-index-v1" in text, "New index release marker missing")
    for n in range(346, 422):
        insist(f'/auctions/{n}/' in text, f"New index missing official #{n}")
        insist(f'/auctions/{n}/' in links, f"New sitemap missing official #{n}")
    insist("/auctions/supplier-kit/" in text and "/auctions/supplier-kit/" in links,
           "Supplier kit must be preserved in index and sitemap")
    for n in NUMBERS:
        p = public / "auctions" / str(n) / "index.html"
        insist(regular(p), f"Source page missing: {n}")
        page = p.read_text(encoding="utf-8")
        insist(f"zm-auctions-72-v1 official-{n}" in page, f"Page marker mismatch: {n}")
        insist(f"شماره رسمی آگهی {n}" in page, f"Number mismatch: {n}")
        insist(f"https://zomorodmelal.ir/auctions/{n}/" in page, f"Canonical mismatch: {n}")
        insist("zomorodmelal@gmail.com" in page and "بدون" in page,
               f"Missing legal information or contact: {n}")
    return public


def immutable_hashes():
    paths = [ROOT / ".htaccess", ROOT / "index.html"]
    paths += [ROOT / "auctions" / str(n) / "index.html" for n in ORIGINALS]
    paths += [ROOT / "auctions/supplier-kit/index.html"]
    return {str(p): digest(p) for p in paths if regular(p)}


def write_atomic(target, data):
    insist(not target.is_symlink(), "Refusing symlink " + str(target))
    tmp = target.with_name(target.name + ".zm-release-new")
    insist(not tmp.exists() and not tmp.is_symlink(), "Stale temporary output")
    try:
        with tmp.open("xb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        tmp.chmod(0o644)
        os.replace(tmp, target)
    finally:
        if tmp.exists():
            tmp.unlink()


def backup_dir(sha):
    return HOME / ".backups" / "zomorod-auctions-350-421" / sha


def metadata_path(sha):
    return backup_dir(sha) / "release-state.json"


def rollback(sha, stage, allow_missing=False):
    bdir = backup_dir(sha)
    meta = metadata_path(sha)
    if not regular(meta):
        if allow_missing:
            return
        raise RuntimeError("No release-state file to roll back")
    data = json.loads(meta.read_text(encoding="utf-8"))
    intended = stage / "public"
    for name in ("auctions/index.html", "sitemap-auctions.xml"):
        target = ROOT / name
        published = intended / name
        saved = bdir / ("before-" + name.replace("/", "--"))
        insist(regular(saved), "No rollback backup for " + name)
        if regular(target) and regular(published) and digest(target) == digest(published):
            write_atomic(target, saved.read_bytes())
    for n in data["newly_created"]:
        dest = ROOT / "auctions" / str(n) / "index.html"
        expected = intended / "auctions" / str(n) / "index.html"
        if regular(dest) and digest(dest) == digest(expected):
            dest.unlink()
            (ROOT / "auctions" / str(n)).rmdir()
    for path, expected in data["protected_hashes"].items():
        insist(regular(Path(path)) and digest(Path(path)) == expected,
               "Protected original changed during rollback: " + path)
    data["status"] = "rolled_back"
    write_atomic(meta, (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode())
    print("AUCTIONS_350_421_ROLLBACK=completed", flush=True)


def apply(sha, stage):
    public = valid_source(stage)
    check_environment()
    area = ROOT / "auctions"
    # Refuse unknown public serials >=350; protects announcements registered
    # elsewhere during preparation (and against subsequent concurrent release).
    extra = [int(p.name) for p in area.iterdir()
             if p.name.isdecimal() and int(p.name) >= 350
             and int(p.name) not in NUMBERS]
    insist(not extra, "Higher public advertisements already exist: " + str(sorted(extra)))
    newly = []
    for n in NUMBERS:
        dst_dir = area / str(n)
        dst = dst_dir / "index.html"
        src = public / "auctions" / str(n) / "index.html"
        insist(not dst_dir.is_symlink() and not dst.is_symlink(), "Unsafe notice path")
        if dst_dir.exists():
            insist(dst_dir.is_dir() and regular(dst) and digest(dst) == digest(src),
                   "Public serial collision or changed content: " + str(n))
        else:
            newly.append(n)
    old_index = (ROOT / "auctions/index.html").read_text(encoding="utf-8")
    if not newly:
        insist("zm-auctions-72-index-v1" in old_index, "Partial registry with no new pages")
        verify(sha, stage)
        print("AUCTIONS_350_421_ALREADY_PUBLISHED=yes", flush=True)
        return
    insist(len(newly) == len(NUMBERS), "Partial existing publication; refusing mixed state")
    insist("zm-auctions-72-index-v1" not in old_index, "Old index unexpectedly has new marker")
    bdir = backup_dir(sha)
    insist(not bdir.exists() and not bdir.is_symlink(), "Backup already exists")
    bdir.mkdir(parents=True, mode=0o700)
    for name in ("auctions/index.html", "sitemap-auctions.xml"):
        shutil.copyfile(ROOT / name, bdir / ("before-" + name.replace("/", "--")))
    state = {"source_sha": sha, "status": "installing", "newly_created": newly,
             "protected_hashes": immutable_hashes(),
             "old_index_sha": digest(ROOT / "auctions/index.html"),
             "old_sitemap_sha": digest(ROOT / "sitemap-auctions.xml")}
    write_atomic(metadata_path(sha),
                 (json.dumps(state, ensure_ascii=False, indent=2) + "\n").encode())
    try:
        # Check final legacy baseline immediately before any write.
        for n in ORIGINALS:
            insist(f"/auctions/{n}/" in old_index, "Legacy notice missing from index")
        for n in newly:
            src = public / "auctions" / str(n) / "index.html"
            dst_dir = area / str(n)
            insist(not dst_dir.exists() and not dst_dir.is_symlink(), "Collision before insert")
            dst_dir.mkdir(mode=0o755)
            write_atomic(dst_dir / "index.html", src.read_bytes())
        # The original four pages and supplier kit remain untouched.
        for name in ("auctions/index.html", "sitemap-auctions.xml"):
            write_atomic(ROOT / name, (public / name).read_bytes())
        verify(sha, stage)
        state["status"] = "deployed"
        write_atomic(metadata_path(sha),
                     (json.dumps(state, ensure_ascii=False, indent=2) + "\n").encode())
        print("AUCTIONS_350_421_RELEASE=deployed_72_pages", flush=True)
    except Exception:
        rollback(sha, stage)
        raise


def verify(sha, stage):
    public = valid_source(stage)
    check_environment()
    for n in NUMBERS:
        src = public / "auctions" / str(n) / "index.html"
        dst = ROOT / "auctions" / str(n) / "index.html"
        insist(regular(dst) and digest(src) == digest(dst), f"Published file mismatch {n}")
    for name in ("auctions/index.html", "sitemap-auctions.xml"):
        insist(regular(ROOT / name) and digest(ROOT / name) == digest(public / name),
               "Index or sitemap failed exact byte verification: " + name)
    bdir = backup_dir(sha)
    if regular(metadata_path(sha)):
        state = json.loads(metadata_path(sha).read_text(encoding="utf-8"))
        for path, expected in state["protected_hashes"].items():
            insist(regular(Path(path)) and digest(Path(path)) == expected,
                   "Protected old file hash changed: " + path)
    print("AUCTIONS_350_421_LOCAL_VERIFY=76_original_and_new_notices_preserved", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("check", "apply", "verify", "rollback"))
    parser.add_argument("sha")
    a = parser.parse_args()
    stage = stage_for(a.sha)
    insist(stage.is_dir() and not stage.is_symlink(), "Private staging directory missing")
    insist(regular(stage / "public/auctions/index.html"), "Staged index absent")
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with LOCK.open("a+") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if a.mode == "check":
            check_environment()
            valid_source(stage)
            print("AUCTIONS_350_421_PREFLIGHT=ready", flush=True)
        elif a.mode == "apply":
            apply(a.sha, stage)
        elif a.mode == "verify":
            verify(a.sha, stage)
        else:
            rollback(a.sha, stage)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("AUCTIONS_350_421_BLOCKED=" + str(exc), file=sys.stderr, flush=True)
        raise SystemExit(1)
