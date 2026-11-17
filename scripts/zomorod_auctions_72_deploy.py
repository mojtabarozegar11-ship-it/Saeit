#!/usr/bin/env python3
"""Conservative release of 72 official Persian RFQs to Zomorod's *actual* Apache routing.

Original live URLs /auctions/346-349 are physically /zm-auction346-349/index.html
and are mapped by Apache RewriteRule. New notices use /zm-auction350-421/ and
ONE exact numbered RewriteRule; directory and sitemap replace only the two
specific files in /zm-auctions-index/. No generic /auctions/ directory is made.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import xml.etree.ElementTree as ET

FIRST, LAST = 350, 421
NUMBERS = tuple(range(FIRST, LAST + 1))
ORIGINALS = tuple(range(346, 350))
HOME = Path.home()
ROOT = None
LOCK = HOME / ".locks" / "zomorod-auctions-350-421.lock"
ANCHOR = b"RewriteRule ^auctions/349/?$ /zm-auction349/index.html [END,NC]"
INDEX_RULE = b"RewriteRule ^auctions/?$ /zm-auctions-index/index.html [END,NC]"
MAP_RULE = b"RewriteRule ^sitemap-auctions[.]xml$ /zm-auctions-index/sitemap.xml [END,NC]"
NEW_MARKER = b"# zm-auctions-official-350-421-v1"
NEW_RULE = (NEW_MARKER + b"\n"
            + b"RewriteRule ^auctions/(35[0-9]|3[6-9][0-9]|4[01][0-9]|42[01])/?$ "
            + b"/zm-auction$1/index.html [END,NC]\n")


def insist(condition, message):
    if not condition:
        raise RuntimeError(message)


def regular(path):
    return path.is_file() and not path.is_symlink()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def directory_for(n):
    return ROOT / ("zm-auction" + str(n))


def index_path():
    return ROOT / "zm-auctions-index/index.html"


def map_path():
    return ROOT / "zm-auctions-index/sitemap.xml"


def ht_path():
    return ROOT / ".htaccess"


def stage_for(sha):
    insist(re.fullmatch(r"[0-9a-f]{40}", sha) is not None, "Invalid Git SHA")
    return HOME / (".zm-auctions-72-stage-" + sha)


def private_backup(sha):
    return HOME / ".backups" / "zomorod-auctions-350-421" / sha


def release_manifest(sha):
    return private_backup(sha) / "release.json"


def real_domain_root():
    insist(HOME.as_posix() == "/home/zomorod2" and os.geteuid() != 0, "Wrong cPanel account")
    try:
        raw = subprocess.check_output(
            ["uapi", "--output=json", "DomainInfo", "domains_data"],
            stderr=subprocess.PIPE, timeout=30)
        doc = json.loads(raw.decode("utf-8"))
    except (OSError, subprocess.TimeoutExpired, subprocess.CalledProcessError,
            ValueError, UnicodeError) as exc:
        raise RuntimeError("Authoritative cPanel DomainInfo unavailable") from exc
    matches = set()
    def walk(obj):
        if isinstance(obj, dict):
            domain = obj.get("domain") or obj.get("servername")
            root = obj.get("documentroot") or obj.get("document_root") or obj.get("docroot")
            if (isinstance(domain, str) and isinstance(root, str)
                    and domain.lower().rstrip(".") in ("zomorodmelal.ir", "www.zomorodmelal.ir")):
                matches.add(root.rstrip("/"))
            for value in obj.values():
                walk(value)
        elif isinstance(obj, list):
            for value in obj:
                walk(value)
    walk(doc)
    allowed = []
    for candidate in sorted(matches):
        p = Path(candidate)
        if (candidate.startswith("/home/zomorod2/") and p.is_dir() and not p.is_symlink()
                and p.resolve() == p and p.stat().st_uid == os.geteuid()
                and all(regular(p / ("zm-auction" + str(n)) / "index.html")
                        for n in ORIGINALS)
                and regular(p / "zm-auctions-index/index.html")):
            allowed.append(p)
    insist(len(allowed) == 1, "No uniquely verified cPanel root with originals 346–349")
    print("AUCTIONS_72_VERIFIED_ORIGIN=" + str(allowed[0]), flush=True)
    return allowed[0]


def assert_exact_rewrite_range():
    pattern = re.compile(r"^auctions/(35[0-9]|3[6-9][0-9]|4[01][0-9]|42[01])/?$")
    matches = [i for i in range(0, 1000) if pattern.fullmatch("auctions/" + str(i) + "/")]
    insist(matches == list(NUMBERS), "Rewrite regex exceeds or omits target official serials")


def validate_stage(stage):
    insist(stage.is_dir() and not stage.is_symlink(), "Missing private cPanel stage")
    src = stage / "public"
    idx = src / "auctions/index.html"
    xml = src / "sitemap-auctions.xml"
    old_idx = stage / "content/auctions-72/previous_live_index_346_349.html"
    old_xml = stage / "content/auctions-72/previous_live_sitemap_346_349.xml"
    insist(all(regular(p) for p in (idx, xml, old_idx, old_xml)),
           "Missing new or historical source assets")
    index_text = idx.read_text(encoding="utf-8")
    sitemap = ET.parse(xml)
    locs = [node.text for node in sitemap.iter() if node.tag.endswith("}loc")]
    insist("zm-auctions-72-index-v1" in index_text, "Index marker missing")
    insist(len(locs) == len(set(locs)) == 78, "Sitemap must have 78 unique URLs")
    for n in range(346, 422):
        url = "https://zomorodmelal.ir/auctions/" + str(n) + "/"
        insist(url in locs, f"Official URL absent from sitemap: {n}")
        insist('href="/auctions/' + str(n) + '/"' in index_text,
               f"Index missing official serial: {n}")
    insist("/auctions/supplier-kit/" in index_text, "Supplier kit link absent")
    for n in NUMBERS:
        source = src / "auctions" / str(n) / "index.html"
        insist(regular(source), f"Missing staged page: {n}")
        txt = source.read_text(encoding="utf-8")
        insist(f"zm-auctions-72-v1 official-{n}" in txt and
               f"شماره رسمی آگهی {n}" in txt and
               "zomorodmelal@gmail.com" in txt and
               f"https://zomorodmelal.ir/auctions/{n}/" in txt,
               f"Notice {n} is not complete")
    assert_exact_rewrite_range()
    return src, old_idx, old_xml


def check_origin():
    insist(ROOT is not None and ROOT.is_dir() and not ROOT.is_symlink(), "Origin missing")
    insist(ROOT.as_posix().startswith("/home/zomorod2/"), "Wrong cPanel root")
    insist(regular(ROOT / "index.html") and regular(ht_path()), "Site baseline incomplete")
    insist(regular(index_path()) and regular(map_path()), "Existing auction index/sitemap absent")
    insist(regular(ROOT / "zm-auctions-index/supplier-kit/index.html"),
           "Existing supplier form kit absent")
    insist(not (ROOT / "auctions").exists() and not (ROOT / "auctions").is_symlink(),
           "Unexpected physical /auctions directory now present")
    for n in ORIGINALS:
        p = directory_for(n)
        insist(p.is_dir() and not p.is_symlink() and regular(p / "index.html"),
               f"Existing published auction {n} missing")
        insist((p / "index.html").stat().st_size > 800,
               f"Existing auction {n} unexpectedly tiny")
    ht = ht_path().read_bytes()
    for n in ORIGINALS:
        line = ("RewriteRule ^auctions/" + str(n) + "/?$ /zm-auction"
                + str(n) + "/index.html [END,NC]").encode()
        insist(ht.count(line) == 1, f"Old rewrite for {n} modified")
    insist(ht.count(INDEX_RULE) == 1 and ht.count(MAP_RULE) == 1,
           "Official index or sitemap rewrite has changed")
    insist(b'PassengerAppRoot "/home/zomorod2/Saeit"' in ht,
           "Unrecognized cPanel Passenger mapping")
    live_index = index_path().read_text(encoding="utf-8")
    for n in ORIGINALS:
        insist(f"/auctions/{n}/" in live_index, "Old notice absent from index")
    insist("/auctions/supplier-kit/" in live_index, "Supplier kit must stay listed")
    return ht


def protected_hashes():
    p = [ROOT / "index.html", ROOT / "zm-auctions-index/supplier-kit/index.html"]
    p += [directory_for(n) / "index.html" for n in ORIGINALS]
    return {str(item): digest(item) for item in p}


def write_atomic(path, data):
    insist(not path.is_symlink(), "Unsafe symlink destination: " + str(path))
    mode = stat.S_IMODE(path.stat().st_mode) if path.is_file() else 0o644
    temp = path.with_name("." + path.name + ".zm72-tmp")
    insist(not temp.exists() and not temp.is_symlink(), "Previous temporary file exists")
    try:
        with temp.open("xb") as fd:
            fd.write(data)
            fd.flush()
            os.fsync(fd.fileno())
        temp.chmod(mode)
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def new_rewrite(old):
    insist(old.count(ANCHOR) == 1, "Existing #349 rewrite anchor changed")
    insist(NEW_MARKER not in old, "New 350–421 rewrite already present")
    # Collision check: no other higher numbered auction rule or unexpected rule.
    nums = [int(x) for x in re.findall(rb"RewriteRule \^auctions/([0-9]{3,})", old)]
    insist(not any(x >= FIRST for x in nums), "Another numbered auction rewrite exists")
    return old.replace(ANCHOR, NEW_RULE + ANCHOR)


def check_number_conflicts():
    seen=[]
    for item in ROOT.iterdir():
        match = re.fullmatch(r"zm-auction([0-9]+)", item.name)
        if match and int(match.group(1)) >= FIRST:
            seen.append(int(match.group(1)))
    insist(not seen, "Official numbers already physically allocated: " + repr(sorted(seen)[:12]))


def rollback(sha, stage):
    base = private_backup(sha)
    record = release_manifest(sha)
    insist(regular(record), "No private release metadata for rollback")
    info = json.loads(record.read_text(encoding="utf-8"))
    src, _, _ = validate_stage(stage)
    # Restore only if bytes are still the exact release version (or original).
    restore = [
        (ht_path(), src, base / "htaccess.original", info["new_ht_sha256"]),
        (index_path(), src, base / "index.original", digest(src / "auctions/index.html")),
        (map_path(), src, base / "sitemap.original", digest(src / "sitemap-auctions.xml")),
    ]
    for target, _unused, prior, new_sha in restore:
        insist(regular(target) and regular(prior), "Rollback baseline absent")
        current = digest(target)
        insist(current in (new_sha, digest(prior)),
               "Concurrent change detected; refuse unsafe rollback: " + str(target))
    for n in NUMBERS:
        target = directory_for(n) / "index.html"
        source = src / "auctions" / str(n) / "index.html"
        if target.exists() or target.is_symlink():
            insist(regular(target) and digest(target) == digest(source),
                   "Concurrent change detected in notice: " + str(n))
    for target, _unused, prior, new_sha in restore:
        if digest(target) == new_sha:
            write_atomic(target, prior.read_bytes())
    for n in NUMBERS:
        dest = directory_for(n) / "index.html"
        if regular(dest):
            dest.unlink()
            directory_for(n).rmdir()
    for path, expected in info["protected"].items():
        insist(regular(Path(path)) and digest(Path(path)) == expected,
               "Old published page changed during rollback: " + path)
    info["status"] = "rolled_back"
    write_atomic(record, (json.dumps(info,ensure_ascii=False,indent=2)+"\n").encode())
    print("AUCTIONS_72_ROLLBACK=protected_previous_state_restored",flush=True)


def verify(sha, stage):
    src, _, _ = validate_stage(stage)
    check_origin()
    expected_ht = (private_backup(sha) / "htaccess.original")
    insist(regular(expected_ht), "Original htaccess backup missing")
    expected_rewrite = new_rewrite(expected_ht.read_bytes())
    insist(digest(ht_path()) == hashlib.sha256(expected_rewrite).hexdigest(),
           "Deployed rewrite not exact")
    for target, name in ((index_path(),"auctions/index.html"),
                         (map_path(),"sitemap-auctions.xml")):
        insist(digest(target) == digest(src / name), "Index/sitemap hash mismatch")
    for n in NUMBERS:
        dest = directory_for(n) / "index.html"
        insist(regular(dest) and digest(dest) == digest(src / "auctions" / str(n) / "index.html"),
               f"Published serial {n} hash mismatch")
    info = json.loads(release_manifest(sha).read_text(encoding="utf-8"))
    for path, expected in info["protected"].items():
        insist(regular(Path(path)) and digest(Path(path)) == expected,
               "Protected live original changed: " + path)
    print("AUCTIONS_72_CPanel_LOCAL=72_hashes_and_originals_verified", flush=True)


def apply(sha, stage):
    src, old_idx, old_xml = validate_stage(stage)
    ht = check_origin()
    # Exact source fingerprint to avoid overwriting newer third-party index changes.
    insist(digest(index_path()) == digest(old_idx),
           "Live auction index differs from reviewed supplier-kit baseline: review before overwrite")
    insist(digest(map_path()) == digest(old_xml),
           "Live auction sitemap differs from reviewed baseline: review before overwrite")
    check_number_conflicts()
    updated_ht = new_rewrite(ht)
    base = private_backup(sha)
    insist(not base.exists() and not base.is_symlink(), "Private release backup already exists")
    base.mkdir(parents=True, mode=0o700)
    for target,name in ((ht_path(),"htaccess.original"),
                        (index_path(),"index.original"),
                        (map_path(),"sitemap.original")):
        shutil.copyfile(target,base/name)
        insist(digest(target) == digest(base/name), "Backup verification failed")
    metadata = {"sha":sha,"status":"installing","protected":protected_hashes(),
                "new_ht_sha256":hashlib.sha256(updated_ht).hexdigest()}
    write_atomic(release_manifest(sha),
                 (json.dumps(metadata,ensure_ascii=False,indent=2)+"\n").encode())
    try:
        for n in NUMBERS:
            targetdir = directory_for(n)
            insist(not targetdir.exists() and not targetdir.is_symlink(),
                   f"Official serial {n} already allocated")
            targetdir.mkdir(mode=0o755)
            write_atomic(targetdir / "index.html",
                         (src / "auctions" / str(n) / "index.html").read_bytes())
        write_atomic(index_path(),(src / "auctions/index.html").read_bytes())
        write_atomic(map_path(),(src / "sitemap-auctions.xml").read_bytes())
        write_atomic(ht_path(),updated_ht)
        verify(sha,stage)
        metadata["status"]="deployed"
        write_atomic(release_manifest(sha),
                     (json.dumps(metadata,ensure_ascii=False,indent=2)+"\n").encode())
        print("AUCTIONS_72_SCOPED_RELEASE=72_pages_350_to_421",flush=True)
    except Exception:
        rollback(sha,stage)
        raise


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("mode",choices=("check","apply","verify","rollback"))
    parser.add_argument("sha")
    args=parser.parse_args()
    global ROOT
    ROOT=real_domain_root()
    stage=stage_for(args.sha)
    insist(stage.is_dir() and not stage.is_symlink(), "Staged source absent")
    LOCK.parent.mkdir(parents=True,exist_ok=True)
    with LOCK.open("a+") as f:
        fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.mode=="check":
            _src, expected_idx, expected_map = validate_stage(stage)
            check_origin()
            check_number_conflicts()
            idx_match = digest(index_path()) == digest(expected_idx)
            map_match = digest(map_path()) == digest(expected_map)
            print("AUCTIONS_72_PRIOR_INDEX_SHA256_MATCH=" + str(idx_match),flush=True)
            print("AUCTIONS_72_PRIOR_SITEMAP_SHA256_MATCH=" + str(map_match),flush=True)
            insist(idx_match and map_match,
                   "Previously published auction directory changed; refuse destructive replacement")
            print("AUCTIONS_72_PREFLIGHT=legacy_rewrite_origin_verified",flush=True)
        elif args.mode=="apply":
            apply(args.sha,stage)
        elif args.mode=="verify":
            verify(args.sha,stage)
        else:
            rollback(args.sha,stage)


if __name__=="__main__":
    try: main()
    except Exception as exc:
        print("AUCTIONS_72_BLOCKED="+str(exc),file=sys.stderr,flush=True)
        raise SystemExit(1)
